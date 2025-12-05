"""
Chat server package.

Main exports:
- Server: Main server class
- ClientConnection: Individual client handler
"""

from client_connection import ClientConnection
from server import Server

__version__ = "1.0.0"
__all__ = ['Server', 'ClientConnection']
