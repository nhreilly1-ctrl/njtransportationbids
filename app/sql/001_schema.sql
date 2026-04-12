CREATE TABLE IF NOT EXISTS registry_sources (
    id SERIAL PRIMARY KEY,
    source_id TEXT UNIQUE NOT NULL,
    source_name TEXT NOT NULL,
    entity_type TEXT,
    county TEXT,
    source_url TEXT,
    priority_tier TEXT,
    website_ready TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
