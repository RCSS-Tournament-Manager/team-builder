import logging
import os
import shutil
import tarfile
import tempfile
from src import env
from src.docker import Docker
from src.states import StateManager
from src.storage import MinioClient
from src.decorators import required_fields
from src.utils.client_initializer import initialize_clients
from src.env import (
    DEFAULT_TEAM_BUILD_DOCKERFILE,
    DEFAULT_UPLOAD_FOLDER,
    REMOVE_AFTER_BUILD,
    USE_TMP_UPLOAD_FOLDER,
)
import json
import asyncio

logger = logging.getLogger("builder")


async def download_team_dockerfile_from_minio(bucket_name: str, object_name: str, client: MinioClient):
    file_path = ""
    errors = []
    return file_path, errors


async def reply_stage(reply, stage_id, message):
    await reply({"stage": stage_id, "data": message})


async def reply_stage_state(reply, stages, current_stage, stage_id, stage_state):
    if stage_state == "success":
        # find index of the current stage
        current = stages.index(next(filter(lambda x: x["id"] == stage_id, stages)))
        current_stage["i"] = current + 1 if current < len(stages) - 1 else current
    await reply({"stage": stage_id, "state": stage_state})


async def log_reply(reply, stages, current_stage, message, log_fn=logger.info, e=None):
    log_fn(message)
    await reply_stage(reply, stages[current_stage["i"]]["id"], message)


async def input_validation(data, docker, storage, reply, stages, current_stage, **kwargs):
    await reply_stage_state(reply, stages, current_stage, "input_validation", "start")
    
    build_id = data["build_id"]
    team_name = data["team_name"]
    image_name = data["image_name"]
    image_tag = data["image_tag"]

    file_id = data["file"]["file_id"]
    file_name = f"{file_id}.tar.gz"
    bucket = data["file"]["bucket"]

    tmp_folder = None
    tmp_file = None

    if "registry" not in data:
        data["registry"] = {"_type": "docker", "_config": "default"}

    extracted_data, errors = initialize_clients(data, docker=docker, storage=storage, **kwargs)
    for error in errors:
        logger.error(error)
        await reply(error)

    if USE_TMP_UPLOAD_FOLDER:
        tmp_folder = tempfile.mkdtemp()
        tmp_file = os.path.join(tmp_folder, file_name)
        await log_reply(reply, stages, current_stage, f"Using tmp folder for build")
    else:
        tmp_folder = os.path.join(DEFAULT_UPLOAD_FOLDER, f"{build_id}_{team_name}")
        await log_reply(reply, stages, current_stage, f"Using pre-defined folder for build")
        os.makedirs(tmp_folder, exist_ok=True)
        tmp_file = os.path.join(tmp_folder, file_name)

    team_dockerfile_path = DEFAULT_TEAM_BUILD_DOCKERFILE
    if "team_dockerfile" in extracted_data:
        if "bucket" not in extracted_data["team_dockerfile"] or "file_id" not in extracted_data["team_dockerfile"]:
            await log_reply(reply, stages, current_stage, "Invalid team_dockerfile object", logger.error)
            del extracted_data["dockerfile"]
        else:
            file_path, errors = await download_team_dockerfile_from_minio(
                bucket_name=extracted_data["team_dockerfile"]["bucket"],
                object_name=extracted_data["team_dockerfile"]["file_id"],
                client=extracted_data["team_dockerfile"]["_client"],
            )
            for error in errors:
                await log_reply(reply, stages, current_stage, error, logger.error)

            if file_path != "":
                team_dockerfile_path = file_path

    await reply_stage_state(reply, stages, current_stage, "input_validation", "success")

    return build_id, team_name, image_name, image_tag, file_name, bucket, tmp_folder, tmp_file, team_dockerfile_path, extracted_data


async def file_download(reply, stages, current_stage, extracted_data, bucket, file_name, tmp_file):
    await reply_stage_state(reply, stages, current_stage, "file_download", "start")

    try:
        if await extracted_data["file"]["_client"].has_object(bucket_name=bucket, object_name=file_name):
            logger.info("File found in S3")
        else:
            await log_reply(reply, stages, current_stage, "File not found in S3", logger.error)
            return False
    except Exception as e:
        await log_reply(reply, stages, current_stage, "Failed to check if file exists in S3", logger.error, e)
        return False

    try:
        await extracted_data["file"]["_client"].download_file(extracted_data["file"]["bucket"], file_name, tmp_file)
        logger.info(f"Team File Download Successful {tmp_file}")
    except Exception as e:
        await log_reply(reply, stages, current_stage, "Failed to download file from S3", logger.error, e)
        return False

    await reply_stage_state(reply, stages, current_stage, "file_download", "success")
    return True


