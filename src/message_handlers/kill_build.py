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

import json

logger = logging.getLogger("builder")

kill_build = False
build_id = None
team_name = None


@required_fields(
    fields=[
        "build_id",
        "team_name"
    ]
)

async def kill_build_command_handler(
    data: dict, 
    docker: Docker, 
    storage: MinioClient, 
    reply, 
    **kwargs
):
    global build_id, team_name, kill_build
    build_id = data["build_id"]
    team_name = data["team_name"]
    kill_build = True

async def check_kill_command(input_team_name, input_build_id):
    global kill_build, build_id, team_name
    #logger.error(f'kill_build {kill_build}')
    if input_team_name == team_name and input_build_id == build_id and kill_build:
        return True
    else:
        return False

async def set_kill_command():
    global kill_build, build_id, team_name
    kill_build = False
    build_id = None
    team_name = None
