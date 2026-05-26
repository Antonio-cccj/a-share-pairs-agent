-- =============================================================================
-- Database schema for a-share-pairs-agent
-- Compatible with SQLite (default) and PostgreSQL.
-- Why a single SQL file? Keeps DDL versioned & reviewable; SQLAlchemy models
-- mirror these tables in core/data/ingest.py.
-- =============================================================================

CREATE TABLE IF NOT EXISTS stocks (
    ts_code      VARCHAR(12) PRIMARY KEY,   -- e.g. 600519.SH
    name         VARCHAR(64) NOT NULL,
    industry     VARCHAR(64),
    market       VARCHAR(16),               -- SH / SZ / BJ
    list_date    DATE,
    delist_date  DATE
);
CREATE INDEX IF NOT EXISTS idx_stocks_industry ON stocks(industry);

-- Daily OHLCV plus turnover + circulating market cap (we'll need cap for
-- neutralisation downstream even if the strategy itself ignores it).
CREATE TABLE IF NOT EXISTS ohlcv_daily (
    ts_code      VARCHAR(12) NOT NULL,
    trade_date   DATE        NOT NULL,
    open         REAL,
    high         REAL,
    low          REAL,
    close        REAL,
    volume       REAL,
    amount       REAL,
    adj_factor   REAL DEFAULT 1.0,
    circ_mv      REAL,
    PRIMARY KEY (ts_code, trade_date)
);
CREATE INDEX IF NOT EXISTS idx_ohlcv_date ON ohlcv_daily(trade_date);
CREATE INDEX IF NOT EXISTS idx_ohlcv_code_date ON ohlcv_daily(ts_code, trade_date);

-- Announcements (cninfo / Tushare anns_d).  Raw text used by RAG agent.
CREATE TABLE IF NOT EXISTS announcements (
    ann_id       VARCHAR(64) PRIMARY KEY,   -- hash(ts_code+date+title)
    ts_code      VARCHAR(12) NOT NULL,
    ann_date     DATE        NOT NULL,
    title        VARCHAR(512),
    url          VARCHAR(512),
    content      TEXT,
    source       VARCHAR(32),               -- cninfo | tushare | sample
    fetched_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_ann_code_date ON announcements(ts_code, ann_date);

-- Output of the event RAG agent.
CREATE TABLE IF NOT EXISTS events (
    event_id     VARCHAR(64) PRIMARY KEY,
    ann_id       VARCHAR(64) NOT NULL,
    ts_code      VARCHAR(12) NOT NULL,
    event_date   DATE        NOT NULL,
    event_type   VARCHAR(32) NOT NULL,      -- one of 9 taxonomy keys
    severity     REAL,                      -- 0..1 scaled risk score
    rationale    TEXT,
    confidence   REAL,
    model        VARCHAR(64),
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (ann_id) REFERENCES announcements(ann_id)
);
CREATE INDEX IF NOT EXISTS idx_events_code_date ON events(ts_code, event_date);
CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);

-- Cointegrated pair registry produced by strategy.pair_selection.
CREATE TABLE IF NOT EXISTS pairs (
    pair_id      VARCHAR(32) PRIMARY KEY,
    code_a       VARCHAR(12) NOT NULL,
    code_b       VARCHAR(12) NOT NULL,
    industry     VARCHAR(64),
    pvalue       REAL,
    hedge_ratio  REAL,
    half_life    REAL,
    formed_on    DATE,
    expires_on   DATE
);
CREATE INDEX IF NOT EXISTS idx_pairs_dates ON pairs(formed_on, expires_on);
