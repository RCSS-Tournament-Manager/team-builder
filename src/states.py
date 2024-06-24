import logging
import asyncio

logger = logging.getLogger("state")


class StateManager:
    run_jobs = None

    build_states = [
        "started",
        "progress",
        "finished",
        "killed",
        "failed",
    ]

    def __init__(self):
        self.run_jobs = {}

    def add_run_job(self, build_id, task, data):
        """Add a run job to the state

        Args:
            build_id (str): ID of the build
            task (str): Task to be run
            data (dict): Additional data related to the job
        """
        self.run_jobs[build_id] = {
            "task": task,
            "status": "started",
            "data": data,
            "states": [],
            "events": {},
            "hooks": {state: [] for state in self.build_states}
        }
        for state in self.build_states:
            event = asyncio.Event()
            self.run_jobs[build_id]["events"][state] = event
        logger.info(f"Added run job for build_id: {build_id}")

    async def kill_run_job(self, build_id):
        """Kill a running job

        Args:
            build_id (str): ID of the build to kill
        """
        if build_id in self.run_jobs:
            self.run_jobs[build_id]["status"] = "killed"
            self.run_jobs[build_id]["states"].append("killed")
            self.run_jobs[build_id]["events"]["killed"].set()
            await self._execute_hooks(build_id, "killed")
            logger.info(f"Killed run job for build_id: {build_id}")
            await self.run_jobs[build_id].task.cancel()
        else:
            logger.error(f"Run job for build_id: {build_id} not found")

    def get_run_jobs_state(self, build_id):
        """Get the state of a running job

        Args:
            build_id (str): ID of the build to get the state for
        
        Returns:
            dict: State of the run job if found, else None
        """
        if build_id in self.run_jobs:
            return self.run_jobs[build_id]
        else:
            logger.error(f"Run job for build_id: {build_id} not found")
            return None

    def get_event(self, build_id, state):
        """Get the event of a specific state for a run build

        Args:
            build_id (str): ID of the build
            state (str): State to get the event for

        Returns:
            asyncio.Event: Event associated with the state if found, else None
        """
        if build_id in self.run_jobs and state in self.run_jobs[build_id]["events"]:
            return self.run_jobs[build_id]["events"][state]
        else:
            logger.error(f"Event for state: {state} in build_id: {build_id} not found")
            return None
        
    async def update_state(self, build_id, new_state):
        """Update the state of a run job

        Args:
            build_id (str): ID of the build
            new_state (str): New state to update to

        Returns:
            bool: True if state updated successfully, else False
        """
        if build_id in self.run_jobs and new_state in self.build_states:
            self.run_jobs[build_id]["status"] = new_state
            self.run_jobs[build_id]["states"].append(new_state)
            self.run_jobs[build_id]["events"][new_state].set()
            await self._execute_hooks(build_id, new_state)
            logger.info(f"Updated state to {new_state} for build_id: {build_id}")
            return True
        else:
            logger.error(f"Failed to update state to {new_state} for build_id: {build_id}")
            return False

    def register_hook(self, build_id, state, hook_fn):
        """Register a hook for a specific state of a run job

        Args:
            build_id (str): ID of the build
            state (str): State to register the hook for
            hook_fn (callable): Function to call when the state is reached
        """
        if build_id in self.run_jobs and state in self.run_jobs[build_id]["hooks"]:
            self.run_jobs[build_id]["hooks"][state].append(hook_fn)
            logger.info(f"Registered hook for state: {state} for build_id: {build_id}")
        else:
            logger.error(f"State: {state} or build_id: {build_id} not found for hook registration")

    async def _execute_hooks(self, build_id, state):
        """Execute hooks for a specific state of a run job

        Args:
            build_id (str): ID of the build
            state (str): State to execute hooks for
        """
        if build_id in self.run_jobs and state in self.run_jobs[build_id]["hooks"]:
            for hook_fn in self.run_jobs[build_id]["hooks"][state]:
                if asyncio.iscoroutinefunction(hook_fn):
                    await hook_fn(build_id)
                else:
                    hook_fn(build_id)
            logger.info(f"Executed hooks for state: {state} for build_id: {build_id}")
        else:
            logger.error(f"State: {state} or build_id: {build_id} not found for hook execution")
            
    def get_all_jobs(self):
        return self.run_jobs