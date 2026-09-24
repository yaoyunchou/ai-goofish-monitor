<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import {
  LayoutDashboard,
  ListTodo,
  Users,
  Layers,
  Terminal,
  Settings2,
  ChevronRight,
  Store,
  UserRoundSearch,
  Activity,
  Plus,
  CircleAlert,
  Archive,
  SlidersHorizontal,
  Package,
  BookMarked,
} from 'lucide-vue-next'
import { useWebSocket } from '@/composables/useWebSocket'
import { useI18n } from 'vue-i18n'

const emit = defineEmits<{
  (event: 'navigate'): void
}>()
const { isConnected } = useWebSocket()
const { t } = useI18n()
const route = useRoute()

interface NavChild {
  to: string
  label: string
  icon: typeof LayoutDashboard
}

interface NavGroup {
  key: string
  label: string
  icon: typeof LayoutDashboard
  children: NavChild[]
}

type NavItem =
  | { to: string; label: string; icon: typeof LayoutDashboard }
  | NavGroup

const navItems = computed<NavItem[]>(() => [
  { to: '/dashboard', label: t('sidebar.dashboard'), icon: LayoutDashboard },
  { to: '/tasks', label: t('sidebar.tasks'), icon: ListTodo },
  { to: '/accounts', label: t('sidebar.accounts'), icon: Users },
  { to: '/results', label: t('sidebar.results'), icon: Layers },
  {
    key: 'seller',
    label: t('sidebar.sellerSubscriptions'),
    icon: UserRoundSearch,
    children: [
      { to: '/seller-subscriptions/collection', label: t('sidebar.sellerCollection'), icon: Activity },
      { to: '/seller-subscriptions/sellers', label: t('sidebar.sellerSellers'), icon: Store },
      { to: '/seller-subscriptions/items', label: t('sidebar.sellerItems'), icon: Package },
    ],
  },
  { to: '/shop-analytics', label: t('sidebar.shopAnalytics'), icon: Store },
  {
    key: 'xhs',
    label: t('sidebar.xhs'),
    icon: BookMarked,
    children: [
      { to: '/xhs', label: t('sidebar.xhsBoard'), icon: Activity },
      { to: '/xhs/notes', label: t('sidebar.xhsNotes'), icon: BookMarked },
      { to: '/xhs/add', label: t('sidebar.xhsAdd'), icon: Plus },
      { to: '/xhs/failed', label: t('sidebar.xhsFailed'), icon: CircleAlert },
      { to: '/xhs/delisted', label: t('sidebar.xhsDelisted'), icon: Archive },
      { to: '/xhs/shops', label: t('sidebar.xhsShops'), icon: Store },
      { to: '/xhs/settings', label: t('sidebar.xhsSettings'), icon: SlidersHorizontal },
    ],
  },
  { to: '/logs', label: t('sidebar.logs'), icon: Terminal },
  { to: '/settings', label: t('sidebar.settings'), icon: Settings2 },
])

const expandedKeys = ref<string[]>([])

function isGroup(item: NavItem): item is NavGroup {
  return 'children' in item
}

function isChildActive(child: NavChild): boolean {
  return route.path === child.to || route.path.startsWith(child.to + '/')
}

function isGroupActive(group: NavGroup): boolean {
  return group.children.some(isChildActive)
}

function isExpanded(group: NavGroup): boolean {
  return expandedKeys.value.includes(group.key)
}

function toggleGroup(group: NavGroup) {
  if (isExpanded(group)) {
    expandedKeys.value = expandedKeys.value.filter((key) => key !== group.key)
  } else {
    expandedKeys.value = [...expandedKeys.value, group.key]
  }
}

// 激活的分组自动展开（含首次进入、路由变化后）
watch(
  () => route.path,
  () => {
    const activeGroups = navItems.value
      .filter(isGroup)
      .filter(isGroupActive)
      .map((group) => group.key)
    if (activeGroups.length) {
      expandedKeys.value = [...new Set([...expandedKeys.value, ...activeGroups])]
    }
  },
  { immediate: true },
)

const connectionLabel = computed(() => (
  isConnected.value ? t('sidebar.backendConnected') : t('sidebar.backendConnecting')
))
const connectionTone = computed(() =>
  isConnected.value
    ? 'bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)]'
    : 'bg-amber-400 shadow-[0_0_8px_rgba(251,191,36,0.45)]'
)
</script>

