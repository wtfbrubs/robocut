CREATE TABLE IF NOT EXISTS channels (
    id                VARCHAR PRIMARY KEY,
    platform          VARCHAR NOT NULL,
    channel_id        VARCHAR NOT NULL,
    slug              VARCHAR NOT NULL,
    name              VARCHAR NOT NULL,
    active            BOOLEAN DEFAULT TRUE,
    tiktok_account_id VARCHAR
);

CREATE TABLE IF NOT EXISTS stream_sessions (
    id         VARCHAR PRIMARY KEY,
    channel_id VARCHAR REFERENCES channels(id),
    started_at TIMESTAMP DEFAULT NOW(),
    ended_at   TIMESTAMP,
    stream_url TEXT
);

CREATE TABLE IF NOT EXISTS clip_candidates (
    id         VARCHAR PRIMARY KEY,
    session_id VARCHAR REFERENCES stream_sessions(id),
    start_ts   FLOAT,
    end_ts     FLOAT,
    score      FLOAT,
    reason     VARCHAR,
    status     VARCHAR DEFAULT 'pending'
);

CREATE TABLE IF NOT EXISTS clips (
    id           VARCHAR PRIMARY KEY,
    candidate_id VARCHAR REFERENCES clip_candidates(id),
    file_path    TEXT,
    duration     FLOAT,
    processed_at TIMESTAMP DEFAULT NOW(),
    status       VARCHAR DEFAULT 'pending'
);

CREATE TABLE IF NOT EXISTS uploads (
    id                VARCHAR PRIMARY KEY,
    clip_id           VARCHAR REFERENCES clips(id),
    tiktok_account_id VARCHAR,
    publish_id        VARCHAR,
    status            VARCHAR DEFAULT 'pending',
    uploaded_at       TIMESTAMP,
    tiktok_url        TEXT
);
