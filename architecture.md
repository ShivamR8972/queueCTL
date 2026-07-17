# QueueCTL - Background Job Queue System

A minimal, production-grade command-line interface (CLI) background job queue system built with Python, Typer, and SQLite. This system manages background execution tasks using independent worker processes, supports automated exponential backoff retries, provides a Dead Letter Queue (DLQ) for permanently failed executions, and guarantees persistent state across restarts.

---

## 1. Architectural Component Overview

The codebase is engineered with a strict separation of concerns across decoupled architectural layers:
              ┌──────────────────────┐
              │    CLI Layer (cli)   &emsp;&emsp;&emsp;&emsp;&emsp;&emsp;&emsp;&emsp;&ensp;&nbsp;│
              └──────────┬───────────┘
&emsp;&emsp;&emsp;&emsp;&emsp;&emsp;&emsp;&ensp;&nbsp;│
&emsp;&emsp;&emsp;&emsp;&emsp;&emsp;&emsp;&ensp; ▼
┌────────────────────────────────────────────────────────┐
│               Core Logic Layer (models) &emsp;&emsp;&emsp;&emsp;&emsp;&emsp;&emsp;&emsp;&ensp;&nbsp; &emsp;&emsp;&emsp;&emsp;&emsp;&emsp;&emsp;&emsp;&ensp;&nbsp; &emsp;&emsp;&emsp;&emsp;&emsp;&emsp;&emsp;&emsp;&ensp;&nbsp;&ensp;             │
├────────────────────────────┬───────────────────────────┤
│   Worker Engine (worker)  &emsp;&emsp;&emsp;&emsp;&emsp;&emsp;&emsp;&emsp;&nbsp; │   Config Engine (config)  &emsp;&emsp;&emsp;&emsp;&emsp;&emsp;&emsp;&emsp;&ensp;&nbsp;│
└────────────────────────────┴───────────────────────────┘
&emsp;&emsp;&emsp;&emsp;&emsp;&emsp;&emsp;&ensp;&nbsp;│
&emsp;&emsp;&emsp;&emsp;&emsp;&emsp;&emsp;&ensp;&nbsp;▼
               ┌──────────────────────┐
               │ Persistence Layer    &emsp;&emsp;&emsp;&emsp;&emsp;&emsp;&emsp;&ensp;│
               │    (database.py)     &emsp;&emsp;&emsp;&emsp;&emsp;&emsp;&emsp;&emsp;&emsp;&nbsp;│
               └──────────────────────┘

1. **CLI Layer (`cli.py`, `main.py`)**: Built with Typer. It handles user inputs, argument parsing, command formatting, and visual shell outputs.
2. **Core Logic Layer (`models.py`)**: Contains the data access object (DAO) functions. It encapsulates all direct transactional state mutations on jobs.
3. **Worker Engine (`worker.py`)**: Coordinates the multi-process processing pool, subprocess command execution, graceful signal handling (`SIGINT`/`SIGTERM`), and retry backoff mechanics.
4. **Configuration Engine (`config.py`)**: Manages dynamic, user-configurable variables (like fallback retry metrics and backoff bases) inside the database.
5. **Persistence Layer (`database.py`)**: Manages the embedded SQLite file lifecycle, schema creation, and raw database connections.

---

## 2. Job Lifecycle & State Machine

Every job transitions through a well-defined state machine to prevent race conditions and ensure reliability:

[ Enqueue ] ──> pending ───(Leased by Worker)───> processing
&emsp;&emsp;&emsp;&emsp;&emsp;&emsp;&emsp;&emsp;&emsp;▲ &emsp;&emsp;&emsp;&emsp;&emsp;&emsp;&emsp;&emsp;&emsp;&emsp;&emsp;&emsp;&emsp;&emsp;&emsp;&emsp;│
&emsp;&emsp;&emsp;&emsp;&emsp;&emsp;&emsp;&emsp;&emsp;│&emsp;&emsp;&emsp;&emsp;&emsp;&emsp;&emsp;&emsp;&emsp;               &emsp;&emsp;&emsp;&emsp;&emsp;&emsp;&emsp;                   ├───> [ Success ] ──> completed
&emsp;&emsp;&emsp;&emsp;&emsp;&emsp;&emsp;&emsp;&emsp;└───(Fail: Attempts <= Max)─────┤
&emsp;&emsp;&emsp;&emsp;&emsp;&emsp;&emsp;&emsp;&emsp;└───> [ Fail: Max Exhausted ] ──> dead (DLQ)

* **`pending`**: The job is waiting inside the storage array to be allocated to an open process node. Retried tasks return to this state with a delayed timestamp lock.
* **`processing`**: The task has been securely leased and locked by a single distinct worker thread/process.
* **`completed`**: The internal sub-process executed perfectly, returning an exit code of `0`[cite: 1]. This is a terminal state[cite: 1].
* **`failed`**: The shell command returned a non-zero exit code or breached runtime deadlines[cite: 1]. If its total runtime counter is within `max_retries`, it reverts to `pending`[cite: 1].
* **`dead`**: The execution has exhausted all configured retries[cite: 1]. It is permanently directed to the Dead Letter Queue (DLQ) for engineering analysis[cite: 1].

---

## 3. Concurrency & Data Resilience Model

### SQLite Row-Level Locking
To scale worker processes across multi-core systems without overlapping task execution, the core layer utilizes a single-step selection block enclosed within a `BEGIN IMMEDIATE` transaction:

```sql
-- Transaction initialized with immediate write-intent locking
SELECT * FROM jobs 
WHERE state = 'pending' AND run_at <= CURRENT_TIMESTAMP 
LIMIT 1;

-- If a record matches, it is locked inside the same execution block:
UPDATE jobs 
SET state = 'processing', updated_at = CURRENT_TIMESTAMP 
WHERE id = ?;
```

The immediate lock blocks subsequent parallel write attempts during the short execution split-second. Concurrent instances encountering the lock safely drop back into a brief sleep rotation, preventing race conditions or duplicate delivery anomalies.

### Multi-Processing and Signal Interception

Instead of running a single process loop susceptible to structural CPU blocks, the daemon implements independent worker processes via Python’s multiprocessing library. The architecture captures termination signals (SIGINT or SIGTERM) globally:

1. Interception flips an internal shared synchronization variable (shutdown_flag).
2. Processing processes complete the immediate lifecycle task currently running inside their sub-shell.
3. The process gracefully exits instead of claiming another job from the database index.

### Retry and Exponential Backoff Formula

Failed executions generate an incremental execution backoff wait period calculated against the failure check value using the following exponential rule:
$$\text{delay} = \text{base}^{\text{attempts}}$$

The tasks database entry sets its scheduler activation variable (run_at) to match the computed delay offset, forcing the query parser to bypass the job entry until the system time moves past the threshold.
