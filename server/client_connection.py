"""
Client connection management.

Handles individual client connections, message queuing, and ordered delivery.
"""

import asyncio
import logging

logger = logging.getLogger(__name__)

class ClientConnection:
    """
    Represents a single connected client.
    
    Manages:
    - Message queue and sender task
    - Sequence-based ordered delivery
    - Network connection
    """

    def __init__(self, writer, addr, seq):
        """
        Initialize client connection.
        
        Args:
            writer: asyncio StreamWriter for this client
            addr: Client address tuple (host, port)
            seq: Initial sequence number (set when client joins)
        """
        self.writer = writer
        self.addr = addr
        self.queue = asyncio.Queue(maxsize=500)
        self.next_seq = seq
        self.pending = dict()
        self.sender_task = None

    def format_addr(self):
        """Format address as IP:Port string."""
        return f"{self.addr[0]}:{self.addr[1]}"
    
    async def sender(self):
        """
        Main sender loop.
        
        Pulls messages from queue and sends to client.
        Handles ordered delivery for broadcast messages.
        """
        try:
            while True:
                msg_type, seq, msg = await self.queue.get()
                if msg_type == "direct":
                    # posion pill ("direct", None, None)
                    # will send message (broadcast or direct) until poison pill is processed
                    if msg == None:
                        self.queue.task_done()
                        break
                    try:
                        self.writer.write(msg.encode() + b'\n')
                        await self.writer.drain()
                    except (ConnectionResetError, BrokenPipeError, ConnectionAbortedError, OSError, asyncio.CancelledError) as e:
                        logger.error(f"Error@{self.format_addr()} in sender() during direct message: {e}")
                        self.queue.task_done()
                        if isinstance(e, asyncio.CancelledError):
                            raise
                        break
                elif msg_type == "broadcast":
                    self.pending[seq] = msg
                    try:
                        while self.next_seq in self.pending:
                            self.writer.write(self.pending.pop(self.next_seq).encode() + b'\n')
                            await self.writer.drain()
                            self.next_seq += 1
                    except (ConnectionResetError, BrokenPipeError, ConnectionAbortedError, OSError, asyncio.CancelledError) as e:
                        logger.error(f"Error@{self.format_addr()} in sender() during broadcast: {e}")
                        self.queue.task_done()
                        if isinstance(e, asyncio.CancelledError):
                            raise
                        break
                
                self.queue.task_done()
        finally:
            logger.debug(f"Sender cleanup for {self.format_addr()}")
            self.pending.clear()

