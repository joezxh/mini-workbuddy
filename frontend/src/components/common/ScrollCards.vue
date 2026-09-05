/**
 * 横向滚动卡片组件
 */
<template>
  <div class="scroll-cards">
    <div class="scroll-cards__container" ref="containerRef">
      <div class="scroll-cards__wrapper" :style="wrapperStyle">
        <div
          v-for="(item, index) in displayItems"
          :key="index"
          class="scroll-cards__item"
          @click="handleItemClick(item)"
        >
          <slot :item="item" :index="index"></slot>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'

interface Props {
  items: any[]
  speed?: number
  gap?: number
}

const props = withDefaults(defineProps<Props>(), {
  speed: 30,
  gap: 16
})

const emit = defineEmits<{
  itemClick: [item: any]
}>()

const containerRef = ref<HTMLElement>()
const offset = ref(0)
let animationId: number

const displayItems = computed(() => {
  // 复制一份数据用于无缝滚动
  return [...props.items, ...props.items]
})

const wrapperStyle = computed(() => ({
  transform: `translateX(-${offset.value}px)`,
  gap: `${props.gap}px`
}))

const handleItemClick = (item: any) => {
  emit('itemClick', item)
}

const startAnimation = () => {
  const animate = () => {
    offset.value += 1
    
    // 当滚动到一半时重置
    const itemWidth = 200 + props.gap
    const halfWidth = props.items.length * itemWidth
    
    if (offset.value >= halfWidth) {
      offset.value = 0
    }
    
    animationId = requestAnimationFrame(animate)
  }
  
  animationId = requestAnimationFrame(animate)
}

onMounted(() => {
  startAnimation()
})

onUnmounted(() => {
  if (animationId) {
    cancelAnimationFrame(animationId)
  }
})
</script>

<style lang="less" scoped>
.scroll-cards {
  width: 100%;
  overflow: hidden;

  &__container {
    width: 100%;
    overflow: hidden;
  }

  &__wrapper {
    display: flex;
    transition: transform 0.1s linear;
  }

  &__item {
    flex-shrink: 0;
    width: 200px;
    cursor: pointer;
    transition: transform 0.3s ease;

    &:hover {
      transform: scale(1.05);
    }
  }
}
</style>

