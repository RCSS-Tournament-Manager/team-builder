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

logger = logging.getLogger("builder")


@required_fields(fields=["build_id"])
async def kill_build_command_handler(
    data: dict, state_manager: StateManager, reply, **kwargs
):
    build_id = data.get("build_id")
    state_manager.kill_run_job(build_id)
    await reply({"status": "killed"})
    
