import asyncio
import time
import random
from typing import List

class StressTestClient:
    def __init__(self, client_id: int, host: str, port: int):
        self.client_id = client_id
        self.host = host
        self.port = port
        self.reader = None
        self.writer = None
        self.messages_sent = 0
        self.messages_received = 0
        self.errors = 0
        
    async def connect(self):
        """Connect to server"""
        try:
            self.reader, self.writer = await asyncio.open_connection(
                self.host, self.port
            )
            return True
        except Exception as e:
            print(f"Client {self.client_id}: Connection failed: {e}")
            self.errors += 1
            return False
    
    async def join(self):
        """Send join command"""
        try:
            self.writer.write(b'/join\n')
            await self.writer.drain()
            return True
        except Exception as e:
            print(f"Client {self.client_id}: Join failed: {e}")
            self.errors += 1
            return False
    
    async def send_message(self, message: str):
        """Send a broadcast message"""
        try:
            msg = f"/broadcast {message}\n"
            self.writer.write(msg.encode())
            await self.writer.drain()
            self.messages_sent += 1
            return True
        except Exception as e:
            self.errors += 1
            return False
    
    async def receive_loop(self):
        """Continuously receive messages"""
        try:
            while True:
                data = await self.reader.readline()
                if not data:
                    break
                self.messages_received += 1
        except asyncio.CancelledError:
            pass
        except Exception as e:
            self.errors += 1
    
    async def send_loop(self, duration: float, rate: float):
        """Send messages at specified rate for duration"""
        end_time = time.time() + duration
        message_interval = 1.0 / rate  # seconds between messages
        
        while time.time() < end_time:
            message = f"Message {self.messages_sent} from client {self.client_id}"
            await self.send_message(message)
            await asyncio.sleep(message_interval)
    
    async def close(self):
        """Close connection"""
        try:
            self.writer.write(b'/leave\n')
            await self.writer.drain()
            self.writer.close()
            await self.writer.wait_closed()
        except:
            pass


class SlowClient(StressTestClient):
    async def receive_loop(self):
        """Continuously receive messages but with delays to simulate slow client"""
        try:
            while True:
                data = await self.reader.readline()
                if not data:
                    break
                self.messages_received += 1
                await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            self.errors += 1        

async def run_stress_test(
    num_clients: int,
    duration: float,
    messages_per_second: float,
    client_type: str = "fast",
    host: str = '127.0.0.1',
    port: int = 8888
):
    """
    Run stress test
    
    Args:
        num_clients: Number of concurrent clients
        duration: How long to run test (seconds)
        messages_per_second: Message rate per client
        host: Server host
        port: Server port
    """
    print(f"Starting stress test:")
    print(f"  Clients: {num_clients}")
    print(f"  Duration: {duration}s")
    print(f"  Rate: {messages_per_second} msg/sec per client")
    print(f"  Total expected messages: {num_clients * messages_per_second * duration:.0f}")

    # Create clients
    if client_type == "fast":
        clients = [StressTestClient(i, host, port) for i in range(num_clients)]
    elif client_type == "mix":
        clients = [StressTestClient(i, host, port) for i in range(num_clients//2)] + [SlowClient(i, host, port) for i in range(num_clients//2)]
    elif client_type == "slow":
        clients = [SlowClient(i, host, port) for i in range(num_clients)]
    else:
        raise Exception
    
    # Connect all clients
    print("Connecting clients...")
    connect_tasks = [client.connect() for client in clients]
    results = await asyncio.gather(*connect_tasks)
    connected = sum(results)
    print(f"Connected: {connected}/{num_clients}")
    
    if connected == 0:
        print("No clients connected. Is server running?")
        return
    
    # Join all clients
    print("Joining clients...")
    join_tasks = [client.join() for client in clients if client.writer]
    await asyncio.gather(*join_tasks)
    await asyncio.sleep(1)  # Let join messages propagate
    
    # Start receive loops
    receive_tasks = [
        asyncio.create_task(client.receive_loop()) 
        for client in clients if client.writer
    ]
    
    # Start test
    print(f"Starting message blast for {duration}s...")
    start_time = time.time()
    
    # Send messages
    send_tasks = [
        asyncio.create_task(client.send_loop(duration, messages_per_second))
        for client in clients if client.writer
    ]
    
    # Wait for send tasks to complete
    await asyncio.gather(*send_tasks, return_exceptions=True)
    
    # Wait a bit for messages to propagate
    await asyncio.sleep(2)
    
    # Stop receive tasks
    for task in receive_tasks:
        task.cancel()
    await asyncio.gather(*receive_tasks, return_exceptions=True)
    
    elapsed = time.time() - start_time
    
    # Close all clients
    print("Closing clients...")
    close_tasks = [client.close() for client in clients if client.writer]
    await asyncio.gather(*close_tasks, return_exceptions=True)
    
    # Calculate statistics
    total_sent = sum(c.messages_sent for c in clients)
    total_received = sum(c.messages_received for c in clients)
    total_errors = sum(c.errors for c in clients)
    
    print("\n" + "="*60)
    print("RESULTS")
    print("="*60)
    print(f"Duration: {elapsed:.2f}s")
    print(f"Clients: {connected}")
    print(f"Messages sent: {total_sent}")
    print(f"Messages received: {total_received}")
    print(f"Errors: {total_errors}")
    print(f"Send rate: {total_sent/elapsed:.2f} msg/sec")
    print(f"Receive rate: {total_received/elapsed:.2f} msg/sec")
    
    # Expected: each message should be received by (num_clients - 1) other clients
    expected_receives = total_sent * (connected - 1)
    if expected_receives > 0:
        delivery_rate = (total_received / expected_receives) * 100
        print(f"Delivery rate: {delivery_rate:.2f}%")
        print(f"Expected receives: {expected_receives}")
    
    print(f"Avg msgs sent per client: {total_sent/connected:.2f}")
    print(f"Avg msgs received per client: {total_received/connected:.2f}")
    print("="*60)


# Test scenarios
async def light_load():
    """Light load: 10 clients, 10 msg/sec each, 30 seconds"""
    await run_stress_test(
        num_clients=10,
        duration=30,
        messages_per_second=10
    )

async def medium_load():
    """Medium load: 50 clients, 5 msg/sec each, 60 seconds"""
    await run_stress_test(
        num_clients=50,
        duration=60,
        messages_per_second=5
    )

async def heavy_load():
    """Heavy load: 100 clients, 10 msg/sec each, 30 seconds"""
    await run_stress_test(
        num_clients=100,
        duration=30,
        messages_per_second=10
    )

async def burst_test():
    """Burst test: 50 clients, 50 msg/sec each, 10 seconds"""
    await run_stress_test(
        num_clients=50,
        duration=10,
        messages_per_second=50
    )

async def mix_test():
    """Medium load: 50 clients, 5 msg/sec each, 60 seconds"""
    await run_stress_test(
        num_clients=50,
        duration=60,
        messages_per_second=5,
        client_type="mix"
    )    


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        test_name = sys.argv[1]
        tests = {
            'light': light_load,
            'medium': medium_load,
            'heavy': heavy_load,
            'burst': burst_test,
            'mix': mix_test
        }
        if test_name in tests:
            asyncio.run(tests[test_name]())
        else:
            print(f"Unknown test: {test_name}")
            print(f"Available: {', '.join(tests.keys())}")
    else:
        # Run light load by default
        asyncio.run(light_load())