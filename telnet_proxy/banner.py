#!/usr/bin/env python3
# telnet_proxy/banner.py
"""
ASCII art banner for the telnet proxy service.
"""

# ASCII art banner displayed at startup
ASCII_BANNER = r"""
 _       _            _                               
| |     | |          | |                              
| |_ ___| |_ __   ___| |_   _ __  _ __ _____  ___   _ 
| __/ _ \ | '_ \ / _ \ __| | '_ \| '__/ _ \ \/ / | | |
| ||  __/ | | | |  __/ |_  | |_) | | | (_) >  <| |_| |
 \__\___|_|_| |_|\___|\__| | .__/|_|  \___/_/\_\\__, |
                           | |                   __/ |
                           |_|                  |___/  

Telnet Proxy is running...
"""

def display_banner():
    """Display the ASCII banner to the console."""
    print(ASCII_BANNER)
    return True