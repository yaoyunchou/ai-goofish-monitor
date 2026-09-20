-- 业务表：关注卖家 + 商品快照
-- followed_sellers 关联 goofish_sellers，支持 per-seller cron 定时拉取
-- seller_item_snapshots 每次拉取新增行，支持历史趋势分析

CREATE TABLE IF NOT EXISTS followed_sellers (
    id BIGSERIAL PRIMARY KEY,
    seller_id TEXT NOT NULL UNIQUE REFERENCES goofish_sellers(seller_id) ON DELETE CASCADE,
    cron TEXT DEFAULT '0 */6 * * *',
    follow_at TEXT NOT NULL,
    last_fetch_at TEXT,
    last_fetch_status TEXT DEFAULT 'pending',
    last_fetch_error TEXT,
    note TEXT
);

CREATE TABLE IF NOT EXISTS seller_item_snapshots (
    id BIGSERIAL PRIMARY KEY,
    seller_id TEXT NOT NULL REFERENCES followed_sellers(seller_id) ON DELETE CASCADE,
    item_id TEXT NOT NULL,
    title TEXT,
    price TEXT,
    pic_url TEXT,
    status TEXT,
    want_cnt INTEGER,
    browse_cnt INTEGER,
    collect_cnt INTEGER,
    sold_cnt INTEGER,
    fetched_at TEXT NOT NULL,
    UNIQUE(seller_id, item_id, fetched_at)
);

CREATE INDEX IF NOT EXISTS idx_followed_sellers_seller ON followed_sellers(seller_id);
CREATE INDEX IF NOT EXISTS idx_seller_snapshots_seller ON seller_item_snapshots(seller_id);
CREATE INDEX IF NOT EXISTS idx_seller_snapshots_want ON seller_item_snapshots(seller_id, want_cnt DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS idx_seller_snapshots_item ON seller_item_snapshots(item_id);
CREATE INDEX IF NOT EXISTS idx_seller_snapshots_fetched ON seller_item_snapshots(fetched_at DESC);

ALTER TABLE followed_sellers ENABLE ROW LEVEL SECURITY;
ALTER TABLE seller_item_snapshots ENABLE ROW LEVEL SECURITY;

COMMENT ON TABLE followed_sellers IS '关注卖家 (关联 goofish_sellers，支持 per-seller cron)';
COMMENT ON TABLE seller_item_snapshots IS '关注卖家商品快照 (每次拉取新增行，支持历史趋势)';
