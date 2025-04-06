#!/usr/bin/env python3
# telnet_proxy_server/proxy_handler.py
"""
Transparent Telnet Proxy Handler Implementation (Raw Pass-Through)

A telnet proxy server that forwards connections to a target telnet server
without sending extra welcome messages or line-based transformations.

Key approach:
    * Hard-code the subpath prefix "/ws" in _parse_target().
    * If raw_path starts with "/ws", parse remainder as "host/port".
      e.g. ws://localhost:8125/ws/telehack.com/23 => subpath remainder "telehack.com/23"
    * If none recognized, fallback to the default target (e.g. time.nist.gov:13).
    * Pass all data from client -> target and target -> client unchanged.
"""

import asyncio
import logging
from typing import Optional, Tuple

from chuk_protocol_server.handlers.telnet_handler import TelnetHandler

logger = logging.getLogger('telnet-proxy-server')

active_telnet_targets = {}  # Mapping: target string -> count of clients using it

class TelnetProxyHandler(TelnetHandler):
    """
    Transparent telnet handler that proxies data between the client
    and a target telnet server without extra messages or line-based logic.
    Logs how it arrives at the final target.
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.target_host: Optional[str] = None
        self.target_port: Optional[int] = None
        self.target_reader: Optional[asyncio.StreamReader] = None
        self.target_writer: Optional[asyncio.StreamWriter] = None
        self.forwarding_task: Optional[asyncio.Task] = None
        self.target_connection_string: Optional[str] = None
        self._reading = False
        # Will be set by the server (via the adapter) for WebSocket path parsing
        self.websocket_path: Optional[str] = None

    def _extract_websocket_path(self) -> Optional[str]:
        """
        Extract the WebSocket path from the websocket object.
        The chuk_protocol_server adapter often sets _original_path or full_path.
        """
        if hasattr(self, 'websocket'):
            if hasattr(self.websocket, '_original_path'):
                p = self.websocket._original_path
                logger.debug(f"Found path in websocket._original_path: {p}")
                return p
            if hasattr(self.websocket, 'full_path'):
                p = self.websocket.full_path
                logger.debug(f"Found path in websocket.full_path: {p}")
                return p
            if hasattr(self.websocket, 'request') and hasattr(self.websocket.request, 'path'):
                p = self.websocket.request.path
                logger.debug(f"Found path in websocket.request.path: {p}")
                return p
        logger.debug("Could not find WebSocket path in any location")
        return None

    async def handle_client(self):
        """
        Capture the WebSocket path and connect to the target.
        Then stream data raw in both directions.
        """
        if hasattr(self, 'websocket'):
            self.websocket_path = self._extract_websocket_path()
            logger.debug(f"Proxy handler captured websocket path: {self.websocket_path}")

        await self.on_connect()

        # If we're in WS mode, read inbound data from the client, forward to target
        if hasattr(self, 'websocket'):
            try:
                async for message in self.websocket:
                    # If it's text, encode it to bytes
                    if isinstance(message, str):
                        data = message.encode('utf-8', errors='replace')
                    else:
                        data = message  # already bytes
                    await self._forward_inbound_bytes(data)
            except Exception as e:
                logger.exception(f"Error processing WebSocket messages: {e}")
            finally:
                await self.on_close()

    async def on_connect(self) -> None:
        """Called when a new client connects. Parse path -> connect to target."""
        logger.info(f"New connection from {self.addr}")

        # If not already set, attempt extraction again
        if not self.websocket_path:
            self.websocket_path = self._extract_websocket_path()
            logger.debug(f"on_connect: extracted websocket path: {self.websocket_path}")

        # Fallback: if still not set, try getting from .handler.websocket
        if not self.websocket_path and hasattr(self, 'handler') and hasattr(self.handler, 'websocket'):
            try:
                self.websocket_path = self.handler.websocket.request.path
                logger.debug(f"on_connect: set websocket path from handler: {self.websocket_path}")
            except Exception as ex:
                logger.error(f"on_connect: could not extract websocket path from handler: {ex}")

        default_target = getattr(self.server, 'default_target', None)
        self.target_host, self.target_port = self._parse_target(default_target)

        if not self.target_host or not self.target_port:
            logger.warning("No valid target found; closing session.")
            await self.end_session()
            return

        self.target_connection_string = f"{self.target_host}:{self.target_port}"
        logger.info(f"Connecting to {self.target_connection_string}")
        if not await self._connect_to_target():
            await self.end_session()
            return

        # Start reading from target -> client
        self.forwarding_task = asyncio.create_task(self._forward_from_target())

    def _parse_target(self, default_target: Optional[str] = None) -> Tuple[Optional[str], Optional[int]]:
        """
        If raw_path starts with "/ws", parse remainder as "host/port".
        Otherwise, fallback to default_target.
        """
        raw_path = self.websocket_path
        logger.debug(f"_parse_target => raw_path='{raw_path}', default_target='{default_target}'")
        target = None

        # If the server has path_mappings, check them
        path_mappings = getattr(self.server, 'path_mappings', {})

        if raw_path and raw_path in path_mappings:
            target = path_mappings[raw_path]
            logger.debug(f"Matched path mapping: {raw_path} => {target}")
        else:
            SUBPATH_PREFIX = "/ws"
            if raw_path and raw_path.startswith(SUBPATH_PREFIX):
                remainder = raw_path[len(SUBPATH_PREFIX):].strip('/')
                logger.debug(f"Subpath remainder: '{remainder}'")
                parts = remainder.split('/')
                if len(parts) == 2:
                    host_part, port_part = parts
                    try:
                        port_val = int(port_part)
                        target = f"{host_part}:{port_val}"
                        logger.debug(f"Parsed target from subpath: {target}")
                    except ValueError:
                        logger.warning(f"Could not parse port from subpath: '{port_part}'")
                else:
                    logger.debug(f"Not enough parts in subpath remainder: '{remainder}'")

        if not target:
            logger.debug(f"No subpath found; fallback to default_target: {default_target}")
            target = default_target

        if not target:
            return None, None

        # Split into host, port
        try:
            host, port_str = target.split(':', 1)
            port_val = int(port_str)
            logger.info(f"Final target parse: host='{host}', port='{port_val}' from target='{target}'")
            return host, port_val
        except Exception as e:
            logger.error(f"Invalid target format '{target}': {e}")
            return None, None

    async def _connect_to_target(self) -> bool:
        """Open a TCP connection to the chosen telnet server."""
        try:
            self.target_reader, self.target_writer = await asyncio.open_connection(
                self.target_host, self.target_port
            )
            logger.info(f"Connected to {self.target_connection_string}")
            self._update_target_stats(self.target_connection_string, +1)
            return True
        except Exception as e:
            logger.error(f"Error connecting to {self.target_connection_string}: {e}")
            return False

    async def _forward_inbound_bytes(self, data: bytes) -> None:
        """
        Send raw inbound data from the client to the target telnet server.
        """
        if self.target_writer:
            try:
                self.target_writer.write(data)
                await self.target_writer.drain()
            except Exception as e:
                logger.error(f"Error forwarding inbound data: {e}")
                await self.end_session()

    async def _forward_from_target(self) -> None:
        """Continuously read data from target -> send to the client."""
        try:
            while True:
                data = await self.target_reader.read(1024)
                if not data:
                    logger.info(f"Target {self.target_connection_string} closed connection")
                    break
                await self.send_bytes(data)
        except asyncio.CancelledError:
            logger.info(f"Forwarding cancelled for {self.target_connection_string}")
        except Exception as e:
            logger.error(f"Error in target read loop: {e}")
        finally:
            await self.end_session()

    async def send_bytes(self, data: bytes) -> None:
        """
        Send raw bytes to the client (via websocket if available, else fallback).
        """
        if hasattr(self, 'websocket'):
            # Send binary data as a WS frame
            await self.websocket.send(data)
        else:
            # If not using WebSocket, we can decode for a normal telnet send
            try:
                text = data.decode('utf-8', errors='replace')
            except Exception:
                text = repr(data)
            await self.send_line(text)

    async def on_close(self) -> None:
        """Clean up resources when the client disconnects."""
        logger.info(f"Client {self.addr} disconnected")
        if self.forwarding_task:
            self.forwarding_task.cancel()
            try:
                await self.forwarding_task
            except Exception as e:
                logger.error(f"Error cancelling forwarding task: {e}")
        await self._close_target_connection()

    async def _close_target_connection(self) -> None:
        """Close the connection to the target telnet server."""
        if self.target_writer:
            try:
                self.target_writer.close()
                await self.target_writer.wait_closed()
                logger.info(f"Closed connection to {self.target_connection_string}")
                self._update_target_stats(self.target_connection_string, -1)
            except Exception as e:
                logger.error(f"Error closing target connection: {e}")
        self.target_reader = None
        self.target_writer = None

    def _update_target_stats(self, target: str, delta: int) -> None:
        """Update the global dictionary of active targets."""
        global active_telnet_targets
        if not target:
            return
        if target in active_telnet_targets:
            active_telnet_targets[target] += delta
            if active_telnet_targets[target] <= 0:
                del active_telnet_targets[target]
        elif delta > 0:
            active_telnet_targets[target] = delta
        logger.info(f"Active telnet targets: {active_telnet_targets}")