-- ==============================================================================================================
-- 供应链场景 CDM 导入脚本（KG「类型约束 = CDM 目录」的数据来源）
--
-- 场景来源：docs/prototypes/kg-knowledge-base-preview.html 预置图谱（部门/供应商/产品/仓库/客户 ×
--           供应/生产/库存/签约/采购/配套/代理/协作），并按 prototypes 下 6 份业务文档扩展
--           物料/订单/物流/协议/风险事件 5 类对象与 12 类关系。
-- 表结构：  backend/app/models/dataops/standard_cdm.py
--           （meta_standard_catalog / meta_object_standard / meta_object_relation）
-- 范式参照：sql/import_ontology_playground_to_meta_cdm.sql（幂等 upsert，可重复执行）
--
-- 导入后在 KgBuildConfig 页「类型约束」选 CDM 目录，节点选「供应链场景（SC）」
-- （build_schema_hint 已做子树闭包展开，选根目录即覆盖 4 个子目录的全部标准）。
--
-- tenant_id = 0：与既有 playground 导入同命名空间；如需挂到业务租户，全局替换 0 为目标租户 id。
-- ==============================================================================================================

-- 注意：本脚本为纯 SQL（无 psql 元命令），可在任意 SQL 客户端整段执行；
-- DO 块失败时由 BEGIN/COMMIT 事务保证整体回滚。
BEGIN;

-- ---------- 0. 预检：目标表必须存在 ----------
DO $$
DECLARE missing text;
BEGIN
    SELECT string_agg(t, ', ') INTO missing
    FROM unnest(ARRAY['meta_standard_catalog','meta_object_standard','meta_object_relation']) AS t
    WHERE NOT EXISTS (SELECT 1 FROM information_schema.tables
                      WHERE table_schema = current_schema() AND table_name = t);
    IF missing IS NOT NULL THEN
        RAISE EXCEPTION '缺少目标表：%（请先执行 alembic upgrade head）', missing;
    END IF;
END $$;

-- ---------- 1. 目录树：根 → 4 个分组 ----------
INSERT INTO meta_standard_catalog
    (tenant_id, parent_id, code, name, description, icon, sort_order, status)
VALUES
    (0, NULL, 'sc', '供应链场景（SC）',
     '供应链知识图谱的类型约束命名空间：组织、产品与物料、仓储物流、协议与风险', '🔗', 90, 'published'),
    (0, (SELECT id FROM meta_standard_catalog WHERE tenant_id = 0 AND code = 'sc'),
     'sc.party',   '主体与组织',   '部门、供应商、客户等参与主体',       NULL, 1, 'published'),
    (0, (SELECT id FROM meta_standard_catalog WHERE tenant_id = 0 AND code = 'sc'),
     'sc.item',    '产品与物料',   '成品、原材料与零部件、订单',         NULL, 2, 'published'),
    (0, (SELECT id FROM meta_standard_catalog WHERE tenant_id = 0 AND code = 'sc'),
     'sc.logi',    '仓储与物流',   '仓库节点、运输配送',                 NULL, 3, 'published'),
    (0, (SELECT id FROM meta_standard_catalog WHERE tenant_id = 0 AND code = 'sc'),
     'sc.risk',    '协议与风险',   '框架协议、风险事件',                 NULL, 4, 'published')
ON CONFLICT (tenant_id, code) DO UPDATE SET
    parent_id = EXCLUDED.parent_id, name = EXCLUDED.name,
    description = EXCLUDED.description, icon = EXCLUDED.icon,
    sort_order = EXCLUDED.sort_order, status = EXCLUDED.status, updated_at = now();

-- ---------- 2. meta_object_standard：10 类实体（name 即 KG 实体类型，LLM 按此输出 label） ----------
INSERT INTO meta_object_standard
    (tenant_id, catalog_id, code, name, aliases_json, description, domain, status, current_version)
