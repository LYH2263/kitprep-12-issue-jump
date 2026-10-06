<script setup lang="ts">
import { RouterLink, RouterView } from 'vue-router'
</script>
<template>
  <div class="kp-kitchen">
    <header class="kp-order-bar">
      <div class="kp-brand">KitPrep · 中央厨房备料台</div>
      <nav class="kp-chips">
        <RouterLink to="/orders" class="kp-chip">订单</RouterLink>
        <RouterLink to="/prep" class="kp-chip">备料单</RouterLink>
        <RouterLink to="/bom" class="kp-chip">BOM树</RouterLink>
        <RouterLink to="/dishes" class="kp-chip">菜品</RouterLink>
        <RouterLink to="/shortages" class="kp-chip">缺料</RouterLink>
        <RouterLink to="/inventory" class="kp-chip">库存</RouterLink>
      </nav>
    </header>
    <main class="kp-bench">
      <RouterView />
    </main>
  </div>
</template>
