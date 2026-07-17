import typer
import json
from database import get_db, init_db
import models
import worker
import config
from typing import Annotated

app = typer.Typer(help="QueueCTL: A production-grade background job queue CLI.")

@app.command()
def enqueue(payload: str = typer.Argument(..., help="JSON payload string, e.g. '{\"id\":\"job1\", \"command\":\"echo hello\"}'")):
    """Add a new job to the background queue."""
    try:
        data = json.loads(payload)
        cmd = data.get("command")
        if not cmd:
            typer.echo("Error: 'command' field is required in payload.")
            raise typer.Exit(code=1)
        
        # Read fallback configuration globally if not specified in the payload
        default_retries = int(config.get_config("max-retries", "3"))
        max_retries = data.get("max_retries", default_retries)
        
        job_id = models.enqueue_job(data.get("id"), cmd, max_retries)
        typer.echo(f"Job '{job_id}' enqueued successfully.")
    except json.JSONDecodeError:
        typer.echo("Error: Invalid JSON string provided.")

# Create a new subcommand group for workers
worker_app = typer.Typer(help="Manage lifecycle of processing workers.")
app.add_typer(worker_app, name="worker")



from typing import Annotated

@worker_app.command(name="start")
def worker_start(
    count: Annotated[int, typer.Option("--count", "-c", help="Number of concurrent workers.")] = 1
):
    """Start one or more workers to process background jobs."""
    worker.start_workers(count)

@worker_app.command(name="stop")
def worker_stop():
    """Stop running workers gracefully."""
    # Since worker.py processes internally using multiprocessing,
    # signaling via Ctrl+C handles individual process lifetimes cleanly.
    typer.echo("To stop workers gracefully, press Ctrl+C in the active worker terminal window.")

@app.command()
def status():
    """Show operational summary of all jobs and structural counts."""
    with get_db() as conn:
        cursor = conn.execute("SELECT state, COUNT(*) as cnt FROM jobs GROUP BY state")
        summary = {row["state"]: row["cnt"] for row in cursor.fetchall()}
    
    typer.echo("--- System Status Summary ---")
    for state in ["pending", "processing", "completed", "failed", "dead"]:
        typer.echo(f"{state.capitalize()}: {summary.get(state, 0)}")

@app.command(name="list-state")
def list_state(state: str):
    """List jobs filtered strictly by their lifecycle state."""
    with get_db() as conn:
        cursor = conn.execute("SELECT id, command, state, attempts FROM jobs WHERE state = ?", (state.lower(),))
        rows = cursor.fetchall()
        
    if not rows:
        typer.echo(f"No jobs found matching state '{state}'.")
        return
        
    for row in rows:
        typer.echo(f"[{row['id']}] Cmd: '{row['command']}' | Attempts: {row['attempts']}")

@app.command()
def dlq(action: str = typer.Argument(..., help="'list' or 'retry'"), job_id: str = typer.Argument(None, help="Job ID required if action is 'retry'")):
    """View or retry dead letters within the Dead Letter Queue."""
    if action == "list":
        list_state("dead")
    elif action == "retry":
        if not job_id:
            typer.echo("Error: Must provide a job_id to retry.")
            return
        with get_db() as conn:
            cursor = conn.execute("SELECT * FROM jobs WHERE id = ? AND state = 'dead'", (job_id,))
            if not cursor.fetchone():
                typer.echo(f"Job '{job_id}' not found in DLQ.")
                return
        models.update_job_status(job_id, "pending", attempts=0)
        typer.echo(f"Job '{job_id}' reset and returned to pending queue.")

@app.command(name="config")
def set_configuration(action: str = typer.Argument(..., help="'set'"), key: str = typer.Argument(...), value: str = typer.Argument(...)):
    """Manage dynamic fallback system configurations."""
    if action == "set":
        config.set_config(key, value)
        typer.echo(f"Config update: {key} updated to {value}")