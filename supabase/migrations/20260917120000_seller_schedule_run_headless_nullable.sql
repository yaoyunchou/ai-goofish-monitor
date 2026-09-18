-- run_headless 允许 NULL：NULL 表示继承全局 RUN_HEADLESS，与 false（用户显式选有头）区分

ALTER TABLE seller_subscription_schedule
    ALTER COLUMN run_headless DROP NOT NULL;

ALTER TABLE seller_subscription_schedule
    ALTER COLUMN run_headless DROP DEFAULT;

UPDATE seller_subscription_schedule
SET run_headless = NULL
WHERE id = 1;
