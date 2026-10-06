import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/dishes', name: 'Dishes', component: () => import('../views/Dishes.vue') },
  { path: '/bom', name: 'Bom', component: () => import('../views/Bom.vue') },
  { path: '/orders', name: 'Orders', component: () => import('../views/Orders.vue') },
  { path: '/prep', name: 'Prep', component: () => import('../views/Prep.vue') },
  { path: '/shortages', name: 'Shortages', component: () => import('../views/Shortages.vue') },
  { path: '/inventory', name: 'Inventory', component: () => import('../views/Inventory.vue') },
  { path: '/', redirect: '/dishes' },
]

export default createRouter({
  history: createWebHistory(),
  routes,
})
