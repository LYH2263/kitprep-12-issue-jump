<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'
const tree = ref<any[]>([])
onMounted(async () => { tree.value = await api('/bom/tree') })
</script>
<template>
  <h1>BOM 树</h1>
  <p class="sub">菜品用料树 · 生产厨房口径</p>
  <div class="kp-bom-tree" style="max-width:420px">
    <h2>菜品 / BOM</h2>
    <div v-for="d in tree" :key="d.code" class="kp-dish-node">
      <strong>{{ d.dish }}</strong>
      <span style="font-size:0.7rem;color:#8a8078">{{ d.code }}</span>
      <ul>
        <li v-for="(c,i) in d.children" :key="i">{{ c.ingredient }} · {{ c.qty }} {{ c.unit }} / 份</li>
      </ul>
    </div>
  </div>
</template>
