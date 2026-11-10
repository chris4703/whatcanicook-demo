"""Install the optional narrow-interface Docker Desktop LAN forwarder."""
import argparse
import ipaddress
import os
from pathlib import Path
import plistlib
import subprocess

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--bind', required=True)
parser.add_argument('--port', type=int, default=8443)
parser.add_argument('--upstream-port', type=int, default=9443)
args = parser.parse_args()
address = ipaddress.IPv4Address(args.bind)
if address.is_unspecified or address.is_multicast or not address.is_private:
    parser.error('--bind must be one explicit private IPv4 address')
if not (1024 <= args.port <= 65535 and 1024 <= args.upstream_port <= 65535):
    parser.error('ports must be between 1024 and 65535')
root = Path(__file__).resolve().parent.parent
label = 'local.pantry-demo.lan-forwarder'
agent = Path.home() / 'Library/LaunchAgents' / (label + '.plist')
agent.parent.mkdir(parents=True, exist_ok=True)
(root / 'data').mkdir(exist_ok=True)
configuration = {
    'Label': label,
    'ProgramArguments': ['/usr/bin/python3', str(root / 'scripts/lan_forward.py'),
                         '--bind', str(address), '--port', str(args.port),
                         '--upstream-port', str(args.upstream_port)],
    'RunAtLoad': True, 'KeepAlive': True, 'ThrottleInterval': 10,
    'StandardOutPath': str(root / 'data/lan-forward.log'),
    'StandardErrorPath': str(root / 'data/lan-forward-error.log'),
}
if agent.exists():
    old = plistlib.loads(agent.read_bytes())
    if old.get('ProgramArguments', [])[:2] != configuration['ProgramArguments'][:2]:
        raise SystemExit('Existing launch agent points to another installation; left unchanged.')
    subprocess.run(['launchctl', 'bootout', f'gui/{os.getuid()}', str(agent)], check=False, capture_output=True)
agent.write_bytes(plistlib.dumps(configuration))
subprocess.run(['launchctl', 'bootstrap', f'gui/{os.getuid()}', str(agent)], check=True)
print(f'Installed {label}: {address}:{args.port} -> 127.0.0.1:{args.upstream_port}')
