-- 为 collected_items 增加更多结构化列，便于查询/筛选/聚合
-- 完整 detail_data 仍保留在 sku_json.detail_data JSONB 中

ALTER TABLE collected_items
    ADD COLUMN IF NOT EXISTS title TEXT,
    ADD COLUMN IF NOT EXISTS sold_price TEXT,
    ADD COLUMN IF NOT EXISTS original_price TEXT,
    ADD COLUMN IF NOT EXISTS want_cnt INTEGER,
    ADD COLUMN IF NOT EXISTS browse_cnt INTEGER,
    ADD COLUMN IF NOT EXISTS collect_cnt INTEGER,
    ADD COLUMN IF NOT EXISTS sold_cnt INTEGER,
    ADD COLUMN IF NOT EXISTS quantity_cnt INTEGER,
    ADD COLUMN IF NOT EXISTS category_id TEXT,
    ADD COLUMN IF NOT EXISTS main_pic_url TEXT,
    ADD COLUMN IF NOT EXISTS image_count INTEGER,
    ADD COLUMN IF NOT EXISTS sku_count INTEGER,
    ADD COLUMN IF NOT EXISTS seller_name TEXT,
    ADD COLUMN IF NOT EXISTS seller_city TEXT,
    ADD COLUMN IF NOT EXISTS seller_sold_cnt INTEGER,
    ADD COLUMN IF NOT EXISTS seller_item_count INTEGER,
    ADD COLUMN IF NOT EXISTS seller_good_rate TEXT,
    ADD COLUMN IF NOT EXISTS seller_register_days INTEGER;

CREATE INDEX IF NOT EXISTS idx_collected_items_title ON collected_items(title) WHERE title IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_collected_items_sold_price ON collected_items(sold_price) WHERE sold_price IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_collected_items_category_id ON collected_items(category_id) WHERE category_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_collected_items_seller_name ON collected_items(seller_name) WHERE seller_name IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_collected_items_want_cnt ON collected_items(want_cnt DESC) WHERE want_cnt IS NOT NULL;
