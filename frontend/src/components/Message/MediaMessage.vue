<template>
  <div class="media-message">
    <template v-if="kind === 'image'">
      <div class="media-message__images" :class="{ single: files.length === 1 }">
        <a v-for="(file, index) in files" :key="file.url || index" :href="fileUrl(file)" target="_blank" rel="noopener">
          <img :src="fileUrl(file)" :alt="file.name || 'Изображение'" loading="lazy" />
        </a>
      </div>
    </template>

    <VoiceMessage
      v-else-if="kind === 'voice' || kind === 'audio'"
      :src="voiceSrc"
      :duration="Number(meta.duration || firstFile.duration || 0)"
      :waveform="meta.waveform || firstFile.waveform || []"
      :transcription="transcription.text"
      :transcription-status="transcription.status"
    />

    <VideoMessage
      v-else-if="kind === 'video'"
      :src="fileUrl(firstFile)"
      :poster="absoluteUrl(meta.poster || firstFile.poster || '')"
      :duration="Number(meta.duration || firstFile.duration || 0)"
      :transcription="transcription.text"
      :transcription-status="transcription.status"
    />

    <div v-else-if="kind === 'file'" class="media-message__files">
      <a v-for="(file, index) in files" :key="file.url || index" class="media-file" :href="fileUrl(file)" target="_blank" rel="noopener">
        <span class="media-file__icon"><i :class="fileIcon(file)"></i></span>
        <span class="media-file__meta"><strong>{{ file.name || 'Файл' }}</strong><small>{{ formatBytes(file.size) }}</small></span>
        <i class="fas fa-download media-file__download"></i>
      </a>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue';
import VoiceMessage from '@/components/Message/VoiceMessage.vue';
import VideoMessage from '@/components/Message/VideoMessage.vue';

const props = defineProps({
  kind: { type: String, required: true },
  metadata: { type: Object, default: () => ({}) },
  content: { type: String, default: '' },
});

const apiBaseUrl = String(import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '');
const meta = computed(() => props.metadata || {});
const files = computed(() => Array.isArray(meta.value.files) ? meta.value.files : []);
const firstFile = computed(() => files.value[0] || {});
const transcription = computed(() => {
  const value = meta.value.transcription || {};
  if (typeof value === 'string') return { status: value ? 'ready' : 'none', text: value };
  return { status: value.status || (value.text ? 'ready' : 'none'), text: value.text || '' };
});
const absoluteUrl = (url) => {
  if (!url) return '';
  if (/^(?:https?:|blob:|data:)/i.test(url)) return url;
  return `${apiBaseUrl}${url.startsWith('/') ? '' : '/'}${url}`;
};
const fileUrl = (file) => absoluteUrl(typeof file === 'string' ? file : file?.url || '');
const voiceSrc = computed(() => absoluteUrl(meta.value.voice || firstFile.value.url || props.content));
const fileIcon = (file) => {
  const type = String(file?.type || '').toLowerCase();
  const name = String(file?.name || '').toLowerCase();
  if (type.includes('pdf') || name.endsWith('.pdf')) return 'fas fa-file-pdf';
  if (type.includes('word') || /\.docx?$/.test(name)) return 'fas fa-file-word';
  if (type.includes('sheet') || /\.xlsx?$/.test(name)) return 'fas fa-file-excel';
  if (/\.(zip|rar|7z)$/.test(name)) return 'fas fa-file-archive';
  return 'fas fa-file';
};
const formatBytes = (bytes) => {
  let value = Number(bytes) || 0;
  if (!value) return '';
  const units = ['Б', 'КБ', 'МБ', 'ГБ'];
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) { value /= 1024; unit += 1; }
  return `${value.toFixed(value >= 10 || unit === 0 ? 0 : 1)} ${units[unit]}`;
};
</script>

<style scoped>
.media-message { width: 100%; min-width: 0; }
.media-message__images { display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap: 3px; overflow: hidden; border-radius: 12px; }
.media-message__images.single { grid-template-columns: minmax(0,1fr); }
.media-message__images a { display: block; min-width: 0; }
.media-message__images img { display: block; width: 100%; max-height: 420px; object-fit: cover; }
.media-message__files { display: grid; gap: .35rem; }
.media-file { display: flex; align-items: center; gap: .6rem; min-height: 48px; padding: .55rem .65rem; border-radius: 12px; background: color-mix(in srgb,var(--ui-surface) 82%,transparent); color: var(--ui-text); text-decoration: none; }
.media-file__icon { width: 30px; text-align: center; font-size: 1.15rem; color: var(--ui-primary); }
.media-file__meta { display: grid; flex: 1; min-width: 0; text-align: left; }
.media-file__meta strong { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: .82rem; }
.media-file__meta small { color: var(--ui-text-muted); font-size: .68rem; }
.media-file__download { color: var(--ui-text-muted); }
@media(max-width:480px){.media-message__images img{max-height:300px}.media-file{min-height:44px;padding:.45rem .55rem}}
</style>
