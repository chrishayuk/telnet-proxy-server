#!/usr/bin/env python3
# telnet_proxy/client_handler.py
"""
Client connection handling for the telnet proxy service.
"""
import websockets
from telnet_proxy.logger import logger
from telnet_proxy.utils import get_request_path, parse_target_from_uri, connected_clients, active_telnet_targets
from telnet_proxy.telnet_connection import TelnetConnection


async def handle_client(websocket, path=None, default_target=None):
    """
    Handle a WebSocket client connection.
    
    Args:
        websocket: The WebSocket connection
        path: The connection path (optional, for compatibility)
        default_target: Default telnet target if none specified
    """
    client_id = id(websocket)
    connected_clients.add(client_id)
    
    # Get the request URI from the websocket object
    req_uri = get_request_path(websocket)
    logger.info(f"Client {client_id}: Connection URI: {req_uri}")
    
    telnet_connection = None
    target_used = None
    
    try:
        # Parse target from URI
        host, port = parse_target_from_uri(req_uri, default_target)
        if not host or not port:
            logger.error(f"Client {client_id}: Invalid or missing target")
            await websocket.send("[Error: invalid or missing target]")
            await websocket.close()
            return

        # Create and connect to telnet server
        telnet_connection = TelnetConnection(host, port, client_id, websocket)
        if not await telnet_connection.connect():
            return
        
        target_used = f"{host}:{port}"
        logger.info(f"Client {client_id}: Connected to Telnet server {target_used}. "
                   f"Active targets: {active_telnet_targets}")
        
        # Start bidirectional forwarding
        await telnet_connection.start_forwarding()
        
    except Exception as e:
        logger.exception(f"Client {client_id}: Unexpected error: {e}")
        try:
            await websocket.send("[Internal server error]")
        except Exception:
            pass
    finally:
        # Clean up resources
        if telnet_connection:
            await telnet_connection.close()
        
        try:
            await websocket.close()
        except Exception:
            pass
            
        connected_clients.discard(client_id)
        logger.info(f"Client {client_id} disconnected. Total clients: {len(connected_clients)} | "
                   f"Active Telnet targets: {active_telnet_targets}")