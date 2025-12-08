"""
Unit test for Tapri chat server"
"""
import pytest
import asyncio
import sys
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch
from server.client_connection import ClientConnection
from server.server import Server

@pytest.mark.fast
@pytest.mark.asyncio
async def test_server_starts():
    """Test that server can start."""
    server = Server(8889)
    server_task = asyncio.create_task(server.run_server())
    await asyncio.sleep(0.5)
    server_task.cancel()
    try:
        await server_task
    except asyncio.CancelledError:
        pass
    assert True


class Writer:
    def write(self, msg):
        pass
    async def drain(self):
        pass

@pytest.mark.fast
@pytest.mark.asyncio
async def test_client_sender_broadcast():
    """Test the client sender function for broadcast msg"""
    writer = Writer()
    writer.write = Mock()
    writer.drain = AsyncMock()
    client = ClientConnection(writer, ('127.0.0.1', 1678), 5)
    task = asyncio.create_task(client.sender())
    msg = "Test client: Hello"
    await client.queue.put(("broadcast", 5, msg))
    await asyncio.sleep(0.5)
    writer.write.assert_called_with(msg.encode()+b'\n')
    writer.drain.assert_called_once()

@pytest.mark.fast
@pytest.mark.asyncio
async def test_client_sender_direct():
    """Test the client sender function for direct msg"""
    Writer.write = Mock()
    Writer.drain = AsyncMock()
    writer = Writer()
    client = ClientConnection(writer, ('127.0.0.1', 1678), 5)
    task = asyncio.create_task(client.sender())
    msg = "Test client: Hello"
    await client.queue.put(("direct", None, msg))
    await asyncio.sleep(0.5)
    writer.write.assert_called_with(msg.encode()+b'\n')
    writer.drain.assert_called_once()

@pytest.mark.fast
@pytest.mark.asyncio
async def test_client_sender_closeup():
    """Test the client sender function closeup process"""
    Writer.write = Mock()
    Writer.drain = AsyncMock()
    writer = Writer()
    client = ClientConnection(writer, ('127.0.0.1', 1678), 5)
    client.queue.get = Mock()
    task = asyncio.create_task(client.sender())
    msg = ""
    await client.queue.put(("direct", None, msg))
    await asyncio.sleep(0.5)
    client.queue.get.assert_called_once()





