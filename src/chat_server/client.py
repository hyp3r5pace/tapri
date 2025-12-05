import asyncio
import sys

class Client():
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.writer = None
        self.reader = None
    
    # functions:
        # send_msg
        # leave
        # interactive loop which reads user input and sends them to the server
    async def connect_to_server(self):
        """Connect to chat server"""
        try:
            reader, writer = await asyncio.open_connection(
                self.host,
                self.port
            )
            print(f"Connected to {self.host}:{self.port}")
            return reader, writer
        except ConnectionRefusedError:
            print(f"ERROR:Server at {self.host}:{self.port} refused connection")
            print("Is the server running?")
            print("Is the port correct?")
            return None, None
        except asyncio.TimeoutError:
            print(f"ERROR: Connection to {self.host}:{self.port} timed out")
            return None, None
        except OSError as e:
            print(f"ERROR: OS Error: {e}")
            return None, None
        except Exception as e:
            print(f"ERROR: Unexpected error: {type(e).__name__}: {e}")
            return None, None
        

    async def send_message(self, message):
        """Send message to server"""
        successful = False
        try:
            self.writer.write(message.encode() + b'\n')
            await self.writer.drain()
            successful = True
        except ConnectionResetError as e:
            print(f"Connection reset: {e}")
        except BrokenPipeError as e:
            print(f"Broken pipe: {e}")
        except ConnectionAbortedError as e:
            print(f"Connection aborted: {e}")
        except OSError as e:
            print(f"OS Error: {e}")
        except Exception as e:
            print(f"Unexpected error: {e}")
        return successful
    
    def message_validation(self, msg):
        """Validate the message sent to the server"""
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
        """Continously receive message from the server"""
        try:
            while True:
                data = await self.reader.readline()
                if not data:
                    print("Server disconnected")
                    break
                message = data.decode().strip()
                print(f"\r{message}")
                print("> ", end="", flush=True)
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError) as e:
            print(f"Connection ERROR: {e}")
        except asyncio.CancelledError:
            print("Stopping receiver...")
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
                    print("\nClient wants to close down...")
                    break
        except asyncio.CancelledError:
            print("\nStopping sender...")
            raise


    async def run(self):
        """Main client loop"""
        self.reader, self.writer = await self.connect_to_server()
        
        if self.reader is None and self.writer is None:
            print("Couldn't connect to the server")
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
            self.writer.close()
            await self.writer.wait_closed()
            print("Disconnected from server")

    
async def main():
    client = Client(host='127.0.0.1', port=8888)
    await client.run()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nClient Stopped")


