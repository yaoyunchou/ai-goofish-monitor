-- 卖家订阅：静/动态拆表 + 通用爬虫原始表 + 日指标 1:1 关联
-- snapshot_day / profile_day 业务层使用 Asia/Shanghai 自然日

CREATE TABLE IF NOT EXISTS crawl_raw_records (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    raw_json JSONB NOT NULL
);

COMMENT ON TABLE crawl_raw_records IS '通用爬虫原始数据（仅时间戳 + JSON）；卖家订阅商品日快照等场景复用';

CREATE TABLE IF NOT EXISTS seller_subscription_items (
    task_name TEXT NOT NULL,
    seller_user_id TEXT NOT NULL,
    item_id TEXT NOT NULL,
    title TEXT,
    price DOUBLE PRECISION,
    item_status TEXT,
    item_link TEXT,
    main_image TEXT,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (task_name, seller_user_id, item_id)
);

CREATE INDEX IF NOT EXISTS idx_seller_subscription_items_seller
    ON seller_subscription_items (seller_user_id, last_seen_at DESC);

COMMENT ON TABLE seller_subscription_items IS '卖家订阅商品静态主表（慢变 UPSERT）';

CREATE TABLE IF NOT EXISTS seller_item_daily_metrics (
    id BIGSERIAL PRIMARY KEY,
    task_name TEXT NOT NULL,
    seller_user_id TEXT NOT NULL,
    item_id TEXT NOT NULL,
    snapshot_day DATE NOT NULL,
    want_count INTEGER,
    view_count INTEGER,
    captured_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    raw_record_id BIGINT NOT NULL REFERENCES crawl_raw_records(id) ON DELETE CASCADE,
    CONSTRAINT uq_seller_item_daily_metrics_day
        UNIQUE (task_name, seller_user_id, item_id, snapshot_day),
    CONSTRAINT uq_seller_item_daily_metrics_raw
        UNIQUE (raw_record_id)
);

CREATE INDEX IF NOT EXISTS idx_seller_item_daily_metrics_item_day
    ON seller_item_daily_metrics (item_id, snapshot_day DESC);

CREATE INDEX IF NOT EXISTS idx_seller_item_daily_metrics_task_day
    ON seller_item_daily_metrics (task_name, snapshot_day DESC);

COMMENT ON TABLE seller_item_daily_metrics IS '商品日指标；与 crawl_raw_records 严格 1:1';

-- 卖家画像按自然日去重
ALTER TABLE seller_profiles
    ADD COLUMN IF NOT EXISTS profile_day DATE;

UPDATE seller_profiles
SET profile_day = (captured_at AT TIME ZONE 'Asia/Shanghai')::date
WHERE profile_day IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_seller_profiles_task_seller_day
    ON seller_profiles (task_name, seller_user_id, profile_day)
    WHERE profile_day IS NOT NULL;

ALTER TABLE crawl_raw_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE seller_subscription_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE seller_item_daily_metrics ENABLE ROW LEVEL SECURITY;
