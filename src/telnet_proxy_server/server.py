#!/usr/bin/env python3
# telnet_proxy_server/server.py
"""
Entry point for the telnet proxy server using chuk_protocol_server framework.
Forces DEBUG-level logs to help debug subpath vs. default target issues.
"""
import asyncio
import logging
import argparse
from typing import Optional, Dict

# Imports from chuk_protocol_server
from chuk_protocol_server.servers.telnet_server import TelnetServer
from chuk_protocol_server.servers.tcp_server import TCPServer
from chuk_protocol_server.servers.ws_server_plain import PlainWebSocketServer
from chuk_protocol_server.servers.ws_telnet_server import WSTelnetServer

from telnet_proxy_server.proxy_handler import TelnetProxyHandler

logger = logging.getLogger('telnet-proxy-main')

ASCII_BANNER = r"""
 *       *            _                               
| |     | |          | |                              
| |_ ___| |_ **   **_| |_   *_*  *_* _____  ___   _ 
| __/ * \ | '* \ / * \ *_| | '_ \| '__/ _ \ \/ / | | |
| ||  **/ | | | |  **/ |_  | |_) | | | (_) >  <| |_| |
 \__\___|_|_| |_|\___|\__| | .__/|_|  \___/_/\_\\__, |
                           | |                   __/ |
                           |_|                  |___/  
Telnet Proxy is running...
"""

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Telnet Proxy Server')
    
    # General arguments
    parser.add_argument('--host', default="0.0.0.0", 
                        help="Server host (default: 0.0.0.0)")
    parser.add_argument('--port', type=int, default=8123, 
                        help="Server port (default: 8123)")
    parser.add_argument('--default-target', default=None, 
                        help="Default Telnet target in the format host:port")
    
    # Protocol selection
    parser.add_argument('--protocol', choices=['telnet', 'tcp', 'websocket', 'ws_telnet'], 
                        default='telnet', help="Server protocol (default: telnet)")
    
    # WebSocket specific options
    parser.add_argument('--ws-path', default="/ws", 
                        help="WebSocket path (default: /ws)")
    # Default is to disallow any path (fixed ws-path enforced)
    parser.add_argument('--no-allow-any-path', dest='allow_any_path', action='store_false',
                        help="Disallow connections on any WebSocket path (force fixed ws-path)")
    parser.set_defaults(allow_any_path=False)
    parser.add_argument('--use-ssl', action='store_true',
                        help="Use SSL for WebSocket connections")
    parser.add_argument('--ssl-cert', default="",
                        help="Path to SSL certificate for WebSocket server")
    parser.add_argument('--ssl-key', default="",
                        help="Path to SSL key for WebSocket server")
    parser.add_argument('--allow-origins', nargs='+', default=["*"],
                        help="Allowed origins for WebSocket connections (default: all)")
    
    # Path mapping options
    parser.add_argument('--path-mapping', action='append', default=[],
                        help="Add a path mapping in the format path=host:port (can be specified multiple times)")
    
    # Connection handling options
    parser.add_argument('--max-connections', type=int, default=100,
                        help="Maximum number of connections (default: 100)")
    parser.add_argument('--connection-timeout', type=int, default=300,
                        help="Connection timeout in seconds (default: 300)")
    # We override --log-level by forcing DEBUG
    parser.add_argument('--log-level', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'], 
                        default='INFO', help="Logging level (forced to DEBUG in code below)")
    
    return parser.parse_args()

def display_banner():
    """Display the ASCII banner."""
    print(ASCII_BANNER)
    return True

def parse_path_mappings(mappings_list):
    """Parse path mappings from command line arguments."""
    path_mappings = {}
    for mapping in mappings_list:
        try:
            path, target = mapping.split('=', 1)
            if not path.startswith('/'):
                path = f"/{path}"
            path_mappings[path] = target
        except ValueError:
            logger.warning(f"Invalid path mapping format: {mapping}. Expected format: path=host:port")
    return path_mappings