VALUES
    (0, (SELECT id FROM meta_standard_catalog WHERE tenant_id = 0 AND code = 'sc.party'),
     'sc.Department', '部门', '["组织单元", "科室"]'::jsonb,
     '公司内部组织单元，如采购部、销售部、仓储部、品控部', 'supply_chain', 'published', 1),
    (0, (SELECT id FROM meta_standard_catalog WHERE tenant_id = 0 AND code = 'sc.party'),
     'sc.Supplier', '供应商', '["供货商", "供方"]'::jsonb,
     '向本公司供货的外部企业，如华创制造、启明电子、恒信科技；含等级、合作年限等属性', 'supply_chain', 'published', 1),
    (0, (SELECT id FROM meta_standard_catalog WHERE tenant_id = 0 AND code = 'sc.party'),
     'sc.Customer', '客户', '["买方", "采购方"]'::jsonb,
     '采购本公司产品的外部企业，如星海科技、远航贸易；含行业、信用等级', 'supply_chain', 'published', 1),
    (0, (SELECT id FROM meta_standard_catalog WHERE tenant_id = 0 AND code = 'sc.item'),
     'sc.Product', '产品', '["成品", "整机"]'::jsonb,
     '可销售的整机/成品，如天枢服务器、智联数码、联影工作站；含型号、单价', 'supply_chain', 'published', 1),
    (0, (SELECT id FROM meta_standard_catalog WHERE tenant_id = 0 AND code = 'sc.item'),
     'sc.Material', '物料', '["原材料", "零部件", "辅料"]'::jsonb,
     '生产投入的原材料与零部件，如电芯、主板、结构件、包装材料', 'supply_chain', 'published', 1),
    (0, (SELECT id FROM meta_standard_catalog WHERE tenant_id = 0 AND code = 'sc.item'),
     'sc.Order', '订单', '["采购订单", "销售订单", "PO"]'::jsonb,
     '采购或销售订单，如 PO-2026-031、年度框架订单；含数量、金额、交期', 'supply_chain', 'published', 1),
    (0, (SELECT id FROM meta_standard_catalog WHERE tenant_id = 0 AND code = 'sc.logi'),
     'sc.Warehouse', '仓库', '["仓", "仓储节点"]'::jsonb,
     '仓储节点，如北京仓、上海仓、华南仓；含面积、库位数', 'supply_chain', 'published', 1),
    (0, (SELECT id FROM meta_standard_catalog WHERE tenant_id = 0 AND code = 'sc.logi'),
     'sc.Logistics', '物流', '["运输", "配送", "发运批次"]'::jsonb,
     '运输/配送过程与单据，如干线运输、冷链配送、发运批次 SH-092', 'supply_chain', 'published', 1),
    (0, (SELECT id FROM meta_standard_catalog WHERE tenant_id = 0 AND code = 'sc.risk'),
     'sc.Agreement', '协议', '["合同", "框架协议"]'::jsonb,
     '框架合同与合作协议，如 2026年度供应商框架协议、销售框架合同', 'supply_chain', 'published', 1),
    (0, (SELECT id FROM meta_standard_catalog WHERE tenant_id = 0 AND code = 'sc.risk'),
     'sc.RiskEvent', '风险事件', '["风险", "事故"]'::jsonb,
     '已发生或潜在的风险，如断供、延迟交付、质量事故、价格波动；来自供应链风险评估报告', 'supply_chain', 'published', 1)
ON CONFLICT (tenant_id, code) DO UPDATE SET
    catalog_id = EXCLUDED.catalog_id, name = EXCLUDED.name,
    aliases_json = EXCLUDED.aliases_json, description = EXCLUDED.description,
    domain = EXCLUDED.domain, status = EXCLUDED.status,
    current_version = EXCLUDED.current_version, updated_at = now();

