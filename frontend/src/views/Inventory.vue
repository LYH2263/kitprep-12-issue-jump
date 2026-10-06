<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'
const rows = ref<any[]>([])
const qty = ref<Record<number, string>>({})
const busy = ref<number | null>(null)
const error = ref<Record<number, string>>({})

async function load() {
  rows.value = await api('/inventory')
}

function messageOf(e: any) {
  try { return JSON.parse(e.message).detail || e.message } catch { return e.message }
}

async function issue(row: any) {
  const q = parseFloat(qty.value[row.id] ?? '')
  error.value[row.id] = ''
  if (!q || q <= 0) {
    error.value[row.id] = '请输入大于 0 的出库数量'
    return
  }
  busy.value = row.id
  try {
    // 库存页出库与备料台领料同一口径：同一后端扣减函数，账面只扣一次
    const updated = await api(`/inventory/${row.id}/issue`, {
      method: 'POST',
      body: JSON.stringify({ qty: q }),
    })
    const idx = rows.value.findIndex(r => r.id === row.id)
    if (idx >= 0) rows.value[idx] = updated
    qty.value[row.id] = ''
  } catch (e: any) {
    // 出库失败后端已整体回滚，这里只提示，账面/占用不变
    error.value[row.id] = messageOf(e)
    await load()
  } finally {
    busy.value = null
  }
}

onMounted(load)
</script>
<template>
  <h1>库存</h1>
  <p class="sub">中央厨房原料库存 · 可用 = 账面结存 − 已预占；出库与备料台领料同一扣减口径</p>
  <div class="card">
    <table>
      <thead><tr><th>编码</th><th>名称</th><th>账面结存</th><th>已预占</th><th>可用</th><th>单位</th><th>出库</th></tr></thead>
      <tbody>
        <tr v-for="r in rows" :key="r.id">
          <td>{{ r.code }}</td>
          <td>{{ r.name }}</td>
          <td>{{ r.stock_qty }}</td>
          <td>{{ r.reserved_qty }}</td>
          <td>{{ r.available_qty }}</td>
          <td>{{ r.unit }}</td>
          <td>
            <input
              v-model="qty[r.id]"
              type="number"
              min="0"
              step="0.01"
              style="width:80px"
              :placeholder="`可用 ${r.available_qty}`"
            />
            <button
              class="btn"
              style="margin-left:0.4rem;padding:0.15rem 0.6rem"
              :disabled="busy === r.id"
              @click="issue(r)"
            >{{ busy === r.id ? '出库中…' : '出库' }}</button>
            <span v-if="error[r.id]" class="badge badge-bad" style="margin-left:0.4rem">{{ error[r.id] }}</span>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
