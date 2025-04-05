#!/usr/bin/env python3
# telnet_proxy_server/proxy_handler.py
"""
Transparent Telnet Proxy Handler Implementation

A telnet proxy server that forwards connections to a target telnet server.
Supports path-based redirection and additional proxy commands.
This version operates transparently without sending extra welcome messages,
and logs how it arrives at the final target.

Key approach:
    * Hard-code the subpath prefix "/ws" in _parse_target().
    * If raw_path starts with "/ws", parse remainder as "host/port".
      e.g. ws://localhost:8125/ws/telehack.com/23 => subpath remainder "telehack.com/23"
    * If none recognized, fallback to the default target (e.g. time.nist.gov:13).
"""

import asyncio
import logging
from typing import Optional, Tuple

# Import from chuk_protocol_server
from chuk_protocol_server.handlers.telnet_handler import TelnetHandler

logger = logging.getLogger('telnet-proxy-server')

active_telnet_targets = {}  # Mapping: target string -> count of clients using it

class TelnetProxyHandler(TelnetHandler):
    """
    Transparent telnet handler that proxies data between the client
    and a target telnet server without extra messages.
    Logs incoming paths and the final chosen target for debugging.
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.target_host = None
        self.target_port = None
        self.target_reader = None
        self.target_writer = None
        self.forwarding_task = None
        self.target_connection_string = None
        self.connection_start_time = None
        self._reading = False

    async def send_bytes(self, data: bytes) -> None:
        """Send raw bytes to the client."""
        if hasattr(self, 'websocket'):
            # WebSocket transport -> send as binary
            await self.websocket.send(data)
        else:
            # Telnet or TCP -> decode to text
            try:
                text = data.decode('utf-8', errors='replace')
            except Exception:
                text = repr(data)
            await self.send_line(text)

    async def on_connect(self) -> None:
        """
        Called when a new client connects.
        We parse the subpath from /ws/host/port if present; else fallback to default.
        """
        logger.info(f"New connection from {self.addr}")
        
        default_target = getattr(self.server, 'default_target', None)
        self.target_host, self.target_port = self._parse_target(default_target)

        if not self.target_host or not self.target_port:
            logger.info("No valid target found; closing session.")
            await self.send_line("[Error: No target specified]")
            await self.end_session()
            return

        self.target_connection_string = f"{self.target_host}:{self.target_port}"
        logger.info(f"Connecting to parsed target => {self.target_connection_string}")

        if not await self._connect_to_target():
            await self.end_session()
            return

        self.connection_start_time = asyncio.get_event_loop().time()
        logger.info(f"Connected to target {self.target_connection_string}")
        self.forwarding_task = asyncio.create_task(self._forward_from_target())

    async def _connect_to_target(self, timeout: int = 10) -> bool:
        """
        Open a TCP connection to the target telnet server.
        """
        try:
            logger.info(f"Attempting to open_connection to {self.target_connection_string}")
            self.target_reader, self.target_writer = await asyncio.wait_for(
                asyncio.open_connection(self.target_host, self.target_port),
                timeout=timeout
            )
            self._update_target_stats(self.target_connection_string, +1)
            return True
        except asyncio.TimeoutError:
            logger.error(f"Timeout connecting to {self.target_connection_string}")
            await self.send_line(f"[Error: timeout connecting to {self.target_connection_string}]")
            return False
        except ConnectionRefusedError:
            logger.error(f"Connection refused by {self.target_connection_string}")
            await self.send_line(f"[Error: connection refused by {self.target_connection_string}]")
            return False
        except Exception as e:
            logger.exception(f"Error connecting to target: {e}")
            await self.send_line(f"[Error connecting to {self.target_connection_string}: {str(e)}]")
            return False

    async def _forward_from_target(self) -> None:
        """
        Continuously forward data from the target server to the client.
        """
        self._reading = True
        try:
            buffer_size = 1024
            while True:
                try:
                    data = await asyncio.wait_for(self.target_reader.read(buffer_size), timeout=30)
                    if not data:
                        logger.info(f"Target {self.target_connection_string} closed connection")
                        await self.end_session()
                        break
                    await self.send_bytes(data)
                except asyncio.TimeoutError:
                    continue
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    logger.error(f"Error in target read loop: {e}")
                    await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            logger.info(f"Forwarding from {self.target_connection_string} cancelled")
        except Exception as e:
            logger.exception(f"Error forwarding data: {e}")
            await self.end_session()
        finally:
            self._reading = False

    async def _close_target_connection(self) -> None:
        """Close the connection to the target telnet server."""
        if self.target_writer:
            try:
                self.target_writer.close()
                await self.target_writer.wait_closed()
                logger.info(f"Closed connection to {self.target_connection_string}")
            except Exception as e:
                logger.error(f"Error closing target connection: {e}")

    async def _reconnect_to_target(self, target: str) -> bool:
        """
        Switch to a new target during an active session.
        E.g. user does "PROXY:CONNECT host:port"
        """
        try:
            host, port_str = target.split(':')
            port = int(port_str)
        except Exception:
            await self.send_line("[Error: Invalid target format]")
            return False

        if self.forwarding_task:
            self.forwarding_task.cancel()
            try:
                await self.forwarding_task
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.error(f"Error cancelling forwarding task: {e}")

        self._reading = False
        if self.target_writer:
            old_target = self.target_connection_string
            await self._close_target_connection()
            if old_target:
                self._update_target_stats(old_target, -1)

        self.target_host = host
        self.target_port = port
        self.target_connection_string = f"{host}:{port}"

        if await self._connect_to_target():
            self.connection_start_time = asyncio.get_event_loop().time()
            self.forwarding_task = asyncio.create_task(self._forward_from_target())
            return True
        return False
    
    def _parse_target(self, default_target: Optional[str] = None) -> Tuple[Optional[str], Optional[int]]:
        """
        Subpath-based approach:
          - If raw_path starts with a fixed prefix ("/ws"), parse the remainder as "/host/port".
          - Otherwise, fallback to default_target.
        """
        target = None
        path_mappings = getattr(self.server, 'path_mappings', {})

        if hasattr(self, 'request') and hasattr(self.request, 'path'):
            raw_path = self.request.path
            logger.debug(f"_parse_target => raw_path='{raw_path}', default_target='{default_target}'")

            # 1) Check exact path mapping
            if raw_path in path_mappings:
                target = path_mappings[raw_path]
                logger.debug(f"Matched path mapping => {raw_path} => {target}")
            else:
                # 2) Hardcode the subpath prefix as "/ws", regardless of server.path
                SUBPATH_PREFIX = "/ws"
                if raw_path.startswith(SUBPATH_PREFIX):
                    remainder = raw_path[len(SUBPATH_PREFIX):].strip('/')
                    logger.debug(f"Subpath remainder => '{remainder}'")
                    parts = remainder.split('/')
                    if len(parts) >= 2:
                        host_part = parts[0]
                        port_part = parts[1]
                        try:
                            _port = int(port_part)
                            target = f"{host_part}:{_port}"
                            logger.debug(f"Parsed from subpath => {target}")
                        except ValueError:
                            logger.warning(f"Could not parse port from subpath => '{port_part}'")
                else:
                    logger.debug(f"Raw path does not start with expected prefix '{SUBPATH_PREFIX}'.")
        else:
            logger.debug("No request.path attribute found.")

        # Fallback to default if no target was found
        if not target:
            logger.debug(f"No subpath or mapping => using default => {default_target}")
            target = default_target

        if not target:
            logger.debug("Still no target => returning None, None.")
            return None, None

        # Parse final host:port
        try:
            host, port_str = target.split(':', 1)
            port = int(port_str)
            logger.info(f"Final parse => host='{host}', port='{port}' from target='{target}'")
            return host, port
        except Exception as e:
            logger.error(f"Invalid target format => '{target}', error: {e}")
            return None, None


    async def on_command_submitted(self, command: str) -> None:
        """
        If the user sends some typed line, forward to target.
        """
        if self.target_writer:
            try:
                self.target_writer.write(f"{command}\r\n".encode('utf-8'))
                await self.target_writer.drain()
            except Exception as e:
                logger.error(f"Error forwarding command: {e}")
                await self.end_session()

    async def process_line(self, line: str) -> bool:
        """
        For line-based input, forward it to the target.
        """
        if self.target_writer:
            try:
                self.target_writer.write(f"{line}\r\n".encode('utf-8'))
                await self.target_writer.drain()
            except Exception as e:
                logger.error(f"Error forwarding line: {e}")
                await self.end_session()
                return False
        return True

    async def on_close(self) -> None:
        """
        Clean up after the client disconnects.
        """
        logger.info(f"Client {self.addr} disconnected")
        if self.forwarding_task:
            self.forwarding_task.cancel()
            try:
                await self.forwarding_task
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.error(f"Error cancelling forwarding task: {e}")
        self._reading = False
        await self._close_target_connection()
        if self.target_connection_string:
            self._update_target_stats(self.target_connection_string, -1)

    def _update_target_stats(self, target: str, delta: int) -> None:
        """
        Update global dictionary of active targets => number of connections.
        """
        global active_telnet_targets
        if target in active_telnet_targets:
            active_telnet_targets[target] += delta
            if active_telnet_targets[target] <= 0:
                del active_telnet_targets[target]
        elif delta > 0:
            active_telnet_targets[target] = delta
        logger.info(f"Active telnet targets: {active_telnet_targets}")