async def file_extract(reply, stages, current_stage, tmp_file, tmp_folder):
    await reply_stage_state(reply, stages, current_stage, "file_extract", "start")

    extracted_folder_path = os.path.join(tmp_folder, "extracted")
    docker_folder_path = os.path.join(tmp_folder, "docker")
    try:
        os.makedirs(extracted_folder_path)
        os.makedirs(docker_folder_path)
    except Exception as e:
        await log_reply(reply, stages, current_stage, "Failed to create extracted and docker folders", logger.error, e)
        return None, None

    try:
        def extract():
            with tarfile.open(tmp_file) as tar:
                tar.extractall(path=extracted_folder_path)
            logger.info(f"Tar file extracted successfully to {extracted_folder_path}")
        await asyncio.create_task(asyncio.to_thread(extract))
    except Exception as e:
        await log_reply(reply, stages, current_stage, "Failed to extract tar file", logger.error, e)
        return None, None

    await reply_stage_state(reply, stages, current_stage, "file_extract", "success")
    return extracted_folder_path, docker_folder_path


async def file_validate(reply, stages, current_stage, extracted_folder_path, docker_folder_path, team_name, team_dockerfile_path):
    await reply_stage_state(reply, stages, current_stage, "file_validate", "start")

    sub_folders = [name for name in os.listdir(extracted_folder_path) if os.path.isdir(os.path.join(extracted_folder_path, name))]
    logger.info(f"Sub folders in the extracted folder: {sub_folders}")
    if len(sub_folders) != 1:
        await log_reply(reply, stages, current_stage, "There should be only one folder in the extracted folder", logger.error)
        return False

    team_folder_path = os.path.join(extracted_folder_path, sub_folders[0])
    extracted_folder_name = sub_folders[0]

    if extracted_folder_name != team_name:
        await log_reply(reply, stages, current_stage, f"Teamname and extracted folder {extracted_folder_name} name do not match", logger.error)
        return False

    required_files = ["start"]
    not_found_files = []
    for file_name in required_files:
        file_path = os.path.join(team_folder_path, file_name)
        logger.info(f"Checking if {file_name} exists in {team_folder_path}")
        if not os.path.exists(file_path):
            not_found_files.append(file_name)
    if len(not_found_files) > 0:
        await log_reply(reply, stages, current_stage, f"Required files not found: {not_found_files}", logger.error)
        return False
    elif len(not_found_files) == 0:
        await log_reply(reply, stages, current_stage, "All required files found")

    dockerfile_types = ["Dockerfile", ".dockerignore"]
    for dockerfile_type in dockerfile_types:
        dockerfile_path = os.path.join(team_folder_path, dockerfile_type)
        if os.path.isfile(dockerfile_path):
            await log_reply(reply, stages, current_stage, f"{dockerfile_type} has been found")
            try:
                os.remove(dockerfile_path)
                await log_reply(reply, stages, current_stage, f"{dockerfile_type} has been removed")
            except Exception as e:
                await log_reply(reply, stages, current_stage, f"Failed to remove {dockerfile_type}", logger.error, e)
                return False
    for dockerfile_type in dockerfile_types:
        dockerfile_path = os.path.join(extracted_folder_path, dockerfile_type)
        if os.path.isfile(dockerfile_path):
            await log_reply(reply, stages, current_stage, f"{dockerfile_type} has been found")
            try:
                os.remove(dockerfile_path)
                await log_reply(reply, stages, current_stage, f"{dockerfile_type} has been removed")
            except Exception as e:
                await log_reply(reply, stages, current_stage, f"Failed to remove {dockerfile_type}", logger.error, e)
                return False

    bin_folder_path = os.path.join(docker_folder_path, "bin")
    try:
        logger.info(f"Renaming {team_folder_path} to {bin_folder_path}")
        os.rename(team_folder_path, bin_folder_path)
        await log_reply(reply, stages, current_stage, "Team folder has been renamed to bin")
    except Exception as e:
        await log_reply(reply, stages, current_stage, "Failed to rename the Team folder to bin", logger.error, e)
        return False

    await log_reply(reply, stages, current_stage, "Extracted folder has been moved to the bin folder")

    try:
        new_dockerfile_path = os.path.join(docker_folder_path, "Dockerfile")
        shutil.copy(team_dockerfile_path, new_dockerfile_path)
        await log_reply(reply, stages, current_stage, "S3 Team Dockerfile has been copied in to the extracted folder")
    except Exception as e:
        await log_reply(reply, stages, current_stage, "Failed to copy Team Dockerfile in the extracted folder", logger.error, e)

    if not os.path.exists(new_dockerfile_path):
        try:
            shutil.copy(DEFAULT_TEAM_BUILD_DOCKERFILE, new_dockerfile_path)
            await log_reply(reply, stages, current_stage, "Default Dockerfile has been copied in to the extracted folder")
        except Exception as e:
            await log_reply(reply, stages, current_stage, "Failed to copy Default Dockerfile in the extracted folder", logger.error, e)
            return False

    os.chmod(os.path.join(bin_folder_path, "start"), 0o755)
    await log_reply(reply, stages, current_stage, "Start file has been made executable")
    await reply_stage_state(reply, stages, current_stage, "file_validate", "success")
    return True


