import os
from playhouse.db_url import connect

# Default to SQLite
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///test.db")

# Initialize the database connection
db = connect(DATABASE_URL)

def get_db():
    return db
