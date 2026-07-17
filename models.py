import uuid
from datetime import datetime, timedelta
from database import get_db

def enqueue_job(job_id: str, command: str, max_retries: int):
    if not job_id:
        job_id = str(uuid.uuid4())[:8]
    
    now = datetime.utcnow().isoformat()
    with get_db() as conn:
        conn.execute(
            """INSERT INTO jobs (id, command, state, attempts, max_retries, created_at, updated_at)
               VALUES (?, ?, 'pending', 0, ?, ?, ?)""",
            (job_id, command, max_retries, now, now)
        )
        conn.commit()
    return job_id

def lease_next_job():
    """Atomically finds and locks a pending job for processing."""
    conn = get_db()
    try:
        conn.execute("BEGIN IMMEDIATE")
        now = datetime.utcnow().isoformat()
        
        # Find a job that is pending and due to run (handles delayed retries)
        cursor = conn.execute(
            "SELECT * FROM jobs WHERE state = 'pending' AND run_at <= ? LIMIT 1",
            (now,)
        )
        job = cursor.fetchone()
        
        if job:
            conn.execute(
                "UPDATE jobs SET state = 'processing', updated_at = ? WHERE id = ?",
                (now, job["id"])
            )
            conn.commit()
            return dict(job)
        
        conn.commit()
        return None
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def update_job_status(job_id: str, state: str, attempts: int = None, next_run_in_sec: int = 0):
    now = datetime.utcnow()
    run_at = now + timedelta(seconds=next_run_in_sec)
    
    with get_db() as conn:
        if attempts is not None:
            conn.execute(
                "UPDATE jobs SET state = ?, attempts = ?, run_at = ?, updated_at = ? WHERE id = ?",
                (state, attempts, run_at.isoformat(), now.isoformat(), job_id)
            )
        else:
            conn.execute(
                "UPDATE jobs SET state = ?, updated_at = ? WHERE id = ?",
                (state, now.isoformat(), job_id)
            )
        conn.commit()