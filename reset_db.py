import os
from app.db.database import engine, Base
import app.db.models  # Import models to ensure all tables are registered with Base.metadata
from sqlalchemy import inspect

def reset_database():
    print("[1/3] Dropping all existing database tables...")
    Base.metadata.drop_all(bind=engine)
    print("[1/3] All tables dropped successfully.\n")

    print("[2/3] Creating new tables with updated schema...")
    Base.metadata.create_all(bind=engine)
    print("[2/3] All tables created successfully.\n")

    print("[3/3] Verifying synced schema:")
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    print(f"Tables in DB: {tables}\n")

    for table in tables:
        cols = inspector.get_columns(table)
        print(f"=== Table: {table} ===")
        for c in cols:
            nullable = "NULL" if c["nullable"] else "NOT NULL"
            print(f"  - {c['name']:32s} {str(c['type']):20s} {nullable}")
        print()

if __name__ == "__main__":
    reset_database()
