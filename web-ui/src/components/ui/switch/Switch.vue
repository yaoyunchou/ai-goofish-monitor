<script setup lang="ts">
import type { SwitchRootEmits, SwitchRootProps } from "reka-ui"
import type { HTMLAttributes } from "vue"
import { computed } from "vue"
import { reactiveOmit } from "@vueuse/core"
import {
  SwitchRoot,
  SwitchThumb,
} from "reka-ui"
import { cn } from "@/lib/utils"

const props = defineProps<SwitchRootProps & {
  class?: HTMLAttributes["class"]
  /** shadcn 兼容：与 modelValue 等价，勿作为原生 HTML checked 属性透传 */
  checked?: boolean
}>()

const emits = defineEmits<SwitchRootEmits & {
  "update:checked": [value: boolean]
}>()

const delegatedProps = reactiveOmit(props, "class", "checked")

const switchValue = computed(() => props.modelValue ?? props.checked ?? false)

function onUpdateModelValue(value: boolean) {
  emits("update:modelValue", value)
  emits("update:checked", value)
}
</script>

<template>
  <SwitchRoot
    v-bind="delegatedProps"
    :model-value="switchValue"
    :class="cn(
      'peer inline-flex h-6 w-11 shrink-0 cursor-pointer items-center rounded-full border-2 border-transparent transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:cursor-not-allowed disabled:opacity-50 data-[state=checked]:bg-primary data-[state=unchecked]:bg-input',
      props.class,
    )"
    @update:model-value="onUpdateModelValue"
  >
    <SwitchThumb
      :class="cn('pointer-events-none block h-5 w-5 rounded-full bg-background shadow-lg ring-0 transition-transform data-[state=checked]:translate-x-5')"
    >
      <slot name="thumb" />
    </SwitchThumb>
  </SwitchRoot>
</template>
