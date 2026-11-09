<template>
  <Teleport to="body">
    <Transition
      enter-active-class="transition-opacity duration-200"
      leave-active-class="transition-opacity duration-200"
      enter-from-class="opacity-0"
      leave-to-class="opacity-0"
    >
      <div
        v-if="isOpen && backlogItem"
        class="fixed inset-0 z-[2000] flex items-center justify-center bg-black/50 p-4"
        @click="close"
      >
        <div
          class="flex max-h-[90vh] w-full max-w-[700px] flex-col overflow-hidden rounded-xl bg-white shadow-2xl"
          role="dialog"
          aria-modal="true"
          @click.stop
        >
          <div class="flex items-center justify-between border-b border-slate-200 p-6">
            <h3 class="text-xl font-bold tracking-tight text-slate-900">
              {{ mode === 'view' ? 'Purchase Order' : 'Create Purchase Order' }}
            </h3>
            <button
              type="button"
              class="flex cursor-pointer items-center justify-center rounded-md border-0 bg-transparent p-2 text-slate-500 hover:bg-slate-100 hover:text-slate-900"
              aria-label="Close"
              @click="close"
            >
              <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                <path d="M15 5L5 15M5 5L15 15" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
              </svg>
            </button>
          </div>

          <div class="flex-1 overflow-y-auto p-6">
            <!-- Backlog item summary -->
            <div class="mb-6 rounded-lg border border-slate-200 bg-slate-50 p-4">
              <div class="flex items-start justify-between gap-3">
                <div class="min-w-0">
                  <div class="text-base font-bold text-slate-900">{{ backlogItem.item_name }}</div>
                  <div class="font-mono text-sm text-slate-500">SKU: {{ backlogItem.item_sku }}</div>
                </div>
                <span
                  class="shrink-0 rounded-md px-3 py-1 text-xs font-semibold uppercase tracking-wide"
                  :class="priorityClass"
                >{{ backlogItem.priority }} priority</span>
              </div>
              <dl class="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
                <div v-for="stat in summaryStats" :key="stat.label">
                  <dt class="text-xs font-semibold uppercase tracking-wide text-slate-500">{{ stat.label }}</dt>
                  <dd class="mt-1 text-sm font-medium text-slate-900">{{ stat.value }}</dd>
                </div>
              </dl>
            </div>

            <!-- Create mode -->
            <form v-if="mode === 'create'" id="po-form" class="grid gap-4" novalidate @submit.prevent="submit">
              <div v-if="submitError" class="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800" role="alert">
                {{ submitError }}
              </div>

              <div>
                <label class="mb-1 block text-sm font-medium text-slate-700" for="po-supplier">Supplier name</label>
                <input
                  id="po-supplier"
                  v-model.trim="form.supplier_name"
                  type="text"
                  class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-blue-500 focus:outline-none"
                  :class="{ 'border-red-400': touched && errors.supplier_name }"
                />
                <p v-if="touched && errors.supplier_name" class="mt-1 text-xs text-red-600">{{ errors.supplier_name }}</p>
              </div>

              <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <div>
                  <label class="mb-1 block text-sm font-medium text-slate-700" for="po-quantity">Quantity</label>
                  <input
                    id="po-quantity"
                    v-model.number="form.quantity"
                    type="number"
                    min="1"
                    step="1"
                    class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-blue-500 focus:outline-none"
                    :class="{ 'border-red-400': touched && errors.quantity }"
                  />
                  <p v-if="touched && errors.quantity" class="mt-1 text-xs text-red-600">{{ errors.quantity }}</p>
                </div>
                <div>
                  <label class="mb-1 block text-sm font-medium text-slate-700" for="po-unit-cost">Unit cost (USD)</label>
                  <input
                    id="po-unit-cost"
                    v-model.number="form.unit_cost"
                    type="number"
                    min="0"
                    step="0.01"
                    class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-blue-500 focus:outline-none"
                    :class="{ 'border-red-400': touched && errors.unit_cost }"
                  />
                  <p v-if="touched && errors.unit_cost" class="mt-1 text-xs text-red-600">{{ errors.unit_cost }}</p>
                </div>
              </div>

              <div>
                <label class="mb-1 block text-sm font-medium text-slate-700" for="po-delivery">Expected delivery date</label>
                <input
                  id="po-delivery"
                  v-model="form.expected_delivery_date"
                  type="date"
                  class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-blue-500 focus:outline-none"
                  :class="{ 'border-red-400': touched && errors.expected_delivery_date }"
                />
                <p v-if="touched && errors.expected_delivery_date" class="mt-1 text-xs text-red-600">{{ errors.expected_delivery_date }}</p>
              </div>

              <div>
                <label class="mb-1 block text-sm font-medium text-slate-700" for="po-notes">Notes (optional)</label>
                <textarea
                  id="po-notes"
                  v-model="form.notes"
                  rows="3"
                  class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-blue-500 focus:outline-none"
                ></textarea>
              </div>
            </form>

            <!-- View mode -->
            <div v-else>
              <div v-if="loading" class="py-8 text-center text-sm text-slate-500">Loading purchase order...</div>
              <div v-else-if="loadError" class="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800" role="alert">
                {{ loadError }}
              </div>
              <div v-else-if="notFound" class="py-8 text-center">
                <div class="text-base font-semibold text-slate-900">No purchase order found</div>
                <p class="mt-1 text-sm text-slate-500">No purchase order has been created for this shortage yet.</p>
              </div>
              <dl v-else-if="purchaseOrder" class="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <div v-for="row in poRows" :key="row.label">
                  <dt class="text-xs font-semibold uppercase tracking-wide text-slate-500">{{ row.label }}</dt>
                  <dd class="mt-1 text-sm font-medium text-slate-900">
                    <span
                      v-if="row.badge"
                      class="inline-block rounded-md px-2 py-0.5 text-xs font-semibold capitalize"
                      :class="statusClass"
                    >{{ row.value }}</span>
                    <template v-else>{{ row.value }}</template>
                  </dd>
                </div>
                <div v-if="purchaseOrder.notes" class="sm:col-span-2">
                  <dt class="text-xs font-semibold uppercase tracking-wide text-slate-500">Notes</dt>
                  <dd class="mt-1 whitespace-pre-wrap text-sm text-slate-900">{{ purchaseOrder.notes }}</dd>
                </div>
              </dl>
            </div>
          </div>

          <div class="flex justify-end gap-3 border-t border-slate-200 p-6">
            <button
              type="button"
              class="cursor-pointer rounded-lg border border-slate-200 bg-slate-100 px-5 py-2.5 text-sm font-medium text-slate-700 hover:bg-slate-200"
              @click="close"
            >{{ mode === 'create' ? 'Cancel' : 'Close' }}</button>
            <button
              v-if="mode === 'create'"
              type="submit"
              form="po-form"
              class="cursor-pointer rounded-lg border-0 bg-blue-600 px-5 py-2.5 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
              :disabled="submitting"
            >{{ submitting ? 'Creating...' : 'Create Purchase Order' }}</button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { ref, reactive, computed, watch } from 'vue'
