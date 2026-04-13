"""PostgreSQL schema for ICD and OPS tables. Matches Sequelize models (underscored)."""

ICD_CREATE = """
CREATE TABLE IF NOT EXISTS icd (
    id SERIAL PRIMARY KEY,
    code VARCHAR(10) NOT NULL,
    label TEXT NOT NULL,
    category3 VARCHAR(4) NOT NULL,
    parent_code VARCHAR(10),
    parent_id INTEGER REFERENCES icd(id),
    level SMALLINT NOT NULL,
    version_year SMALLINT NOT NULL,
    is_terminal BOOLEAN DEFAULT TRUE,
    code_type VARCHAR(20) DEFAULT 'primary',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (code, version_year)
);
CREATE INDEX IF NOT EXISTS ix_icd_category3_version_year ON icd(category3, version_year);
CREATE INDEX IF NOT EXISTS ix_icd_parent_code_version_year ON icd(parent_code, version_year);
CREATE INDEX IF NOT EXISTS ix_icd_parent_id ON icd(parent_id);
CREATE INDEX IF NOT EXISTS ix_icd_version_year ON icd(version_year);
"""

OPS_CREATE = """
CREATE TABLE IF NOT EXISTS ops (
    id SERIAL PRIMARY KEY,
    code VARCHAR(12) NOT NULL,
    label TEXT NOT NULL,
    chapter SMALLINT NOT NULL,
    parent_code VARCHAR(12),
    parent_id INTEGER REFERENCES ops(id),
    level SMALLINT NOT NULL,
    version_year SMALLINT NOT NULL,
    is_terminal BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (code, version_year)
);
CREATE INDEX IF NOT EXISTS ix_ops_chapter_version_year ON ops(chapter, version_year);
CREATE INDEX IF NOT EXISTS ix_ops_parent_code_version_year ON ops(parent_code, version_year);
CREATE INDEX IF NOT EXISTS ix_ops_parent_id ON ops(parent_id);
CREATE INDEX IF NOT EXISTS ix_ops_version_year ON ops(version_year);
"""


def ensure_schema(conn) -> None:
    """Create icd and ops tables if they do not exist."""
    cur = conn.cursor()
    try:
        cur.execute(ICD_CREATE)
        cur.execute(OPS_CREATE)
        conn.commit()
    finally:
        cur.close()
