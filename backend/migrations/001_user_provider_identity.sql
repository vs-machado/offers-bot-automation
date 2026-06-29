ALTER TABLE users ALTER COLUMN hashed_password DROP NOT NULL;
ALTER TABLE users ADD COLUMN IF NOT EXISTS auth_provider VARCHAR(50) DEFAULT 'credentials' NOT NULL;
ALTER TABLE users ADD COLUMN IF NOT EXISTS provider_account_id VARCHAR(255);
CREATE INDEX IF NOT EXISTS ix_users_provider_account_id ON users (provider_account_id);
