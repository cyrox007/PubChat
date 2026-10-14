<template>
  <section class="composer" :class="{ disabled: isDisabled }">
    <div v-if="replyTo" class="composer__reply">
      <div><strong>{{ replyTo.sender?.name || 'Пользователь' }}</strong><span>{{ truncate(replyTo.content, 72) }}</span></div>
      <button type="button" aria-label="Отменить ответ" @click="clearReply"><i class="fas fa-times"></i></button>
    </div>

    <div v-if="selectedFiles.length" class="composer__files">
      <div v-for="(file,index) in selectedFiles" :key="`${file.name}-${index}`" class="composer-file">
        <img v-if="isImage(file)" :src="thumbnail(file)" alt="" />
        <i v-else :class="getFileIcon(file.type)"></i>
        <span>{{ file.name }}</span>
        <button type="button" aria-label="Удалить файл" @click="removeFile(index)"><i class="fas fa-times"></i></button>
      </div>
    </div>

    <div v-if="isRecording" class="recorder">
      <span class="recorder__dot"></span>
      <strong>{{ recordingKind === 'voice' ? 'Голосовое' : 'Видео' }}</strong>
      <span class="recorder__time">{{ formatTime(recordingSeconds) }}</span>
      <div class="recorder__level"><span :style="{ width: `${Math.max(4,audioLevel * 100)}%` }"></span></div>
      <button type="button" class="icon-btn danger" aria-label="Отменить запись" @click="cancelRecording"><i class="fas fa-trash"></i></button>
      <button type="button" class="icon-btn" aria-label="Остановить запись" @click="stopRecording"><i class="fas fa-stop"></i></button>
    </div>

    <div v-else-if="recordedMedia" class="recorded-preview">
      <VoiceMessage v-if="recordedMedia.kind === 'voice'" :src="recordedMedia.url" :duration="recordedMedia.duration" :waveform="recordedMedia.waveform" />
      <VideoMessage v-else :src="recordedMedia.url" :duration="recordedMedia.duration" />
      <div class="recorded-preview__actions">
        <button type="button" class="icon-btn danger" aria-label="Удалить запись" @click="clearRecording"><i class="fas fa-trash"></i></button>
        <button type="button" class="icon-btn primary" aria-label="Отправить запись" :disabled="isDisabled || sending" @click="prepareMessage"><i class="fas fa-paper-plane"></i></button>
      </div>
    </div>

    <div v-else class="composer__bar">
      <button type="button" class="icon-btn" aria-label="Эмодзи" @click="toggleEmojiPicker"><i class="fas fa-smile"></i></button>
      <input ref="textInput" v-model="messageInput" type="text" placeholder="Сообщение" :disabled="isDisabled || sending" @keydown.enter.prevent="prepareMessage" />
      <button type="button" class="icon-btn" aria-label="Прикрепить файл" :disabled="isDisabled || sending" @click="selectFile"><i class="fas fa-paperclip"></i></button>
      <template v-if="hasOutgoingContent">
        <button type="button" class="icon-btn primary" aria-label="Отправить" :disabled="isDisabled || sending" @click="prepareMessage"><i class="fas fa-paper-plane"></i></button>
      </template>
      <template v-else>
        <button type="button" class="icon-btn" :class="{ active: recordingKind === 'voice' }" aria-label="Записать голосовое" @click="startRecording('voice')"><i class="fas fa-microphone"></i></button>
        <button type="button" class="icon-btn" :class="{ active: recordingKind === 'video' }" aria-label="Записать видео" @click="startRecording('video')"><i class="fas fa-video"></i></button>
      </template>
    </div>

    <input ref="fileInput" class="visually-hidden" type="file" multiple :disabled="isDisabled" accept="image/jpeg,image/png,image/gif,image/webp,video/mp4,video/webm,video/ogg,audio/mpeg,audio/wav,audio/ogg,audio/webm,.pdf,.docx,.xlsx" @change="handleFileUpload" />
    <EmojiPicker @emoji-selected="insertEmoji" :is-show="isEmojiPickerVisible" />
    <p v-if="isDisabled" class="composer__disabled">Отправка сообщений ограничена.</p>
  </section>
</template>

<script setup>
import { computed, nextTick, onUnmounted, ref } from 'vue';
import imageCompression from 'browser-image-compression';
import EmojiPicker from './EmojiPicker.vue';
import VoiceMessage from '@/components/Message/VoiceMessage.vue';
import VideoMessage from '@/components/Message/VideoMessage.vue';

