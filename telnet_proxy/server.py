#!/usr/bin/env python3
# telnet_proxy/server.py
"""
WebSocket server setup and main loop for the telnet proxy service.
"""

import asyncio
import signal
import websockets
from functools import partial
from telnet_proxy.logger import logger
from telnet_proxy.banner import display_banner
from telnet_proxy.client_handler import handle_client


class TelnetProxyServer:
    """WebSocket server for telnet proxy service."""
    
    def __init__(self, ws_host, ws_port, default_target=None):
        """
        Initialize the telnet proxy server.
        
        Args:
            ws_host (str): WebSocket host to bind to
            ws_port (int): WebSocket port to bind to
            default_target (str, optional): Default telnet target in host:port format
        """
        self.ws_host = ws_host
        self.ws_port = ws_port
        self.default_target = default_target
        self.server = None
        self.shutdown_event = None
    
    def _process_client(self, websocket, path=None):
        """Process client connection with compatibility for different websockets versions."""
        if path is not None:
            # Old-style websockets with separate path parameter
            return handle_client(websocket, path, self.default_target)
        else:
            # New-style websockets without path parameter
            return handle_client(websocket, default_target=self.default_target)
    
    async def start(self):
        """Start the WebSocket server."""
        display_banner()
        listening_url = f"ws://{self.ws_host}:{self.ws_port}"
        print(f"Listening on: {listening_url}\n")
        
        # Set up graceful shutdown
        self.shutdown_event = asyncio.Event()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, self.shutdown_event.set)
        
        # Create handler with default target
        client_handler = partial(handle_client, default_target=self.default_target)
        
        try:
            # Try new style signature first (without path)
            self.server = await websockets.serve(
                client_handler,
                self.ws_host,
                self.ws_port,
                ping_interval=20,
                ping_timeout=30
            )
            logger.info("Server started with new-style websockets API")
        except TypeError:
            # Fall back to old style signature (with path)
            logger.info("Using legacy websockets.serve() with path parameter")
            self.server = await websockets.serve(
                self._process_client,
                self.ws_host,
                self.ws_port,
                ping_interval=20,
                ping_timeout=30
            )
        
        logger.info(f"Server started on {listening_url}")
        
        try:
            # Wait for shutdown signal
            await self.shutdown_event.wait()
        finally:
            await self.stop()
    
    async def stop(self):
        """Stop the WebSocket server."""
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            print("\nTelnet Proxy is shutting down gracefully...")
            logger.info("Server stopped")