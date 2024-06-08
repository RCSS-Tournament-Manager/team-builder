import asyncio
import logging
import os
import shutil
import tarfile
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
import uuid
from fastapi.responses import StreamingResponse
import urllib3
from src import env
from src.models import ImageBuildedResponse
from src.rabbitmq import RabbitMQ
logger = logging.getLogger("builder")

router = APIRouter(
    prefix="/api/v1/builder",
    tags=["Builder"],
    responses={404: {"description": "Not found"}},
)

async def test_stream():
    for i in range(10):
        yield f"data: {i}\n\n"
        await asyncio.sleep(1)
    return

@router.post(
    path="/image/file",
    description="build an image with the given data",
    response_model=ImageBuildedResponse
)
async def build_image_with_file(
        file: UploadFile = File(description=".tar.gz file of the image"),
        image_name: str = Form(description="Name of the image"),
        image_tag: str = Form(default="latest",description="Tag of the image"),
        timeout: int = Form(default=1200,gt=0,lt=3600,description="Timeout in seconds")
):
    
    # check file extension
    if not file.filename.endswith(".tar.gz") or \
            file.content_type != "application/gzip":
        raise HTTPException(status_code=400, detail="File type not supported")

    # random file name
    id = str(uuid.uuid4())
    tmp_file = os.path.join(os.getcwd(), 'upload', id + ".tar.gz")
    with open(tmp_file, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # extract file
    folder_path = os.path.join(os.getcwd(), 'upload', id)
    try:
        tar = tarfile.open(tmp_file)
        tar.extractall(path=folder_path)
        tar.close()
    except Exception as e:
        logger.error("Error while extracting tar file", e)
        os.remove(tmp_file)
        raise HTTPException(status_code=400, detail="File type not supported")
    

    if len(os.listdir(folder_path)) == 1 and os.path.isdir(folder_path):
        folder_path = os.path.join(folder_path, os.listdir(folder_path)[0])
        if not os.path.exists(os.path.join(folder_path, "Dockerfile")):
            os.remove(tmp_file)
            shutil.rmtree(os.path.join(os.getcwd(), 'upload', id))
            raise HTTPException(status_code=400, detail="Dockerfile not found")
    
    elif not os.path.exists(os.path.join(folder_path, "Dockerfile")):
        os.remove(tmp_file)
        shutil.rmtree(os.path.join(os.getcwd(), 'upload', id))
        raise HTTPException(status_code=400, detail="Dockerfile not found")
    
    
    logger.info(f"Building image {image_name}:{image_tag}")
    logger.info(f"Building image from {folder_path}")
    build_progress = env.docker_i.build_with_path(
        path=folder_path,
        id=id,
        image_name=image_name,
        image_tag=image_tag,
        timeout=timeout
    )
    
    def build_progress_fn():
        error = False
        try:
            for line in build_progress:
                yield line
        except urllib3.exceptions.ReadTimeoutError as e:
            logger.error("Timeout while building image", e)
            yield '{"stream": "timeout", "error": "timeout"}'
            error = True
        except Exception as e:
            logger.error("Error while building image", e)
            yield '{"stream": "error", "error": "error"}'
            error = True
            
            
        
        if error:
            os.remove(tmp_file)
            shutil.rmtree(os.path.join(os.getcwd(), 'upload', id))
            return 
        
        yield '{"stream": "build_done"}'
        
        for line in env.docker_i.push_to_registry(
                image_name=image_name,
                image_tag=image_tag,
        ):
            yield line
            
        yield '{"stream": "push_done"}'
         
        
        
    
    return StreamingResponse(
        build_progress_fn(),
        media_type='text/event-stream'
    )
    

@router.post(
    path="/image/s3",
    description="build an image from s3 location",
)
async def build_image_with_s3(
        file_id: str,
):
    
    #Create RabbitMQ
    rabbit = RabbitMQ()
    rabbit.connect()

    s3_client = env.s3_client
    bucket_name = env.s3_bucket_name
    file_key = f"{file_id}.tar.gz"
    tmp_file = f"/tmp/{file_id}.tar.gz"
    tmp_folder = f"/tmp/{file_id}"

    # Check if the file exists in S3
    try:
        s3_client.head_object(Bucket=bucket_name, Key=file_key)
    except s3_client.exceptions.NoSuchKey:
        raise HTTPException(status_code=404, detail="File not found in S3")

    # Download the file
    try:
        s3_client.download_file(bucket_name, file_key, tmp_file)
    except Exception as e:
        logger.error("Failed to download file from S3", e)
        raise HTTPException(status_code=500, detail="Failed to download file from S3")

    # Check if it is a tar file and extract it
    try:
        with tarfile.open(tmp_file) as tar:
            tar.extractall(path=tmp_folder)
    except Exception as e:
        logger.error("Failed to extract tar file", e)
        raise HTTPException(status_code=400, detail="Invalid tar file")

    # Check if the folder has a Dockerfile
    dockerfile_path = os.path.join(tmp_folder, "Dockerfile")
    if not os.path.exists(dockerfile_path):
        shutil.rmtree(tmp_folder)
        raise HTTPException(status_code=400, detail="Dockerfile not found")

    # Build the image
    image_name = f"{file_id.lower()}"
    image_tag = "latest"
    try:
        build_result = env.docker_i.build_with_path(
            path=tmp_folder,
            id=file_id,
            image_name=image_name,
            image_tag=image_tag,
            timeout=1200  # or another appropriate timeout
        )
        # Assuming env.docker_i.build_with_path returns a stream of build output
        for line in build_result:
            logger.info(line)
    except Exception as e:
        logger.error("Failed to build image", e)
        shutil.rmtree(tmp_folder)
        raise HTTPException(status_code=500, detail="Failed to build image")

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
        raise HTTPException(status_code=500, detail="Failed to push image to registry")

    # Clean up
    shutil.rmtree(tmp_folder)
    os.remove(tmp_file)

    # Return the image details
    return {"image_name": image_name, "image_tag": image_tag}