import { api } from '../api'

const props = defineProps({
  isOpen: { type: Boolean, default: false },
  backlogItem: { type: Object, default: null },
  mode: { type: String, default: 'create', validator: (v) => ['create', 'view'].includes(v) }
})

const emit = defineEmits(['close', 'po-created'])

const emptyForm = () => ({
  supplier_name: '',
  quantity: 1,
  unit_cost: null,
  expected_delivery_date: '',
  notes: ''
})

const form = reactive(emptyForm())
const touched = ref(false)
const submitting = ref(false)
const submitError = ref('')

const purchaseOrder = ref(null)
const loading = ref(false)
const loadError = ref('')
const notFound = ref(false)

const shortage = computed(() => {
  if (!props.backlogItem) return 1
  return Math.max(1, (props.backlogItem.quantity_needed || 0) - (props.backlogItem.quantity_available || 0))
})

const errors = computed(() => {
  const e = {}
  if (!form.supplier_name) e.supplier_name = 'Supplier name is required'
  if (!Number.isInteger(form.quantity) || form.quantity <= 0) e.quantity = 'Enter a whole number greater than 0'
  if (typeof form.unit_cost !== 'number' || !Number.isFinite(form.unit_cost) || form.unit_cost < 0) {
    e.unit_cost = 'Enter a unit cost of 0 or more'
  }
  if (!form.expected_delivery_date) e.expected_delivery_date = 'Expected delivery date is required'
  return e
})

