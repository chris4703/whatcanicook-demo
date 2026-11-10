"""Forward one explicit LAN interface to Docker's loopback-only HTTPS port.

TLS remains end-to-end between the browser and Caddy. This process never reads
certificates or API keys and cannot expose an arbitrary upstream host.
"""
import argparse
import ipaddress
import select
import socket
import socketserver

class Forwarder(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

class Connection(socketserver.BaseRequestHandler):
    def handle(self):
        try:
            with socket.create_connection(('127.0.0.1', self.server.upstream_port), timeout=10) as upstream:
                self.request.settimeout(30)
                upstream.settimeout(30)
                sockets = [self.request, upstream]
                while True:
                    readable, _, _ = select.select(sockets, [], [], 300)
                    if not readable:
                        return
                    for source in readable:
                        data = source.recv(65536)
                        if not data:
                            return
                        destination = upstream if source is self.request else self.request
                        destination.sendall(data)
        except (OSError, ValueError):
            # A disconnected browser or restarting container is routine.
            return

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bind', required=True)
    parser.add_argument('--port', type=int, default=8443)
    parser.add_argument('--upstream-port', type=int, default=9443)
    args = parser.parse_args()
    address = ipaddress.IPv4Address(args.bind)
    if address.is_unspecified or address.is_multicast or not address.is_private:
        parser.error('--bind must be one explicit private IPv4 address, never all interfaces')
    if not (1024 <= args.port <= 65535 and 1024 <= args.upstream_port <= 65535):
        parser.error('ports must be between 1024 and 65535')
    with Forwarder((str(address), args.port), Connection) as server:
        server.upstream_port = args.upstream_port
        print(f'Pantry TLS forwarding {address}:{args.port} -> 127.0.0.1:{args.upstream_port}', flush=True)
        server.serve_forever()

if __name__ == '__main__':
    main()