async def team_build(reply, stages, current_stage, extracted_data, docker_folder_path, image_name, image_tag):
    await reply_stage_state(reply, stages, current_stage, "team_build", "start")
    try:
        loop = asyncio.get_running_loop()
        build_q = asyncio.Queue()

        def build():
            build_result = extracted_data["registry"]["_client"].build_with_path(
                path=docker_folder_path,
                image_name=image_name,
                image_tag=image_tag,
            )
            for line in build_result:
                asyncio.run_coroutine_threadsafe(build_q.put(line), loop)
            asyncio.run_coroutine_threadsafe(build_q.put(None), loop)

        asyncio.create_task(asyncio.to_thread(build))

        await log_reply(reply, stages, current_stage, "Build started")
        while True:
            line = await build_q.get()
            if line is None:
                break
            msg = None
            try:
                msg = json.loads(line)
            except:
                msg = line

            logger.debug(msg)
            await log_reply(reply, stages, current_stage, msg, logger.debug)

    except Exception as e:
        logger.error("Failed to build image", e)
        return False
    await reply_stage_state(reply, stages, current_stage, "team_build", "success")
    return True


async def team_push(reply, stages, current_stage, extracted_data, image_name, image_tag):
    await reply_stage_state(reply, stages, current_stage, "team_push", "start")
    try:
        loop = asyncio.get_running_loop()
        push_q = asyncio.Queue()

        def push():
            push_result = extracted_data["registry"]["_client"].push_to_registry(
                image_name=image_name,
                image_tag=image_tag,
            )
            for line in push_result:
                asyncio.run_coroutine_threadsafe(push_q.put(line), loop)
            asyncio.run_coroutine_threadsafe(push_q.put(None), loop)

        asyncio.create_task(asyncio.to_thread(push))

        await log_reply(reply, stages, current_stage, "Push started")
        while True:
            line = await push_q.get()
            if line is None:
                break
            msg = None
            try:
                msg = json.loads(line)
            except:
                msg = line

            logger.debug(msg)
            await log_reply(reply, stages, current_stage, msg, logger.debug)

    except Exception as e:
        await log_reply(reply, stages, current_stage, "Failed to push image to registry", logger.error, e)
        return False
    await reply_stage_state(reply, stages, current_stage, "team_push", "success")
    return True


async def cleanup(reply, stages, current_stage, extracted_folder_path, docker_folder_path):
    await reply_stage_state(reply, stages, current_stage, "cleanup", "start")
    if REMOVE_AFTER_BUILD:
        try:
            shutil.rmtree(extracted_folder_path)
            shutil.rmtree(docker_folder_path)
        except Exception as e:
            await log_reply(reply, stages, current_stage, "Failed to remove the extracted folder", logger.error, e)
            return False
    await reply_stage_state(reply, stages, current_stage, "cleanup", "success")
    return True


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
    data: dict, docker: Docker, storage: MinioClient, reply, state_manager: StateManager,
    **kwargs
):
    async def run_job():
        await state_manager.update_state(data["build_id"], "progress")
        stages = [
            {"id": "input_validation", "name": "Input Validation"},
            {"id": "file_download", "name": "File Download"},
            {"id": "file_extract", "name": "File Extract"},
            {"id": "file_validate", "name": "File Validate"},
            {"id": "team_build", "name": "Team Build"},
            {"id": "team_push", "name": "Team Push"},
            {"id": "cleanup", "name": "Cleanup"},
        ]

        current_stage = {"i": 0}

        await reply({"stages": stages})

        build_id, team_name, image_name, image_tag, file_name, bucket, tmp_folder, tmp_file, team_dockerfile_path, extracted_data = \
            await input_validation(data, docker, storage, reply, stages, current_stage, **kwargs)
            
        if not extracted_data:
            return

        if not await file_download(reply, stages, current_stage, extracted_data, bucket, file_name, tmp_file):
            return

        extracted_folder_path, docker_folder_path = await file_extract(reply, stages, current_stage, tmp_file, tmp_folder)
        if not extracted_folder_path or not docker_folder_path:
            return

        if not await file_validate(reply, stages, current_stage, extracted_folder_path, docker_folder_path, team_name, team_dockerfile_path):
            return

        if not await team_build(reply, stages, current_stage, extracted_data, docker_folder_path, image_name, image_tag):
            return

        if not await team_push(reply, stages, current_stage, extracted_data, image_name, image_tag):
            return

        if not await cleanup(reply, stages, current_stage, extracted_folder_path, docker_folder_path):
            return

        await log_reply(reply, stages, current_stage, f"Image {image_name}:{image_tag} has been built and pushed successfully", logger.info)
        await state_manager.update_state(data["build_id"], "finished")
    
    task = asyncio.create_task(run_job())
    state_manager.add_run_job(data["build_id"], task, data)
    await task
    return