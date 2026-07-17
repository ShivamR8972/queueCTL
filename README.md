# QueueCTL - Background Job Queue System

A minimal, production-grade background job execution queue utilizing Python, Typer, and SQLite.

## Architecture & Choices
- **Persistence Layer**: SQLite was selected instead of a raw JSON text file to ensure clean, concurrency-safe row mutations using atomic `BEGIN IMMEDIATE` transaction locking structures across parallel threads or micro-processes.
- **Concurrency**: Handled via Python's standard `multiprocessing` package to isolate sub-execution runtime scopes.
- **Retry Logic**: Leverages exponential backoff strategies ($base^{attempts}$) before transferring unresolvable payloads directly into a Dead Letter Queue (DLQ).

## Setup & Local Installation
```bash
# Clone and open directory
cd queuectl

# Create and activate virtual environment
python -m venv .venv
.venv\Scripts\activate

# Install the required libraries
pip install -r requirements.txt

# Install the application locally in editable state
pip install -e .
