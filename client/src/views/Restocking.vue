<template>
  <div class="restocking">
    <div class="page-header">
      <h2>{{ t('restocking.title') }}</h2>
      <p>{{ t('restocking.description') }}</p>
    </div>

    <div class="card">
      <div class="flex flex-wrap items-end gap-6">
        <div class="flex flex-col gap-1">
          <label for="restock-budget" class="text-xs font-semibold uppercase tracking-wide text-slate-500">
            {{ t('restocking.budgetLabel') }}
          </label>
          <input
            id="restock-budget"
            v-model="budgetInput"
            type="number"
            min="0"
            step="1000"
            inputmode="decimal"
            :placeholder="t('restocking.budgetPlaceholder')"
            :aria-invalid="!!budgetError"
            :class="[
              'w-48 rounded-lg border bg-slate-50 px-3 py-2 text-sm text-slate-900 focus:bg-white focus:outline-none focus:ring-2',
              budgetError ? 'border-red-400 focus:ring-red-200' : 'border-slate-300 focus:border-blue-500 focus:ring-blue-100'
            ]"
          />
        </div>

        <div class="flex flex-col gap-1">
          <span class="text-xs font-semibold uppercase tracking-wide text-slate-500">{{ t('restocking.presetsLabel') }}</span>
          <div class="flex gap-2">
            <button
              v-for="preset in presets"
              :key="preset.value"
              type="button"
              :class="[
                'cursor-pointer rounded-lg border px-3 py-2 text-sm font-medium transition-colors',
                Number(budgetInput) === preset.value
                  ? 'border-slate-900 bg-slate-900 text-white'
                  : 'border-slate-300 bg-white text-slate-700 hover:bg-slate-100'
              ]"
              @click="applyPreset(preset.value)"
            >
              {{ preset.label }}
            </button>
          </div>
        </div>

        <div class="flex flex-col gap-1">
          <label for="restock-horizon" class="text-xs font-semibold uppercase tracking-wide text-slate-500">
            {{ t('restocking.horizonLabel') }}
          </label>
          <select
            id="restock-horizon"
            v-model.number="horizonDays"
            class="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-100"
          >
            <option v-for="days in horizonOptions" :key="days" :value="days">
              {{ t('restocking.horizonDays', { days }) }}
            </option>
          </select>
        </div>

        <span v-if="refreshing" class="pb-2 text-sm text-slate-500">{{ t('restocking.updating') }}</span>
      </div>

      <p v-if="budgetError" class="mt-3 text-sm text-red-600" role="alert">{{ budgetError }}</p>
      <p v-if="currentLocale === 'ja'" class="mt-3 text-sm text-slate-500">{{ t('restocking.usdNote') }}</p>
    </div>

    <div v-if="loading" class="loading">{{ t('common.loading') }}</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <div v-else-if="plan && !budgetError" :class="{ 'opacity-60': refreshing }">
      <div class="mb-5 grid grid-cols-2 gap-4 lg:grid-cols-4 xl:grid-cols-7">
        <div v-for="card in summaryCards" :key="card.key" class="rounded-[10px] border border-slate-200 bg-white p-4">
          <div class="text-xs font-semibold uppercase tracking-wide text-slate-500">{{ card.label }}</div>
          <div :class="['mt-1 text-2xl font-bold', card.color]">{{ card.value }}</div>
        </div>
      </div>

      <div class="card">
        <h3 class="mb-3 text-lg font-bold tracking-tight text-slate-900">{{ t('restocking.allocation.title') }}</h3>
        <div
          class="flex h-4 w-full overflow-hidden rounded-full bg-slate-200"
          role="img"
          :aria-label="t('restocking.allocation.ofBudget', { percent: allocatedPercent })"
        >
          <div class="h-full bg-blue-500 transition-all" :style="{ width: allocatedPercent + '%' }"></div>
        </div>
        <div class="mt-2 flex flex-wrap justify-between gap-2 text-sm text-slate-600">
          <span>
            <span class="mr-1 inline-block h-2 w-2 rounded-full bg-blue-500"></span>
            {{ t('restocking.allocation.allocated') }}: {{ money(plan.total_allocated) }}
            ({{ t('restocking.allocation.ofBudget', { percent: allocatedPercent }) }})
          </span>
          <span>
            <span class="mr-1 inline-block h-2 w-2 rounded-full bg-slate-300"></span>
            {{ t('restocking.allocation.remaining') }}: {{ money(plan.remaining_budget) }}
            ({{ t('restocking.allocation.ofBudget', { percent: remainingPercent }) }})
          </span>
        </div>
        <p class="mt-2 text-sm text-slate-500">{{ t('restocking.allocation.coverage', { percent: coveragePercent }) }}</p>
      </div>

      <div v-if="plan.items.length === 0" class="card py-8 text-center text-slate-500">
        {{ t('restocking.empty') }}
      </div>
      <div v-else class="card">
        <h3 class="mb-3 text-lg font-bold tracking-tight text-slate-900">
          {{ t('restocking.tableTitle') }} ({{ plan.items.length }})
        </h3>
        <div class="table-container">
          <table>
            <thead>
              <tr>
                <th>{{ t('restocking.table.rank') }}</th>
                <th>{{ t('restocking.table.sku') }}</th>
                <th>{{ t('restocking.table.itemName') }}</th>
                <th>{{ t('restocking.table.warehouse') }}</th>
                <th class="text-right">{{ t('restocking.table.onHand') }}</th>
                <th class="text-right">{{ t('restocking.table.reorderPoint') }}</th>
                <th class="text-right">{{ t('restocking.table.daysOfCover') }}</th>
                <th class="text-right">{{ t('restocking.table.recommendedQty') }}</th>
                <th class="text-right">{{ t('restocking.table.fundedQty') }}</th>
                <th class="text-right">{{ t('restocking.table.cost') }}</th>
                <th>{{ t('restocking.table.status') }}</th>
                <th>{{ t('restocking.table.reasons') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in plan.items" :key="item.sku">
                <td>{{ item.priority_rank }}</td>
                <td><strong>{{ item.sku }}</strong></td>
                <td>{{ translateProductName(item.name) }}</td>
                <td>{{ translateWarehouse(item.warehouse) }}</td>
                <td class="text-right">{{ item.quantity_on_hand.toLocaleString() }}</td>
                <td class="text-right">{{ item.reorder_point.toLocaleString() }}</td>
                <td class="text-right">{{ item.days_of_cover == null ? '—' : item.days_of_cover.toFixed(1) }}</td>
                <td class="text-right">{{ item.recommended_qty.toLocaleString() }}</td>
                <td class="text-right"><strong>{{ item.funded_qty.toLocaleString() }}</strong></td>
                <td class="text-right"><strong>{{ money(item.cost) }}</strong></td>
                <td>
                  <span :class="['inline-block whitespace-nowrap rounded-md px-2.5 py-1 text-xs font-semibold', statusClass(item.status)]">
                    {{ statusLabel(item.status) }}
                  </span>
                </td>
                <td>
                  <div class="flex flex-wrap gap-1">
                    <span
                      v-for="reason in item.reasons"
                      :key="reason"
                      class="inline-block whitespace-nowrap rounded-md bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-700"
                    >
                      {{ reasonLabel(reason) }}
                    </span>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { api } from '../api'
import { useFilters } from '../composables/useFilters'
import { useI18n } from '../composables/useI18n'
import { formatCurrency } from '../utils/currency'

const MAX_BUDGET = 100000000
const DEBOUNCE_MS = 400

export default {
  name: 'Restocking',
  setup() {
    const { t, currentLocale, currentCurrency, translateProductName, translateWarehouse } = useI18n()
    const { selectedLocation, selectedCategory } = useFilters()

    const presets = [
      { label: '$50K', value: 50000 },
      { label: '$250K', value: 250000 },
      { label: '$1M', value: 1000000 }
    ]
    const horizonOptions = [30, 60, 90]

    const budgetInput = ref(250000)
    const horizonDays = ref(30)
    const plan = ref(null)
    const loading = ref(true)
    const refreshing = ref(false)
    const error = ref(null)

    let requestId = 0
    let debounceTimer = null

    // Parsed budget, or null when empty/invalid/<=0
    const parsedBudget = computed(() => {
      const raw = budgetInput.value
      if (raw === '' || raw === null || raw === undefined) return null
      const n = Number(raw)
      return Number.isFinite(n) && n > 0 ? n : null
    })

    const budgetError = computed(() => {
      if (parsedBudget.value === null) return t('restocking.invalidBudget')
      if (parsedBudget.value > MAX_BUDGET) return t('restocking.budgetTooLarge')
      return null
    })

    const loadPlan = async () => {
      if (budgetError.value) {
        // Invalidate any in-flight request so it can't overwrite the validation state
        requestId++
        refreshing.value = false
        loading.value = false
        return
      }
      const myId = ++requestId
      refreshing.value = true
      try {
        const result = await api.getRestockingPlan({
          budget: parsedBudget.value,
          horizonDays: horizonDays.value,
          warehouse: selectedLocation.value,
          category: selectedCategory.value
        })
        if (myId !== requestId) return
        plan.value = result
        error.value = null
      } catch (err) {
        if (myId !== requestId) return
        error.value = t('restocking.loadError')
        console.error('Load error:', err)
      } finally {
        if (myId === requestId) {
          loading.value = false
          refreshing.value = false
        }
      }
    }

    const clearDebounce = () => {
      if (debounceTimer) {
        clearTimeout(debounceTimer)
        debounceTimer = null
      }
    }

    // Typing: debounce. Presets set the input then fetch immediately.
    watch(budgetInput, () => {
      clearDebounce()
      if (budgetError.value) {
        requestId++
        refreshing.value = false
        loading.value = false
        return
      }
      debounceTimer = setTimeout(() => {
        debounceTimer = null
        loadPlan()
      }, DEBOUNCE_MS)
    })

    const applyPreset = (value) => {
      clearDebounce()
      if (budgetInput.value === value) {
        loadPlan()
        return
      }
      budgetInput.value = value
      // The watcher schedules a debounce; cancel it after it runs and fetch now
      Promise.resolve().then(() => {
        clearDebounce()
        loadPlan()
      })
    }

    watch(horizonDays, () => {
      clearDebounce()
      loadPlan()
    })

    watch([selectedLocation, selectedCategory], () => {
      clearDebounce()
      loadPlan()
    })

    const money = (amount) => formatCurrency(amount, currentCurrency.value)

    const percent = (part, whole) => {
      if (!whole || whole <= 0) return 0
      return Math.max(0, Math.min(100, Math.round((part / whole) * 100)))
    }

    const allocatedPercent = computed(() => plan.value ? percent(plan.value.total_allocated, plan.value.budget) : 0)
    const remainingPercent = computed(() => plan.value ? 100 - allocatedPercent.value : 0)
    const coveragePercent = computed(() => plan.value ? percent(plan.value.total_allocated, plan.value.total_needed) : 0)

    const summaryCards = computed(() => {
      const p = plan.value
      if (!p) return []
      return [
        { key: 'budget', label: t('restocking.summary.budget'), value: money(p.budget), color: 'text-slate-900' },
        { key: 'allocated', label: t('restocking.summary.allocated'), value: money(p.total_allocated), color: 'text-blue-600' },
        { key: 'remaining', label: t('restocking.summary.remaining'), value: money(p.remaining_budget), color: 'text-slate-900' },
        { key: 'funded', label: t('restocking.summary.funded'), value: p.funded_count, color: 'text-green-600' },
        { key: 'partial', label: t('restocking.summary.partial'), value: p.partial_count, color: 'text-yellow-600' },
        { key: 'unfunded', label: t('restocking.summary.unfunded'), value: p.unfunded_count, color: 'text-slate-500' },
        { key: 'needed', label: t('restocking.summary.totalNeeded'), value: money(p.total_needed), color: 'text-slate-900' }
      ]
    })

    const statusClass = (status) => {
      if (status === 'funded') return 'bg-green-100 text-green-800'
      if (status === 'partial') return 'bg-yellow-100 text-yellow-800'
      return 'bg-slate-200 text-slate-700'
    }
    const statusLabel = (status) => t(`restocking.statuses.${status}`)
    const reasonLabel = (reason) => t(`restocking.reasons.${reason}`)

    onMounted(loadPlan)
    onBeforeUnmount(() => {
      clearDebounce()
      requestId++
    })

    return {
      t,
      currentLocale,
      translateProductName,
      translateWarehouse,
      presets,
      horizonOptions,
      budgetInput,
      horizonDays,
      plan,
      loading,
      refreshing,
      error,
      budgetError,
      applyPreset,
      money,
      allocatedPercent,
      remainingPercent,
      coveragePercent,
      summaryCards,
      statusClass,
      statusLabel,
      reasonLabel
    }
  }
}
</script>
