<template>
  <div class="video-message">
    <div class="video-message__frame">
      <video ref="video" :src="src" :poster="poster || undefined" playsinline preload="metadata"
        @loadedmetadata="onLoaded" @timeupdate="onTimeUpdate" @ended="playing = false" @click="togglePlay" />
      <button v-if="!playing" class="video-message__play" type="button" aria-label="Воспроизвести видео" @click.stop="togglePlay">
        <i class="fas fa-play"></i>
      </button>
      <div class="video-message__controls">
        <button type="button" :aria-label="playing ? 'Пауза' : 'Воспроизвести'" @click.stop="togglePlay"><i :class="playing ? 'fas fa-pause' : 'fas fa-play'"></i></button>
        <input type="range" min="0" :max="total || 1" step="0.1" :value="current" aria-label="Позиция видео" @input="seek" />
        <span>{{ formatTime(current) }} / {{ formatTime(total) }}</span>
        <button type="button" aria-label="На весь экран" @click.stop="fullscreen"><i class="fas fa-expand"></i></button>
      </div>
    </div>
    <TranscriptionBlock :status="transcriptionStatus" :text="transcription" />
  </div>
</template>

<script setup>
import { ref } from 'vue';
import TranscriptionBlock from '@/components/Message/TranscriptionBlock.vue';

const props = defineProps({
  src: { type: String, required: true },
  poster: { type: String, default: '' },
  duration: { type: Number, default: 0 },
  transcription: { type: String, default: '' },
  transcriptionStatus: { type: String, default: 'none' },
});
const video = ref(null);
const playing = ref(false);
const current = ref(0);
const total = ref(Number(props.duration) || 0);
const togglePlay = async () => {
  if (!video.value) return;
  if (video.value.paused) { try { await video.value.play(); playing.value = true; } catch (_) {} }
  else { video.value.pause(); playing.value = false; }
};
const onLoaded = () => { if (Number.isFinite(video.value?.duration)) total.value = video.value.duration; };
const onTimeUpdate = () => { current.value = video.value?.currentTime || 0; playing.value = Boolean(video.value && !video.value.paused); };
const seek = (event) => { if (video.value) video.value.currentTime = Number(event.target.value) || 0; };
const fullscreen = async () => { try { await video.value?.requestFullscreen?.(); } catch (_) {} };
const formatTime = (seconds) => { const value = Math.max(0, Math.floor(Number(seconds) || 0)); return `${Math.floor(value / 60)}:${String(value % 60).padStart(2, '0')}`; };
</script>

<style scoped>
.video-message { width: min(100%, 460px); }
.video-message__frame { position: relative; overflow: hidden; border-radius: 14px; background: #111; aspect-ratio: 16/10; }
.video-message__frame video { width: 100%; height: 100%; object-fit: contain; display: block; }
.video-message__play { position: absolute; inset: 50% auto auto 50%; translate: -50% -50%; width: 48px; height: 48px; border: 0; border-radius: 50%; background: rgba(0,0,0,.64); color: #fff; cursor: pointer; }
.video-message__controls { position: absolute; left: 0; right: 0; bottom: 0; display: grid; grid-template-columns: 30px minmax(70px,1fr) auto 30px; align-items: center; gap: .4rem; padding: .45rem .55rem; background: linear-gradient(transparent, rgba(0,0,0,.78)); color: white; font-size: .68rem; }
.video-message__controls button { width: 30px; height: 30px; padding: 0; border: 0; background: transparent; color: white; cursor: pointer; }
.video-message__controls input { width: 100%; min-width: 0; }
@media(max-width:480px){.video-message__controls{grid-template-columns:28px minmax(50px,1fr) auto 28px;padding:.35rem}.video-message__frame{border-radius:12px}}
</style>
