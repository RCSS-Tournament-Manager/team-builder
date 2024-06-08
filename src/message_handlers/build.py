import logging
import os
import shutil
import tarfile
import tempfile
from src import env
from src.docker import Docker
from src.storage import MinioClient
from src.decorators import required_fields

logger = logging.getLogger("builder")

DEFAULT_TEAM_BUILD_DOCKERFILE = "team-build.Dockerfile"


@required_fields(
    fields = [
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
    file_name = f"{file_id}.tar.gz"
    bucket = data["file"]["bucket"]

    storage_type = data["file"]["type"]
    storage_client = storage
    if (
        storage_type == "minio"
        and "config" in data["file"]
    ):
        storage_client = MinioClient(**data["file"]['config'])
    data["file"]["client"] = storage_client
    

    docker_client = docker

    try:
        docker_client = Docker(**data["registry"]["config"])
    except Exception as e:
        pass

    data["registry"]["client"] = docker_client


    file_key = file_name
    tmp_folder =  tempfile.mkdtemp()
    tmp_file = os.path.join(tmp_folder, file_name)
    
    
    # if there is a dockerfile object in the data it must have a type and a config
    if "dockerfile" in data:
        if "type" not in data["dockerfile"]:
            await reply("Dockerfile type and config must be provided")            
        elif "bucket_name" not in data["dockerfile"] or "object_name" not in data["dockerfile"]:
            await reply("Bucket name must be provided to use minio for downloading dockerfile")
            del data["dockerfile"]
        elif data["dockerfile"]["type"] == "minio":
            if "config" in data["dockerfile"]:
                try:
                    data["dockerfile"]["client"] = MinioClient(**data["dockerfile"]["config"])
                except Exception as e:
                    await reply("Failed to create minio client")
                    return
            else :
                data["dockerfile"]["client"] = storage
        else:
            await reply("Invalid dockerfile type")
            del data["dockerfile"]
            return
    

    # ----------------------------- Validation 
    
    # TODO: check the file extension
    
    
    # Check if the file exists in storage
    try:
        if data["file"]["client"].has_object(bucket_name=bucket, object_name=file_name):
            logger.info("File found in S3")
        else:
            logger.error("File not found in S3")
            await reply("File not found in S3")
            return
    except Exception as e:
        logger.error("File not found in S3", e)
        await reply("File not found in S3")
        return
    
    
    
    # ----------------------------- Build the image
    
    # Download the file to temp folder
    try:
        data["file"]["client"].download_file(data["file"]["bucket"], file_key, tmp_file)
    except Exception as e:
        logger.error("Failed to download file from S3", e)
        await reply("Failed to download file from S3")
        return

    # Check if it is a tar file and extract it to the temp fol
    try:
        with tarfile.open(tmp_file) as tar:
            tar.extractall(path=tmp_folder)
    except Exception as e:
        logger.error("Failed to extract tar file", e)
        await reply(f"Failed to extract tar file")
        return


    # --- tmp
    # -------- file.tar.gz
    # -------- extraced/
    # ------------------ teamname/
    # -------------------------- start
    # -------------------------- Dockerfile
    # -------------------------- .dockerignore
    # -------------------------- other files
    # ------------------ --
    sub_folders = [name for name in os.listdir(tmp_folder) if os.path.isdir(os.path.join(tmp_folder, name))]
    if len(sub_folders) != 1:
        logger.error("There should be only one folder in the extracted folder")
        await reply("There should be only one folder in the extracted folder")
        return
    # check the teamname and the extracted folder name is the same
    extracted_folder_path = os.path.join(tmp_folder, sub_folders[0])
    extracted_folder_name = sub_folders[0]

    if extracted_folder_name != image_name:
        logger.error("Teamname and extracted folder name do not match")
        await reply("Teamname and extracted folder name do not match")
        return
    
    # Check if the required files exist in the extracted folder
    required_files = ["start"]  # Add more file names if needed
    not_found_files = []
    for file_name in required_files:
        file_path = os.path.join(extracted_folder_path, file_name)
        if not os.path.exists(file_path):
            not_found_files.append(file_name)
    if len(not_found_files) > 0:
        logger.error(f"Required files not found: {not_found_files}")
        await reply(f"Required files not found: {not_found_files}")
        return

    # Check if any Dockerfile type exists in the extracted folder 
    dockerfile_types = ["Dockerfile", "dockerfile", "Dockerfile.dev", "Dockerfile.prod" , ".dockerignore"]  # Add more Dockerfile types if needed
    dockerfile_found = False
    for dockerfile_type in dockerfile_types:
        dockerfile_path = os.path.join(extracted_folder_path, dockerfile_type)
        if os.path.isfile(dockerfile_path):
            dockerfile_found = True
            logger.info(f"{dockerfile_path} has been found")
            await reply(f"{dockerfile_type} has been found")
            try:
                os.remove(dockerfile_path)
                logger.info(f"{dockerfile_path} has been removed")
                await reply(f"{dockerfile_type} has been removed")
            except:
                logger.error(f"Failed to remove {dockerfile_path}")
                await reply(f"Failed to remove {dockerfile_type}")
                return
    
    if not dockerfile_found:
        logger.info("No Dockerfile found in the extracted folder")
        await reply("No Dockerfile found in the extracted folder")
    
    # Copy the dockerfile from s3 to the extracted folder or falback
    default_dockerfile_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "static", DEFAULT_TEAM_BUILD_DOCKERFILE
        )
    docker_filed_copied = False
    
    if "dockerfile" in data:
        try:
            await data["dockerfile"]['client'].download_file(
                data["dockerfile"]["bucket_name"], 
                data["dockerfile"]["object_name"], 
                os.path.join(extracted_folder_path, "Dockerfile")
            )
            docker_filed_copied = True
        except Exception as e:
            logger.error("Failed to download dockerfile from S3", e)
            await reply("Failed to download dockerfile from S3, using default Dockerfile")
    if not docker_filed_copied:
        try:
            shutil.copy(default_dockerfile_path, extracted_folder_path) # TODO: CHECK THIS
            docker_filed_copied = True
            logger.info(f"{default_dockerfile_path} has been copied in to the extracted folder")
            await reply(f"{dockerfile_type} has been copied in to the extracted folder")
        except:
            logger.info(f"Failed to copy {default_dockerfile_path} in the extracted folder")
            await reply(f"Failed to copy {default_dockerfile_path} in the extracted folder")
            return
    
    # #falback dockerfile process
    # if docker_filed_copied == False:
    #     config_docker_file_path = os.path.join(
    #         os.path.dirname(os.path.abspath(__file__)), "static", "team-build.Dockerfile"
    #     )
    #     dockerfile_path = os.path.join(extracted_folder_path, "team-build.Dockerfile")
    #     if not os.path.exists(dockerfile_path):
    #         # shutil.rmtree(tmp_folder)
    #         logger.info("Failed to find Dockerfile attempt to add docker file")
    #         await reply(f"Failed to find Dockerfile attempt to add docker file")
    #         shutil.copy(config_docker_file_path, tmp_folder)
    # TODO: TAINJA boodim

    
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
    await reply({"image_name": image_name, "image_tag": image_tag})
    return 
