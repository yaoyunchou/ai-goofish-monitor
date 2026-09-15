-- 卖家订阅独立注册表（与 tasks 解耦）

CREATE TABLE IF NOT EXISTS seller_subscriptions (
    id BIGSERIAL PRIMARY KEY,
    seller_user_id TEXT NOT NULL UNIQUE,
    seller_url TEXT,
    nickname TEXT,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    note TEXT,
    last_captured_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS seller_subscription_schedule (
    id INT PRIMARY KEY DEFAULT 1,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    cron TEXT NOT NULL DEFAULT '0 8 * * *',
    item_limit INT NOT NULL DEFAULT 100,
    collect_ratings BOOLEAN NOT NULL DEFAULT FALSE,
    account_state_file TEXT,
    account_strategy TEXT NOT NULL DEFAULT 'auto',
    is_running BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT seller_subscription_schedule_single_row CHECK (id = 1)
);

INSERT INTO seller_subscription_schedule (id, enabled, cron, item_limit)
VALUES (1, TRUE, '0 8 * * *', 100)
ON CONFLICT (id) DO NOTHING;

COMMENT ON TABLE seller_subscriptions IS '独立卖家订阅列表';
COMMENT ON TABLE seller_subscription_schedule IS '卖家订阅全局调度配置';