const emit = defineEmits(['send-message']);
const props = defineProps({
  replyTo: { type: Object, default: null },
  isDisabled: { type: Boolean, default: false },
});

const messageInput = ref('');
const replyTo = ref(props.replyTo || null);
const selectedFiles = ref([]);
const isEmojiPickerVisible = ref(false);
const fileInput = ref(null);
const textInput = ref(null);
const isRecording = ref(false);
const recordingKind = ref('voice');
const recordedMedia = ref(null);
const mediaRecorder = ref(null);
const recordingStream = ref(null);
const recordingChunks = ref([]);
const recordingStartedAt = ref(0);
const recordingSeconds = ref(0);
const recordingTimer = ref(null);
const audioContext = ref(null);
const analyser = ref(null);
const audioLevel = ref(0);
const waveformSamples = ref([]);
const sending = ref(false);

const allowedMimeTypes = [
  'image/jpeg','image/png','image/gif','image/webp','video/mp4','video/webm','video/ogg',
  'audio/mpeg','audio/wav','audio/ogg','audio/webm','application/pdf',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
];
const hasOutgoingContent = computed(() => Boolean(messageInput.value.trim() || selectedFiles.value.length));

const selectFile = () => fileInput.value?.click();
const isImage = (file) => file.type?.startsWith('image/');
const thumbnail = (file) => URL.createObjectURL(file);
const getFileIcon = (type = '') => type.startsWith('video/') ? 'fas fa-file-video' : type.startsWith('audio/') ? 'fas fa-file-audio' : type.includes('pdf') ? 'fas fa-file-pdf' : 'fas fa-file';
const truncate = (text,length) => String(text || '').length > length ? `${String(text).slice(0,length)}…` : String(text || '');
const formatTime = (seconds) => { const value = Math.max(0,Math.floor(Number(seconds)||0)); return `${Math.floor(value/60)}:${String(value%60).padStart(2,'0')}`; };

const compressImage = async (file) => {
  try {
    const result = await imageCompression(file,{ maxSizeMB:1,maxWidthOrHeight:1600,useWebWorker:true,fileType:'image/webp' });
    return new File([result],file.name.replace(/\.[^.]+$/,'.webp'),{ type:'image/webp' });
  } catch (_) { return file; }
};
const handleFileUpload = async (event) => {
  const incoming = Array.from(event.target.files || []).filter((file) => allowedMimeTypes.includes(file.type) && file.size <= 10*1024*1024);
  for (const file of incoming) selectedFiles.value.push(isImage(file) ? await compressImage(file) : file);
  event.target.value = '';
};
const removeFile = (index) => selectedFiles.value.splice(index,1);

const toggleEmojiPicker = () => { isEmojiPickerVisible.value = !isEmojiPickerVisible.value; };
const insertEmoji = (emoji) => { messageInput.value += emoji; isEmojiPickerVisible.value = false; nextTick(() => textInput.value?.focus()); };
const setReply = (message) => { replyTo.value = message; nextTick(() => textInput.value?.focus()); };
const clearReply = () => { replyTo.value = null; };
const focusInput = () => textInput.value?.focus();
defineExpose({ setReply, focusInput });

