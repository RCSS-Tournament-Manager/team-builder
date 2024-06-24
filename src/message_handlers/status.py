import asyncio
from src.states import StateManager
from src.logger import get_logger

logger = get_logger(__name__)

subscribe_timeout = 10


async def status_command_handler(
    data: dict, state_manager: StateManager, reply, **kwargs
):
    jobs = state_manager.get_all_jobs()

    mode = data.get("mode", "subscribe")
    fetch = data.get("fetch", "all")

    if mode == "subscribe" and fetch == "all":
        # subscription time
        while True:
            jobs = state_manager.get_all_jobs()
            out = []
            counter = 0
            for build_id, job in jobs.items():
                out.append(
                    {
                        "build_id": build_id,
                        "status": job["status"],
                    }
                )
            try:
                await reply({"jobs": out})
                await asyncio.sleep(1)
                counter += 1
                if counter > subscribe_timeout:
                    break
            except:
                logger.info("Connection closed")
                break
    if mode == "fetch" and fetch == "all":
        out = []
        for build_id, job in jobs.items():
            out.append(
                {
                    "build_id": build_id,
                    "status": job["status"],
                }
            )

        await reply({"jobs": out})
        return

    # jobs is dict which key is build_id
    out = []
    for build_id, job in jobs.items():
        out.append(
            {
                "build_id": build_id,
                "status": job["status"],
            }
        )

    await reply({"jobs": out})
    return
