import os
import subprocess
import json
import time

def run_cmd(args):
    """Helper function to execute queuectl commands and return stdout."""
    result = subprocess.run(["queuectl"] + args, capture_output=True, text=True)
    return result.stdout.strip()

def main():
    print("=== STARTING QUEUECTL INTEGRATION TEST ===")

    # 1. Clean up past database execution safely using native OS APIs
    db_filename = "queuectl.db"
    print("\n1. Cleaning up past database execution...")
    if os.path.exists(db_filename):
        try:
            os.remove(db_filename)
            print(f"   Successfully removed existing database: {db_filename}")
        except PermissionError:
            print(f"   Warning: Could not delete {db_filename}. It may be locked by a running worker.")
    else:
        print("   No existing database found. Starting fresh.")

    # 2. Initialize Fallback System Configurations
    print("\n2. Initializing System Config...")
    cfg_retries = run_cmd(["config", "set", "max-retries", "2"])
    print(f"   {cfg_retries}")
    cfg_backoff = run_cmd(["config", "set", "backoff_base", "2"])
    print(f"   {cfg_backoff}")

    # 3. Enqueue Controlled Test Scenarios
    print("\n3. Enqueuing test jobs...")
    
    # Scenario A: Basic job designed to complete successfully
    job_success = {"id": "job-success", "command": "echo Execution Successful"}
    res_success = run_cmd(["enqueue", json.dumps(job_success)])
    print(f"   {res_success}")

    # Scenario B: Invalid command designed to fail, trigger backoff, and enter DLQ
    job_fail = {"id": "job-fail", "command": "exit 1"}
    res_fail = run_cmd(["enqueue", json.dumps(job_fail)])
    print(f"   {res_fail}")

    # Scenario C: A slow process to demonstrate concurrent multi-worker execution
    # Using a cross-platform approach or standard Windows timeout ping
    slow_cmd = "ping 127.0.0.1 -n 4 > nul" if os.name == "nt" else "sleep 3"
    job_slow = {"id": "job-slow", "command": slow_cmd}
    res_slow = run_cmd(["enqueue", json.dumps(job_slow)])
    print(f"   {res_slow}")

    # 4. Verify Current Queue Summary Status
    print("\n4. Verifying Pending Queue State Summary:")
    status_summary = run_cmd(["status"])
    print(status_summary)

    print("\n========================================================")
    print("Verification Setup Complete! The engine is ready for processing.")
    print("Next Steps to execute the lifecycle loop:")
    print("1. Launch your workers in this directory: queuectl worker start --count=3")
    print("2. Run 'queuectl status' or 'queuectl dlq list' in another terminal to watch the results.")
    print("========================================================")

if __name__ == "__main__":
    main()