"""
Utility: create DB tables for SupportBot object/ticket models.
Run this locally during development if you don't want to start the API.
"""
from app.database import init_db

if __name__ == "__main__":
    init_db()
    print("Database tables created (or already exist).")
