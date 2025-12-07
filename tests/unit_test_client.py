"""
Basic unit tests for Tapri chat client.
"""
import pytest
import asyncio
import sys
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).parent.parent))

from server.client_connection import ClientConnection
from client.client import Client
from server.server import Server

def test_client_format_addr():
    """Test address formatting"""
    writer = Mock()
    client = ClientConnection(writer, ('192.168.1.100', 5000), 0)
    assert client.format_addr() == "192.168.1.100:5000"

def test_client_message_validation():
    """Test message validation"""
    client = Client('localhost', 8888)

   # Valid messages
    assert client.message_validation("/join") == True
    assert client.message_validation("/leave") == True
    assert client.message_validation("/broadcast hello") == True
    
    # Invalid messages
    assert client.message_validation("") == False
    assert client.message_validation("   ") == False
    assert client.message_validation("/broadcast ") == False
    assert client.message_validation("random text") == False