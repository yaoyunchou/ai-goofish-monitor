-- 用户页订阅 + 卖家工作台数据罗盘

ALTER TABLE tasks
    ADD COLUMN IF NOT EXISTS task_type TEXT NOT NULL DEFAULT 'keyword_search';

ALTER TABLE tasks
    ADD COLUMN IF NOT EXISTS seller_user_ids_json JSONB NOT NULL DEFAULT '[]'::jsonb;

ALTER TABLE tasks
    ADD COLUMN IF NOT EXISTS seller_urls_json JSONB NOT NULL DEFAULT '[]'::jsonb;

ALTER TABLE tasks
    ADD COLUMN IF NOT EXISTS collect_ratings BOOLEAN NOT NULL DEFAULT FALSE;

CREATE TABLE IF NOT EXISTS seller_profiles (
    id BIGSERIAL PRIMARY KEY,
    task_name TEXT NOT NULL,
    seller_user_id TEXT NOT NULL,
    nickname TEXT,
    shop_level TEXT,
    praise_ratio NUMERIC,
    followers INTEGER,
    item_count INTEGER,
    rating_count INTEGER,
    profile_json JSONB NOT NULL,
    captured_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_seller_profiles_task_time
    ON seller_profiles(task_name, captured_at DESC);

CREATE INDEX IF NOT EXISTS idx_seller_profiles_seller
    ON seller_profiles(seller_user_id, captured_at DESC);

CREATE TABLE IF NOT EXISTS seller_item_metrics (
    id BIGSERIAL PRIMARY KEY,
    task_name TEXT NOT NULL,
    seller_user_id TEXT NOT NULL,
    item_id TEXT NOT NULL,
    title TEXT,
    price DOUBLE PRECISION,
    item_status TEXT,
    want_count INTEGER,
    view_count INTEGER,
    snapshot_time TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_seller_metrics_item_time
    ON seller_item_metrics(item_id, snapshot_time DESC);

CREATE INDEX IF NOT EXISTS idx_seller_metrics_task_time
    ON seller_item_metrics(task_name, snapshot_time DESC);

CREATE TABLE IF NOT EXISTS shop_datacompass_snapshots (
    id BIGSERIAL PRIMARY KEY,
    account_state_file TEXT NOT NULL,
    shop_name TEXT,
    time_cycle TEXT NOT NULL,
    snapshot_date DATE NOT NULL,
    api_name TEXT NOT NULL,
    metrics_json JSONB NOT NULL,
    raw_json JSONB,
    captured_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_datacompass_snapshot UNIQUE (account_state_file, time_cycle, snapshot_date, api_name)
);

CREATE INDEX IF NOT EXISTS idx_datacompass_account_cycle
    ON shop_datacompass_snapshots(account_state_file, time_cycle, captured_at DESC);

ALTER TABLE seller_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE seller_item_metrics ENABLE ROW LEVEL SECURITY;
ALTER TABLE shop_datacompass_snapshots ENABLE ROW LEVEL SECURITY;

COMMENT ON COLUMN tasks.task_type IS 'keyword_search | seller_subscription | shop_datacompass';
COMMENT ON TABLE seller_profiles IS '订阅卖家画像快照';
COMMENT ON TABLE seller_item_metrics IS '订阅商品想要/浏览量时序';
COMMENT ON TABLE shop_datacompass_snapshots IS '卖家工作台 datacompass 快照';
