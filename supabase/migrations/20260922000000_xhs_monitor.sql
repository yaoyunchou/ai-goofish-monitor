-- 小红书公开商品监控。快照只追加，禁止按日或按整点覆盖。

CREATE TABLE IF NOT EXISTS xhs_products (
    id TEXT PRIMARY KEY,
    source_url TEXT,
    title TEXT,
    shop_name TEXT,
    cover_url TEXT,
    price DOUBLE PRECISION,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    last_error TEXT,
    last_status TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE xhs_products IS '小红书公开商品。不保存登录态。';

CREATE TABLE IF NOT EXISTS xhs_snapshots (
    id BIGSERIAL PRIMARY KEY,
    product_id TEXT NOT NULL REFERENCES xhs_products(id) ON DELETE CASCADE,
    captured_at TIMESTAMPTZ NOT NULL,
    sold INTEGER,
    price DOUBLE PRECISION,
    raw_note TEXT
);

COMMENT ON TABLE xhs_snapshots IS '每次采集追加一行。高水位取 MAX(sold)，更小的新读数不回退。';

CREATE INDEX IF NOT EXISTS idx_xhs_snapshots_product_time
    ON xhs_snapshots (product_id, captured_at);

CREATE TABLE IF NOT EXISTS xhs_schedule (
    id INTEGER PRIMARY KEY,
    cron TEXT NOT NULL DEFAULT '0 * * * *',
    enabled BOOLEAN NOT NULL DEFAULT FALSE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO xhs_schedule (id, cron, enabled)
VALUES (1, '0 * * * *', FALSE)
ON CONFLICT (id) DO NOTHING;
