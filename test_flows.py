import time
import subprocess
import json
import sqlite3

def run_cmd(args):
    result = subprocess.run(["queuectl"] + args, capture_output=True, text=True)
    return result.stdout.strip()

print("1. Cleaning up past database execution...")
subprocess.run(["rm", "queuectl.db"], errors="ignore") # Use 'del queuectl.db' if purely testing on CMD/Windows

print("\n2. Initializing System Config...")
run_cmd(["config", "set", "max-retries", "2"])
run_cmd(["config", "set", "backoff_base", "2"])

print("\n3. Enqueuing test jobs...")
# Job 1: Basic successful execution
run_cmd(["enqueue", '{"id": "job-success", "command": "echo Success!"}'])
# Job 2: Fails cleanly to test backoff and DLQ routing
run_cmd(["enqueue", '{"id": "job-fail", "command": "exit 1"}'])
# Job 3: A slow task to demonstrate worker parallelism
run_cmd(["enqueue", '{"id": "job-slow", "command": "ping 127.0.0.1 -n 3 > nul"}'])

print("\n4. Current Queue Summary Status before workers start:")
print(run_cmd(["status"]))

print("\n5. Testing complete. Spin up your workers using:")
print("   queuectl worker start --count=3")
print("   Then run 'queuectl status' or 'queuectl dlq list' to observe results.")