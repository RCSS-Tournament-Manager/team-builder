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


logger = logging.getLogger("builder")

DEFAULT_TEAM_BUILD_DOCKERFILE = os.path.join(
    os.path.dirname(__file__), 
    "..", 
    "static", 
    "team-build.Dockerfile"
)



async def download_team_dockerfile_from_minio(
    bucket_name: str, 
    object_name: str, 
    client: MinioClient
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
        "file._type"
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
    
    if "registry" not in data:
        data["registry"] = {
            "_type": "docker",
            "_config": "default"
        }
    
    
    d, errors = initialize_clients(
        data,
        docker=docker,
        storage=storage,
        **kwargs
    )
    for error in errors:
        logger.error(error)
        await reply(error)

    tmp_folder = tempfile.mkdtemp()
    tmp_file = os.path.join(tmp_folder, file_name)

    
    team_dockerfile_path = DEFAULT_TEAM_BUILD_DOCKERFILE
    if "team_dockerfile" in d:
        if "bucket" not in d["team_dockerfile"] or \
            "file_id" not in d["team_dockerfile"]:
            logger.error("Invalid team_dockerfile object")
            await reply("Invalid team_dockerfile object")
            del d["dockerfile"]
        else:
            file_path , errors = await download_team_dockerfile_from_minio(
                bucket_name=d["team_dockerfile"]["bucket"],
                object_name=d["team_dockerfile"]["file_id"],
                client=d["team_dockerfile"]["_client"]
            )
            for error in errors:
                logger.error(error)
                await reply(error)
                
            if file_path != "":
                team_dockerfile_path = file_path
                
        
        
        

    # ----------------------------- Validation

    # Check if the file exists in storage
    try:
        if d["file"]["_client"].has_object(bucket_name=bucket, object_name=file_name):
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

    # The structure of the temp folder should be like this:
    # --- tmp
    # -------- file.tar.gz
    # -------- extraced/
    # ------------------ teamname/
    # -------------------------- start
    # -------------------------- Dockerfile
    # -------------------------- .dockerignore
    # -------------------------- other files
    # ------------------ --
    
    
    # Download the file to temp folder
    try:
        await d["file"]["_client"].download_file(
            d["file"]["bucket"], 
            file_name, 
            tmp_file
        )
        logger.info(f"Team File Download Successful { tmp_file }")

    except Exception as e:
        logger.error("Failed to download file from S3", e)
        await reply("Failed to download file from S3")
        return

    # Check if it is a tar file and extract it to the temp folder
    try:
        with tarfile.open(tmp_file) as tar:
            tar.extractall(path=tmp_folder)
        logger.info(f"Tar file extracted successfully to {tmp_folder}")

    except Exception as e:
        logger.error("Failed to extract tar file", e)
        await reply(f"Failed to extract tar file")
        return

    sub_folders = [
        name
        for name in os.listdir(tmp_folder)
        if os.path.isdir(os.path.join(tmp_folder, name))
    ]
    logger.info(f"Sub folders in the extracted folder: {sub_folders}")
    if len(sub_folders) != 1:
        logger.error("There should be only one folder in the extracted folder")
        await reply("There should be only one folder in the extracted folder")
        return
    
    # check the teamname and the extracted folder name is the same
    extracted_folder_path = os.path.join(tmp_folder, sub_folders[0])
    extracted_folder_name = sub_folders[0]

    if extracted_folder_name != team_name:
        logger.error(f"Teamname and extracted folder {extracted_folder_name} name do not match")
        await reply(f"Teamname and extracted folder {extracted_folder_name} name do not match")
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
    elif len(not_found_files) == 0:
        logger.info("All required teamfiles found")
        await reply("All required teamfiles found")
    # Check if any Dockerfile type exists in the extracted folder
    dockerfile_types = [
        "Dockerfile",
        ".dockerignore",
    ]  # Add more Dockerfile types if needed
    for dockerfile_type in dockerfile_types:
        dockerfile_path = os.path.join(extracted_folder_path, dockerfile_type)
        if os.path.isfile(dockerfile_path):
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
    
    # create a bin folder in the extracted folder

    bin_folder_path = os.path.join(extracted_folder_path, "bin")
    try:
        os.makedirs(bin_folder_path)
    except:
        logger.error(f"Failed to create bin folder in the extracted folder")
        await reply(f"Failed to create bin folder in the extracted folder")
        return
    # move all of the extracted folder to 'bin' folder, if failed replay the error
    for file_name in os.listdir(extracted_folder_path):
        file_path = os.path.join(extracted_folder_path, file_name)
        if os.path.isfile(file_path):
            try:
                shutil.move(file_path, bin_folder_path)
            except Exception as e:
                logger.error(f"Failed to move file {file_name} to bin folder", e)
                await reply(f"Failed to move file {file_name} to bin folder")
                return
    # replay the success message
    logger.info(f"Extracted folder has been moved to the bin folder")
    await reply(f"Extracted folder has been moved to the bin folder")



    # Copy the dockerfile from s3 to the extracted folder or falback
    try:
        new_dockerfile_path = os.path.join(
            extracted_folder_path,
            # team_name,
            "Dockerfile"
        )
        shutil.copy(
            team_dockerfile_path, 
            new_dockerfile_path
        )  # TODO: CHECK THIS
        logger.info(f"S3 Dockerfile has been copied in to the extracted folder")
        await reply(f"S3 Dockerfile has been copied in to the extracted folder")
    except Exception as e:
        logger.error(f"Failed to copy S3 Dockerfile in the extracted folder", e)
        await reply(f"Failed to copy S3 Dockerfile in the extracted folder")
        
    # falback to default dockerfile and copy it to the extracted folder
    if not os.path.exists(new_dockerfile_path):
        try:
            shutil.copy(
                DEFAULT_TEAM_BUILD_DOCKERFILE, 
                new_dockerfile_path
            )
            logger.info(f"Default Dockerfile has been copied in to the extracted folder")
            await reply(f"Default Dockerfile has been copied in to the extracted folder")
        except Exception as e:
            logger.error(f"Failed to copy Default Dockerfile in the extracted folder", e)
            await reply(f"Failed to copy Default Dockerfile in the extracted folder")
            return
    # -----------------------------
    # Build the image
    try:
        build_result = d['registry']['_client'].build_with_path(
            path=extracted_folder_path,
            image_name=image_name,
            image_tag=image_tag,
        )
        # Assuming env.docker_i.build_with_path returns a stream of build output
        for line in build_result:
            logger.info(line)
            await reply(line)
    except Exception as e:
        logger.error("Failed to build image", e)
        shutil.rmtree(tmp_folder)
        await reply("Failed to build image")
        return

    # Push the image to the registry
    try:
        push_result = d['registry']['_client'].push_to_registry(
            image_name=image_name,
            image_tag=image_tag,
        )
        # Assuming env.docker_i.push_to_registry returns a stream of push output
        for line in push_result:
            logger.info(line)
            await reply(line)
    except Exception as e:
        logger.error("Failed to push image to registry", e)
        shutil.rmtree(tmp_folder)
        await reply("Failed to push image to registry")
        return
    # remove the extracted folder after the image has been pushed
    try:
        shutil.rmtree(extracted_folder_path)
    except Exception as e:
        logger.error("Failed to remove the extracted folder", e)
        await reply("Failed to remove the extracted folder")
        return

    # replay the success message with the image name and tag
    logger.info(f"Image {image_name}:{image_tag} has been built and pushed successfully")
    await reply(f"Image {image_name}:{image_tag} has been built and pushed successfully")
    return
