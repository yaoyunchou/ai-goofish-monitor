-- 闲鱼商品详情 API（mtop.taobao.idle.pc.detail）完整响应归档表
-- 与商品 item_id 关联，按采集时间保留历史快照

CREATE TABLE IF NOT EXISTS item_detail_api_raw (
    id BIGSERIAL PRIMARY KEY,
    item_id TEXT NOT NULL,
    seller_user_id TEXT,
    task_name TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'seller_subscription',
    api_name TEXT NOT NULL DEFAULT 'mtop.taobao.idle.pc.detail',
    raw_json JSONB NOT NULL,
    captured_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_item_detail_api_raw_item_time
    ON item_detail_api_raw (item_id, captured_at DESC);

CREATE INDEX IF NOT EXISTS idx_item_detail_api_raw_task_item_time
    ON item_detail_api_raw (task_name, item_id, captured_at DESC);
