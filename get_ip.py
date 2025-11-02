#!/usr/bin/env python3
"""
Helper script to get the local IP address for network connections
"""

import socket

def get_local_ip():
    """Get the local IP address"""
    try:
        # Connect to a remote address (doesn't actually send data)
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        try:
            # Fallback method
            hostname = socket.gethostname()
            ip = socket.gethostbyname(hostname)
            return ip
        except Exception:
            return "127.0.0.1"

if __name__ == '__main__':
    ip = get_local_ip()
    print(f"\n{'='*50}")
    print(f"🌐 Your Local IP Address: {ip}")
    print(f"{'='*50}")
    print(f"\nUse this IP to connect from other devices on your network:")
    print(f"  - UDP Server: {ip}:8888")
    print(f"  - TCP Server: {ip}:8889")
    print(f"\nTo test locally (same machine):")
    print(f"  - UDP Server: localhost or 127.0.0.1")
    print(f"  - TCP Server: localhost or 127.0.0.1")
    print(f"{'='*50}\n")

