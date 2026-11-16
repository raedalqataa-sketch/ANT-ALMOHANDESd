"""Offline checks for optional CAD MCP integration; no npm or network."""
import json
from pathlib import Path
import subprocess
import sys
import unittest

from scripts.check_cad_mcp import validate_config

ROOT = Path(__file__).resolve().parents[1]


class CadMcpConfigTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((ROOT / '.mcp.json').read_text())

    def test_committed_config_is_valid(self):
        self.assertEqual(validate_config(self.config), [])

    def test_floating_version_rejected(self):
        self.config['mcpServers']['archlang']['args'][-1] = '@chanmeng666/archlang-mcp@latest'
        self.assertTrue(validate_config(self.config))

    def test_missing_server_rejected(self):
        del self.config['mcpServers']['aspicio']
        self.assertTrue(validate_config(self.config))

    def test_shell_command_rejected(self):
        self.config['mcpServers']['aspicio']['command'] = 'sh'
        self.assertTrue(validate_config(self.config))

    def test_remote_endpoint_rejected(self):
        self.config['mcpServers']['aspicio']['url'] = 'https://example.com/mcp'
        self.assertTrue(validate_config(self.config))

    def test_non_object_config_rejected(self):
        for data in (None, [], 'bad', {'mcpServers': None}, {'mcpServers': []}):
            with self.subTest(data=data):
                self.assertTrue(validate_config(data))

    def test_additional_server_preserved(self):
        self.config['mcpServers']['other'] = {'command': 'local-tool'}
        self.assertEqual(validate_config(self.config), [])

    def test_live_probe_requires_explicit_flag(self):
        result = subprocess.run([sys.executable, 'scripts/smoke_cad_mcp.py'], cwd=ROOT, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 2)
        self.assertIn('--live', result.stderr)


class StdioProbeTests(unittest.TestCase):
    def client(self, code, timeout=2):
        from scripts.smoke_cad_mcp import StdioClient
        client = StdioClient([sys.executable, '-u', '-c', code], timeout, ROOT)
        self.addCleanup(client.close)
        return client

    def test_real_child_protocol_response(self):
        code = "import json,sys\nfor line in sys.stdin:\n m=json.loads(line)\n print(json.dumps({'jsonrpc':'2.0','id':m['id'],'result':{'ok':True}}),flush=True)"
        self.assertEqual(self.client(code).request('tools/list'), {'ok': True})

    def test_jsonrpc_error_cannot_be_success(self):
        code = "import json,sys\nm=json.loads(sys.stdin.readline())\nprint(json.dumps({'jsonrpc':'2.0','id':m['id'],'error':{'code':-32601}}),flush=True)\nsys.stdin.read()"
        with self.assertRaises(ValueError):
            self.client(code).request('initialize')

    def test_deadline_stops_unresponsive_child(self):
        with self.assertRaises(TimeoutError):
            self.client('import time;time.sleep(20)', timeout=.1).request('initialize')

    def test_non_json_stdout_is_rejected(self):
        with self.assertRaises(ValueError):
            self.client("import sys;print('not MCP',flush=True);sys.stdin.read()").request('initialize')


if __name__ == '__main__':
    unittest.main()
