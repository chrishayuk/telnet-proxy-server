#!/usr/bin/env python3
# telnet_proxy/logger.py
"""
Logging configuration for the telnet proxy service.
"""
import logging

def setup_logging():
    """Configure the logging for the application."""
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger('telnet-proxy')

    # Reduce noise from websockets library
    logging.getLogger("websockets.server").setLevel(logging.WARNING)

    # return the logger
    return logger

# Create and export the logger
logger = setup_logging()