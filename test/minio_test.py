import asyncio
from src.storage import MinioClient
from src.logger import get_logger
import os
import asyncio
import aio_pika
import json

def log(msg):
    print (f' [+] {msg}')

logger = get_logger("test")

async def upload_binary(storage):
    file_path = os.path.join(os.getcwd(), "test/cyrus2d.tar.gz")
    await storage.upload_file('test','cyrus2d.tar.gz',file_path)

async def run():
    storage = MinioClient(
        endpoint="localhost:9000",
        access_key="minioadmin",
        secret_key="minioadmin",
        secure=False
    )
    try:
        logger.info("storage connecting...")
        storage.connect()
        logger.info("storage connected")
    except Exception as e:
        logger.error("storage connection failed")
        logger.error(e)
        exit(1)
    
    # await upload_binary()
    connection = await aio_pika.connect_robust("amqp://test:test@localhost/")
    loop  = asyncio.get_event_loop()
    async with connection:
        channel = await connection.channel()
        loop.create_task(send_run_message(channel,"build_queue"))

        # wait for all tasks to be done
        await asyncio.gather(*asyncio.all_tasks())

def data():
    return {
        "command":"build",
        "data":{
            "build_id": "1234",
            "image_name": "cyrus2d",
            "image_tag": "latest",
            "file": {
                "type": "minio",
                "config": {
                    "endpoint": "http://localhost:9000",
                    "access_key": "minioadmin",
                    "secret_key": "minioadmin",
                },
                "bucket": "test",
                "file_id": "1234"
            },
            "registry": {
                "config": {
                    "host": "",
                    "port": 1234,
                    "username": "registry",
                    "password": "registry"
                }
            },
            "log": {
                "level": "info",
                "stream": {
                    "build": {
                        "type": "rabbitmq",
                        "host": "rabbitmq",
                        "port": 5672,
                        "username": "username",
                        "password": "password",
                        "exchange": "exchange",
                        "queue": "queue"
                    }
                }
            }
        }

    }

async def send_run_message(channel,send_queue):
    # create a channel for getting the reply
    reply_queue = await channel.declare_queue(exclusive=True)
    print(f"The name of the declared queue is: {reply_queue.name}")
    
    msg = data()
    
    # Sending run_match command
    await channel.default_exchange.publish(
        aio_pika.Message(
            body=json.dumps(msg).encode(),
            reply_to=reply_queue.name
        ),
        routing_key=send_queue
    )
    
    log(f"Sent 'run_match' command. on {send_queue}")

    # print the reply from the queue
    async with reply_queue.iterator() as queue_iter:
        async for message in queue_iter:
            async with message.process():
                print(f" [x] Received reply from {send_queue}:", message.body.decode())
                # it means it is finished
                if "killed" in message.body.decode():
                    break
