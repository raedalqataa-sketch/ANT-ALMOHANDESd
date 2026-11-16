"""Validate pinned optional CAD MCP configuration without starting processes."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PINNED = {
    'archlang': '@chanmeng666/archlang-mcp@0.2.45',
    'aspicio': '@aspicio/mcp@0.13.2',
}


def validate_config(config: object) -> list[str]:
    if not isinstance(config, dict) or not isinstance(config.get('mcpServers'), dict):
        return ['mcpServers must be an object']
    errors = []
    for name, package in PINNED.items():
        server = config['mcpServers'].get(name)
        if not isinstance(server, dict):
            errors.append(f'{name}: missing server configuration')
            continue
        if server.get('command') != 'npx':
            errors.append(f'{name}: command must be npx')
        if server.get('args') != ['-y', package]:
            errors.append(f'{name}: expected exactly -y {package}')
        if set(server) - {'command', 'args'}:
            errors.append(f'{name}: unexpected configuration keys')
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=ROOT / '.mcp.json')
    args = parser.parse_args()
    try:
        errors = validate_config(json.loads(args.config.read_text(encoding='utf-8')))
    except (OSError, ValueError) as exc:
        errors = [str(exc)]
    print(json.dumps({'scope': 'configuration_only', 'ok': not errors, 'errors': errors,
                      'live_connection_verified': False, 'architecturally_approved': False}, indent=2))
    return int(bool(errors))


if __name__ == '__main__':
    raise SystemExit(main())
