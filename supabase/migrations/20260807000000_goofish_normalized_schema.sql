-- goofish_ 前缀规范化表：将 MTOP mtop.taobao.idle.pc.detail 返回的完整数据按实体拆分
-- 与现有 collected_items / result_items 等业务表分离，便于扩展与查询
-- 每张表均带 raw_json JSONB 保留原始数据，结构化列用于查询/索引

-- ========== 1. 卖家主表 ==========
CREATE TABLE IF NOT EXISTS goofish_sellers (
    seller_id TEXT PRIMARY KEY,
    unique_name TEXT,
    nick TEXT,
    portrait_url TEXT,
    city TEXT,
    publish_city TEXT,
    signature TEXT,
    user_reg_day INTEGER,
    register_time BIGINT,
    has_sold_num INTEGER,
    item_count INTEGER,
    reply_ratio_24h TEXT,
    reply_in24h_ratio_double DOUBLE PRECISION,
    reply_interval TEXT,
    avg_reply_30d_long INTEGER,
    last_visit_time TEXT,
    new_good_ratio_rate TEXT,
    zhima_auth BOOLEAN,
    aoi_type TEXT,
    seller_type_string TEXT,
    yxp_pro BOOLEAN,
    xianyu_summary TEXT,
    remark_good_cnt INTEGER,
    remark_default_cnt INTEGER,
    remark_bad_cnt INTEGER,
    raw_json JSONB,
    updated_at TEXT NOT NULL
);

-- ========== 2. 商品主表 ==========
CREATE TABLE IF NOT EXISTS goofish_items (
    item_id TEXT PRIMARY KEY,
    seller_id TEXT REFERENCES goofish_sellers(seller_id) ON DELETE SET NULL,
    title TEXT,
    description TEXT,
    desc_tag TEXT,
    desc_tag_color TEXT,
    sold_price TEXT,
    original_price TEXT,
    transport_fee TEXT,
    quantity INTEGER,
    sold_cnt INTEGER,
    want_cnt INTEGER,
    want_cnt_unit TEXT,
    browse_cnt INTEGER,
    collect_cnt INTEGER,
    favor_cnt INTEGER,
    interact_favor_cnt INTEGER,
    item_status INTEGER,
    item_status_str TEXT,
    item_type TEXT,
    simple_item BOOLEAN,
    bargained BOOLEAN,
    trade_access_type INTEGER,
    gmt_create BIGINT,
    gmt_create_date TEXT,
    category_id BIGINT,
    title_is_user_input BOOLEAN,
    raw_json JSONB,
    updated_at TEXT NOT NULL
);

-- ========== 3. 商品 SKU 表 ==========
CREATE TABLE IF NOT EXISTS goofish_item_skus (
    id BIGSERIAL PRIMARY KEY,
    item_id TEXT NOT NULL REFERENCES goofish_items(item_id) ON DELETE CASCADE,
    sku_id TEXT,
    price BIGINT,
    price_in_cent BIGINT,
    quantity INTEGER,
    inventory_id BIGINT,
    properties JSONB,
    property_image_url TEXT,
    UNIQUE(item_id, sku_id)
);

-- ========== 4. 商品图片表 ==========
CREATE TABLE IF NOT EXISTS goofish_item_images (
    id BIGSERIAL PRIMARY KEY,
    item_id TEXT NOT NULL REFERENCES goofish_items(item_id) ON DELETE CASCADE,
    url TEXT NOT NULL,
    major BOOLEAN DEFAULT FALSE,
    width INTEGER,
    height INTEGER,
    sort_order INTEGER
);

-- ========== 5. 商品分类标签表 (itemLabelExtList + cpvLabels) ==========
CREATE TABLE IF NOT EXISTS goofish_item_labels (
    id BIGSERIAL PRIMARY KEY,
    item_id TEXT NOT NULL REFERENCES goofish_items(item_id) ON DELETE CASCADE,
    source TEXT NOT NULL,
    property_id BIGINT,
    property_text TEXT,
    value_id BIGINT,
    value_text TEXT,
    label_type TEXT,
    sort_order INTEGER
);

-- ========== 6. 商品标签表 (commonTags + priceRelativeTags + recommendTagList + descRelativeTags) ==========
CREATE TABLE IF NOT EXISTS goofish_item_tags (
    id BIGSERIAL PRIMARY KEY,
    item_id TEXT NOT NULL REFERENCES goofish_items(item_id) ON DELETE CASCADE,
    tag_type TEXT NOT NULL,
    text TEXT,
    text_color TEXT,
    bg_color TEXT,
    border_color TEXT,
    sort_order INTEGER
);

-- ========== 7. 分类表 ==========
CREATE TABLE IF NOT EXISTS goofish_categories (
    cat_id BIGINT PRIMARY KEY,
    leaf_id BIGINT,
    tb_cat_id BIGINT,
    channel_cat_id BIGINT,
    root_channel_cat_id BIGINT,
    level2_channel_cat_id BIGINT,
    level3_channel_cat_id BIGINT,
    sug_show BOOLEAN
);

-- ========== 8. 卖家标签表 (identityTags + sellerInfoTags + levelTags) ==========
CREATE TABLE IF NOT EXISTS goofish_seller_tags (
    id BIGSERIAL PRIMARY KEY,
    seller_id TEXT NOT NULL REFERENCES goofish_sellers(seller_id) ON DELETE CASCADE,
    tag_type TEXT NOT NULL,
    text TEXT,
    icon_url TEXT,
    link TEXT,
    sort_order INTEGER
);

