import time
import asyncio
import multiprocessing

def log(worker, msg):
    print(f"+ {worker} - {msg}")

def normal_worker():
    log(1, "Worker 1 started")
    counter = 0
    while True:
        log(1, f"Working... {counter}")
        time.sleep(1)
        counter += 1

def worker_with_async(loop):
    log(2, "Worker 2 started")
    counter = 0
    while True:
        log(2, f"Working... {counter}")
        asyncio.run_coroutine_threadsafe(asyncio.sleep(1), loop)
        counter += 1

async def async_worker(queue):
    log(3, "Async Worker 3 started")
    await asyncio.sleep(2)
    result = "Result from async worker 3"
    queue.put(result)
    log(3, "Async Worker 3 finished")

def run_async_worker(queue):
    asyncio.run(async_worker(queue))

async def run():
    loop = asyncio.get_running_loop()

    # Create a queue for the new async worker to communicate its result back
    queue = multiprocessing.Queue()

    # Create processes for each worker
    worker1_process = multiprocessing.Process(target=normal_worker)
    # worker2_process = multiprocessing.Process(target=worker_with_async, args=(loop,))
    async_worker_process = multiprocessing.Process(target=run_async_worker, args=(queue,))

    # Start the worker processes
    worker1_process.start()
    # worker2_process.start()
    async_worker_process.start()

    # Let the workers run for some time
    await asyncio.sleep(5)
    log(0, "Terminating worker 1")
    
    # Terminate the first worker process
    worker1_process.terminate()
    
    # Let the remaining worker run for some more time
    await asyncio.sleep(5)
    
    # Terminate the second worker process
    # worker2_process.terminate()

    # Get the result from the async worker
    result = queue.get()
    log(0, f"Received from async worker 3: {result}")

    # Terminate the async worker process
    async_worker_process.terminate()