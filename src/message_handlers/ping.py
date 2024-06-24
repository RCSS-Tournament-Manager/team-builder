import asyncio
from time import sleep

from src.logger import get_logger
from src.storage import MinioClient


logger = get_logger(__name__)

async def ping_command_handler(data: dict, reply, **kwargs):
    logger.info("Handling ping command")
    sleep(10)
    for i in range(50):
        await reply("""""")
        





