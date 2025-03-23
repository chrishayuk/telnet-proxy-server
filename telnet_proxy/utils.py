#!/usr/bin/env python3
# telnet_proxy/utils.py
"""
Utility functions for the telnet proxy service.
"""

from urllib.parse import urlparse, parse_qs
from telnet_proxy.logger import logger

# Maximum allowed message length from the client
MAX_MESSAGE_LENGTH = 4096

# Global variable tracking active telnet targets
active_telnet_targets = {}  # Mapping: target string -> count of clients using it

# Global set tracking connected clients
connected_clients = set()  # Set of client identifiers


def get_request_path(websocket):
    """
    Extract the request path from websocket object across different websockets versions.
    
    Args:
        websocket: The websocket connection object
        
    Returns:
        str: The request path
    """
    # Try different attributes that might contain the path based on the websockets version
    if hasattr(websocket, "path"):
        return websocket.path
    elif hasattr(websocket, "request_uri"):
        return websocket.request_uri
    elif hasattr(websocket, "request") and hasattr(websocket.request, "path"):
        return websocket.request.path
    elif hasattr(websocket, "request") and hasattr(websocket.request, "uri"):
        return websocket.request.uri
    elif hasattr(websocket, "raw_request") and hasattr(websocket.raw_request, "path"):
        return websocket.raw_request.path
    
    # If we can't find it, return the default handler path
    logger.warning("Could not find request path in websocket object.")
    return "/"


def parse_target_from_uri(req_uri, default_target=None):
    """
    Parse the target server from the request URI.
    
    Args:
        req_uri (str): The request URI
        default_target (str, optional): Default target to use if none specified
        
    Returns:
        tuple: (host, port) if valid, or (None, None) if invalid
    """
    qs = parse_qs(urlparse(req_uri).query)
    target = qs.get("target", [None])[0] or default_target
    
    if not target:
        return None, None
    
    try:
        host, port_str = target.split(':')
        port = int(port_str)
        return host, port
    except Exception:
        return None, None


def update_target_stats(target, delta):
    """
    Increment or decrement the count for a target.
    
    Args:
        target (str): The target identifier (host:port)
        delta (int): +1 to increment, -1 to decrement
    """
    if target in active_telnet_targets:
        active_telnet_targets[target] += delta
        if active_telnet_targets[target] <= 0:
            del active_telnet_targets[target]
    elif delta > 0:
        active_telnet_targets[target] = delta