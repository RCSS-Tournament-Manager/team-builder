from src.docker import Docker
from src.logger import get_logger
from src import env
import asyncio

logger = get_logger(__name__)

async def run():
    docker = Docker(
        default_registry=env.DOCKER_REGISTERY_ADDRESS
        + ":"
        + str(env.DOCKER_REGISTERY_PORT),
        username=env.DOCKER_REGISTERY_USERNAME,
        password=env.DOCKER_REGISTERY_PASSWORD,
    )
    try:
        logger.info("docker connecting...")
        docker.connect()
        logger.info("docker connected")
    except Exception as e:
        logger.error("docker connection failed")
        logger.error(e)
        exit(1)

    build_path = "/home/piker/Projects/other/2D/RCSS-Tournament-Manager/team-builder/uploads/422_agent_r/docker"
    image_name = "agent_r"
    image_tag = "latest"

    tag = f"{docker.default_registry}/{image_name}:{image_tag}"
    
    q = asyncio.Queue()

    def build(loop):
        build_result = docker.api.build(
            path=build_path,
            rm=True,
            tag=tag,
            timeout=12000,
        )
        
        for line in build_result:
            asyncio.run_coroutine_threadsafe(q.put(""), loop)
            logger.info(line)

    # Get the current event loop
    loop = asyncio.get_running_loop()

    # to_thread
    asyncio.create_task(asyncio.to_thread(build, loop))
    
    logger.info("build started")
    await q.get()
    logger.info("build finished")

