-- 闲鱼账号登录态存入数据库（替代/镜像 state/*.json）
CREATE TABLE IF NOT EXISTS xianyu_account_states (
    name TEXT PRIMARY KEY,
    content_json JSONB NOT NULL,
    updated_at TEXT NOT NULL,
    note TEXT
);

CREATE INDEX IF NOT EXISTS idx_xianyu_account_states_name ON xianyu_account_states(name);

ALTER TABLE xianyu_account_states ENABLE ROW LEVEL SECURITY;