const chooseMimeType = (kind) => {
  const candidates = kind === 'video'
    ? ['video/webm;codecs=vp9,opus','video/webm;codecs=vp8,opus','video/webm']
    : ['audio/webm;codecs=opus','audio/webm'];
  return candidates.find((type) => window.MediaRecorder?.isTypeSupported?.(type)) || '';
};
const updateAudioLevel = () => {
  if (!analyser.value || !isRecording.value) return;
  const data = new Uint8Array(analyser.value.frequencyBinCount);
  analyser.value.getByteFrequencyData(data);
  const level = data.length ? data.reduce((sum,n) => sum+n,0)/(data.length*255) : 0;
  audioLevel.value = level;
  if (waveformSamples.value.length < 96 && Math.random() > .55) waveformSamples.value.push(Math.round(Math.max(.08,level)*100));
  requestAnimationFrame(updateAudioLevel);
};
const startRecording = async (kind) => {
  if (props.isDisabled || isRecording.value || !navigator.mediaDevices?.getUserMedia) return;
  recordingKind.value = kind;
  try {
    const stream = await navigator.mediaDevices.getUserMedia(kind === 'video' ? { audio:true,video:{ facingMode:'user',width:{ ideal:720 },height:{ ideal:720 } } } : { audio:true });
    recordingStream.value = stream;
    const mimeType = chooseMimeType(kind);
    const recorder = new MediaRecorder(stream,mimeType ? { mimeType } : undefined);
    mediaRecorder.value = recorder;
    recordingChunks.value = [];
    waveformSamples.value = [];
    recorder.ondataavailable = (event) => { if (event.data?.size) recordingChunks.value.push(event.data); };
    recorder.onstop = finalizeRecording;
    audioContext.value = new (window.AudioContext || window.webkitAudioContext)();
    analyser.value = audioContext.value.createAnalyser();
    analyser.value.fftSize = 128;
    audioContext.value.createMediaStreamSource(stream).connect(analyser.value);
    recorder.start(250);
    recordingStartedAt.value = performance.now();
    recordingSeconds.value = 0;
    isRecording.value = true;
    recordingTimer.value = window.setInterval(() => { recordingSeconds.value = (performance.now()-recordingStartedAt.value)/1000; },250);
    updateAudioLevel();
  } catch (error) {
    console.error('Media recording permission failed',error);
    alert(kind === 'video' ? 'Не удалось получить доступ к камере и микрофону' : 'Не удалось получить доступ к микрофону');
  }
};
const stopRecording = () => { if (isRecording.value && mediaRecorder.value?.state !== 'inactive') mediaRecorder.value.stop(); isRecording.value = false; };
const cancelRecording = () => {
  if (mediaRecorder.value) mediaRecorder.value.onstop = null;
  if (mediaRecorder.value?.state !== 'inactive') mediaRecorder.value.stop();
  teardownCapture();
  recordedMedia.value = null;
};
const teardownCapture = () => {
  isRecording.value = false;
  if (recordingTimer.value) window.clearInterval(recordingTimer.value);
  recordingTimer.value = null;
  recordingStream.value?.getTracks()?.forEach((track) => track.stop());
  recordingStream.value = null;
  audioContext.value?.close?.().catch?.(() => null);
  audioContext.value = null;
  analyser.value = null;
  audioLevel.value = 0;
};
const finalizeRecording = () => {
  const duration = Math.max(.1,(performance.now()-recordingStartedAt.value)/1000);
  const kind = recordingKind.value;
  const mime = mediaRecorder.value?.mimeType || (kind === 'video' ? 'video/webm' : 'audio/webm');
  const blob = new Blob(recordingChunks.value,{ type:mime });
  if (blob.size) recordedMedia.value = { kind,url:URL.createObjectURL(blob),blob,duration,waveform:[...waveformSamples.value] };
  teardownCapture();
};
const clearRecording = () => { if (recordedMedia.value?.url) URL.revokeObjectURL(recordedMedia.value.url); recordedMedia.value = null; recordingChunks.value = []; };

const fileAsDataUrl = (file) => new Promise((resolve,reject) => { const reader = new FileReader(); reader.onload = () => resolve(reader.result); reader.onerror = reject; reader.readAsDataURL(file); });
const processFiles = async () => Promise.all(selectedFiles.value.map(async (file) => ({ url:await fileAsDataUrl(file),name:file.name,type:file.type,size:file.size })));
const processRecorded = async () => recordedMedia.value ? fileAsDataUrl(recordedMedia.value.blob) : null;
const determineContentType = () => {
  if (recordedMedia.value) return recordedMedia.value.kind;
  if (selectedFiles.value.length) {
    const type = selectedFiles.value[0].type || '';
    return type.startsWith('image/') ? 'image' : type.startsWith('video/') ? 'video' : type.startsWith('audio/') ? 'audio' : 'file';
  }
  return 'text';
};
const prepareMessage = async () => {
  if (props.isDisabled || sending.value || (!messageInput.value.trim() && !selectedFiles.value.length && !recordedMedia.value)) return;
  sending.value = true;
  try {
    const type = determineContentType();
    const files = await processFiles();
    const recorded = await processRecorded();
    const media_metadata = { files };
    if (recordedMedia.value) {
      media_metadata.files = [{ url:recorded,name:recordedMedia.value.kind === 'video' ? 'video-message.webm' : 'voice-message.webm',type:recordedMedia.value.blob.type,size:recordedMedia.value.blob.size,duration:recordedMedia.value.duration,waveform:recordedMedia.value.waveform }];
      if (type === 'voice') media_metadata.voice = recorded;
      media_metadata.duration = recordedMedia.value.duration;
      media_metadata.waveform = recordedMedia.value.waveform;
      media_metadata.transcription = { status:'pending',text:'' };
    } else if (type === 'video' || type === 'audio') {
      media_metadata.transcription = { status:'pending',text:'' };
    }
    const payload = { content:messageInput.value.trim(),content_type:type,media_metadata,reply_to_uid:replyTo.value?.uid || null };
    emit('send-message',payload);
    messageInput.value = '';
    selectedFiles.value = [];
    clearRecording();
    clearReply();
  } finally { sending.value = false; }
};

