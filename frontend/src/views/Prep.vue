<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'
const tree = ref<any[]>([])
const data = ref<any>(null)
const shortages = ref<any[]>([])
const orders = ref<any[]>([])
const issuing = ref(false)
const issueMsg = ref('')
const issueErr = ref('')
async function run() {
  issueMsg.value = ''; issueErr.value = ''
  data.value = await api('/prep/run?order_id=1', { method: 'POST' })
  try {
    const res = await api('/prep/shortages?order_id=1')
    shortages.value = res.shortages || []
  } catch { shortages.value = [] }
}
async function issue() {
  if (!data.value || issuing.value) return
  issuing.value = true
  issueMsg.value = ''; issueErr.value = ''
  try {
    const res = await api(`/prep/issue?run_id=${data.value.id}`, { method: 'POST' })
    data.value.status = res.status
    issueMsg.value = '已领料出库：本单占用已清，账面按预占扣减一次'
  } catch (e: any) {
    issueErr.value = `领料失败：${e?.message || ''}`
  } finally {
    issuing.value = false
  }
}
onMounted(async () => {
  tree.value = await api('/bom/tree')
  orders.value = await api('/orders')
  await run()
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
    <button class="btn" @click="run">生成备料单</button>
    <button class="btn" :disabled="!data || data.status === 'issued' || issuing" @click="issue">
      {{ data?.status === 'issued' ? '已领料' : '领料出库' }}
    </button>
  </div>
  <p v-if="issueMsg" style="color:var(--kp-ok);font-size:0.8rem;margin:0.4rem 0 0">{{ issueMsg }}</p>
  <p v-if="issueErr" style="color:var(--kp-bad);font-size:0.8rem;margin:0.4rem 0 0">{{ issueErr }}</p>
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
      <h2>
        备料单 · {{ data.order?.code }} · {{ data.order?.outlet }}
        <span class="badge" :class="data.status === 'issued' ? 'badge-ok' : 'badge-warn'">
          {{ data.status === 'issued' ? '已领' : '待领' }}
        </span>
      </h2>
      <table>
        <thead><tr><th>原料</th><th>需求</th><th>库存</th><th>单位</th></tr></thead>
        <tbody>
          <tr v-for="l in data.prep_lines" :key="l.ingredient_id">
            <td>{{ l.ingredient_name }}</td><td>{{ l.need_qty }}</td><td>{{ l.stock_qty }}</td><td>{{ l.unit }}</td>
          </tr>
        </tbody>
      </table>
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
