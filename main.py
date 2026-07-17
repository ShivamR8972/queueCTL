from cli import app
from database import init_db

if __name__ == "__main__":
    init_db()  # Run simple migrations before execution starts
    app()