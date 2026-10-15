<template>
  <div class="resource-card">
    <span class="resource-badge"><el-icon><Box /></el-icon> 虚拟资源</span>
    <div class="name">{{ resource.name }}</div>
    <div class="desc">{{ resource.description || '暂无资源介绍' }}</div>
    <div class="card-actions">
      <el-button tag="a" :href="resource.purchase_url" target="_blank" rel="noopener">
        <el-icon style="margin-right: 4px"><ShoppingCart /></el-icon>前往购买
      </el-button>
      <el-button type="primary" :plain="resource.unlocked" @click="$emit('unlock', resource)">
        <el-icon style="margin-right: 4px"><View /></el-icon>{{ resource.unlocked ? '已解锁·直接查看' : '查看资源' }}
      </el-button>
    </div>
  </div>
</template>

<script setup>
defineProps({
  resource: { type: Object, required: true },
})

defineEmits(['unlock'])
</script>
