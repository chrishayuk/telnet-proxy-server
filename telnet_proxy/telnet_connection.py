#!/usr/bin/env python3
# telnet_proxy/telnet_connection.py
"""
Telnet connection management for the telnet proxy service.
"""
import asyncio
import websockets
from telnet_proxy.logger import logger
from telnet_proxy.utils import update_target_stats, MAX_MESSAGE_LENGTH


class TelnetConnection:
    """Manages a connection to a telnet server."""
    
    def __init__(self, host, port, client_id, websocket):
        """
        Initialize a telnet connection.
        
        Args:
            host (str): Telnet server hostname
            port (int): Telnet server port
            client_id: Unique identifier for the client
            websocket: WebSocket connection to the client
        """
        self.host = host
        self.port = port
        self.client_id = client_id
        self.websocket = websocket
        self.reader = None
        self.writer = None
        self.target = f"{host}:{port}"
        
        # Configure the websocket for binary mode
        try:
            # Some websockets implementations might not support this directly
            # If this fails, the conversion will happen automatically in the handler
            if hasattr(websocket, 'binary_type'):
                websocket.binary_type = 'arraybuffer'
        except Exception as e:
            logger.warning(f"Client {self.client_id}: Could not set binary mode: {e}")
    
    async def connect(self, timeout=10):
        """
        Establish connection to the telnet server.
        
        Args:
            timeout (int): Connection timeout in seconds
            
        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            self.reader, self.writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port), 
                timeout=timeout
            )
            update_target_stats(self.target, +1)
            logger.info(f"Client {self.client_id}: Connected to Telnet server {self.target}")
            return True
        except asyncio.TimeoutError:
            logger.error(f"Client {self.client_id}: Timeout connecting to Telnet server.")
            await self.websocket.send("[Error: timeout connecting to Telnet server]")
            return False
        except ConnectionRefusedError:
            logger.error(f"Client {self.client_id}: Connection refused by Telnet server.")
            await self.websocket.send("[Error: connection refused by Telnet server]")
            return False
        except Exception as e:
            logger.exception(f"Client {self.client_id}: Failed to connect to telnet server: {e}")
            await self.websocket.send(f"[Error connecting to telnet server: {str(e)}]")
            return False

    async def close(self):
        """Close the telnet connection."""
        try:
            if self.writer:
                self.writer.close()
                await self.writer.wait_closed()
                update_target_stats(self.target, -1)
        except Exception as e:
            logger.exception(f"Client {self.client_id}: Error closing Telnet connection: {e}")

    async def ws_to_telnet(self):
        """Forward messages from WebSocket to Telnet."""
        try:
            async for message in self.websocket:
                # Check for message type - handle both text and binary messages
                if isinstance(message, bytes):
                    # Binary data received directly
                    binary_data = message
                    logger.debug(f"Client {self.client_id}: Received binary data from WebSocket: {len(binary_data)} bytes")
                else:
                    # Text data received (most likely from JavaScript)
                    # Convert to binary without adding newline
                    binary_data = message.encode('utf-8')
                    logger.debug(f"Client {self.client_id}: Received text data from WebSocket: {message[:50]}...")
                
                # Enforce maximum message length
                if len(binary_data) > MAX_MESSAGE_LENGTH:
                    logger.warning(f"Client {self.client_id}: Message too long ({len(binary_data)} bytes). Truncating.")
                    binary_data = binary_data[:MAX_MESSAGE_LENGTH]
                
                # Send binary data to telnet server without automatically adding newline
                self.writer.write(binary_data)
                await self.writer.drain()
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"Client {self.client_id}: WebSocket closed (ws_to_telnet).")
        except Exception as ex:
            logger.exception(f"Client {self.client_id}: Exception in ws_to_telnet: {ex}")

    async def telnet_to_ws(self):
        """Forward messages from Telnet to WebSocket."""
        try:
            buffer_size = 1024  # Use a reasonable buffer size
            while True:
                # Read raw binary data instead of lines
                data = await asyncio.wait_for(self.reader.read(buffer_size), timeout=30)
                if not data:
                    logger.info(f"Client {self.client_id}: Telnet connection closed by remote host.")
                    await self.websocket.send("[Telnet connection closed]")
                    break
                
                # Log data for debugging (only first 50 bytes to avoid clutter)
                logger.debug(f"Client {self.client_id}: Received from telnet: {data[:50]} ({len(data)} bytes)")
                
                # Send raw binary data to WebSocket
                try:
                    # Attempt to send as binary data
                    await self.websocket.send(data)
                except Exception as e:
                    # If binary send fails, attempt to send as text with byte representation
                    logger.warning(f"Client {self.client_id}: Binary send failed, trying fallback: {e}")
                    try:
                        # Fallback: try to decode with lenient error handling
                        text_data = data.decode('utf-8', errors='replace')
                        await self.websocket.send(text_data)
                    except Exception as text_error:
                        logger.error(f"Client {self.client_id}: Text fallback failed: {text_error}")
                        # If all else fails, close the connection
                        break
                
        except asyncio.TimeoutError:
            logger.warning(f"Client {self.client_id}: Telnet read timed out.")
            await self.websocket.send("[Telnet read timed out]")
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"Client {self.client_id}: WebSocket closed (telnet_to_ws).")
        except Exception as ex:
            logger.exception(f"Client {self.client_id}: Exception in telnet_to_ws: {ex}")

    async def start_forwarding(self):
        """Start bidirectional forwarding between WebSocket and Telnet."""
        await asyncio.gather(self.ws_to_telnet(), self.telnet_to_ws())