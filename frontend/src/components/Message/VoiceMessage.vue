<template>
  <div class="voice-message">
    <audio ref="audio" :src="src" preload="metadata" @loadedmetadata="onLoaded" @timeupdate="onTimeUpdate" @ended="playing = false" />
    <button class="voice-message__play" type="button" :aria-label="playing ? 'Пауза' : 'Воспроизвести'" @click="togglePlay">
      <i :class="playing ? 'fas fa-pause' : 'fas fa-play'" aria-hidden="true"></i>
    </button>
    <button class="voice-message__wave" type="button" aria-label="Перемотать голосовое сообщение" @click="seekFromPointer">
      <span v-for="(bar, index) in bars" :key="index" class="voice-message__bar" :class="{ played: index <= playedBar }" :style="{ height: `${bar}%` }"></span>
    </button>
    <span class="voice-message__time">{{ formatTime(current) }} / {{ formatTime(total) }}</span>
    <button class="voice-message__speed" type="button" aria-label="Скорость воспроизведения" @click="cycleSpeed">{{ speed }}×</button>
  </div>
  <TranscriptionBlock :status="transcriptionStatus" :text="transcription" />
</template>

<script setup>
import { computed, onBeforeUnmount, ref } from 'vue';
import TranscriptionBlock from '@/components/Message/TranscriptionBlock.vue';

const props = defineProps({
  src: { type: String, required: true },
  duration: { type: Number, default: 0 },
  waveform: { type: Array, default: () => [] },
  transcription: { type: String, default: '' },
  transcriptionStatus: { type: String, default: 'none' },
});

const audio = ref(null);
const playing = ref(false);
const current = ref(0);
const total = ref(Number(props.duration) || 0);
const speed = ref(1);
const fallbackBars = [36,52,68,44,76,58,42,72,88,54,62,80,46,70,92,64,48,78,56,84,44,66,74,52,88,62,48,72,58,82,46,68,54,76,42,64];
const bars = computed(() => props.waveform?.length ? props.waveform.slice(0, 48).map((v) => Math.max(20, Math.min(100, Number(v) || 20))) : fallbackBars);
const playedBar = computed(() => total.value > 0 ? Math.floor((current.value / total.value) * (bars.value.length - 1)) : -1);

const togglePlay = async () => {
  if (!audio.value) return;
  if (audio.value.paused) {
    try { await audio.value.play(); playing.value = true; } catch (_) { playing.value = false; }
  } else {
    audio.value.pause(); playing.value = false;
  }
};
const onLoaded = () => { if (audio.value?.duration && Number.isFinite(audio.value.duration)) total.value = audio.value.duration; };
const onTimeUpdate = () => { current.value = audio.value?.currentTime || 0; playing.value = Boolean(audio.value && !audio.value.paused); };
const seekFromPointer = (event) => {
  if (!audio.value || !total.value) return;
  const rect = event.currentTarget.getBoundingClientRect();
  const ratio = Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width));
  audio.value.currentTime = ratio * total.value;
};
const cycleSpeed = () => {
  const values = [1, 1.5, 2];
  speed.value = values[(values.indexOf(speed.value) + 1) % values.length];
  if (audio.value) audio.value.playbackRate = speed.value;
};
const formatTime = (seconds) => {
  const value = Math.max(0, Math.floor(Number(seconds) || 0));
  return `${Math.floor(value / 60)}:${String(value % 60).padStart(2, '0')}`;
};

onBeforeUnmount(() => { if (audio.value) audio.value.pause(); });
</script>

<style scoped>
.voice-message {
  display: grid;
  grid-template-columns: 34px minmax(88px,1fr) auto 35px;
  align-items: center;
  gap: .45rem;
  width: min(100%, 360px);
  min-width: 220px;
}
.voice-message__play,.voice-message__speed {
  border: 0;
  color: currentColor;
  background: color-mix(in srgb, currentColor 10%, transparent);
  cursor: pointer;
}
.voice-message__play { width: 34px; height: 34px; border-radius: 50%; }
.voice-message__speed { min-width: 35px; height: 28px; border-radius: 999px; font-size: .7rem; font-weight: 700; }
.voice-message__wave {
  height: 34px;
  display: flex;
  align-items: center;
  gap: 2px;
  padding: 0;
  border: 0;
  background: transparent;
  cursor: pointer;
  overflow: hidden;
}
.voice-message__bar { width: 2px; min-height: 4px; max-height: 30px; flex: 1 1 2px; border-radius: 99px; background: currentColor; opacity: .26; }
.voice-message__bar.played { opacity: .9; }
.voice-message__time { white-space: nowrap; font-size: .7rem; opacity: .75; font-variant-numeric: tabular-nums; }
@media (max-width: 480px) {
  .voice-message { min-width: 190px; grid-template-columns: 32px minmax(72px,1fr) auto 33px; gap: .35rem; }
  .voice-message__play { width: 32px; height: 32px; }
  .voice-message__time { font-size: .66rem; }
}
</style>
