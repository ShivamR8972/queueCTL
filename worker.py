import os
import time
import signal
import subprocess
import multiprocessing
from datetime import datetime
from models import lease_next_job, update_job_status
from config import get_config

shutdown_flag = multiprocessing.Event()

def signal_handler(signum, frame):
    shutdown_flag.set()

def run_worker_loop(worker_id: int):
    # Setup graceful termination signals inside the child process
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    while not shutdown_flag.is_set():
        job = lease_next_job()
        if not job:
            time.sleep(1)
            continue
            
        print(f"[Worker-{worker_id}] Processing job {job['id']}: '{job['command']}'")
        
        try:
            # Execute systemic command safely via subprocess
            result = subprocess.run(
                job["command"], shell=True, capture_output=True, text=True, timeout=30
            )
            
            if result.returncode == 0:
                update_job_status(job["id"], "completed")
                print(f"[Worker-{worker_id}] Job {job['id']} completed successfully.")
            else:
                handle_failure(job)
        except subprocess.TimeoutExpired:
            print(f"[Worker-{worker_id}] Job {job['id']} timed out.")
            handle_failure(job)
        except Exception:
            handle_failure(job)

def handle_failure(job: dict):
    new_attempts = job["attempts"] + 1
    max_retries = job["max_retries"]
    
    if new_attempts > max_retries:
        update_job_status(job["id"], "dead", attempts=new_attempts)
        print(f"Job {job['id']} failed permanently. Moved to DLQ.")
    else:
        # Exponential backoff calculation: base^attempts
        backoff_base = int(get_config("backoff_base", 2))
        delay = backoff_base ** new_attempts
        update_job_status(job["id"], "pending", attempts=new_attempts, next_run_in_sec=delay)
        print(f"Job {job['id']} failed. Retrying attempt {new_attempts}/{max_retries} in {delay}s.")

def start_workers(count: int):
    print(f"Starting {count} workers smoothly... Press Ctrl+C to shut down.")
    processes = []
    for i in range(count):
        p = multiprocessing.Process(target=run_worker_loop, args=(i+1,))
        p.start()
        processes.append(p)
        
    try:
        for p in processes:
            p.join()
    except KeyboardInterrupt:
        print("\nInitiating graceful shutdown. Waiting for workers to finish current jobs...")
        shutdown_flag.set()
        for p in processes:
            p.join()
    print("All workers stopped clean.")