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

                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name='users' AND column_name='openai_api_key_encrypted'
                ) THEN
                    ALTER TABLE users ADD COLUMN openai_api_key_encrypted VARCHAR;
                END IF;

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

                -- QuestionBanks: add visibility
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name='question_banks' AND column_name='visibility'
                ) THEN
                    ALTER TABLE question_banks ADD COLUMN visibility VARCHAR(20) DEFAULT 'private' NOT NULL;
                END IF;

                -- Questions: add repeat_count
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name='questions' AND column_name='repeat_count'
                ) THEN
                    ALTER TABLE questions ADD COLUMN repeat_count INTEGER DEFAULT 1 NOT NULL;
                END IF;

                -- Questions: add years_appeared
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name='questions' AND column_name='years_appeared'
                ) THEN
                    ALTER TABLE questions ADD COLUMN years_appeared VARCHAR;
                END IF;

                -- Answers: add repeat_count
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name='answers' AND column_name='repeat_count'
                ) THEN
                    ALTER TABLE answers ADD COLUMN repeat_count INTEGER DEFAULT 1 NOT NULL;
                END IF;

                -- Answers: add years_appeared
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name='answers' AND column_name='years_appeared'
                ) THEN
                    ALTER TABLE answers ADD COLUMN years_appeared VARCHAR;
                END IF;
                -- QuestionBanks: drop unique index on cloudinary_public_id to allow JSON arrays
                DROP INDEX IF EXISTS ix_question_banks_cloudinary_public_id;
                ALTER TABLE question_banks DROP CONSTRAINT IF EXISTS question_banks_cloudinary_public_id_key;

                -- QuestionBanks: add files_meta
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name='question_banks' AND column_name='files_meta'
                ) THEN
                    ALTER TABLE question_banks ADD COLUMN files_meta TEXT;
                END IF;

                -- SharedPredictedPapers: add visibility
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name='shared_predicted_papers' AND column_name='visibility'
                ) THEN
                    ALTER TABLE shared_predicted_papers ADD COLUMN visibility VARCHAR(20) DEFAULT 'private' NOT NULL;
                END IF;
            END $$;
        """))
        conn.commit()