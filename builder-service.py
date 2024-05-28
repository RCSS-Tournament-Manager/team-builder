import logging
from src.docker import Docker
from src import env
from fastapi import FastAPI
import uvicorn
from src.routes import builder
from src.logger import init_logger
init_logger()


logger = logging.getLogger("runner")

# --- Global Instances

app = FastAPI(
    title="Image Builder Service",
    version="0.1.0"
)

app.include_router(builder.router)


@app.get("/health-check")
def get_item():
    return {"status": "OK"}


if __name__ == "__main__":
    try:
        env.docker_i = Docker(
            default_registry=env.DOCKER_REGISTRY
        )
        logger.info("Docker connected")
    except Exception as e:
        logger.error("Docker connection failed")
        logger.error(e)
        exit(1)
    
    uvicorn.run(
        app,
        host=env.HOST,
        port=env.PORT
    )
