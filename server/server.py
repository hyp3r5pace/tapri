"""
Main chat server implementation.

Handles client connections, broadcasting, and server lifecycle.
"""

import asyncio
import logging
from client_connection import ClientConnection
import argparse

logger = logging.getLogger(__name__)

class Server:
    """
    Async chat server with ordered broadcast delivery.
    
    Features:
    - Multiple concurrent clients
    - Ordered message delivery
    - Graceful slow client handling
    """

    def __init__(self, port):
        """
        Initialize server.
        
        Args:
            port: Port to listen on
        """
        self.port = port
        self.client_list = {} # writer: Client()
        self.global_seq = 0
        self.global_lock = asyncio.Lock()
        self.global_del_lock = asyncio.Lock()
        self.background_tasks = set()
    
    async def client_handler(self, reader, writer):
        """Handle a single client connection."""
        addr = writer.get_extra_info("peername")
        logger.info(f"Client Connected: {addr}")
        while True:
            try:
                msg = await reader.readline()
            except (ConnectionResetError,ConnectionAbortedError,ConnectionRefusedError) as e:
                logger.error(f"ERROR: {addr} has connection error: {e}")
                client = self.client_list.get(writer, None)
                if client:
                    if await self.remove_client_immediate(client):
                        task = asyncio.create_task(self.client_cleanup(client))
                        self.background_tasks.add(task)
                        task.add_done_callback(self._task_done_callback)
                break
            except Exception as e:
                logger.error(f"ERROR: Unexpected error: {e}")
                client = self.client_list.get(writer, None)
                if client:
                    if await self.remove_client_immediate(client):
                        task = asyncio.create_task(self.client_cleanup(client))
                        self.background_tasks.add(task)
                        task.add_done_callback(self._task_done_callback)
                break
            # if writer.close(), i.e, connection is closed, then exit the loop
            if not msg:
                logger.info(f"{addr} disconnected (EOF)")
                client = self.client_list.get(writer, None)
                if client:
                    if await self.remove_client_immediate(client):
                        task = asyncio.create_task(self.client_cleanup(client))
                        self.background_tasks.add(task)
                        task.add_done_callback(self._task_done_callback)
                break
            text = msg.decode().strip()
            logger.debug(f"Received msg: {text}")
            if text == "/join":
                if writer in self.client_list:
                    client = self.client_list[writer]
                    await self.add_to_queue(client, "direct", None, "Server: Already joined!")
                else:
                    client = ClientConnection(writer, addr, None)
                    sender = asyncio.create_task(client.sender())
                    client.sender_task = sender
                    await self.join(client)
            elif text == '/leave':
                # to leave, first remove the client from client_list
                # if the client is already removed from list, no need to spin cleanup task
                # cleanup task is already in the event loop - done due to full queue
                # broadcast the leaving message to other clients
                # send a direct messge to self from server
                # trying to invalidate /leave before join... how to do it?
                # if client is not in client_list, the client hasn't joined
                client = self.client_list.get(writer, None)
                if client is None:
                    logger.info(f"{addr[0]}:{addr[1]} hasn't joined yet")
                else:
                    await self.leave(client)
                    break
            elif text[:10] == "/broadcast":
                logger.info("Broadcasting message")
                # check if client has joined yet or not
                client = self.client_list.get(writer, None)
                if client is None:
                    logger.info(f"{addr[0]}:{addr[1]} hasn't joined yet!")
                    # should I send a informative msg to the client here? - yes
                    continue
                # get the main msg content to be broadcasted
                content = text[10:].strip()
                logger.debug(f"Broadcast content: {content}")
                # broadcast the msg
                # what will happen if current client is removed from the server due to full queue
                # as done in broadcast()?
                # ans: in the next reader.readline() statement, output will be b'', which will
                # make the client_handler() to exit.
                await self.broadcast(content, client.addr)

    async def remove_client_immediate(self, client):
        """Remove client from client list immediately."""
        async with self.global_del_lock:
            writer = client.writer
            if writer in self.client_list:
                del self.client_list[writer]
                return True
        return False

    async def client_cleanup(self, client):
        """Gracefully clean up client resources."""
        # need timeout here since client sender might get over while queue is full and
        # hence queue will never be processed and the coroutine will wait here indefinetly.
        try:
            await asyncio.wait_for(
                client.queue.put(("direct", None, None)),
                timeout=10.0
            )
            poison_sent = True
        except asyncio.TimeoutError:
            logger.warning(f"Queue full/sender dead for {client.addr}, skipping poison pill")
            poison_sent = False
        if poison_sent:
            try:
                await client.sender_task
            except Exception as e:
                logger.error(f"Sender error: {e}")
        else:
            # poison pill not sent, check if sender is already done
            if not client.sender_task.done():
                # sender still running but queue is full - cancel it
                client.sender_task.cancel()
                try:
                    await client.sender_task
                except asyncio.CancelledError:
                    pass
        
        if not client.writer.is_closing():
            client.writer.close()
            await client.writer.wait_closed()

    def _task_done_callback(self, task):
        """Called when background task completes"""
        # remove from set
        self.background_tasks.discard(task)
        try:
            task.result()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Background task failed: {e}")

    async def add_to_queue(self, client, msg_type, seq, msg):
        """Add message to client queue with timeout."""
        item = (msg_type, seq, msg)
        try:
            await asyncio.wait_for(
                client.queue.put(item),
                timeout=2.0
            )
            logger.debug(f"{item}: sent for {client.addr} successfully!")
            return client, None
        except asyncio.TimeoutError:
            return client, "timeout"
        except Exception as e:
            return client, str(e)

    async def broadcast(self, msg, sender_addr):
        """Broadcast message to all connected clients."""
        async with self.global_lock:
            seq = self.global_seq
            self.global_seq += 1

        # do the work of adding to queue concurrently
        async with self.global_del_lock:
            clients_snapshot = list(self.client_list.items())
        msg = f"{sender_addr[0]}:{sender_addr[1]}: {msg}" if sender_addr else msg
        logger.debug(f"broadcast(): {msg}")
        tasks = [self.add_to_queue(client, "broadcast", seq, msg) for writer, client in clients_snapshot]
        results = await asyncio.gather(*tasks)

        # handle failed clients eg: slow clients
        failed_client = [client for client, error in results if error]
        if failed_client:
            for client in failed_client:
                if await self.remove_client_immediate(client):
                    task = asyncio.create_task(self.client_cleanup(client))
                    self.background_tasks.add(task)
                    # auto-remove when done
                    task.add_done_callback(self._task_done_callback)


    async def join(self, client):
        """Add a new client to the list and announce"""
        # broadcast to all the clients
        await self.broadcast(f"Server: {client.addr[0]}:{client.addr[1]} has joined the broadcast", None)
        # add client to client list
        async with self.global_del_lock:
            self.client_list[client.writer] = client
            client.next_seq = self.global_seq
        # this is a welcome server message to the client
        # there is a very low chance that the queue will be full here
        # thus, just adding msg to the queue with nowait
        # broadcast messages from other clients are more important than a direct server message, those entail for queue to be not full
        client.queue.put_nowait(("direct", None, f"Server: Welcome! You are now connected as {client.addr[0]}:{client.addr[1]}"))
        logger.info(f"{client.addr} joined the chat!")

    async def leave(self, client):
        """Remove the client from the list and close task associated with it"""
        # send direct message to the client regarding leaving
        # if queue full, not sent as timeout happens
        if await self.remove_client_immediate(client):
            await self.add_to_queue(client, "direct", None, f"Server: You will be removed soon! Bye!")
            task = asyncio.create_task(self.client_cleanup(client))
            self.background_tasks.add(task)
            task.add_done_callback(self._task_done_callback)
            await self.broadcast(f"Server: {client.addr[0]}:{client.addr[1]} left the chat", None)
        else:
            logger.info(f"Client {client.addr[0]}:{client.addr[1]} already removed!")


    async def run_server(self):
        server = await asyncio.start_server(
            self.client_handler,
            'localhost',
            self.port
        )
        addr = server.sockets[0].getsockname()
        logger.info(f"Server running on {addr}")
        async with server:
            await server.serve_forever()

def main():
    """Entry point for server"""
    parser = argparse.ArgumentParser(description="Chat Server")
    parser.add_argument('--port', type=int, default=8888, help='Port to listen on')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    args = parser.parse_args()

    # setup logging
    level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    server = Server(args.port)
    try:
        asyncio.run(server.run_server())
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    
if __name__ == "__main__":
    main()


    
            


