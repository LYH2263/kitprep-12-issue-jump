<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'
const rows = ref<any[]>([])
onMounted(async () => { rows.value = await api('/inventory') })
</script>
<template>
  <h1>库存</h1>
  <p class="sub">中央厨房原料库存</p>
  <div class="card">
    <table>
      <thead><tr><th>编码</th><th>名称</th><th>库存</th><th>单位</th></tr></thead>
      <tbody>
        <tr v-for="r in rows" :key="r.id ?? JSON.stringify(r)"><td>{{ r.code }}</td><td>{{ r.name }}</td><td>{{ r.stock_qty }}</td><td>{{ r.unit }}</td></tr>
      </tbody>
    </table>
  </div>
</template>
