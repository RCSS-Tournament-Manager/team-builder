import asyncio
import aio_pika
import json
import os
from src.storage import MinioClient
from src.logger import get_logger

import random
logger = get_logger(__name__)


bucket = "test"
file_id = "cyrus2d"


def data():
   return {
        "command":"build",
        "data":{
            "build_id": "8789",
            "team_name": "cyrus2d",
            "image_name": "cyrus2d",
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
def kill_data():
   return {
        "command":"kill_build",
        "data":{
            "build_id": "8789",
            "team_name": "cyrus2d",
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
        "cyrus2d.tar.gz"
    )
    
    await minio.upload_file(
        bucket_name=bucket,
        object_name=f'{file_id}.tar.gz',
        file_path=file_path
    )
    logger.info(f"Uploaded file {file_id} to {bucket}")
    pass


async def send_build_message(channel,send_queue):
    # create a channel for getting the reply
    reply_queue = await channel.declare_queue(exclusive=True)
    
    msg = data()
    # Sending run_match command
    await channel.default_exchange.publish(
        aio_pika.Message(
            body=json.dumps(msg).encode(),
            reply_to=reply_queue.name
        ),
        routing_key=send_queue
    )
    
    logger.info(f"Sent 'build' command. on {send_queue}")
    
    # print the reply from the queue
    async with reply_queue.iterator() as queue_iter:
        async for message in queue_iter:
            async with message.process():
                logger.info(f" [x] Received reply from {send_queue}:", message.body.decode())
                # it means it is finished
                if "killed" in message.body.decode():
                    break

async def send_kill_message(channel,send_queue):
    # create a channel for getting the reply
    reply_queue = await channel.declare_queue(exclusive=True)
    
    msg = kill_data()
    # Sending run_match command
    await channel.default_exchange.publish(
        aio_pika.Message(
            body=json.dumps(msg).encode(),
            reply_to=reply_queue.name
        ),
        routing_key=send_queue
    )
    
    logger.info(f"Sent 'kill_build' command. on {send_queue}")
    
    # print the reply from the queue
    async with reply_queue.iterator() as queue_iter:
        async for message in queue_iter:
            async with message.process():
                logger.info(f" [x] Received reply from {send_queue}:", message.body.decode())
                # it means it is finished
                if "killed" in message.body.decode():
                    break

async def run(): 
    await upload_file()
    
    connection = await aio_pika.connect_robust("amqp://test:test@localhost/")
    loop  = asyncio.get_event_loop()
    async with connection:
        channel = await connection.channel()
        #Sending build message
        loop.create_task(send_build_message(channel,"build_queue"))
        await asyncio.sleep(0.5)  
        loop.create_task(send_kill_message(channel , "build_queue"))
        # wait for all tasks to be done
        await asyncio.gather(*asyncio.all_tasks())
