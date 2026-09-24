-- 账号按渠道索引。Cookie 仍在 state 文件里。
CREATE TABLE IF NOT EXISTS monitor_accounts (
    id BIGSERIAL PRIMARY KEY,
    channel TEXT NOT NULL,
    name TEXT NOT NULL,
    state_path TEXT NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    last_checked_at TIMESTAMPTZ,
    last_error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT monitor_accounts_channel_check CHECK (channel IN ('goofish', 'xhs')),
    CONSTRAINT uq_monitor_accounts_channel_name UNIQUE (channel, name),
    CONSTRAINT uq_monitor_accounts_state_path UNIQUE (state_path)
);

CREATE TABLE IF NOT EXISTS xhs_notes (
    id TEXT PRIMARY KEY,
    source_url TEXT,
    title TEXT,
    author_name TEXT,
    cover_url TEXT,
    account_id BIGINT REFERENCES monitor_accounts(id),
    active BOOLEAN NOT NULL DEFAULT TRUE,
    last_error TEXT,
    last_status TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS xhs_note_daily (
    id BIGSERIAL PRIMARY KEY,
    note_id TEXT NOT NULL REFERENCES xhs_notes(id) ON DELETE CASCADE,
    snapshot_day DATE NOT NULL,
    liked_count INTEGER,
    collected_count INTEGER,
    comment_count INTEGER,
    view_count INTEGER,
    captured_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT uq_xhs_note_daily_day UNIQUE (note_id, snapshot_day)
);

CREATE TABLE IF NOT EXISTS xhs_note_schedule (
    id INTEGER PRIMARY KEY,
    cron TEXT NOT NULL DEFAULT '0 9 * * *',
    enabled BOOLEAN NOT NULL DEFAULT FALSE,
    account_id BIGINT REFERENCES monitor_accounts(id),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO xhs_note_schedule (id, cron, enabled)
VALUES (1, '0 9 * * *', FALSE)
ON CONFLICT (id) DO NOTHING;
