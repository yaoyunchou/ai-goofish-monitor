-- 小红书店铺归属、分类和标记。页面店名仍在 xhs_products.shop_name。

CREATE TABLE IF NOT EXISTS xhs_shops (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_xhs_shops_name ON xhs_shops (name);

ALTER TABLE xhs_products ADD COLUMN IF NOT EXISTS shop_id BIGINT;
ALTER TABLE xhs_products ADD COLUMN IF NOT EXISTS category TEXT;
ALTER TABLE xhs_products ADD COLUMN IF NOT EXISTS tags_json JSONB NOT NULL DEFAULT CAST('[]' AS jsonb);

COMMENT ON TABLE xhs_shops IS '用户归类用的小红书店铺。同名只有一行。';
