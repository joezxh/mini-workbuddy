<script setup lang="ts">
// Recursive sidebar entry.
//
// A menu node with children renders as a collapsible group; a leaf renders as a
// nav item. The component recurses into itself to support arbitrary depth, which
// matches how `sys_menu.parent_id` is modelled. Clicking a leaf emits `select`
// with the resolved route path. Visual style follows the explorer "rail" skin.
import { computed, ref } from 'vue'
import type { MenuNode } from '@/types/menu'
import { resolveIcon } from '@/utils/icons'
import { localise } from '@/i18n'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'

const props = defineProps<{ node: MenuNode; collapsed?: boolean }>()
const emit = defineEmits<{ (e: 'select', path: string): void }>()

const route = useRoute()
const { t } = useI18n()
const open = ref(false)

/**
 * 展示文案：`titleKey` 走 vue-i18n（本地静态菜单），否则退回后端菜单自带的
 * `i18n` 语言映射。
 */
const label = computed(() =>
  props.node.titleKey ? String(t(props.node.titleKey)) : localise(props.node.i18n, props.node.name),
)

function isActive(node: MenuNode): boolean {
  if (node.path) return route.path === node.path || route.path.startsWith(node.path + '/')
  return false
}

function onLeafClick(node: MenuNode) {
  if (node.path) emit('select', node.path)
}

function onGroupClick() {
  if (props.collapsed) return
  open.value = !open.value
}
</script>

<template>
  <!-- Group with children -->
  <div v-if="node.children?.length" class="nav-group" :class="{ 'nav-group--open': open }">
    <button class="nav-row nav-row--group" :title="label" @click="onGroupClick">
      <span class="nav-ico"><component :is="resolveIcon(node.icon)" /></span>
      <span v-show="!collapsed" class="nav-label">{{ label }}</span>
      <span v-show="!collapsed" class="nav-caret">⌄</span>
    </button>
    <div v-show="open && !collapsed" class="nav-children">
      <SidebarItem
        v-for="child in node.children"
        :key="child.id"
        :node="child"
        :collapsed="collapsed"
        @select="(p) => emit('select', p)"
      />
    </div>
  </div>

  <!-- Leaf -->
  <button
    v-else
    class="nav-row nav-row--leaf"
    :class="{ 'nav-row--active': isActive(node) }"
    :title="label"
    @click="onLeafClick(node)"
  >
    <span class="nav-ico"><component :is="resolveIcon(node.icon)" /></span>
    <span v-show="!collapsed" class="nav-label">{{ label }}</span>
  </button>
</template>

<style scoped>
.nav-group {
  display: flex;
  flex-direction: column;
}

.nav-row {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  padding: 10px 12px;
  border: 0;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--fg-secondary);
  font-family: var(--font-sans);
  font-size: 14px;
  font-weight: 500;
  text-align: left;
  cursor: pointer;
  transition: color var(--transition), background-color var(--transition);
}

.nav-row:hover {
  color: var(--fg);
  background: var(--bg-hover);
}

.nav-row--active {
  color: var(--fg);
  background: var(--accent-soft);
  box-shadow: inset 3px 0 0 var(--accent);
}

.nav-row--active .nav-ico {
  color: var(--accent);
}

.nav-ico {
  flex: 0 0 20px;
  display: grid;
  place-items: center;
  font-size: 16px;
  color: inherit;
}

.nav-label {
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.nav-caret {
  font-size: 12px;
  color: var(--fg-muted);
  transition: transform var(--transition);
}

.nav-group--open .nav-caret {
  transform: rotate(180deg);
}

.nav-children {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 2px 0 2px 16px;
  margin-left: 16px;
  border-left: 1px solid var(--divider);
}

/* Collapsed rail: show icon-only, centered */
:global(.rail--collapsed) .nav-row {
  justify-content: center;
  padding: 10px 0;
}
</style>
