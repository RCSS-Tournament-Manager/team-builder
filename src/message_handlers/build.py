import logging
import os
import shutil
import tarfile
import tempfile
from src import env
from src.docker import Docker
from src.storage import MinioClient
from src.decorators import required_fields
from src.utils.client_initializer import initialize_clients
from src.env import (
    DEFAULT_TEAM_BUILD_DOCKERFILE,
    DEFAULT_UPLOAD_FOLDER,
    REMOVE_AFTER_BUILD,
    USE_TMP_UPLOAD_FOLDER,
)
from src.message_handlers.kill_build import (check_kill_command,set_kill_command)
import json
import asyncio

logger = logging.getLogger("builder")


async def download_team_dockerfile_from_minio(
    bucket_name: str, object_name: str, client: MinioClient
):
    file_path = ""
    errors = []
    return file_path, errors


@required_fields(
    fields=[
        "build_id",
        "team_name",
        "image_name",
        "image_tag",
        "file.file_id",
        "file.bucket",
        "file._type",
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
    team_name = data["team_name"]
    image_name = data["image_name"]
    image_tag = data["image_tag"]

    file_id = data["file"]["file_id"]
    file_name = f"{file_id}.tar.gz"
    bucket = data["file"]["bucket"]

    tmp_folder = None
    tmp_file = None

    async def log_reply(message, log_fn=logger.info, e=None):
        log_fn(message)
        await reply(message)

    if "registry" not in data:
        data["registry"] = {"_type": "docker", "_config": "default"}

    extracted_data, errors = initialize_clients(data, docker=docker, storage=storage, **kwargs)
    for error in errors:
        logger.error(error)
        await reply(error)

    if USE_TMP_UPLOAD_FOLDER:
        tmp_folder = tempfile.mkdtemp()
        tmp_file = os.path.join(tmp_folder, file_name)
        log_reply(f"Using tmp folder: {tmp_folder}")
    else:
        # create a folder with the build_id and teamname
        tmp_folder = os.path.join(DEFAULT_UPLOAD_FOLDER, f"{build_id}_{team_name}")
        await log_reply(f"Using pre-defined folder: {tmp_folder}")
        os.makedirs(tmp_folder, exist_ok=True)
        tmp_file = os.path.join(tmp_folder, file_name)

    team_dockerfile_path = DEFAULT_TEAM_BUILD_DOCKERFILE
    if "team_dockerfile" in extracted_data:
        if (
            "bucket" not in extracted_data["team_dockerfile"]
            or "file_id" not in extracted_data["team_dockerfile"]
        ):
            await log_reply("Invalid team_dockerfile object", logger.error)
            del extracted_data["dockerfile"]
        else:
            file_path, errors = await download_team_dockerfile_from_minio(
                bucket_name=extracted_data["team_dockerfile"]["bucket"],
                object_name=extracted_data["team_dockerfile"]["file_id"],
                client=extracted_data["team_dockerfile"]["_client"],
            )
            for error in errors:
                await log_reply(error, logger.error)

            if file_path != "":
                team_dockerfile_path = file_path

    # ----------------------------- Validation

    # Check if the file exists in storage
    try:
        if await extracted_data["file"]["_client"].has_object(
            bucket_name=bucket, object_name=file_name
        ):
            logger.info("File found in S3")
        else:
            await log_reply("File not found in S3", logger.error)
            return
    except Exception as e:
        await log_reply("Failed to check if file exists in S3", logger.error, e)
        return

    # ----------------------------- Build the image

    # The structure of the temp folder should be like this:
    # --- tmp_foolder
    # -------- file.tar.gz
    # -------- extraced/
    # ------------------ teamname/
    # -------------------------- start
    # -------------------------- Dockerfile
    # -------------------------- .dockerignore
    # -------------------------- other files
    # ------------------ --
    # -------- docker/
    # -------------- bin/
    # -------------- Dockerfile

    # Download the file to temp folder
    try:
        await extracted_data["file"]["_client"].download_file(
            extracted_data["file"]["bucket"], file_name, tmp_file
        )
        logger.info(f"Team File Download Successful { tmp_file }")

    except Exception as e:
        await log_reply("Failed to download file from S3", logger.error, e)
        return

    # create extracted and docker folder in the temp folder
    extracted_folder_path = os.path.join(tmp_folder, "extracted")
    docker_folder_path = os.path.join(tmp_folder, "docker")
    try:
        os.makedirs(extracted_folder_path)
        os.makedirs(docker_folder_path)
    except Exception as e:
        await log_reply("Failed to create extracted and docker folders", logger.error, e)
        return

    # Check if it is a tar file and extract it to the extract folder inside temp folder

    try:
        with tarfile.open(tmp_file) as tar:
            tar.extractall(path=extracted_folder_path)
        logger.info(f"Tar file extracted successfully to {extracted_folder_path}")

    except Exception as e:
        await log_reply("Failed to extract tar file", logger.error, e)
        return

    # Check if the extracted folder has only one sub folder
    sub_folders = [
        name
        for name in os.listdir(extracted_folder_path)
        if os.path.isdir(os.path.join(extracted_folder_path, name))
    ]
    logger.info(f"Sub folders in the extracted folder: {sub_folders}")
    if len(sub_folders) != 1:
        await log_reply(
            "There should be only one folder in the extracted folder", logger.error
        )
        return

    # Check the teamname and the extracted folder name is the same
    team_folder_path = os.path.join(extracted_folder_path, sub_folders[0])
    extracted_folder_name = sub_folders[0]

    if extracted_folder_name != team_name:
        await log_reply(
            f"Teamname and extracted folder {extracted_folder_name} name do not match",
            logger.error,
        )
        return
    
    # Check if the required files exist in the extracted folder
    required_files = ["start"]  # Add more file names if needed
    not_found_files = []
    for file_name in required_files:
        file_path = os.path.join(team_folder_path, file_name)
        logger.info(f"Checking if {file_name} exists in {team_folder_path}")
        if not os.path.exists(file_path):
            not_found_files.append(file_name)
    if len(not_found_files) > 0:
        await log_reply(f"Required files not found: {not_found_files}", logger.error)
        return
    elif len(not_found_files) == 0:
        await log_reply("All required files found")

    # Check if any Dockerfile type exists in the extracted folder and remove it
    dockerfile_types = [ # what dockerfiles to remove 
        "Dockerfile",
        ".dockerignore",
    ] 
    for dockerfile_type in dockerfile_types:
        dockerfile_path = os.path.join(team_folder_path, dockerfile_type)
        if os.path.isfile(dockerfile_path):
            await log_reply(f"{dockerfile_type} has been found")
            try:
                os.remove(dockerfile_path)
                await log_reply(f"{dockerfile_type} has been removed")
            except Exception as e:
                await log_reply(f"Failed to remove {dockerfile_type}", logger.error, e)
                return
    for dockerfile_type in dockerfile_types:
        dockerfile_path = os.path.join(extracted_folder_path, dockerfile_type)
        if os.path.isfile(dockerfile_path):
            await log_reply(f"{dockerfile_type} has been found")
            try:
                os.remove(dockerfile_path)
                await log_reply(f"{dockerfile_type} has been removed")
            except Exception as e:
                await log_reply(f"Failed to remove {dockerfile_type}", logger.error, e)
                return

    # rename and move the team folder to bin
    bin_folder_path = os.path.join(docker_folder_path, "bin")
    try:
        logger.info(f"Renaming {team_folder_path} to {bin_folder_path}")
        os.rename(team_folder_path, bin_folder_path)
        await log_reply(f"Team folder has been renamed to bin")
    except Exception as e:
        await log_reply("Failed to rename the Team folder to bin", logger.error, e)
        return

    # replay the success message
    await log_reply(f"Extracted folder has been moved to the bin folder")

    # Copy the dockerfile from s3 to the extracted folder or falback
    try:
        new_dockerfile_path = os.path.join(
            docker_folder_path,
            # team_name,
            "Dockerfile",
        )
        shutil.copy(team_dockerfile_path, new_dockerfile_path)  

        await log_reply(
            f"S3 Team Dockerfile has been copied in to the extracted folder"
        )
    except Exception as e:
        await log_reply(
            f"Failed to copy Team Dockerfile in the extracted folder", logger.error, e
        )

    # falback to default dockerfile and copy it to the extracted folder
    if not os.path.exists(new_dockerfile_path):
        try:
            shutil.copy(DEFAULT_TEAM_BUILD_DOCKERFILE, new_dockerfile_path)
            await log_reply(
                f"Default Dockerfile has been copied in to the extracted folder"
            )

        except Exception as e:
            await log_reply(
                f"Failed to copy Default Dockerfile in the extracted folder",
                logger.error,
                e,
            )
            return
    # -----------------------------
    # Check if there was a kill build command
    wait_time = 1
    logger.info(f"Waiting {wait_time} second for any kill command")
    await asyncio.sleep(wait_time)  
    if await check_kill_command(team_name,build_id):
        await set_kill_command()
        logger.info(f"An kill build command was set for {team_name} --- Building has been stopped")
        await log_reply(f"An kill build command was set for {team_name} --- Building has been stopped")
        return
    # Build the image
    try:
        build_result = extracted_data["registry"]["_client"].build_with_path(
            path=docker_folder_path,
            image_name=image_name,
            image_tag=image_tag,
        )
        # Assuming env.docker_i.build_with_path returns a stream of build output
        for line in build_result:
            msg = None
            try:
                logger.debug("line : " + line)
                msg = json.loads(line)
            except:
                msg = line
                logger.debug("Failed to parse the msg")

            logger.debug(msg)
            await reply(msg)
    except Exception as e:
        logger.error("Failed to build image", e)
        if REMOVE_AFTER_BUILD:
            shutil.rmtree(tmp_folder)
        await reply("Failed to build image")
        return

    # Push the image to the registry
    try:
        push_result = extracted_data["registry"]["_client"].push_to_registry(
            image_name=image_name,
            image_tag=image_tag,
        )
        # Assuming env.docker_i.push_to_registry returns a stream of push output
        for line in push_result:
            msg = None
            try:
                logger.debug("line : " + line)
                msg = json.loads(line)
            except Exception as e:
                msg = line
                logger.debug("Failed to parse the msg")
                logger.debug(e)

            logger.debug(msg)
            await reply(msg)
    except Exception as e:
        await log_reply("Failed to push image to registry", logger.error, e)
        if REMOVE_AFTER_BUILD:
            shutil.rmtree(tmp_folder)
        return
    # remove the extracted folder and docker folder after the image has been pushed
    if REMOVE_AFTER_BUILD:
        try:
            shutil.rmtree(extracted_folder_path)
            shutil.rmtree(docker_folder_path)
        except Exception as e:
            await log_reply("Failed to remove the extracted folder", logger.error, e)
            return

    # replay the success message with the image name and tag
    await log_reply(
        f"Image {image_name}:{image_tag} has been built and pushed successfully",
        logger.info,
    )

    return
