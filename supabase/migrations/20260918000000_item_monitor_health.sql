-- 商品级监控健康度：停用标记 + 周判定结果
-- 用途：卖家订阅的商品若一周内浏览/想要数据无增长，自动停止监控（不再采其详情）。
-- 判定周期：Asia/Shanghai 自然周（周一 ~ 周日）。

-- ---------------------------------------------------------------------------
-- 1) 商品级监控开关
-- ---------------------------------------------------------------------------
ALTER TABLE seller_subscription_items
    ADD COLUMN IF NOT EXISTS is_muted      BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS muted_at      TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS muted_reason  TEXT,
    ADD COLUMN IF NOT EXISTS muted_week    DATE;

COMMENT ON COLUMN seller_subscription_items.is_muted IS
    '是否已停止监控该商品（自动健康度判定或人工操作）；TRUE 时采集阶段跳过其详情';
COMMENT ON COLUMN seller_subscription_items.muted_reason IS
    '停用原因（含判定时的周数据快照），用于人工复核';
COMMENT ON COLUMN seller_subscription_items.muted_week IS
    '触发停用的判定周起始日（周一）';

CREATE INDEX IF NOT EXISTS idx_seller_subscription_items_muted
    ON seller_subscription_items (seller_user_id, is_muted);

-- ---------------------------------------------------------------------------
-- 2) 周判定结果留存（可审计、可回溯、避免重复停用与重复通知）
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS item_monitor_health_weekly (
    id             BIGSERIAL PRIMARY KEY,
    week_start     DATE NOT NULL,
    week_end       DATE NOT NULL,
    seller_user_id TEXT NOT NULL,
    item_id        TEXT NOT NULL,
    title          TEXT,
    days_with_data INT,
    view_start     INTEGER,
    view_end       INTEGER,
    view_growth    INTEGER,
    want_start     INTEGER,
    want_end       INTEGER,
    want_growth    INTEGER,
    healthy        BOOLEAN NOT NULL,
    reason         TEXT,
    action         TEXT NOT NULL,
    decided_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_item_monitor_health_week
        UNIQUE (week_start, seller_user_id, item_id)
);

COMMENT ON TABLE item_monitor_health_weekly IS
    '商品监控健康度周判定结果；每周一判定一次，action 记录实际动作';
COMMENT ON COLUMN item_monitor_health_weekly.action IS
    'kept=保留 | muted=已停用 | dry_run=影子模式仅记录 | skipped=数据不足/宽限期 | interrupted=数据中断（疑似已售）';

CREATE INDEX IF NOT EXISTS idx_item_monitor_health_week
    ON item_monitor_health_weekly (week_start DESC, action);

CREATE INDEX IF NOT EXISTS idx_item_monitor_health_item
    ON item_monitor_health_weekly (seller_user_id, item_id, week_start DESC);

ALTER TABLE item_monitor_health_weekly ENABLE ROW LEVEL SECURITY;