const priorityClass = computed(() => {
  switch (props.backlogItem?.priority) {
    case 'high': return 'bg-red-100 text-red-800'
    case 'medium': return 'bg-yellow-100 text-yellow-800'
    default: return 'bg-blue-100 text-blue-800'
  }
})

const statusClass = computed(() => {
  switch ((purchaseOrder.value?.status || '').toLowerCase()) {
    case 'received':
    case 'delivered': return 'bg-green-100 text-green-800'
    case 'cancelled': return 'bg-red-100 text-red-800'
    case 'ordered':
    case 'shipped': return 'bg-blue-100 text-blue-800'
    default: return 'bg-yellow-100 text-yellow-800'
  }
})

const summaryStats = computed(() => {
  const b = props.backlogItem
  if (!b) return []
  return [
    { label: 'Order', value: b.order_id },
    { label: 'Needed', value: `${b.quantity_needed} units` },
    { label: 'Available', value: `${b.quantity_available} units` },
    { label: 'Days delayed', value: `${b.days_delayed} days` }
  ]
})

const formatDate = (value) => {
  if (!value) return 'N/A'
  const d = new Date(value)
  if (isNaN(d.getTime())) return String(value)
  return d.toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })
}

const formatMoney = (n) =>
  typeof n === 'number' ? n.toLocaleString('en-US', { style: 'currency', currency: 'USD' }) : 'N/A'

const poRows = computed(() => {
  const po = purchaseOrder.value
  if (!po) return []
  const total = typeof po.quantity === 'number' && typeof po.unit_cost === 'number' ? po.quantity * po.unit_cost : null
  return [
    { label: 'Supplier', value: po.supplier_name },
    { label: 'Status', value: po.status || 'N/A', badge: true },
    { label: 'Quantity', value: `${po.quantity} units` },
    { label: 'Unit cost', value: formatMoney(po.unit_cost) },
    { label: 'Total cost', value: formatMoney(total) },
    { label: 'Expected delivery', value: formatDate(po.expected_delivery_date) },
    { label: 'Created', value: formatDate(po.created_at || po.created_date) }
  ]
})

const resetState = () => {
  Object.assign(form, emptyForm())
  touched.value = false
  submitting.value = false
  submitError.value = ''
  purchaseOrder.value = null
  loading.value = false
  loadError.value = ''
  notFound.value = false
}

const loadPurchaseOrder = async () => {
  const id = props.backlogItem?.id
  loading.value = true
  loadError.value = ''
  notFound.value = false
  purchaseOrder.value = null
  try {
    const response = await api.getPurchaseOrderByBacklogItem(id)
    // Ignore stale responses if the modal switched items or closed
    if (!props.isOpen || props.backlogItem?.id !== id) return
    purchaseOrder.value = response
  } catch (err) {
    if (!props.isOpen || props.backlogItem?.id !== id) return
    if (err?.response?.status === 404) {
      notFound.value = true
    } else {
      loadError.value = 'Failed to load purchase order. Please try again.'
      console.error('Failed to load purchase order:', err)
    }
  } finally {
    if (props.isOpen && props.backlogItem?.id === id) loading.value = false
  }
}

const initialize = () => {
  resetState()
  if (!props.isOpen || !props.backlogItem) return
  if (props.mode === 'view') {
    loadPurchaseOrder()
  } else {
    form.quantity = shortage.value
  }
}

watch(() => [props.isOpen, props.backlogItem?.id, props.mode], initialize)

const submit = async () => {
  touched.value = true
  submitError.value = ''
  if (Object.keys(errors.value).length > 0 || submitting.value) return
  submitting.value = true
  try {
    const response = await api.createPurchaseOrder({
      backlog_item_id: props.backlogItem.id,
      supplier_name: form.supplier_name,
      quantity: form.quantity,
      unit_cost: form.unit_cost,
      expected_delivery_date: form.expected_delivery_date,
      notes: form.notes
    })
    emit('po-created', response)
    emit('close')
  } catch (err) {
    console.error('Failed to create purchase order:', err)
    const detail = err?.response?.data?.detail
    submitError.value = typeof detail === 'string'
      ? detail
      : 'Failed to create purchase order. Please try again.'
  } finally {
    submitting.value = false
  }
}

const close = () => emit('close')
</script>
