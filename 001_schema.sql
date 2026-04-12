CREATE TABLE IF NOT EXISTS registry_sources (
    source_id VARCHAR(80) PRIMARY KEY,
    source_level VARCHAR(32) NOT NULL,
    entity_type VARCHAR(64) NOT NULL,
    source_name VARCHAR(255) NOT NULL,
    county VARCHAR(128),
    municipality VARCHAR(128),
    region VARCHAR(64) NOT NULL,
    coverage_scope VARCHAR(255),
    priority_tier VARCHAR(32),
    priority_rank INTEGER,
    rank_area VARCHAR(64),
    statewide_dos_directory TEXT,
    direct_legal_notice_url TEXT,
    effective_notice_entry_url TEXT NOT NULL,
    primary_procurement_url TEXT NOT NULL,
    verification_url_county_url TEXT,
    portal_type VARCHAR(128),
    crawl_entry TEXT NOT NULL,
    verification_status VARCHAR(64) NOT NULL DEFAULT 'Unknown',
    source_status VARCHAR(32) NOT NULL DEFAULT 'Pinned',
    refresh_cadence VARCHAR(32) NOT NULL DEFAULT 'Weekly',
    website_ready VARCHAR(16) NOT NULL DEFAULT 'Yes',
    import_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    parser_hint VARCHAR(64) NOT NULL DEFAULT 'Manual review',
    use_for TEXT,
    notes TEXT,
    last_crawled_at TIMESTAMPTZ,
    next_crawl_at TIMESTAMPTZ,
    source_sheet VARCHAR(64),
    source_row_number INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS crawl_runs (
    crawl_run_id SERIAL PRIMARY KEY,
    source_id VARCHAR(80) NOT NULL REFERENCES registry_sources(source_id) ON DELETE CASCADE,
    crawl_stage VARCHAR(32) NOT NULL DEFAULT 'notice_discovery',
    trigger_type VARCHAR(32) NOT NULL DEFAULT 'scheduled',
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    status VARCHAR(32) NOT NULL,
    http_status INTEGER,
    records_found INTEGER NOT NULL DEFAULT 0,
    records_promoted INTEGER NOT NULL DEFAULT 0,
    parser_used VARCHAR(64),
    source_url_checked TEXT,
    error_message TEXT,
    checksum_snapshot TEXT
);

CREATE TABLE IF NOT EXISTS opportunity_leads (
    lead_id SERIAL PRIMARY KEY,
    source_id VARCHAR(80) NOT NULL REFERENCES registry_sources(source_id) ON DELETE CASCADE,
    crawl_run_id INTEGER REFERENCES crawl_runs(crawl_run_id) ON DELETE SET NULL,
    owner_name VARCHAR(255),
    owner_type VARCHAR(64),
    county VARCHAR(128),
    municipality VARCHAR(128),
    region VARCHAR(64),
    notice_title TEXT NOT NULL,
    category VARCHAR(128),
    project_type VARCHAR(128),
    notice_url TEXT NOT NULL,
    official_url TEXT,
    portal_url TEXT,
    posted_at TIMESTAMPTZ,
    due_at TIMESTAMPTZ,
    estimate_range VARCHAR(128),
    official_status VARCHAR(64),
    raw_text TEXT,
    transport_score INTEGER NOT NULL DEFAULT 0,
    confidence_score INTEGER NOT NULL DEFAULT 0,
    verification_status VARCHAR(64) NOT NULL DEFAULT 'Unknown',
    promotion_decision VARCHAR(16) NOT NULL DEFAULT 'Review',
    lead_status VARCHAR(32) NOT NULL DEFAULT 'new',
    duplicate_hash VARCHAR(128),
    promoted_flag BOOLEAN NOT NULL DEFAULT FALSE,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS opportunities_live (
    opportunity_id SERIAL PRIMARY KEY,
    lead_id INTEGER UNIQUE REFERENCES opportunity_leads(lead_id) ON DELETE SET NULL,
    source_id VARCHAR(80) REFERENCES registry_sources(source_id) ON DELETE SET NULL,
    title TEXT NOT NULL,
    owner_name VARCHAR(255) NOT NULL,
    owner_type VARCHAR(64),
    county VARCHAR(128),
    municipality VARCHAR(128),
    category VARCHAR(128),
    project_type VARCHAR(128),
    status VARCHAR(64) NOT NULL DEFAULT 'Open',
    posted_at TIMESTAMPTZ,
    due_at TIMESTAMPTZ,
    estimate_range VARCHAR(128),
    official_notice_url TEXT,
    official_procurement_url TEXT NOT NULL,
    lead_url TEXT,
    portal_url TEXT,
    promotion_rule TEXT,
    notes TEXT,
    last_checked_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS opportunities_archive (
    archive_id SERIAL PRIMARY KEY,
    original_opportunity_id INTEGER,
    source_id VARCHAR(80),
    title TEXT NOT NULL,
    owner_name VARCHAR(255) NOT NULL,
    owner_type VARCHAR(64),
    county VARCHAR(128),
    municipality VARCHAR(128),
    category VARCHAR(128),
    project_type VARCHAR(128),
    posted_at TIMESTAMPTZ,
    due_at TIMESTAMPTZ,
    close_date TIMESTAMPTZ,
    final_status VARCHAR(64) NOT NULL,
    archive_reason VARCHAR(64) NOT NULL,
    official_notice_url TEXT,
    official_procurement_url TEXT,
    lead_url TEXT,
    archived_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_registry_sources_source_name ON registry_sources(source_name);
CREATE INDEX IF NOT EXISTS ix_registry_sources_region ON registry_sources(region);
CREATE INDEX IF NOT EXISTS ix_registry_sources_county ON registry_sources(county);
CREATE INDEX IF NOT EXISTS ix_registry_sources_priority_tier ON registry_sources(priority_tier);
CREATE INDEX IF NOT EXISTS ix_registry_sources_import_enabled ON registry_sources(import_enabled);
CREATE INDEX IF NOT EXISTS ix_crawl_runs_source_id ON crawl_runs(source_id);
CREATE INDEX IF NOT EXISTS ix_opportunity_leads_source_id ON opportunity_leads(source_id);
CREATE INDEX IF NOT EXISTS ix_opportunity_leads_duplicate_hash ON opportunity_leads(duplicate_hash);
CREATE INDEX IF NOT EXISTS ix_opportunities_live_due_at ON opportunities_live(due_at);
CREATE INDEX IF NOT EXISTS ix_opportunities_live_status ON opportunities_live(status);
