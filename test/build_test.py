import asyncio
import aio_pika
import json
import os
from src.storage import MinioClient
from src.logger import get_logger

import random
logger = get_logger(__name__)


bucket = "test"
file_id = "agent_r"


def data():
   return {
        "command":"build",
        "data":{
            "build_id": random.randint(1000,9000),
            "team_name": file_id,
            "image_name": file_id,
            "image_tag": "latest",
            

            "file":{
                "_type": "minio",
                "bucket": bucket,
                "file_id": file_id
            },

            "registry":{
                "_type": "docker",
            },
        }

    }

def log(msg):
    print (f' [+] {msg}')


async def upload_file():
    minio = MinioClient(
        endpoint="localhost:9000",
        access_key="minioadmin",
        secret_key="minioadmin",
        secure=False
    )
    
    file_path = os.path.join(
        os.path.dirname(__file__),
        f'{file_id}.tar.gz'
    )
    
    await minio.upload_file(
        bucket_name=bucket,
        object_name=f'{file_id}.tar.gz',
        file_path=file_path
    )
    log(f"Uploaded file {file_id} to {bucket}")
    pass


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
    
    log(f"Sent 'build' command. on {send_queue}")

    # print the reply from the queue
    async with reply_queue.iterator() as queue_iter:
        async for message in queue_iter:
            async with message.process():
                print(f" [x] Received reply from {send_queue}:", message.body.decode())
                # it means it is finished
                if "killed" in message.body.decode():
                    break

async def run(): 
    await upload_file()
    
    connection = await aio_pika.connect_robust("amqp://test:test@localhost/")
    loop  = asyncio.get_event_loop()
    async with connection:
        channel = await connection.channel()
        loop.create_task(send_run_message(channel,"build_queue"))


        # wait for all tasks to be done
        await asyncio.gather(*asyncio.all_tasks())
