from sqlalchemy import text
from app.db.database import Base, engine
import app.db.models


def init_db():
    Base.metadata.create_all(bind=engine)

    # Perform lightweight automatic schema migrations for newly added columns
    with engine.connect() as conn:
        # Check and add username column to users if missing
        conn.execute(text("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name='users' AND column_name='username'
                ) THEN
                    ALTER TABLE users ADD COLUMN username VARCHAR(100);
                    -- Set fallback username for existing records
                    UPDATE users SET username = CONCAT('user_', id) WHERE username IS NULL;
                    ALTER TABLE users ALTER COLUMN username SET NOT NULL;
                    CREATE UNIQUE INDEX IF NOT EXISTS ix_users_username ON users (username);
                END IF;

                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name='users' AND column_name='password_hash'
                ) THEN
                    ALTER TABLE users ADD COLUMN password_hash VARCHAR(255) DEFAULT '' NOT NULL;
                END IF;

                -- Make openai_api_key_encrypted nullable if it was NOT NULL
                ALTER TABLE users ALTER COLUMN openai_api_key_encrypted DROP NOT NULL;

                -- Check and add visibility column to answer_sets if missing
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name='answer_sets' AND column_name='visibility'
                ) THEN
                    ALTER TABLE answer_sets ADD COLUMN visibility VARCHAR(20) DEFAULT 'private' NOT NULL;
                END IF;

                -- Check and add pdf_url column to answer_sets if missing
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name='answer_sets' AND column_name='pdf_url'
                ) THEN
                    ALTER TABLE answer_sets ADD COLUMN pdf_url VARCHAR;
                END IF;
            END $$;
        """))
        conn.commit()