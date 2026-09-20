-- 为 collected_items 增加结构化标签/分类列，便于查询与筛选
-- item_labels: 商品分类标签（来自 itemLabelExtList + cpvLabels，去重后的 [{label,value}]）
-- common_tags: 通用标签（来自 commonTags，[string]）
-- seller_id: 卖家ID（从 sellerDO 提取，便于按卖家聚合）

ALTER TABLE collected_items
    ADD COLUMN IF NOT EXISTS item_labels JSONB DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS common_tags JSONB DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS seller_id TEXT;

-- GIN 索引支持 JSONB 包含查询（如 item_labels @> '[{"label":"成色"}]'）
CREATE INDEX IF NOT EXISTS idx_collected_items_item_labels ON collected_items USING GIN (item_labels);
CREATE INDEX IF NOT EXISTS idx_collected_items_common_tags ON collected_items USING GIN (common_tags);
CREATE INDEX IF NOT EXISTS idx_collected_items_seller_id ON collected_items(seller_id) WHERE seller_id IS NOT NULL;
