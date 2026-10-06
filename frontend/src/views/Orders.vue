<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'
const orders = ref<any[]>([])
const lines = ref<any[]>([])
onMounted(async () => {
  orders.value = await api('/orders')
  if (orders.value.length) lines.value = await api('/orders/' + orders.value[0].id + '/lines')
})
</script>
<template>
  <h1>订单芯片</h1>
  <p class="sub">门店要货 · 顶栏芯片对应订单</p>
  <div class="kp-chips" style="margin-bottom:1rem">
    <span v-for="o in orders" :key="o.id" class="kp-chip">{{ o.code }} · {{ o.outlet }} · {{ o.status }}</span>
  </div>
  <div class="kp-worksheet">
    <h2>订单行</h2>
    <table>
      <thead><tr><th>菜品</th><th>份数</th></tr></thead>
      <tbody>
        <tr v-for="l in lines" :key="l.id"><td>{{ l.dish_name }}</td><td>{{ l.portions }}</td></tr>
      </tbody>
    </table>
  </div>
</template>
