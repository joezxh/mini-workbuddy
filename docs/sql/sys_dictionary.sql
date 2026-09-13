/*
 Navicat Premium Dump SQL

 Source Server         : pgvector-localhost
 Source Server Type    : PostgreSQL
 Source Server Version : 170011 (170011)
 Source Host           : localhost:5432
 Source Catalog        : miniworkbuddy
 Source Schema         : public

 Target Server Type    : PostgreSQL
 Target Server Version : 170011 (170011)
 File Encoding         : 65001

 Date: 13/09/2026 16:03:22
*/


-- ----------------------------
-- Table structure for sys_dictionary
-- ----------------------------
DROP TABLE IF EXISTS "public"."sys_dictionary";
CREATE TABLE "public"."sys_dictionary" (
  "dict_id" int8 NOT NULL DEFAULT nextval('sys_dictionary_dict_id_seq'::regclass),
  "dict_code" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "dict_name" varchar(100) COLLATE "pg_catalog"."default" NOT NULL,
  "dict_type" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "description" text COLLATE "pg_catalog"."default",
  "sort_order" int4 DEFAULT 0,
  "is_active" bool NOT NULL DEFAULT true,
  "extra_data" jsonb,
  "created_by" int8,
  "created_at" timestamp(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updated_at" timestamp(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "is_deleted" bool NOT NULL DEFAULT false,
  "tenant_id" int8
)
;
COMMENT ON COLUMN "public"."sys_dictionary"."dict_id" IS '字典ID';
COMMENT ON COLUMN "public"."sys_dictionary"."dict_code" IS '字典编码';
COMMENT ON COLUMN "public"."sys_dictionary"."dict_name" IS '字典名称';
COMMENT ON COLUMN "public"."sys_dictionary"."dict_type" IS '字典类型';
COMMENT ON COLUMN "public"."sys_dictionary"."description" IS '字典描述';
COMMENT ON COLUMN "public"."sys_dictionary"."sort_order" IS '排序顺序';
COMMENT ON COLUMN "public"."sys_dictionary"."is_active" IS '是否启用';
COMMENT ON COLUMN "public"."sys_dictionary"."extra_data" IS '扩展数据';
COMMENT ON COLUMN "public"."sys_dictionary"."tenant_id" IS '租户ID';
COMMENT ON TABLE "public"."sys_dictionary" IS '系统字典表';

-- ----------------------------
-- Records of sys_dictionary
-- ----------------------------
INSERT INTO "public"."sys_dictionary" VALUES (5, 'source_type', '来源类型', 'business', '数据来源类型', 5, 'f', NULL, NULL, '2026-03-07 14:41:47.482381', '2026-03-07 14:41:47.482381', 'f', NULL);
INSERT INTO "public"."sys_dictionary" VALUES (8, 'tag', '标签', 'business', '事件和人员标签', 8, 'f', NULL, NULL, '2026-03-07 14:41:47.482381', '2026-03-07 14:41:47.482381', 'f', NULL);
INSERT INTO "public"."sys_dictionary" VALUES (91, 'audit_operation_module', '日志-操作模块', 'system', '系统审计日志的操作模块映射，对应各业务功能模块', 101, 'f', NULL, NULL, '2026-03-26 06:29:27.413877', '2026-03-26 06:56:54.412591', 'f', NULL);
INSERT INTO "public"."sys_dictionary" VALUES (90, 'audit_operation_type', '日志-操作类型', 'system', '系统审计日志的操作类型映射，用于仪表盘日志显示', 100, 'f', NULL, NULL, '2026-03-26 06:29:27.364697', '2026-03-26 06:57:00.534379', 'f', NULL);
INSERT INTO "public"."sys_dictionary" VALUES (126, 'agent_impl_type', '专家实现类型', 'system', '专家（Agent）技术实现类型', 11, 'f', NULL, NULL, '2026-07-16 20:07:21.152191', '2026-07-16 20:07:21.152191', 'f', NULL);
INSERT INTO "public"."sys_dictionary" VALUES (132, 'ontology_rel_type', '本体关系类型', 'ontology', 'UML 类图关系类型', 0, 'f', NULL, NULL, '2026-08-11 16:47:59.857638', '2026-08-11 16:47:59.857638', 'f', NULL);
INSERT INTO "public"."sys_dictionary" VALUES (133, 'kg_reasoning_exec_mode', '推理执行模式', 'system', '知识图谱推理规则执行模式（Skill/Tool/P1-P6 推理范式）', 20, 'f', NULL, NULL, '2026-08-13 22:42:34.260358', '2026-08-13 22:42:34.260358', 'f', NULL);
INSERT INTO "public"."sys_dictionary" VALUES (134, 'tool_type', '工具类型', 'system', 'AI工具管理-工具类型分类', 10, 'f', NULL, NULL, '2026-08-20 18:07:04.017625', '2026-08-20 18:07:04.017625', 'f', NULL);
INSERT INTO "public"."sys_dictionary" VALUES (135, 'web_search_platform', 'AI 联网搜索平台', 'business', '联网搜索供应商可选平台', 0, 'f', NULL, NULL, '2026-08-24 15:20:15.892423', '2026-08-24 15:20:15.892423', 'f', NULL);
INSERT INTO "public"."sys_dictionary" VALUES (123, 'skill_category', 'AI技能类目', 'config', 'AI技能包的分类，如论证分析、法律推理、文档处理等', 0, 'f', NULL, NULL, '2026-07-13 17:49:59.156076', '2026-07-13 17:49:59.156076', 'f', NULL);
INSERT INTO "public"."sys_dictionary" VALUES (136, 'model_type', '模型类型', 'system', '模型类型', 200, 'f', 'null', NULL, '2026-09-03 18:47:30.46293', '2026-09-13 15:59:17.985395', 'f', NULL);
INSERT INTO "public"."sys_dictionary" VALUES (124, 'agent_category', '专家用途分类', 'business', '专家（Agent）用途/业务领域分类', 10, 'f', NULL, NULL, '2026-07-16 19:52:43.902779', '2026-09-13 15:59:31.760586', 'f', NULL);
INSERT INTO "public"."sys_dictionary" VALUES (80, 'task_type', '任务类型', 'business', '调度任务的任务类型', 10, 'f', 'null', NULL, '2026-03-24 08:55:21.819685', '2026-09-13 15:59:43.373498', 'f', NULL);
INSERT INTO "public"."sys_dictionary" VALUES (6, 'dept_type', '部门类型', 'business', '来源部门类型', 6, 'f', NULL, NULL, '2026-03-07 14:41:47.482381', '2026-09-13 15:59:53.446382', 'f', NULL);
INSERT INTO "public"."sys_dictionary" VALUES (115, 'agent_type', 'Agent角色类型', 'business', '仿真中Agent的角色类型', 4, 'f', NULL, NULL, '2026-05-06 19:30:56.016168', '2026-09-13 16:00:02.502869', 'f', NULL);
INSERT INTO "public"."sys_dictionary" VALUES (81, 'report_type', 'AI报告类型', 'business', 'AI智能报告的类型分类', 1, 'f', NULL, NULL, '2026-03-25 06:07:13.806351', '2026-09-13 16:00:12.969898', 'f', NULL);
INSERT INTO "public"."sys_dictionary" VALUES (4, 'region', '行政区域', 'system', '行政区域划分', 120, 'f', NULL, NULL, '2026-03-07 14:41:47.482381', '2026-09-13 16:00:42.794339', 'f', NULL);
INSERT INTO "public"."sys_dictionary" VALUES (127, 'session_type', '会话类别', 'system', '会话类别', 160, 'f', 'null', NULL, '2026-07-25 19:54:19.175519', '2026-09-13 16:00:52.83128', 'f', NULL);

-- ----------------------------
-- Table structure for sys_dictionary_item
-- ----------------------------
DROP TABLE IF EXISTS "public"."sys_dictionary_item";
CREATE TABLE "public"."sys_dictionary_item" (
  "item_id" int8 NOT NULL DEFAULT nextval('sys_dictionary_item_item_id_seq'::regclass),
  "dict_code" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "item_code" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "item_name" varchar(100) COLLATE "pg_catalog"."default" NOT NULL,
  "item_value" varchar(200) COLLATE "pg_catalog"."default",
  "parent_code" varchar(50) COLLATE "pg_catalog"."default",
  "level" int4,
  "color" varchar(20) COLLATE "pg_catalog"."default",
  "icon" varchar(50) COLLATE "pg_catalog"."default",
  "sort_order" int4,
  "is_active" bool NOT NULL,
  "extra_data" json,
  "remark" text COLLATE "pg_catalog"."default",
  "created_by" int8,
  "created_at" timestamp(6) NOT NULL DEFAULT now(),
  "updated_at" timestamp(6) NOT NULL DEFAULT now(),
  "is_deleted" bool NOT NULL,
  "tenant_id" int8
)
;
COMMENT ON COLUMN "public"."sys_dictionary_item"."item_id" IS '字典项ID';
COMMENT ON COLUMN "public"."sys_dictionary_item"."dict_code" IS '所属字典编码';
COMMENT ON COLUMN "public"."sys_dictionary_item"."item_code" IS '字典项编码';
COMMENT ON COLUMN "public"."sys_dictionary_item"."item_name" IS '字典项名称';
COMMENT ON COLUMN "public"."sys_dictionary_item"."item_value" IS '字典项值';
COMMENT ON COLUMN "public"."sys_dictionary_item"."parent_code" IS '父级编码';
COMMENT ON COLUMN "public"."sys_dictionary_item"."level" IS '层级';
COMMENT ON COLUMN "public"."sys_dictionary_item"."color" IS '颜色标识';
COMMENT ON COLUMN "public"."sys_dictionary_item"."icon" IS '图标';
COMMENT ON COLUMN "public"."sys_dictionary_item"."sort_order" IS '排序顺序';
COMMENT ON COLUMN "public"."sys_dictionary_item"."is_active" IS '是否启用';
COMMENT ON COLUMN "public"."sys_dictionary_item"."extra_data" IS '扩展数据';
COMMENT ON COLUMN "public"."sys_dictionary_item"."remark" IS '备注';
COMMENT ON COLUMN "public"."sys_dictionary_item"."created_by" IS '创建人ID';
COMMENT ON COLUMN "public"."sys_dictionary_item"."tenant_id" IS '租户ID';
COMMENT ON TABLE "public"."sys_dictionary_item" IS '系统字典项表';

-- ----------------------------
-- Records of sys_dictionary_item
-- ----------------------------
INSERT INTO "public"."sys_dictionary_item" VALUES (872, 'model_type', '6', '向量排序模型', '6', NULL, 1, '#09fb31', '', 6, 'f', 'null', '向量排序模型', NULL, '2026-09-03 18:51:11.925408', '2026-09-13 15:58:58.451592', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (868, 'model_type', '1', '文本模型', '1', NULL, 1, '#0af038', '', 1, 'f', 'null', '文本模型', NULL, '2026-09-03 18:48:23.776542', '2026-09-13 15:59:02.17352', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (400, 'region', '330200', '宁波市', '330200', '330000', 2, NULL, NULL, 2, 'f', NULL, NULL, NULL, '2026-03-10 07:12:22.250029', '2026-03-15 14:28:00.752643', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (403, 'region', '330300', '温州市', '330300', '330000', 2, NULL, NULL, 3, 'f', NULL, NULL, NULL, '2026-03-10 07:12:22.250029', '2026-03-15 14:28:03.724358', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (409, 'region', '330500', '湖州市', '330500', '330000', 2, NULL, NULL, 5, 'f', NULL, NULL, NULL, '2026-03-10 07:12:22.250029', '2026-03-15 14:28:28.655162', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (406, 'region', '330400', '嘉兴市', '330400', '330000', 2, NULL, NULL, 4, 'f', NULL, NULL, NULL, '2026-03-10 07:12:22.250029', '2026-03-15 14:28:30.470621', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (410, 'region', '330502', '吴兴区', '330502', '330500', 3, NULL, NULL, 1, 'f', NULL, NULL, NULL, '2026-03-10 07:12:22.250029', '2026-03-15 14:28:33.598947', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (396, 'region', '330000', '浙江省', '330000', NULL, 1, NULL, NULL, 1, 'f', NULL, NULL, NULL, '2026-03-10 07:12:22.250029', '2026-03-15 14:29:21.252077', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (397, 'region', '330100', '杭州市', '330100', '330000', 2, NULL, NULL, 1, 'f', NULL, NULL, NULL, '2026-03-10 07:12:22.250029', '2026-03-15 14:29:23.302803', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (398, 'region', '330106', '西湖区', '330106', '330100', 3, NULL, NULL, 1, 'f', NULL, NULL, NULL, '2026-03-10 07:12:22.250029', '2026-03-15 14:29:26.128346', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (399, 'region', '330106001', '北山街道', '330106001', '330106', 4, NULL, NULL, 1, 'f', NULL, NULL, NULL, '2026-03-10 07:12:22.250029', '2026-03-15 14:29:28.361148', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (401, 'region', '330206', '海曙区', '330206', '330200', 3, NULL, NULL, 1, 'f', NULL, NULL, NULL, '2026-03-10 07:12:22.250029', '2026-03-15 14:29:40.984277', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (402, 'region', '330206001', '白云街道', '330206001', '330206', 4, NULL, NULL, 1, 'f', NULL, NULL, NULL, '2026-03-10 07:12:22.250029', '2026-03-15 14:29:42.80259', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (404, 'region', '330302', '鹿城区', '330302', '330300', 3, NULL, NULL, 1, 'f', NULL, NULL, NULL, '2026-03-10 07:12:22.250029', '2026-03-15 14:29:44.701156', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (405, 'region', '330302001', '五马街道', '330302001', '330302', 4, NULL, NULL, 1, 'f', NULL, NULL, NULL, '2026-03-10 07:12:22.250029', '2026-03-15 14:29:46.593678', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (407, 'region', '330402', '南湖区', '330402', '330400', 3, NULL, NULL, 1, 'f', NULL, NULL, NULL, '2026-03-10 07:12:22.250029', '2026-03-15 14:29:48.368129', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (408, 'region', '330402001', '新嘉街道', '330402001', '330402', 4, NULL, NULL, 1, 'f', NULL, NULL, NULL, '2026-03-10 07:12:22.250029', '2026-03-15 14:29:50.639923', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (33, 'source_type', 'manual', '手动录入', 'manual', NULL, 1, NULL, NULL, 1, 'f', NULL, NULL, NULL, '2026-03-07 14:41:47.482381', '2026-03-08 05:29:35.783014', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (34, 'source_type', 'import', '批量导入', 'import', NULL, 1, NULL, NULL, 2, 'f', NULL, NULL, NULL, '2026-03-07 14:41:47.482381', '2026-03-08 05:29:36.357494', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (35, 'source_type', 'api', 'API接入', 'api', NULL, 1, NULL, NULL, 3, 'f', NULL, NULL, NULL, '2026-03-07 14:41:47.482381', '2026-03-08 05:29:36.88575', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (36, 'source_type', 'sync', '数据同步', 'sync', NULL, 1, NULL, NULL, 4, 'f', NULL, NULL, NULL, '2026-03-07 14:41:47.482381', '2026-03-08 05:29:37.407249', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (37, 'source_type', 'crawler', '爬虫采集', 'crawler', NULL, 1, NULL, NULL, 5, 'f', NULL, NULL, NULL, '2026-03-07 14:41:47.482381', '2026-03-08 05:29:38.381007', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (54, 'tag', 'urgent', '紧急', 'urgent', NULL, 1, '#f5222d', NULL, 1, 'f', NULL, NULL, NULL, '2026-03-07 14:41:47.482381', '2026-03-08 05:29:53.630597', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (55, 'tag', 'important', '重要', 'important', NULL, 1, '#fa8c16', NULL, 2, 'f', NULL, NULL, NULL, '2026-03-07 14:41:47.482381', '2026-03-08 05:29:55.06883', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (58, 'tag', 'repeat', '重复', 'repeat', NULL, 1, '#faad14', NULL, 5, 'f', NULL, NULL, NULL, '2026-03-07 14:41:47.482381', '2026-03-08 05:29:56.685079', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (60, 'tag', 'media_attention', '媒体关注', 'media_attention', NULL, 1, '#1890ff', NULL, 7, 'f', NULL, NULL, NULL, '2026-03-07 14:41:47.482381', '2026-03-08 05:29:57.654143', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (492, 'task_type', 'report', '报表生成', '报表生成', NULL, 1, '#2889f0', '', 0, 'f', 'null', '', NULL, '2026-03-24 09:16:45.446621', '2026-03-24 09:17:19.893073', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (497, 'task_type', 'migration', '数据迁移', '数据迁移', NULL, 1, '#f4c2c2', '', 6, 'f', 'null', '数据迁移', NULL, '2026-03-24 09:18:36.746462', '2026-03-24 09:18:36.746462', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (501, 'report_type', 'custom', '自定义报告', 'custom', NULL, 1, 'default', NULL, 40, 'f', NULL, NULL, NULL, '2026-03-25 06:07:13.829743', '2026-03-25 06:07:13.829743', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (418, 'region', '330800', '衢州市', '330800', '330000', 2, NULL, NULL, 8, 'f', NULL, NULL, NULL, '2026-03-10 07:12:22.250029', '2026-03-15 14:27:48.585408', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (427, 'region', '331100', '丽水市', '331100', '330000', 2, NULL, NULL, 11, 'f', NULL, NULL, NULL, '2026-03-10 07:12:22.250029', '2026-03-15 14:27:27.250856', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (424, 'region', '331000', '台州市', '331000', '330000', 2, NULL, NULL, 10, 'f', NULL, NULL, NULL, '2026-03-10 07:12:22.250029', '2026-03-15 14:27:44.590585', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (421, 'region', '330900', '舟山市', '330900', '330000', 2, NULL, NULL, 9, 'f', NULL, NULL, NULL, '2026-03-10 07:12:22.250029', '2026-03-15 14:27:46.649877', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (425, 'region', '331002', '椒江区', '331002', '331000', 3, NULL, NULL, 1, 'f', NULL, NULL, NULL, '2026-03-10 07:12:22.250029', '2026-03-15 14:27:51.63445', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (426, 'region', '331002001', '海门街道', '331002001', '331002', 4, NULL, NULL, 1, 'f', NULL, NULL, NULL, '2026-03-10 07:12:22.250029', '2026-03-15 14:27:54.473214', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (428, 'region', '331102', '莲都区', '331102', '331100', 3, NULL, NULL, 1, 'f', NULL, NULL, NULL, '2026-03-10 07:12:22.250029', '2026-03-15 14:27:56.520232', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (429, 'region', '331102001', '紫金街道', '331102001', '331102', 4, NULL, NULL, 1, 'f', NULL, NULL, NULL, '2026-03-10 07:12:22.250029', '2026-03-15 14:27:58.310003', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (415, 'region', '330700', '金华市', '330700', '330000', 2, NULL, NULL, 7, 'f', NULL, NULL, NULL, '2026-03-10 07:12:22.250029', '2026-03-15 14:28:24.253307', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (412, 'region', '330600', '绍兴市', '330600', '330000', 2, NULL, NULL, 6, 'f', NULL, NULL, NULL, '2026-03-10 07:12:22.250029', '2026-03-15 14:28:26.76365', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (411, 'region', '330502001', '月河街道', '330502001', '330502', 4, NULL, NULL, 1, 'f', NULL, NULL, NULL, '2026-03-10 07:12:22.250029', '2026-03-15 14:28:35.534235', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (423, 'region', '330902001', '昌国街道', '330902001', '330902', 4, NULL, NULL, 1, 'f', NULL, NULL, NULL, '2026-03-10 07:12:22.250029', '2026-03-15 14:29:05.016863', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (500, 'report_type', 'trend_forecast', '金融预测报告', 'trend_forecast', NULL, 1, 'purple', '', 30, 'f', NULL, '', NULL, '2026-03-25 06:07:13.829743', '2026-09-13 15:37:27.457003', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (498, 'report_type', 'disposal_analysis', '金融分析报表', 'statistics_analysis', NULL, 1, 'blue', '', 10, 'f', NULL, '', NULL, '2026-03-25 06:07:13.829743', '2026-09-13 15:37:37.193598', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (422, 'region', '330902', '定海区', '330902', '330900', 3, NULL, NULL, 1, 'f', NULL, NULL, NULL, '2026-03-10 07:12:22.250029', '2026-03-15 14:29:06.661638', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (420, 'region', '330802001', '府山街道', '330802001', '330802', 4, NULL, NULL, 1, 'f', NULL, NULL, NULL, '2026-03-10 07:12:22.250029', '2026-03-15 14:29:08.222388', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (419, 'region', '330802', '柯城区', '330802', '330800', 3, NULL, NULL, 1, 'f', NULL, NULL, NULL, '2026-03-10 07:12:22.250029', '2026-03-15 14:29:09.820634', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (417, 'region', '330702001', '城东街道', '330702001', '330702', 4, NULL, NULL, 1, 'f', NULL, NULL, NULL, '2026-03-10 07:12:22.250029', '2026-03-15 14:29:11.580468', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (416, 'region', '330702', '婺城区', '330702', '330700', 3, NULL, NULL, 1, 'f', NULL, NULL, NULL, '2026-03-10 07:12:22.250029', '2026-03-15 14:29:14.111021', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (414, 'region', '330602001', '府山街道', '330602001', '330602', 4, NULL, NULL, 1, 'f', NULL, NULL, NULL, '2026-03-10 07:12:22.250029', '2026-03-15 14:29:15.995185', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (413, 'region', '330602', '越城区', '330602', '330600', 3, NULL, NULL, 1, 'f', NULL, NULL, NULL, '2026-03-10 07:12:22.250029', '2026-03-15 14:29:17.955961', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (870, 'model_type', '3', '视频生成', '3', NULL, 1, '#f70808', '', 3, 'f', 'null', '视频生成', NULL, '2026-09-03 18:49:20.695152', '2026-09-13 15:59:00.798713', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (540, 'audit_operation_type', 'login', '登录', 'login', NULL, 1, 'cyan', NULL, 10, 'f', NULL, NULL, NULL, '2026-03-26 06:29:27.402017', '2026-03-26 06:29:27.402017', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (541, 'audit_operation_type', 'logout', '登出', 'logout', NULL, 1, 'orange', NULL, 20, 'f', NULL, NULL, NULL, '2026-03-26 06:29:27.402017', '2026-03-26 06:29:27.402017', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (542, 'audit_operation_type', 'create', '创建', 'create', NULL, 1, 'green', NULL, 30, 'f', NULL, NULL, NULL, '2026-03-26 06:29:27.402017', '2026-03-26 06:29:27.402017', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (543, 'audit_operation_type', 'update', '更新', 'update', NULL, 1, 'blue', NULL, 40, 'f', NULL, NULL, NULL, '2026-03-26 06:29:27.402017', '2026-03-26 06:29:27.402017', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (544, 'audit_operation_type', 'delete', '删除', 'delete', NULL, 1, 'red', NULL, 50, 'f', NULL, NULL, NULL, '2026-03-26 06:29:27.402017', '2026-03-26 06:29:27.402017', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (545, 'audit_operation_type', 'query', '查询', 'query', NULL, 1, 'default', NULL, 60, 'f', NULL, NULL, NULL, '2026-03-26 06:29:27.402017', '2026-03-26 06:29:27.402017', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (546, 'audit_operation_type', 'export', '导出', 'export', NULL, 1, 'purple', NULL, 70, 'f', NULL, NULL, NULL, '2026-03-26 06:29:27.402017', '2026-03-26 06:29:27.402017', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (547, 'audit_operation_type', 'import', '导入', 'import', NULL, 1, 'geekblue', NULL, 80, 'f', NULL, NULL, NULL, '2026-03-26 06:29:27.402017', '2026-03-26 06:29:27.402017', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (548, 'audit_operation_type', 'upload', '上传', 'upload', NULL, 1, 'lime', NULL, 90, 'f', NULL, NULL, NULL, '2026-03-26 06:29:27.402017', '2026-03-26 06:29:27.402017', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (549, 'audit_operation_type', 'analyze', 'AI分析', 'analyze', NULL, 1, 'magenta', NULL, 100, 'f', NULL, NULL, NULL, '2026-03-26 06:29:27.402017', '2026-03-26 06:29:27.402017', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (550, 'audit_operation_module', 'auth', '身份认证', 'auth', NULL, 1, NULL, NULL, 10, 'f', NULL, NULL, NULL, '2026-03-26 06:29:27.455435', '2026-03-26 06:29:27.455435', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (551, 'audit_operation_module', 'user', '用户管理', 'user', NULL, 1, NULL, NULL, 20, 'f', NULL, NULL, NULL, '2026-03-26 06:29:27.455435', '2026-03-26 06:29:27.455435', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (552, 'audit_operation_module', 'role', '角色管理', 'role', NULL, 1, NULL, NULL, 30, 'f', NULL, NULL, NULL, '2026-03-26 06:29:27.455435', '2026-03-26 06:29:27.455435', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (553, 'audit_operation_module', 'permission', '权限管理', 'permission', NULL, 1, NULL, NULL, 40, 'f', NULL, NULL, NULL, '2026-03-26 06:29:27.455435', '2026-03-26 06:29:27.455435', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (561, 'audit_operation_module', 'report', 'AI报告', 'report', NULL, 1, NULL, NULL, 120, 'f', NULL, NULL, NULL, '2026-03-26 06:29:27.455435', '2026-03-26 06:29:27.455435', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (562, 'audit_operation_module', 'dictionary', '字典管理', 'dictionary', NULL, 1, NULL, NULL, 130, 'f', NULL, NULL, NULL, '2026-03-26 06:29:27.455435', '2026-03-26 06:29:27.455435', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (563, 'audit_operation_module', 'migration', '数据迁移', 'migration', NULL, 1, NULL, NULL, 140, 'f', NULL, NULL, NULL, '2026-03-26 06:29:27.455435', '2026-03-26 06:29:27.455435', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (564, 'audit_operation_module', 'system', '系统设置', 'system', NULL, 1, NULL, NULL, 150, 'f', NULL, NULL, NULL, '2026-03-26 06:29:27.455435', '2026-03-26 06:29:27.455435', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (565, 'audit_operation_module', 'dws', '源数据浏览', 'dws', NULL, 1, NULL, NULL, 160, 'f', NULL, NULL, NULL, '2026-03-26 06:29:27.455435', '2026-03-26 06:29:27.455435', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (566, 'audit_operation_module', 'search', '全局搜索', 'search', NULL, 1, NULL, NULL, 170, 'f', NULL, NULL, NULL, '2026-03-26 06:29:27.455435', '2026-03-26 06:29:27.455435', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (567, 'audit_operation_module', 'graph', '关系图谱', 'graph', NULL, 1, NULL, NULL, 180, 'f', NULL, NULL, NULL, '2026-03-26 06:29:27.455435', '2026-03-26 06:29:27.455435', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (568, 'audit_operation_module', 'ai_assistant', 'AI助手', 'ai_assistant', NULL, 1, NULL, NULL, 190, 'f', NULL, NULL, NULL, '2026-03-26 06:29:27.455435', '2026-03-26 06:29:27.455435', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (839, 'ontology_rel_type', 'aggregation', '聚合', 'aggregation', NULL, 1, NULL, NULL, 4, 'f', NULL, NULL, NULL, '2026-08-11 16:47:59.857638', '2026-08-11 16:47:59.857638', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (857, 'web_search_platform', 'bocha', '博查搜索', 'bocha', NULL, 1, 'blue', NULL, 1, 'f', NULL, NULL, NULL, '2026-08-24 15:20:15.908563', '2026-08-24 15:20:15.908563', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (858, 'web_search_platform', 'anspire', 'Anspire', 'anspire', NULL, 1, 'cyan', NULL, 2, 'f', NULL, NULL, NULL, '2026-08-24 15:20:15.908563', '2026-08-24 15:20:15.908563', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (859, 'web_search_platform', 'google', 'Google', 'google', NULL, 1, 'red', NULL, 3, 'f', NULL, NULL, NULL, '2026-08-24 15:20:15.908563', '2026-08-24 15:20:15.908563', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (860, 'web_search_platform', 'bing', 'Bing', 'bing', NULL, 1, 'green', NULL, 4, 'f', NULL, NULL, NULL, '2026-08-24 15:20:15.908563', '2026-08-24 15:20:15.908563', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (861, 'web_search_platform', 'custom', '自定义平台', 'custom', NULL, 1, 'default', NULL, 5, 'f', NULL, NULL, NULL, '2026-08-24 15:20:15.908563', '2026-08-24 15:20:15.908563', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (853, 'tool_type', 'group', '分组', 'group', NULL, 1, 'cyan', NULL, 40, 'f', NULL, '工具分组', NULL, '2026-08-20 18:07:04.017625', '2026-08-20 18:07:04.017625', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (690, 'agent_type', 'simulator', '模拟引擎', 'simulator', NULL, 1, 'magenta', NULL, 70, 'f', NULL, '系统模拟引擎（非人员角色）', NULL, '2026-05-06 19:30:56.057399', '2026-05-06 19:30:56.057399', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (840, 'ontology_rel_type', 'composition', '组合', 'composition', NULL, 1, NULL, NULL, 5, 'f', NULL, NULL, NULL, '2026-08-11 16:47:59.857638', '2026-08-11 16:47:59.857638', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (836, 'ontology_rel_type', 'inheritance', '继承', 'inheritance', NULL, 1, NULL, NULL, 1, 'f', NULL, NULL, NULL, '2026-08-11 16:47:59.857638', '2026-08-11 16:47:59.857638', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (837, 'ontology_rel_type', 'implementation', '实现', 'implementation', NULL, 1, NULL, NULL, 2, 'f', NULL, NULL, NULL, '2026-08-11 16:47:59.857638', '2026-08-11 16:47:59.857638', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (838, 'ontology_rel_type', 'association', '关联', 'association', NULL, 1, NULL, NULL, 3, 'f', NULL, NULL, NULL, '2026-08-11 16:47:59.857638', '2026-08-11 16:47:59.857638', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (841, 'ontology_rel_type', 'dependency', '依赖', 'dependency', NULL, 1, NULL, NULL, 6, 'f', NULL, NULL, NULL, '2026-08-11 16:47:59.857638', '2026-08-11 16:47:59.857638', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (862, 'web_search_platform', 'baidu', '百度', 'baidu', NULL, 1, '#99a30f', '', 5, 'f', 'null', '百度', NULL, '2026-08-24 15:21:42.793416', '2026-08-24 15:21:42.793416', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (871, 'model_type', '5', '向量化模型', '5', NULL, 1, '#0a06f9', '', 5, 'f', 'null', '向量化模型', NULL, '2026-09-03 18:50:51.112515', '2026-09-13 15:58:59.247914', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (796, 'agent_impl_type', 'WORKFLOW', '工作流型', 'WORKFLOW', NULL, 1, 'purple', '', 20, 'f', NULL, '适用于执行 Dify 工作流，可配置输入输出映射', NULL, '2026-07-16 20:07:21.157903', '2026-07-16 20:14:02.190974', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (795, 'agent_impl_type', 'CHAT', '会话型', 'CHAT', NULL, 1, 'blue', '', 10, 'f', NULL, '适用于通用对话，支持 LLM 调用与工具集成', NULL, '2026-07-16 20:07:21.157903', '2026-07-16 20:14:07.870383', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (797, 'agent_impl_type', 'SKILL', '技能型', 'SKILL', NULL, 1, 'green', '', 30, 'f', NULL, '适用于调用技能包，支持规则引擎自动触发', NULL, '2026-07-16 20:07:21.157903', '2026-07-16 20:14:14.795326', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (785, 'agent_category', 'legal_consult', '法律处理', 'legal_consult', NULL, 1, 'orange', '', 20, 'f', NULL, '', NULL, '2026-07-16 19:52:43.917504', '2026-07-16 20:14:29.238758', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (790, 'agent_category', 'general', '通用助手', 'general', NULL, 1, 'default', '', 70, 'f', NULL, '', NULL, '2026-07-16 19:52:43.917504', '2026-07-16 20:14:52.419216', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (791, 'agent_category', 'other', '其他', 'other', NULL, 1, 'default', '', 99, 'f', NULL, '', NULL, '2026-07-16 19:52:43.917504', '2026-07-16 20:14:56.249993', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (842, 'kg_reasoning_exec_mode', 'skill', 'Skill（LLM 执行）', 'skill', NULL, 1, 'purple', 'robot', 10, 'f', NULL, '通过 SkillExecutionService 调用 LLM 技能执行', NULL, '2026-08-13 22:42:34.310695', '2026-08-13 22:42:34.310695', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (873, 'model_type', '4', '多模态理解', '4', NULL, 1, '#f80d0d', '', 4, 'f', 'null', '多模态理解', NULL, '2026-09-03 18:51:37.996039', '2026-09-13 15:58:59.943183', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (869, 'model_type', '2', '图形生成', '2', NULL, 1, '#e0d910', '', 2, 'f', 'null', '图形生成', NULL, '2026-09-03 18:48:51.679812', '2026-09-13 15:59:01.542972', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (784, 'agent_category', 'event_analysis', '事件分析', 'event_analysis', NULL, 1, 'red', '', 10, 'f', NULL, '', NULL, '2026-07-16 19:52:43.917504', '2026-09-13 15:59:36.057253', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (843, 'kg_reasoning_exec_mode', 'tool', 'Tool（MCP Tool 直调）', 'tool', NULL, 1, 'cyan', 'tool', 20, 'f', NULL, '通过 MCP Tool 直调执行', NULL, '2026-08-13 22:42:34.310695', '2026-08-13 22:42:34.310695', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (848, 'kg_reasoning_exec_mode', 'bayesian', 'Bayesian（贝叶斯）', 'bayesian', NULL, 1, 'orange', 'experiment', 70, 'f', NULL, '贝叶斯推理范式', NULL, '2026-08-13 22:42:34.310695', '2026-08-13 22:42:34.310695', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (849, 'kg_reasoning_exec_mode', 'fusion', 'Fusion（多范式融合）', 'fusion', NULL, 1, 'red', 'deployment', 80, 'f', NULL, '多范式融合推理范式', NULL, '2026-08-13 22:42:34.310695', '2026-08-13 22:42:34.310695', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (847, 'kg_reasoning_exec_mode', 'fuzzy', 'Fuzzy（模糊推理）', 'fuzzy', NULL, 1, 'orange', 'thunderbolt', 60, 'f', NULL, '模糊推理范式', NULL, '2026-08-13 22:42:34.310695', '2026-08-14 10:21:46.39085', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (846, 'kg_reasoning_exec_mode', 'sparql', 'SPARQL（图查询）', 'sparql', NULL, 1, 'blue', 'share-alt', 50, 'f', NULL, 'SPARQL 图查询推理范式', NULL, '2026-08-13 22:42:34.310695', '2026-08-14 10:21:36.023456', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (845, 'kg_reasoning_exec_mode', 'prolog', 'Prolog（逻辑编程）', 'prolog', NULL, 1, 'blue', 'code', 40, 'f', NULL, 'Prolog 逻辑编程推理范式', NULL, '2026-08-13 22:42:34.310695', '2026-08-14 10:20:54.607057', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (844, 'kg_reasoning_exec_mode', 'owl', 'OWL（描述逻辑）', 'owl', NULL, 1, 'blue', 'branches', 30, 'f', NULL, 'OWL 描述逻辑推理范式', NULL, '2026-08-13 22:42:34.310695', '2026-08-14 10:20:45.202335', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (863, 'web_search_platform', 'tavily', 'Tavily', 'tavily', NULL, 1, 'purple', 'robot', 60, 'f', NULL, '面向 LLM 的检索 API，Bearer 鉴权', NULL, '2026-08-24 15:35:59.253789', '2026-08-24 15:35:59.253789', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (864, 'web_search_platform', 'exa', 'Exa', 'exa', NULL, 1, 'magenta', 'thunderbolt', 70, 'f', NULL, '神经/嵌入搜索 API，Bearer 鉴权', NULL, '2026-08-24 15:35:59.253789', '2026-08-24 15:35:59.253789', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (865, 'web_search_platform', 'firecrawl', 'Firecrawl', 'firecrawl', NULL, 1, 'volcano', 'cloud', 80, 'f', NULL, '自托管或 SaaS，统一 /v1/search，可免 Key', NULL, '2026-08-24 15:35:59.253789', '2026-08-24 15:35:59.253789', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (866, 'web_search_platform', 'searxng', 'SearXNG', 'searxng', NULL, 1, 'gold', 'fork', 90, 'f', NULL, '自托管元搜索引擎，GET /search?format=json', NULL, '2026-08-24 15:35:59.253789', '2026-08-24 15:35:59.253789', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (850, 'tool_type', 'custom', '自定义', 'custom', NULL, 1, 'default', NULL, 10, 'f', NULL, '用户自定义工具', NULL, '2026-08-20 18:07:04.017625', '2026-08-20 18:07:04.017625', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (851, 'tool_type', 'skill', '技能', 'skill', NULL, 1, 'blue', NULL, 20, 'f', NULL, '技能类型工具', NULL, '2026-08-20 18:07:04.017625', '2026-08-20 18:07:04.017625', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (852, 'tool_type', 'mcp', 'MCP', 'mcp', NULL, 1, 'purple', NULL, 30, 'f', NULL, 'MCP协议工具', NULL, '2026-08-20 18:07:04.017625', '2026-08-20 18:07:04.017625', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (798, 'session_type', 'general', '通用对话', 'general', NULL, 1, '#8ae5db', '', 1, 'f', 'null', '通用对话，使用LLM直接调用', NULL, '2026-07-25 19:56:02.887205', '2026-09-13 15:36:59.98139', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (801, 'session_type', 'skill', '技能', 'skill', NULL, 1, 'green', NULL, 4, 'f', NULL, NULL, NULL, '2026-07-25 20:02:15.099158', '2026-09-13 15:37:03.332918', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (803, 'session_type', 'deep_research', '深度研究', 'deep_research', NULL, 1, '#05fa09', 'SearchOutlined', 60, 'f', NULL, '', NULL, '2026-07-29 14:08:01.977271', '2026-09-13 15:38:35.3641', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (804, 'session_type', 'agent', '智能体', 'agent', NULL, 1, 'green', 'RobotOutlined', 70, 'f', NULL, NULL, NULL, '2026-07-29 14:08:01.977271', '2026-09-13 15:37:08.097456', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (805, 'session_type', 'team', '智能体团队', 'team', NULL, 1, 'purple', 'TeamOutlined', 80, 'f', NULL, NULL, NULL, '2026-07-29 14:08:01.977271', '2026-09-13 15:37:08.79289', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (802, 'session_type', 'thinking', '深度思考', 'thinking', NULL, 1, '#0c08f7', 'BulbOutlined', 50, 'f', NULL, '', NULL, '2026-07-29 14:08:01.977271', '2026-09-13 15:38:26.841048', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (800, 'session_type', 'data', 'NL2SQL', 'nl2sql', NULL, 1, '#caee17', '', 3, 'f', 'null', '数据分析', NULL, '2026-07-25 19:57:32.274971', '2026-09-13 15:39:07.028203', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (799, 'session_type', 'legal_consult', '法律咨询', 'legal_consult', NULL, 1, '#2ce713', '', 2, 'f', 'null', '纠纷调解', NULL, '2026-07-25 19:56:25.478394', '2026-09-13 15:36:57.239582', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (854, 'tool_type', 'sqlbot', 'SQLBot', 'sqlbot', NULL, 1, 'orange', NULL, 50, 'f', NULL, 'NL2SQL查询工具', NULL, '2026-08-20 18:07:04.017625', '2026-08-20 18:07:04.017625', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (855, 'tool_type', 'agentscope_builtin', 'AgentScope内置', 'agentscope_builtin', NULL, 1, 'geekblue', NULL, 60, 'f', NULL, 'AgentScope 2.0.6 SDK内置工具', NULL, '2026-08-20 18:07:04.017625', '2026-08-20 18:07:04.017625', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (856, 'tool_type', 'custom_dev', '自定义开发', 'custom_dev', NULL, 1, 'green', NULL, 70, 'f', NULL, '项目自定义开发的工具', NULL, '2026-08-20 18:07:04.017625', '2026-08-20 18:07:04.017625', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (831, 'skill_category', 'ai-skill', 'AI/Skill治理', 'ai-skill', NULL, 1, '#2f54eb', 'robot', 31, 'f', NULL, NULL, NULL, '2026-08-05 17:56:51.084964', '2026-08-05 17:56:51.084964', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (2, 'model_type', '8', '语音识别', '8', NULL, NULL, '#0f0bf9', '', 8, 'f', NULL, '', NULL, '2026-09-12 21:10:56.934428', '2026-09-13 15:58:56.304722', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (1, 'model_type', '7', '语音合成', '7', NULL, NULL, '#dffb09', '', 7, 'f', NULL, '', NULL, '2026-09-12 21:10:56.934428', '2026-09-13 15:58:57.689318', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (776, 'skill_category', 'other', '其他', 'other', NULL, 1, '#8c8c8c', 'appstore', 99, 'f', NULL, '未分类或其他类型的技能', NULL, '2026-07-13 17:49:59.179102', '2026-07-30 17:14:44.69585', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (835, 'session_type', 'scheduled', '云端调度', 'scheduled', NULL, 1, '#06f90a', '', 90, 'f', 'null', '云端调度', NULL, '2026-08-06 21:07:12.653836', '2026-09-13 15:37:09.796131', 'f', NULL);
INSERT INTO "public"."sys_dictionary_item" VALUES (834, 'skill_category', 'monitoring', '监测与知识运营', '舆情联动与企业信用核查类技能', NULL, 1, '#722ed1', 'radar', 34, 'f', NULL, '', NULL, '2026-08-05 17:56:51.104772', '2026-09-13 15:38:09.669931', 'f', NULL);
