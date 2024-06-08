import logging
import os
import shutil
import tarfile
from src import env
from src.docker import Docker
from src.storage import MinioClient
from src.decorators import required_fields

logger = logging.getLogger("builder")


@required_fields(
    [
        "build_id",
        "image_name",
        "image_tag",
        "file.type",
        "file.file_id",
        "file.bucket",
    ]
)
async def build_command_handler(
    data: dict, 
    docker: Docker, 
    storage: MinioClient, 
    reply, 
    **kwargs
):
    # ----------------------------- Parse input
    build_id = data["build_id"]
    image_name = data["image_name"]
    image_tag = data["image_tag"]

    file_id = data["file"]["file_id"]
    bucket = data["file"]["bucket"]

    storage_type = data["file"]["type"]
    storage_client = storage
    if (
        storage_type == "minio"
        and "access_key" in data["file"]
        and "secret_key" in data["file"]
        and "endpoint" in data["file"]
    ):

        storage_client = MinioClient(
            endpoint=data["file"]["endpoint"],
            access_key=data["file"]["access_key"],
            secret_key=data["file"]["secret_key"],
            secure=data["file"]["secure"] if "secure" in data["file"] else True,
        )

    data["file"]["client"] = storage_client

    docker_client = docker

    try:
        docker_client = Docker(**data["registry"]["config"])
    except Exception as e:
        pass

    data["registry"]["client"] = docker_client

    file_key = f"{file_id}.tar.gz"
    tmp_file = f"/tmp/{file_id}.tar.gz"
    tmp_folder = f"/tmp/{file_id}"

    # Check if the file exists in S3
    try:
        data["file"]["client"].head_object(Bucket=data["file"]["bucket"], Key=file_key)
    except data["file"]["client"].exceptions.NoSuchKey:
        logger.error("File not found in S3")
        await reply("File not found in S3")
        return

    # Download the file
    try:
        data["file"]["client"].download_file(data["file"]["bucket"], file_key, tmp_file)
    except Exception as e:
        logger.error("Failed to download file from S3", e)
        await reply("Failed to download file from S3")
        return

    # Check if it is a tar file and extract it
    try:
        with tarfile.open(tmp_file) as tar:
            tar.extractall(path=tmp_folder)
    except Exception as e:
        logger.error("Failed to extract tar file", e)
        await reply(f"Failed to extract tar file")
        return

    # TODO get config for docker file ?
    # Check if the folder has a Dockerfile

    config_docker_file_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "static", "team-build.Dockerfile"
    )
    dockerfile_path = os.path.join(tmp_folder, "team-build.Dockerfile")
    if not os.path.exists(dockerfile_path):
        shutil.rmtree(tmp_folder)
        logger.info("Failed to find Dockerfile attempt to add docker file")
        await reply(f"Failed to find Dockerfile attempt to add docker file")
        shutil.copy(config_docker_file_path, tmp_folder)

    # Build the image
    try:
        build_result = env.docker_i.build_with_path(
            path=tmp_folder,
            id=file_id,
            image_name=image_name,
            image_tag=image_tag,
            timeout=1200,  # or another appropriate timeout
        )
        # Assuming env.docker_i.build_with_path returns a stream of build output
        for line in build_result:
            logger.info(line)
    except Exception as e:
        logger.error("Failed to build image", e)
        shutil.rmtree(tmp_folder)
        await reply("Failed to build image")
        return

    # Push the image to the registry
    try:
        push_result = env.docker_i.push_to_registry(
            image_name=image_name,
            image_tag=image_tag,
        )
        # Assuming env.docker_i.push_to_registry returns a stream of push output
        for line in push_result:
            logger.info(line)
    except Exception as e:
        logger.error("Failed to push image to registry", e)
        shutil.rmtree(tmp_folder)
        await reply("Failed to push image to registry")
        return
    # Clean up
    shutil.rmtree(tmp_folder)
    os.remove(tmp_file)
    await reply(f"Building done image_name:{image_name} , image_tag:{image_tag}")
    # Return the image details
    return {"image_name": image_name, "image_tag": image_tag}
