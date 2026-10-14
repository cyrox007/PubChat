<template>
  <div v-if="visible" class="transcription">
    <button class="transcription__toggle" type="button" @click="expanded = !expanded">
      <i class="fas fa-align-left" aria-hidden="true"></i>
      <span>{{ label }}</span>
      <i :class="expanded ? 'fas fa-chevron-up' : 'fas fa-chevron-down'" aria-hidden="true"></i>
    </button>
    <div v-if="expanded" class="transcription__body" aria-live="polite">
      <p v-if="status === 'ready' && text">{{ text }}</p>
      <p v-else-if="status === 'processing' || status === 'pending'" class="transcription__muted">
        <i class="fas fa-spinner fa-spin"></i> Расшифровываем…
      </p>
      <p v-else-if="status === 'failed'" class="transcription__muted">Расшифровка пока недоступна.</p>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue';

const props = defineProps({
  status: { type: String, default: 'none' },
  text: { type: String, default: '' },
});

const expanded = ref(false);
const visible = computed(() => props.status !== 'none' || Boolean(props.text));
const label = computed(() => props.status === 'ready' && props.text ? 'Расшифровка' : 'Текст сообщения');
</script>

<style scoped>
.transcription { margin-top: .35rem; }
.transcription__toggle {
  display: inline-flex;
  align-items: center;
  gap: .35rem;
  min-height: 30px;
  padding: .2rem .45rem;
  border: 0;
  border-radius: var(--ui-radius-sm);
  background: transparent;
  color: currentColor;
  opacity: .8;
  font-size: .76rem;
  cursor: pointer;
}
.transcription__toggle:hover { background: color-mix(in srgb, currentColor 8%, transparent); }
.transcription__body {
  margin-top: .25rem;
  padding: .55rem .65rem;
  border-radius: var(--ui-radius-sm);
  background: color-mix(in srgb, var(--ui-surface) 82%, transparent);
  color: var(--ui-text);
  font-size: .82rem;
  line-height: 1.45;
  text-align: left;
}
.transcription__body p { margin: 0; white-space: pre-wrap; }
.transcription__muted { color: var(--ui-text-muted); }
</style>
