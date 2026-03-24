"""
Migration script to add 2FA fields to the users table.
Run this once after updating the User model to add 2FA support.

Usage:
    python scripts/migrate_2fa.py
"""
import sys
import os

# Add the parent directory to the path so we can import app modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.database import engine


def migrate():
    """Add 2FA columns to the users table if they don't exist."""
    columns_to_add = [
        ("twofa_code", "VARCHAR(6)"),
        ("twofa_code_expires", "DATETIME"),
        ("twofa_pending_action", "VARCHAR(20)"),
    ]

    with engine.connect() as conn:
        # Check existing columns
        result = conn.execute(text("PRAGMA table_info(users)"))
        existing_columns = {row[1] for row in result.fetchall()}

        for column_name, column_type in columns_to_add:
            if column_name not in existing_columns:
                print(f"Adding column: {column_name}")
                conn.execute(text(f"ALTER TABLE users ADD COLUMN {column_name} {column_type}"))
                conn.commit()
                print(f"Successfully added column: {column_name}")
            else:
                print(f"Column already exists: {column_name}")

    print("\nMigration complete!")


if __name__ == "__main__":
    migrate()
