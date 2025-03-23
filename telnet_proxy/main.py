#!/usr/bin/env python3
"""
Entry point for the telnet proxy service.
Handles command line arguments and starts the server.
"""
import asyncio
import argparse
from telnet_proxy.logger import logger
from telnet_proxy.server import TelnetProxyServer


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Telnet Proxy WebSocket Server')
    parser.add_argument('--ws-host', default="0.0.0.0", 
                        help="WebSocket server host (default: 0.0.0.0)")
    parser.add_argument('--ws-port', type=int, default=8123, 
                        help="WebSocket server port (default: 8123)")
    parser.add_argument('--default-target', default=None, 
                        help="Default Telnet target in the format host:port")
    return parser.parse_args()


def main():
    """Main entry point for the telnet proxy service."""
    args = parse_arguments()
    
    if args.default_target:
        logger.info(f"Using default Telnet target: {args.default_target}")
    
    # Create and start the server
    server = TelnetProxyServer(args.ws_host, args.ws_port, args.default_target)
    
    try:
        asyncio.run(server.start())
    except KeyboardInterrupt:
        print("\nTelnet Proxy is shutting down gracefully...")


if __name__ == '__main__':
    main()