"""Opt-in stdio MCP initialize/tools-list probe. May download npm packages."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import queue
import shutil
import signal
import subprocess
import sys
import threading
import time

try:
    from scripts.check_cad_mcp import PINNED, ROOT, validate_config
except ModuleNotFoundError:
    from check_cad_mcp import PINNED, ROOT, validate_config


class StdioClient:
    """Small bounded JSON-RPC client, used only for connection diagnostics."""

    def __init__(self, command: list[str], timeout: float, cwd: Path):
        self.timeout = timeout
        self.messages = queue.Queue(maxsize=128)
        self.sequence = 0
        self.process = subprocess.Popen(
            command, cwd=cwd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, encoding='utf-8',
            start_new_session=(os.name == 'posix'),
        )
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        try:
            for _ in range(1000):
                line = self.process.stdout.readline(2 * 1024 * 1024 + 1)
                if not line:
                    self.messages.put_nowait(RuntimeError('MCP process closed stdout'))
                    return
                if len(line) > 2 * 1024 * 1024:
                    raise ValueError('MCP response exceeds probe size limit')
                try:
                    message = json.loads(line)
                except ValueError:
                    raise ValueError('MCP stdout must contain JSON-RPC only')
                self.messages.put_nowait(message)
            raise ValueError('Too many MCP messages')
        except (ValueError, OSError, queue.Full) as exc:
            try:
                self.messages.put_nowait(exc)
            except queue.Full:
                pass

    def send(self, message):
        self.process.stdin.write(json.dumps(message) + '\n')
        self.process.stdin.flush()

    def request(self, method, params=None):
        self.sequence += 1
        identifier = self.sequence
        self.send({'jsonrpc': '2.0', 'id': identifier, 'method': method, 'params': params or {}})
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            try:
                message = self.messages.get(timeout=max(.001, deadline - time.monotonic()))
            except queue.Empty as exc:
                raise TimeoutError(f'MCP timed out during {method}') from exc
            if isinstance(message, Exception):
                raise message
            if not isinstance(message, dict):
                raise ValueError('MCP response is not an object')
            # Answer unsupported server-initiated requests instead of deadlocking.
            if 'method' in message and 'id' in message:
                self.send({'jsonrpc': '2.0', 'id': message['id'],
                           'error': {'code': -32601, 'message': 'Probe does not provide client methods'}})
                continue
            if message.get('id') != identifier:
                continue
            if message.get('jsonrpc') != '2.0' or 'error' in message or not isinstance(message.get('result'), dict):
                raise ValueError(f'Invalid or failed MCP response to {method}')
            return message['result']
        raise TimeoutError(f'MCP timed out during {method}')

    def close(self):
        try:
            if os.name == 'posix':
                os.killpg(self.process.pid, signal.SIGTERM)
            elif self.process.poll() is None:
                self.process.terminate()
            self.process.wait(timeout=3)
        except ProcessLookupError:
            pass
        except subprocess.TimeoutExpired:
            if os.name == 'posix':
                os.killpg(self.process.pid, signal.SIGKILL)
            else:
                self.process.kill()
            self.process.wait(timeout=3)
        finally:
            for stream in (self.process.stdin, self.process.stdout):
                if stream:
                    stream.close()


def probe(name, config, timeout):
    client = StdioClient([shutil.which('npx') or 'npx', *config['args']], timeout, ROOT)
    try:
        init = client.request('initialize', {
            'protocolVersion': '2024-11-05', 'capabilities': {},
            'clientInfo': {'name': 'ant-cad-connection-probe', 'version': '1.0.0'},
        })
        if not isinstance(init.get('serverInfo'), dict) or init.get('protocolVersion') != '2024-11-05':
            raise ValueError('Missing serverInfo or incompatible MCP protocol version')
        client.send({'jsonrpc': '2.0', 'method': 'notifications/initialized'})
        names, cursor, seen = [], None, set()
        for _ in range(20):
            result = client.request('tools/list', {'cursor': cursor} if cursor else {})
            tools = result.get('tools')
            if not isinstance(tools, list) or any(not isinstance(t, dict) or not isinstance(t.get('name'), str) for t in tools):
                raise ValueError('Invalid tools/list response')
            names.extend(t['name'] for t in tools)
            cursor = result.get('nextCursor')
            if not cursor:
                break
            if not isinstance(cursor, str) or cursor in seen:
                raise ValueError('Invalid pagination cursor')
            seen.add(cursor)
        else:
            raise ValueError('Too many tools/list pages')
        if not names:
            raise ValueError('Server advertised no tools')
        return {'ok': True, 'package': PINNED[name], 'protocol_version': init['protocolVersion'],
                'server_info': init['serverInfo'], 'tool_names': names,
                'tool_count': len(names), 'tool_calls_performed': False}
    finally:
        client.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true', help='Allow npx processes and first-run downloads')
    parser.add_argument('--timeout', type=float, default=90, help='Seconds per protocol request, 1..300')
    parser.add_argument('--report', type=Path, help='Optional NEW JSON report; existing files are never overwritten')
    args = parser.parse_args()
    if not args.live:
        parser.error('--live is required; the default never starts MCP servers')
    if not 1 <= args.timeout <= 300:
        parser.error('--timeout must be 1..300')
    if args.report and args.report.exists():
        parser.error('--report already exists; choose a new file to preserve evidence')
    config = json.loads((ROOT / '.mcp.json').read_text(encoding='utf-8'))
    errors = validate_config(config)
    if errors:
        parser.error('; '.join(errors))
    if not shutil.which('npx'):
        parser.error('Node.js and npm/npx are required')
    report = {'timestamp_utc': datetime.now(timezone.utc).isoformat(),
              'scope': 'stdio_connection_and_discovery_only',
              'architecturally_approved': False, 'servers': {}}
    for name in PINNED:
        try:
            report['servers'][name] = probe(name, config['mcpServers'][name], args.timeout)
        except (OSError, ValueError, RuntimeError, TimeoutError, subprocess.SubprocessError) as exc:
            report['servers'][name] = {'ok': False, 'error': str(exc), 'package': PINNED[name]}
    report['ok'] = all(s['ok'] for s in report['servers'].values())
    text = json.dumps(report, indent=2, ensure_ascii=False)
    print(text)
    if args.report:
        with args.report.open('x', encoding='utf-8') as stream:
            stream.write(text + '\n')
    return 0 if report['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
