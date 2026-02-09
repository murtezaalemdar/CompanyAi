ALTER TABLE conversation_memory ADD COLUMN IF NOT EXISTS session_id INTEGER REFERENCES chat_sessions(id);
CREATE INDEX IF NOT EXISTS idx_conversation_memory_session_id ON conversation_memory(session_id);
