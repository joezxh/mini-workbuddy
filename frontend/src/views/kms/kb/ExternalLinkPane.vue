<template>
  <a-card :title="t('kbMgmt.externalKb')" size="small">
    <a-empty :description="t('kbMgmt.externalPlaceholder')">
      <a-button type="primary" @click="$router.push('/admin?tab=kg-external-kb')">
        {{ t('kbMgmt.openExternalPanel') }}
      </a-button>
    </a-empty>
  </a-card>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
</script>