async def start_server(args):
    """Start the appropriate server based on protocol."""
    logging.basicConfig(
        level=args.log_level.upper(),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    display_banner()
    
    path_mappings = parse_path_mappings(args.path_mapping)
    if path_mappings:
        logger.info(f"Path mappings: {path_mappings}")
    
    server = None
    if args.protocol == 'telnet':
        server = TelnetServer(
            args.host, 
            args.port, 
            TelnetProxyHandler,
            max_connections=args.max_connections,
            connection_timeout=args.connection_timeout
        )
        logger.info(f"Starting Telnet Proxy Server (Telnet protocol) on {args.host}:{args.port}")
        
    elif args.protocol == 'tcp':
        server = TCPServer(
            args.host, 
            args.port, 
            TelnetProxyHandler,
            max_connections=args.max_connections,
            connection_timeout=args.connection_timeout
        )
        logger.info(f"Starting Telnet Proxy Server (TCP protocol) on {args.host}:{args.port}")
        
    elif args.protocol == 'websocket':
        kwargs = {
            'host': args.host,
            'port': args.port,
            'handler_class': TelnetProxyHandler,
            'ping_interval': 30,
            'ping_timeout': 10,
            'allow_origins': args.allow_origins,
            'ssl_cert': args.ssl_cert if args.use_ssl else None,
            'ssl_key': args.ssl_key if args.use_ssl else None,
            'enable_monitoring': True,
            'monitor_path': "/monitor"
        }
        if args.allow_any_path:
            kwargs['path'] = None
            logger.info("Allowing connections on ANY path for WebSocket (dynamic proxying).")
        else:
            kwargs['path'] = args.ws_path
            logger.info(f"Fixed WebSocket path = {args.ws_path}")
        server = PlainWebSocketServer(**kwargs)
        logger.info(f"Starting Telnet Proxy Server (WebSocket protocol) on {args.host}:{args.port}")
        
    elif args.protocol == 'ws_telnet':
        ws_telnet_path = None if args.allow_any_path else args.ws_path
        if args.allow_any_path:
            logger.info("Allowing connections on ANY path for ws_telnet (dynamic).")
        else:
            logger.info(f"Fixed ws_telnet path = {args.ws_path}")
        server = WSTelnetServer(
            host=args.host,
            port=args.port,
            handler_class=TelnetProxyHandler,
            path=ws_telnet_path,
            ping_interval=30,
            ping_timeout=10,
            allow_origins=args.allow_origins,
            ssl_cert=args.ssl_cert if args.use_ssl else None,
            ssl_key=args.ssl_key if args.use_ssl else None,
            enable_monitoring=True,
            monitor_path="/monitor"
        )
        logger.info(f"Starting Telnet Proxy Server (WebSocket-Telnet protocol) on {args.host}:{args.port}")
    
    server.transport = args.protocol
    server.max_connections = args.max_connections
    server.connection_timeout = args.connection_timeout

    if args.default_target:
        server.default_target = args.default_target
        logger.info(f"Using default telnet target: {args.default_target}")
    
    if path_mappings:
        server.path_mappings = path_mappings
    
    try:
        await server.start_server()
    except KeyboardInterrupt:
        logger.info("Server shutdown initiated by user.")
    except Exception as e:
        logger.error(f"Error running server: {e}")
    finally:
        logger.info("Telnet Proxy Server has shut down.")

def main():
    """Main entry point for the telnet proxy service."""
    args = parse_arguments()
    try:
        try:
            import uvloop
            uvloop.install()
            logger.info("Using uvloop for improved performance")
        except ImportError:
            logger.info("uvloop not available, using standard asyncio event loop")
        asyncio.run(start_server(args))
    except KeyboardInterrupt:
        print("\nTelnet Proxy is shutting down gracefully...")

if __name__ == "__main__":
    main()
