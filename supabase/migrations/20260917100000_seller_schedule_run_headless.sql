-- 卖家订阅调度：无头模式开关（与 Web UI 采集控制台联动）

ALTER TABLE seller_subscription_schedule
    ADD COLUMN IF NOT EXISTS run_headless BOOLEAN NOT NULL DEFAULT FALSE;