-- ========== 9. 卖家其他在售商品表 ==========
CREATE TABLE IF NOT EXISTS goofish_seller_other_items (
    id BIGSERIAL PRIMARY KEY,
    seller_id TEXT NOT NULL REFERENCES goofish_sellers(seller_id) ON DELETE CASCADE,
    item_id TEXT,
    title TEXT,
    text TEXT,
    icon_url TEXT,
    link TEXT,
    sort_order INTEGER,
    fetched_at TEXT NOT NULL
);

-- ========== 10. 商品详情快照表 (完整 MTOP 响应) ==========
CREATE TABLE IF NOT EXISTS goofish_item_details (
    id BIGSERIAL PRIMARY KEY,
    collected_item_id BIGINT REFERENCES collected_items(id) ON DELETE CASCADE,
    item_id TEXT NOT NULL,
    seller_id TEXT,
    server_time TEXT,
    buyer_json JSONB,
    config_json JSONB,
    track_params_json JSONB,
    raw_json JSONB NOT NULL,
    fetched_at TEXT NOT NULL
);

-- ========== 11. 跟踪参数表 ==========
CREATE TABLE IF NOT EXISTS goofish_item_track_params (
    id BIGSERIAL PRIMARY KEY,
    item_id TEXT NOT NULL REFERENCES goofish_items(item_id) ON DELETE CASCADE,
    seller_id TEXT,
    category_id TEXT,
    main_pic TEXT,
    channel_cat_id TEXT,
    root_channel_cat_id TEXT,
    buyer_id TEXT,
    medal_id TEXT,
    buyer_bucket_id TEXT,
    seller_bucket_id TEXT,
    raw_json JSONB
);

-- ========== 索引 ==========
CREATE INDEX IF NOT EXISTS idx_goofish_items_seller ON goofish_items(seller_id);
CREATE INDEX IF NOT EXISTS idx_goofish_items_want ON goofish_items(want_cnt DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS idx_goofish_items_browse ON goofish_items(browse_cnt DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS idx_goofish_items_category ON goofish_items(category_id);
CREATE INDEX IF NOT EXISTS idx_goofish_item_skus_item ON goofish_item_skus(item_id);
CREATE INDEX IF NOT EXISTS idx_goofish_item_images_item ON goofish_item_images(item_id);
CREATE INDEX IF NOT EXISTS idx_goofish_item_labels_item ON goofish_item_labels(item_id);
CREATE INDEX IF NOT EXISTS idx_goofish_item_tags_item ON goofish_item_tags(item_id);
CREATE INDEX IF NOT EXISTS idx_goofish_seller_tags_seller ON goofish_seller_tags(seller_id);
CREATE INDEX IF NOT EXISTS idx_goofish_seller_other_items_seller ON goofish_seller_other_items(seller_id);
CREATE INDEX IF NOT EXISTS idx_goofish_item_details_item ON goofish_item_details(item_id);
CREATE INDEX IF NOT EXISTS idx_goofish_item_details_collected ON goofish_item_details(collected_item_id);
CREATE INDEX IF NOT EXISTS idx_goofish_item_track_params_item ON goofish_item_track_params(item_id);

-- ========== RLS ==========
ALTER TABLE goofish_sellers ENABLE ROW LEVEL SECURITY;
ALTER TABLE goofish_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE goofish_item_skus ENABLE ROW LEVEL SECURITY;
ALTER TABLE goofish_item_images ENABLE ROW LEVEL SECURITY;
ALTER TABLE goofish_item_labels ENABLE ROW LEVEL SECURITY;
ALTER TABLE goofish_item_tags ENABLE ROW LEVEL SECURITY;
ALTER TABLE goofish_categories ENABLE ROW LEVEL SECURITY;
ALTER TABLE goofish_seller_tags ENABLE ROW LEVEL SECURITY;
ALTER TABLE goofish_seller_other_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE goofish_item_details ENABLE ROW LEVEL SECURITY;
ALTER TABLE goofish_item_track_params ENABLE ROW LEVEL SECURITY;

COMMENT ON TABLE goofish_sellers IS '闲鱼卖家主表 (from sellerDO)';
COMMENT ON TABLE goofish_items IS '闲鱼商品主表 (from itemDO)';
COMMENT ON TABLE goofish_item_skus IS '商品SKU规格表 (from itemDO.skuList)';
COMMENT ON TABLE goofish_item_images IS '商品图片表 (from itemDO.imageInfos)';
COMMENT ON TABLE goofish_item_labels IS '商品分类标签 (from itemLabelExtList + cpvLabels)';
COMMENT ON TABLE goofish_item_tags IS '商品标签 (from commonTags + priceRelativeTags + recommendTagList)';
COMMENT ON TABLE goofish_categories IS '商品分类表 (from itemCatDTO)';
COMMENT ON TABLE goofish_seller_tags IS '卖家标签 (from identityTags + sellerInfoTags + levelTags)';
COMMENT ON TABLE goofish_seller_other_items IS '卖家其他在售商品 (from sellerDO.sellerItems)';
COMMENT ON TABLE goofish_item_details IS '商品详情完整快照 (完整 MTOP 响应)';
COMMENT ON TABLE goofish_item_track_params IS '跟踪参数 (from trackParams)';
