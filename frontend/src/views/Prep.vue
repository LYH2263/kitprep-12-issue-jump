<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'
const tree = ref<any[]>([])
const data = ref<any>(null)
const shortages = ref<any[]>([])
const orders = ref<any[]>([])
const issuing = ref(false)
const error = ref('')

async function refreshShortages() {
  try {
    const res = await api('/prep/shortages?order_id=1')
    shortages.value = res.shortages || []
  } catch { shortages.value = [] }
}

async function run() {
  error.value = ''
  try {
    data.value = await api('/prep/run?order_id=1', { method: 'POST' })
    await refreshShortages()
  } catch (e: any) {
    error.value = messageOf(e)
  }
}

async function issue() {
  if (!data.value || data.value.status === 'issued' || issuing.value) return
  issuing.value = true
  error.value = ''
  try {
    // 领料：把这张单的预占转成真正出库（占用清掉、账面按占用扣一次）
    data.value = await api(`/prep/runs/${data.value.run_id}/issue`, { method: 'POST' })
    await refreshShortages()
  } catch (e: any) {
    error.value = messageOf(e)
  } finally {
    issuing.value = false
  }
}

function messageOf(e: any) {
  try { return JSON.parse(e.message).detail || e.message } catch { return e.message }
}

onMounted(async () => {
  tree.value = await api('/bom/tree')
  orders.value = await api('/orders')
  data.value = await api('/prep/latest?order_id=1')
  await refreshShortages()
})
</script>
<template>
  <h1>备料工作台</h1>
  <p class="sub">左 BOM 树 · 中备料表 · 右缺料便利贴 · 顶栏订单芯片</p>
  <div class="kp-chips" style="margin-bottom:0.75rem" v-if="orders.length">
    <span v-for="o in orders" :key="o.id" class="kp-chip" style="cursor:default">
      {{ o.code }} · {{ o.outlet }}
    </span>
  </div>
  <div style="display:flex;gap:0.5rem;align-items:center">
    <button class="btn" @click="run">生成备料单（预占）</button>
    <button class="btn" :disabled="!data || data.status === 'issued' || issuing" @click="issue">
      {{ data?.status === 'issued' ? '已领料' : (issuing ? '领料中…' : '领料出库') }}
    </button>
    <span v-if="data" class="badge" :class="data.status === 'issued' ? 'badge-ok' : 'badge-warn'">
      {{ data.status === 'issued' ? '已领' : '待领（已预占）' }}
    </span>
  </div>
  <p v-if="error" class="badge badge-bad" style="margin-top:0.6rem;display:inline-block">{{ error }}</p>
  <div class="kp-workbench" style="margin-top:0.85rem">
    <aside class="kp-bom-tree">
      <h2>菜品 / BOM</h2>
      <div v-for="d in tree" :key="d.code" class="kp-dish-node">
        <strong>{{ d.dish }}</strong>
        <span style="font-size:0.7rem;color:#8a8078">{{ d.code }}</span>
        <ul>
          <li v-for="(c,i) in d.children" :key="i">{{ c.ingredient }} · {{ c.qty }} {{ c.unit }}</li>
        </ul>
      </div>
    </aside>
    <section class="kp-worksheet" v-if="data">
      <h2>备料单 #{{ data.run_id }} · {{ data.order?.code }} · {{ data.order?.outlet }}</h2>
      <table>
        <thead><tr><th>原料</th><th>需求</th><th>本单占用</th><th>账面结存</th><th>可用</th><th>单位</th></tr></thead>
        <tbody>
          <tr v-for="l in data.prep_lines" :key="l.ingredient_id">
            <td>{{ l.ingredient_name }}</td>
            <td>{{ l.need_qty }}</td>
            <td>{{ l.reserved_qty }}</td>
            <td>{{ l.book_qty }}</td>
            <td>{{ l.available_qty }}</td>
            <td>{{ l.unit }}</td>
          </tr>
        </tbody>
      </table>
      <p class="sub" style="margin-top:0.5rem">
        生成时按可用量预占，领料时占用转出库：占用清掉、账面只扣占用那一笔，不重复扣。
      </p>
    </section>
    <aside class="kp-shortage-sticky">
      <h2>⚠ 缺料便利贴</h2>
      <div v-for="r in shortages" :key="r.ingredient_id" class="kp-shortage-item">
        <span>{{ r.ingredient_name }}</span>
        <span class="kp-qty">−{{ r.shortage }} {{ r.unit }}</span>
      </div>
      <p v-if="!shortages.length" style="font-size:0.8rem;margin:0.5rem 0 0">暂无缺料</p>
    </aside>
  </div>
</template>
