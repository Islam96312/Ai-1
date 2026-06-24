#!/usr/bin/env python
"""
Database Initializer
Run once before starting the system:
    python database/init_db.py

Creates all tables defined in database/schemas.py.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from database.schemas import Base
from config.settings import settings


def init_database():
    print(f'Connecting to: {settings.DATABASE_URL.replace(settings.DB_PASSWORD, "***")}')
    engine = create_engine(settings.DATABASE_URL)

    # Test connection
    try:
        with engine.connect() as conn:
            conn.execute(text('SELECT 1'))
        print('✅ Connection OK')
    except Exception as e:
        print(f'❌ Connection FAILED: {e}')
        sys.exit(1)

    # Create all tables
    print('Creating tables...')
    Base.metadata.create_all(bind=engine)
    print('✅ All tables created successfully')

    # List created tables
    from sqlalchemy import inspect
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    print(f'\nTables in database ({len(tables)}):')
    for t in sorted(tables):
        cols = [c['name'] for c in inspector.get_columns(t)]
        print(f'  ├─ {t} ({len(cols)} columns)')

    print('\n✨ Database initialization complete!')
    print('Next step: python scripts/start_system.py')


if __name__ == '__main__':
    init_database()