<template>
  <nav class="space-y-1">
    <template v-for="item in navItems" :key="isGroup(item) ? item.key : item.to">
      <!-- 普通导航项 -->
      <RouterLink
        v-if="!isGroup(item)"
        :to="item.to"
        v-slot="{ isActive }"
        class="group relative flex items-center px-4 py-3 rounded-xl transition-all duration-200 overflow-hidden"
        @click="emit('navigate')"
      >
        <!-- Active Background Effect -->
        <div
          v-if="isActive"
          class="absolute inset-0 bg-gradient-to-r from-primary/10 to-transparent z-0"
        ></div>
        <div
          v-if="isActive"
          class="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-6 bg-primary rounded-r-full"
        ></div>

        <div class="relative z-10 flex items-center w-full">
          <component
            :is="item.icon"
            class="w-5 h-5 mr-3 transition-colors"
            :class="isActive ? 'text-primary' : 'text-slate-400 group-hover:text-slate-600'"
          />
          <span
            class="text-sm font-bold transition-colors flex-grow"
            :class="isActive ? 'text-slate-900' : 'text-slate-500 group-hover:text-slate-700'"
          >
            {{ item.label }}
          </span>
          <ChevronRight
            v-if="isActive"
            class="w-4 h-4 text-primary animate-in fade-in slide-in-from-left-2"
          />
        </div>
      </RouterLink>

      <!-- 分组导航项 -->
      <div v-else class="group relative overflow-hidden rounded-xl transition-all duration-200">
        <button
          type="button"
          class="relative flex w-full items-center px-4 py-3 rounded-xl transition-all duration-200"
          :class="isGroupActive(item) ? 'bg-gradient-to-r from-primary/10 to-transparent' : ''"
          @click="toggleGroup(item)"
        >
          <div
            v-if="isGroupActive(item)"
            class="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-6 bg-primary rounded-r-full"
          ></div>
          <component
            :is="item.icon"
            class="w-5 h-5 mr-3 transition-colors"
            :class="isGroupActive(item) ? 'text-primary' : 'text-slate-400 group-hover:text-slate-600'"
          />
          <span
            class="text-sm font-bold transition-colors flex-grow text-left"
            :class="isGroupActive(item) ? 'text-slate-900' : 'text-slate-500 group-hover:text-slate-700'"
          >
            {{ item.label }}
          </span>
          <ChevronRight
            class="w-4 h-4 transition-transform duration-200 text-slate-400"
            :class="isExpanded(item) ? 'rotate-90' : ''"
          />
        </button>

        <!-- 子菜单 -->
        <div
          v-show="isExpanded(item)"
          class="space-y-0.5 pb-1"
        >
          <RouterLink
            v-for="child in item.children"
            :key="child.to"
            :to="child.to"
            v-slot="{ isActive }"
            class="group relative flex items-center pl-12 pr-4 py-2.5 rounded-lg transition-all duration-200 overflow-hidden"
            @click="emit('navigate')"
          >
            <div
              v-if="isActive"
              class="absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-5 bg-primary rounded-r-full"
            ></div>
            <component
              :is="child.icon"
              class="w-4 h-4 mr-2.5 transition-colors"
              :class="isActive ? 'text-primary' : 'text-slate-400 group-hover:text-slate-600'"
            />
            <span
              class="text-[13px] font-semibold transition-colors"
              :class="isActive ? 'text-slate-900' : 'text-slate-500 group-hover:text-slate-700'"
            >
              {{ child.label }}
            </span>
          </RouterLink>
        </div>
      </div>
    </template>

    <!-- Support Section -->
    <div class="mt-12 px-4">
      <div class="rounded-2xl p-4 bg-slate-50/50 border border-slate-100 border-dashed">
         <p class="text-[10px] font-black text-slate-400 uppercase tracking-widest mb-2">{{ t('sidebar.systemStatus') }}</p>
         <div class="flex items-center gap-2">
            <div class="w-2 h-2 rounded-full" :class="connectionTone"></div>
            <span class="text-xs font-bold text-slate-600">{{ connectionLabel }}</span>
         </div>
      </div>
    </div>
  </nav>
</template>

<style scoped>
.router-link-active {
  background-color: transparent !important;
}
</style>
