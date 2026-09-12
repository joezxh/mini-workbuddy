-- ============================================================
-- 修复「私有知识库」菜单：path 误写为 vue 文件路径导致点击落到控制台首页且无 Tab
--
-- 根因：app/routers/auth.py 中菜单序列化
--   "permissionCode": m.path,
--   "menuKey": m.path.rstrip('/').split('/')[-1]
-- 若 sys_menu.path = '/views/kms/wiki/index.vue'，则 menuKey = 'index.vue'，
-- componentMap['index.vue'] 不存在 → 无 Tab；且侧栏 onSelect 正则 ^/admin/([^/]+)
-- 匹配不到，router.push 该非法路径 → 被 catch-all 重定向到 /dashboard。
--
-- 修正：path 改为 /admin/kg-private-kb，menuKey 即 'kg-private-kb'，
-- 与 frontend/src/views/admin/componentMap.ts 中
--   'kg-private-kb': PrivateKbWiki
-- 对齐，点击即在控制台以 Tab 打开 Wiki 组件。
-- ============================================================

-- 1) 修正 path（component 列在 Tab 机制中未被使用，保留仅作信息）
UPDATE "public"."sys_menu"
SET path = '/admin/kg-private-kb',
    component = '/views/kms/wiki/index.vue'
WHERE i18n_key = 'knowledge.menu.private.knowledge'
  AND path = '/views/kms/wiki/index.vue';

-- 2) 若 i18n_key 尚未登记，确保多语言文案存在（示例：zh-CN / en-US）
--    文案请按实际 i18n 资源文件补充；此处仅校验键已存在。
--    缺失时可在前端 src/i18n/locales/*.ts 的 knowledge.menu 下补：
--      private: { knowledge: '私有知识库' }   // zh-CN
--      private: { knowledge: 'Private Knowledge Base' } // en-US
