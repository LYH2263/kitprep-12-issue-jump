<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'
const rows = ref<any[]>([])
onMounted(async () => { rows.value = await api('/dishes') })
</script>
<template>
  <h1>菜品</h1>
  <p class="sub">中央厨房出品菜品</p>
  <div class="card">
    <table>
      <thead><tr><th>编码</th><th>名称</th><th>单位</th></tr></thead>
      <tbody>
        <tr v-for="r in rows" :key="r.id ?? JSON.stringify(r)"><td>{{ r.code }}</td><td>{{ r.name }}</td><td>{{ r.portion_unit }}</td></tr>
      </tbody>
    </table>
  </div>
</template>
