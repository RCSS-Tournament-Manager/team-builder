import docker
import os
from src.docker import Docker
from src.logger import get_logger

logger = get_logger(__name__)

async def run():
    # Initialize a Docker client
    docker = Docker()
    

    # Path to the directory containing the Dockerfile
    dockerfile_path = '/home/piker/Projects/other/2D/RCSS-Tournament-Manager/team-builder'

    # Build the Docker image
    try:
        build_result = docker.build_with_path(
            path=dockerfile_path,
            image_name="test",
            image_tag="test",
        )
        # Assuming env.docker_i.build_with_path returns a stream of build output
        for line in build_result:
            logger.info(line)
            
        print("\nDocker image built successfully.")
        
        
        push_result = docker.push_to_registry(
            image_name="test",
            image_tag="test",
        )
        # Assuming env.docker_i.push_to_registry returns a stream of push output
        for line in push_result:
            logger.info(line)

    except Exception as e:
        print(f"An unexpected error occurred: {e}")
    pass
