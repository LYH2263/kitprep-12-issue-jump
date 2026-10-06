<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'
const rows = ref<any[]>([])
const qty = ref<Record<number, number>>({})
const err = ref('')
async function load() { rows.value = await api('/inventory') }
async function stockOut(r: any) {
  err.value = ''
  try {
    await api(`/inventory/stock-out?ingredient_id=${r.id}&qty=${Number(qty.value[r.id] || 0)}`, { method: 'POST' })
    qty.value[r.id] = 0
    await load()
  } catch (e: any) {
    err.value = `出库失败：${e?.message || ''}`
  }
}
onMounted(load)
</script>
<template>
  <h1>库存</h1>
  <p class="sub">中央厨房原料库存 · 账面 / 占用 / 可用；出库与备料台领料同一口径</p>
  <div class="card">
    <p v-if="err" style="color:var(--kp-bad);font-size:0.8rem;margin:0 0 0.5rem">{{ err }}</p>
    <table>
      <thead><tr><th>编码</th><th>名称</th><th>账面库存</th><th>占用</th><th>可用</th><th>单位</th><th>出库</th></tr></thead>
      <tbody>
        <tr v-for="r in rows" :key="r.id ?? JSON.stringify(r)">
          <td>{{ r.code }}</td><td>{{ r.name }}</td>
          <td>{{ r.stock_qty }}</td><td>{{ r.reserved_qty }}</td><td>{{ r.available_qty }}</td><td>{{ r.unit }}</td>
          <td>
            <input v-model.number="qty[r.id]" type="number" min="0" step="0.1"
                   style="width:5rem;padding:0.25rem 0.4rem;margin-right:0.4rem" />
            <button class="btn" style="padding:0.3rem 0.7rem" @click="stockOut(r)">出库</button>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