onUnmounted(() => { if (isRecording.value) cancelRecording(); else teardownCapture(); clearRecording(); });
</script>

<style scoped>
.composer { position:relative; display:grid; gap:.35rem; width:100%; padding:.45rem .65rem; border-top:1px solid var(--ui-border); background:var(--ui-surface); }
.composer__bar { display:grid; grid-template-columns:36px minmax(0,1fr) 36px auto; align-items:center; gap:.25rem; min-height:44px; }
.composer__bar input { width:100%; min-width:0; height:40px; padding:0 .8rem; border:1px solid var(--ui-border-strong); border-radius:999px; background:var(--ui-surface-soft); color:var(--ui-text); }
.icon-btn { width:36px; height:36px; display:grid; place-items:center; flex:0 0 36px; border:0; border-radius:50%; background:transparent; color:var(--ui-text-muted); cursor:pointer; }
.icon-btn:hover,.icon-btn.active { background:var(--ui-surface-muted); color:var(--ui-primary); }.icon-btn.primary{background:var(--ui-primary);color:var(--ui-primary-contrast)}.icon-btn.danger{color:var(--ui-danger)}.icon-btn:disabled{opacity:.45;cursor:not-allowed}
.composer__reply { display:flex; align-items:center; gap:.5rem; padding:.35rem .55rem; border-left:3px solid var(--ui-primary); border-radius:0 8px 8px 0; background:var(--ui-surface-muted); }.composer__reply>div{display:grid;min-width:0;flex:1}.composer__reply strong{font-size:.7rem;color:var(--ui-primary)}.composer__reply span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:.76rem;color:var(--ui-text-muted)}.composer__reply button{border:0;background:transparent;color:var(--ui-text-muted);cursor:pointer}
.composer__files{display:flex;gap:.35rem;overflow-x:auto;padding-bottom:.1rem}.composer-file{display:flex;align-items:center;gap:.35rem;min-width:130px;max-width:210px;padding:.3rem .4rem;border:1px solid var(--ui-border);border-radius:10px;background:var(--ui-surface-soft);font-size:.72rem}.composer-file img{width:28px;height:28px;border-radius:6px;object-fit:cover}.composer-file span{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.composer-file button{border:0;background:transparent;color:var(--ui-text-muted);cursor:pointer}
.recorder{display:flex;align-items:center;gap:.5rem;min-height:44px;padding:0 .25rem}.recorder__dot{width:9px;height:9px;border-radius:50%;background:var(--ui-danger);animation:pulse 1s infinite}.recorder strong{font-size:.8rem}.recorder__time{font-size:.75rem;font-variant-numeric:tabular-nums;color:var(--ui-text-muted)}.recorder__level{height:5px;flex:1;overflow:hidden;border-radius:999px;background:var(--ui-surface-muted)}.recorder__level span{display:block;height:100%;background:var(--ui-primary);transition:width 100ms linear}
.recorded-preview{display:flex;align-items:center;gap:.5rem;min-width:0}.recorded-preview>:first-child{flex:1;min-width:0}.recorded-preview__actions{display:flex;gap:.2rem}.composer__disabled{margin:0;color:var(--ui-danger);font-size:.7rem}.visually-hidden{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}.disabled{opacity:.78}
@keyframes pulse{50%{opacity:.35;transform:scale(.82)}}
@media(max-width:680px){.composer{padding:.32rem .45rem;gap:.25rem}.composer__bar{grid-template-columns:34px minmax(0,1fr) 34px auto;min-height:42px;gap:.15rem}.composer__bar input{height:38px;font-size:16px;padding:0 .7rem}.icon-btn{width:34px;height:34px;flex-basis:34px}.recorded-preview{gap:.3rem}.composer__files{margin-inline:-.1rem}}
</style>
