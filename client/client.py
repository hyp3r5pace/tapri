"""
Main client implementation
Handles client connection with server, message sending and receiving, message validation and graceful shutdown
"""

import asyncio
import sys
import logging
import argparse
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

class Client():
    """
    Async client for communicating with the server

    Features:
    - Message validation before sending messages
    - Message sender and receiver functions
    - graceful shutdown of the client
    """
    def __init__(self, host: str, port: int) -> None:
        """
        Initialize client
        Args:
            host: ip of the server to connect to
            port: port of the server to connect to
        """
        self.host = host
        self.port = port
        self.writer: Optional[asyncio.StreamWriter] = None
        self.reader: Optional[asyncio.StreamReader] = None
    
    async def connect_to_server(self) -> Tuple[Optional[asyncio.StreamReader], Optional[asyncio.StreamWriter]]:
        """Handle the connection to the chat server"""
        try:
            reader, writer = await asyncio.open_connection(
                self.host,
                self.port
            )
            logger.info(f"Connected to {self.host}:{self.port}")
            return reader, writer
        except ConnectionRefusedError:
            logger.error(f"ERROR:Server at {self.host}:{self.port} refused connection")
            print("Is the server running?")
            print("Is the port correct?")
            return None, None
        except asyncio.TimeoutError:
            logger.error(f"ERROR: Connection to {self.host}:{self.port} timed out")
            return None, None
        except OSError as e:
            logger.error(f"ERROR: OS Error: {e}")
            return None, None
        except Exception as e:
            logger.error(f"ERROR: Unexpected error: {type(e).__name__}: {e}")
            return None, None
        

    async def send_message(self, message: str) -> bool:
        """handle the sending of messages to server"""
        successful = False
        try:
            self.writer.write(message.encode() + b'\n')
            await self.writer.drain()
            successful = True
        except ConnectionResetError as e:
            logger.error(f"Connection reset: {e}")
        except BrokenPipeError as e:
            logger.error(f"Broken pipe: {e}")
        except ConnectionAbortedError as e:
            logger.error(f"Connection aborted: {e}")
        except OSError as e:
            logger.error(f"OS Error: {e}")
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
        return successful
    
    def message_validation(self, msg: str) -> bool:
        """handle the validation of the message sent to the server"""
        if not msg or not msg.strip():
            return False
        
        if len(msg) > 1000:
            print("\nError: Message too long (max 1000 chars)")
            return False

        if msg.startswith("/broadcast "):
            if not msg[11:].strip():
                print("\nError: Broadcast message is empty")
                return False
            return True
        elif msg in ["/join", "/leave"]:
            return True
        else:
            print(f"\nError: Unknown command. Use /join, /leave, or /broadcast <message>")
            return False
    
    async def receive_message(self):
        """Handle the receiving of messages from the server"""
        try:
            while True:
                data = await self.reader.readline()
                if not data:
                    logger.info("Server disconnected")
                    break
                message = data.decode().strip()
                print(f"\r{message}")
                print("> ", end="", flush=True)
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError) as e:
            logger.error(f"Connection ERROR: {e}")
        except asyncio.CancelledError:
            logger.info("Stopping receiver...")
            raise

    async def send_user_input(self):
        """Read user input and send to the server"""
        try:
            while True:
                print("> ", end="", flush=True)
                message = await asyncio.get_event_loop().run_in_executor(
                    None, sys.stdin.readline
                )
                message = message.strip()
                # not sending empty string or string with whitespaces to the server
                if not self.message_validation(message):
                    print("\nNot a valid message!")
                    continue
                # send the message to the server
                status = await self.send_message(message)
                if not status or message == "/leave":
                    logger.info("\nClient wants to close down...")
                    break
        except asyncio.CancelledError:
            logger.info("\nStopping sender...")
            raise


    async def run(self):
        """Main client loop"""
        self.reader, self.writer = await self.connect_to_server()
        
        if self.reader is None and self.writer is None:
            logger.error("Failed to connect to the server")
            return
        
        receiver_task = asyncio.create_task(self.receive_message())
        sender_task = asyncio.create_task(self.send_user_input())

        try:
            done, pending = await asyncio.wait(
                {receiver_task, sender_task},
                return_when=asyncio.FIRST_COMPLETED
            )

            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        finally:
            if self.writer and not self.writer.is_closing():
                self.writer.close()
                await self.writer.wait_closed()
            logger.info("Disconnected from server")

    
async def main():
    parser = argparse.ArgumentParser(description="Chat Client")
    parser.add_argument('--host', default='127.0.0.1', help='Server host')
    parser.add_argument('--port', type=int, default=8888, help='Server port')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    args = parser.parse_args()
    # setup logging
    level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    client = Client(host=args.host, port=args.port)
    await client.run()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\nClient Stopped by user")


