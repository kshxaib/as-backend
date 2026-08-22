from app.db.database import engine
from sqlalchemy import inspect

inspector = inspect(engine)
tables = inspector.get_table_names()
print(f'Tables found: {tables}\n')

for table in tables:
    cols = inspector.get_columns(table)
    print(f'=== {table} ===')
    for c in cols:
        nullable = 'NULL' if c['nullable'] else 'NOT NULL'
        default = f" DEFAULT={c.get('default','')}" if c.get('default') else ''
        print(f"  {c['name']:35s} {str(c['type']):20s} {nullable}{default}")
    print()
