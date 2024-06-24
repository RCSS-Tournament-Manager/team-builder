import asyncio
import aio_pika

from src.docker import Docker
from src.logger import get_logger
from src.message_handlers.kill_build import kill_build_command_handler
from src.message_handlers.ping import ping_command_handler
from src.message_handlers.build import build_command_handler
from src.message_handlers.status import status_command_handler
from src.message_handler import MessageHandler
from src.rabbitmq import RabbitMQ
from src.routes.status import handle_status
from src.states import StateManager
from src.storage import MinioClient
from src.webserver import Webserver
from src import env
logger = get_logger(__name__)

loop = asyncio.get_event_loop()


async def main(loop):


    # ---------------------- 
    # RabbitMQ
    # ---------------------- 
    rabbit = RabbitMQ(
        loop=loop, 
        server=env.RABBITMQ_ADDRESS, 
        port=61613,
        queue="build_queue",
        username=env.RABBITMQ_USERNAME,
        password=env.RABBITMQ_PASSWORD
    )
    logger.info("rabbitmq consumer started")
    try:
        logger.info("rabbitmq connecting...")
        await rabbit.connect()
        logger.info("rabbitmq connected")
    except Exception as e:
        logger.error("rabbitmq connection failed")
        logger.error(e)
        exit(1)

    
    
    # ----------------------
    # Storage
    # ----------------------
    storage = MinioClient(
        endpoint=env.MINIO_ADDRESS+ ":" + str(env.MINIO_PORT),
        access_key=env.MINIO_USERNAME,
        secret_key=env.MINIO_PASSWORD,
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
        
        
    # ----------------------
    # Docker
    # ----------------------
    docker = Docker(
        default_registry=env.DOCKER_REGISTERY_ADDRESS+ ":" + str(env.DOCKER_REGISTERY_PORT),
        username=env.DOCKER_REGISTERY_USERNAME,
        password=env.DOCKER_REGISTERY_PASSWORD
    )
    try:
        logger.info("docker connecting...")
        docker.connect()
        logger.info("docker connected")
    except Exception as e:
        logger.error("docker connection failed")
        logger.error(e)
        exit(1)
    
    
    # ----------------------
    # Webserver
    # ----------------------
    server = Webserver(
        host=env.WEBSERVER_ADDRESS,
        port=env.WEBSERVER_PORT
    )
    
    # --- routes
    server.add_get('/status', handle_status)
    try:
        await server.listen()
        logger.info("webserver connected")
    except Exception as e:
        logger.error("webserver connection failed")
        logger.error(e)
        exit(1)
    

    # ----------------------
    # State Manager
    # ----------------------
    state_manager = StateManager()


    # ----------------------
    
    # --- add message handler
    mh = MessageHandler(
        rabbit=rabbit,
        storage=storage,
        docker=docker,
        server=server,
        state_manager=state_manager
    )
    
    mh.add_command_handler("build", build_command_handler)
    mh.add_command_handler("kill_build" , kill_build_command_handler)
    mh.add_command_handler("ping", ping_command_handler)
    mh.add_command_handler("status", status_command_handler)


    
    await rabbit.add_message_handler(mh.message_processor)



if __name__ == "__main__":
    try:
        loop.run_until_complete(main(loop))
        loop.run_forever()
    except KeyboardInterrupt:
        pass
    finally:
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()