-- ---------- 3. meta_object_relation：20 条关系标准（16 个可用关系名） ----------
-- 端点多态（如"订单归属于客户或供应商"）在 CDM 中拆成独立行，保证 from/to 机器可校验；
-- 关系 name 即 KG 关系类型，LLM 按此输出 relation_type。
INSERT INTO meta_object_relation
    (tenant_id, catalog_id, code, name, from_object_id, to_object_id, relation_type,
     via_attribute_ids, description, status)
SELECT v.tenant_id, v.catalog_id, v.code, v.name, fo.id, t.id, v.relation_type,
       NULL, v.description, 'published'
FROM (VALUES
    -- 原型图谱既有 8 类
    (0, (SELECT id FROM meta_standard_catalog WHERE tenant_id = 0 AND code = 'sc'),
     'sc.supplies',     '供应',   'sc.Department',  'sc.Supplier',   'N:N',
     '部门接受供应商供货（采购部—华创制造）'),
    (0, (SELECT id FROM meta_standard_catalog WHERE tenant_id = 0 AND code = 'sc'),
     'sc.produces',     '生产',   'sc.Supplier',    'sc.Product',    'N:N',
     '供应商生产该产品（华创制造—天枢服务器）'),
    (0, (SELECT id FROM meta_standard_catalog WHERE tenant_id = 0 AND code = 'sc'),
     'sc.stocks',       '库存',   'sc.Product',     'sc.Warehouse',  'N:N',
     '产品在仓库存有常备/前置库存（天枢服务器—北京仓）'),
    (0, (SELECT id FROM meta_standard_catalog WHERE tenant_id = 0 AND code = 'sc'),
     'sc.signs_with',   '签约',   'sc.Department',  'sc.Customer',   'N:N',
     '部门与客户签署年度销售框架合同（销售部—星海科技）'),
    (0, (SELECT id FROM meta_standard_catalog WHERE tenant_id = 0 AND code = 'sc'),
     'sc.purchases',    '采购',   'sc.Customer',    'sc.Product',    'N:N',
     '客户采购该产品（星海科技—智联数码 500 台）'),
    (0, (SELECT id FROM meta_standard_catalog WHERE tenant_id = 0 AND code = 'sc'),
     'sc.matches_with', '配套',   'sc.Product',     'sc.Product',    'N:N',
     '两产品配套/组合销售（智联数码—联影工作站）'),
    (0, (SELECT id FROM meta_standard_catalog WHERE tenant_id = 0 AND code = 'sc'),
     'sc.represents',   '代理',   'sc.Supplier',    'sc.Supplier',   'N:N',
     '一方代理另一方产线产能或产品（启明电子—华创制造）'),
    (0, (SELECT id FROM meta_standard_catalog WHERE tenant_id = 0 AND code = 'sc'),
     'sc.collaborates', '协作',   'sc.Department',  'sc.Department', 'N:N',
     '部门间业务协同（销售部与采购部缺货订单联合评审）'),
    -- 按业务文档扩展 12 条
    (0, (SELECT id FROM meta_standard_catalog WHERE tenant_id = 0 AND code = 'sc'),
     'sc.provides',      '提供',   'sc.Supplier',   'sc.Material',   'N:N',
     '供应商提供某物料（框架协议附件物料清单）'),
    (0, (SELECT id FROM meta_standard_catalog WHERE tenant_id = 0 AND code = 'sc'),
     'sc.stored_in',     '存储',   'sc.Material',   'sc.Warehouse',  'N:N',
     '物料按仓储作业规范存放于仓库'),
    (0, (SELECT id FROM meta_standard_catalog WHERE tenant_id = 0 AND code = 'sc'),
     'sc.order_by_cust', '下单',   'sc.Order',      'sc.Customer',   'N:1',
     '销售订单归属于下单客户（端点拆分：另一头见 sc.order_by_sup）'),
    (0, (SELECT id FROM meta_standard_catalog WHERE tenant_id = 0 AND code = 'sc'),
     'sc.order_by_sup',  '接单',   'sc.Order',      'sc.Supplier',   'N:1',
     '采购订单归属于承接供应商（端点拆分：另一头见 sc.order_by_cust）'),
    (0, (SELECT id FROM meta_standard_catalog WHERE tenant_id = 0 AND code = 'sc'),
     'sc.includes',      '包含',   'sc.Order',      'sc.Product',    'N:N',
     '订单明细包含某产品'),
    (0, (SELECT id FROM meta_standard_catalog WHERE tenant_id = 0 AND code = 'sc'),
     'sc.delivers_to',   '承运',   'sc.Logistics',  'sc.Warehouse',  'N:N',
     '物流运输/送达至仓库'),
    (0, (SELECT id FROM meta_standard_catalog WHERE tenant_id = 0 AND code = 'sc'),
     'sc.covers',        '覆盖',   'sc.Agreement',  'sc.Supplier',   'N:N',
     '框架协议覆盖的合作供应商（协议—客户方向复用同名关系，见 sc.covers_cust）'),
    (0, (SELECT id FROM meta_standard_catalog WHERE tenant_id = 0 AND code = 'sc'),
     'sc.covers_cust',   '覆盖',   'sc.Agreement',  'sc.Customer',   'N:N',
     '销售框架协议覆盖的客户'),
    (0, (SELECT id FROM meta_standard_catalog WHERE tenant_id = 0 AND code = 'sc'),
     'sc.triggers',      '引发风险', 'sc.Supplier',  'sc.RiskEvent',  'N:N',
     '供应商引发风险事件（断供等；物料/物流方向复用同名关系，见 sc.triggers_mat/logi）'),
    (0, (SELECT id FROM meta_standard_catalog WHERE tenant_id = 0 AND code = 'sc'),
     'sc.triggers_mat',  '引发风险', 'sc.Material',  'sc.RiskEvent',  'N:N',
     '物料引发风险事件（来料质量事故）'),
    (0, (SELECT id FROM meta_standard_catalog WHERE tenant_id = 0 AND code = 'sc'),
     'sc.triggers_logi', '引发风险', 'sc.Logistics', 'sc.RiskEvent',  'N:N',
     '物流环节引发风险事件（延迟交付）'),
    (0, (SELECT id FROM meta_standard_catalog WHERE tenant_id = 0 AND code = 'sc'),
     'sc.delivers_to_cust', '配送', 'sc.Logistics', 'sc.Customer',   'N:N',
     '物流将订单货物配送至客户')
) AS v(tenant_id, catalog_id, code, name, from_code, to_code, relation_type, description)
JOIN meta_object_standard AS fo
     ON fo.tenant_id = v.tenant_id AND fo.code = v.from_code
JOIN meta_object_standard AS t
     ON t.tenant_id = v.tenant_id AND t.code = v.to_code
ON CONFLICT (tenant_id, code) DO UPDATE SET
    catalog_id = EXCLUDED.catalog_id, name = EXCLUDED.name,
    from_object_id = EXCLUDED.from_object_id, to_object_id = EXCLUDED.to_object_id,
    relation_type = EXCLUDED.relation_type, description = EXCLUDED.description,
    status = EXCLUDED.status, updated_at = now();

COMMIT;

-- ---------- 验证 ----------
-- SELECT c.name AS catalog, o.code, o.name FROM meta_object_standard o
--   JOIN meta_standard_catalog c ON c.id = o.catalog_id
--   WHERE o.domain = 'supply_chain' ORDER BY o.code;
-- SELECT r.code, r.name, f.name AS "from", t.name AS "to", r.relation_type
--   FROM meta_object_relation r
--   JOIN meta_object_standard f ON f.id = r.from_object_id
--   JOIN meta_object_standard t ON t.id = r.to_object_id
--   WHERE r.code LIKE 'sc.%' ORDER BY r.code;
