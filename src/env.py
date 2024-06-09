import os
from src.docker import Docker
from dotenv import load_dotenv

load_dotenv()

HOST = os.environ.get('HOST')
PORT = int(os.environ.get('PORT'))
DOCKER_REGISTRY=os.environ.get('DOCKER_REGISTRY')



DEFAULT_TEAM_BUILD_DOCKERFILE = os.path.join(
    os.path.dirname(__file__), 
    "static", 
    "team-build.DockerFile"
)

DEFAULT_UPLOAD_FOLDER = os.path.join(
    os.path.dirname(__file__), 
    "..",
    "uploads"
)

USE_TMP_UPLOAD_FOLDER = False

REMOVE_AFTER_BUILD = False

docker_i: Docker = None