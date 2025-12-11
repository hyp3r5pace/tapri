import asyncio
import pytest
from unittest.mock import Mock, AsyncMock, patch
import sys
from pathlib import Path

from server.server import Server
from client.client import Client

@pytest.mark.slow
@pytest.mark.asyncio
async def test_complete_chat_flow():
    """
    Test the complete chat flow:
    1. Start the server
    2. Two clients connect
    3. client 1 joins, broadcast message, leaves
    4. client 2 receives the broadcast
    5. Verify message delivery
    """

    # start the server on test port
    test_server = Server(8891)
    test_server_task = asyncio.create_task(test_server.run_server())

    # waiting for server to spin up
    await asyncio.sleep(1)

    try:
        # spin two clients who connect to the server
        client_1 = Client('127.0.0.1', 8891)
        client_2 = Client('127.0.0.1', 8891)

        reader_1, writer_1 = await client_1.connect_to_server()
        reader_2, writer_2 = await client_2.connect_to_server()

        assert reader_1 is not None, "client 1 failed to connect"
        assert reader_2 is not None, "client 2 failed to connect"
        
        # get the receiver function for client 2
        client2_messages = []
        async def client2_receiver():
            """Receive messages for client 2"""
            try:
                while True:
                    data = await reader_2.readline()
                    if not data:
                        break
                    msg = data.decode().strip()
                    client2_messages.append(msg)
                    print(f"Client 2 received: {msg}")
            except asyncio.CancelledError:
                pass
        
        # starting the receiver for client 2
        receiver_task = asyncio.create_task(client2_receiver())

        await asyncio.sleep(0.2)
        
        # client 2 join
        writer_2.write(b'/join\n')
        await writer_2.drain()
        print("client 2 sent /join")

        await asyncio.sleep(0.5)

        # client 1 join
        writer_1.write(b'/join\n')
        await writer_1.drain()
        print("Client 1 sent /join")

        await asyncio.sleep(0.3)

        writer_1.write(b'/broadcast Hello from client 1!\n')
        await writer_1.drain()
        print("Client 1: Sent broadcast message")

        await asyncio.sleep(0.5)

        writer_1.write(b'/leave\n')
        await writer_1.drain()
        print("Client 1: Sent /leave")

        await asyncio.sleep(0.5)

        receiver_task.cancel()
        try:
            await receiver_task
        except asyncio.CancelledError:
            pass

        writer_1.close()
        await writer_1.wait_closed()
        writer_2.close()
        await writer_2.wait_closed()
        
        print(f"\nClient 2 received {len(client2_messages)} messages:")
        for i, msg in enumerate(client2_messages):
            print(f"  {i+1}. {msg}")
        
        assert len(client2_messages) >= 3, f"Expected at least 3 messages, got {len(client2_messages)}"
        # check if join notification is received
        join_received = any("has joined the broadcast" in msg for msg in client2_messages)
        assert join_received, "Client 2 did not recieve join notification"

        # check if broadcast notification is received
        broadcast_recieved = any("Hello from client 1!" in msg for msg in client2_messages)
        assert broadcast_recieved, "Client 2 did not receive broadcast message"

        # check if leave notification was received
        leave_received = any("left the chat" in msg for msg in client2_messages)
        assert leave_received, "Client 2 did not recieve leave notification"

        print("\n✅ All assertions passed!")

    finally:
        # close down the server
        test_server_task.cancel()
        try:
            await test_server_task
        except asyncio.CancelledError:
            pass
    


