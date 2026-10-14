<template>
  <Teleport to="body">
    <div v-if="launcherVisible" class="call-launcher" aria-label="Звонок в текущем диалоге">
      <button type="button" title="Аудиозвонок" aria-label="Аудиозвонок" @click="startCall('audio')"><i class="fas fa-phone"></i></button>
      <button type="button" title="Видеозвонок" aria-label="Видеозвонок" @click="startCall('video')"><i class="fas fa-video"></i></button>
    </div>
    <Transition name="call-overlay">
      <section v-if="visible" class="call-overlay" role="dialog" aria-modal="true" :aria-label="title">
        <div class="call-card" :class="{ 'call-card--video': call.state.mode === 'video' }">
          <div v-if="call.state.mode === 'video' && ['connecting','active'].includes(call.state.phase)" class="call-video">
            <video ref="remoteVideo" class="call-video__remote" autoplay playsinline></video>
            <video ref="localVideo" class="call-video__local" autoplay playsinline muted></video>
          </div>
          <div class="call-copy">
            <div class="call-avatar">{{ avatarLetter }}</div>
            <span class="call-state">{{ statusLabel }}</span>
            <h2>{{ peerName }}</h2>
            <p>{{ call.state.mode === 'video' ? 'Видеозвонок' : 'Аудиозвонок' }}</p>
            <p v-if="call.state.error" class="call-error">{{ call.state.error }}</p>
          </div>
          <div v-if="call.state.phase === 'incoming'" class="call-actions call-actions--incoming">
            <button type="button" class="call-action call-action--decline" aria-label="Отклонить" @click="call.decline()"><i class="fas fa-phone-slash"></i></button>
            <button type="button" class="call-action call-action--accept" aria-label="Принять" @click="call.accept()"><i :class="call.state.mode === 'video' ? 'fas fa-video' : 'fas fa-phone'"></i></button>
          </div>
          <div v-else-if="['outgoing','connecting','active'].includes(call.state.phase)" class="call-actions">
            <button type="button" class="call-action" :class="{ active: call.state.muted }" :aria-label="call.state.muted ? 'Включить микрофон' : 'Выключить микрофон'" @click="call.toggleMute()"><i :class="call.state.muted ? 'fas fa-microphone-slash' : 'fas fa-microphone'"></i></button>
            <button v-if="call.state.mode === 'video'" type="button" class="call-action" :class="{ active: !call.state.cameraEnabled }" :aria-label="call.state.cameraEnabled ? 'Выключить камеру' : 'Включить камеру'" @click="call.toggleCamera()"><i :class="call.state.cameraEnabled ? 'fas fa-video' : 'fas fa-video-slash'"></i></button>
            <button v-if="call.state.mode === 'video'" type="button" class="call-action" aria-label="Переключить камеру" @click="call.switchCamera()"><i class="fas fa-camera-rotate"></i></button>
            <button type="button" class="call-action call-action--decline" aria-label="Завершить звонок" @click="call.end()"><i class="fas fa-phone-slash"></i></button>
          </div>
          <div v-else-if="['ended','error'].includes(call.state.phase)" class="call-actions">
            <button type="button" class="call-dismiss" @click="call.dismiss()">Закрыть</button>
          </div>
        </div>
      </section>
    </Transition>
  </Teleport>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import { useStore } from 'vuex';
import { useWebRtcCall } from '@/calls/useWebRtcCall';

const call = useWebRtcCall();
const store = useStore();
const router = useRouter();
const remoteVideo = ref(null);
const localVideo = ref(null);
const isAuthenticated = computed(() => Boolean(store.getters.isAuth));
const visible = computed(() => isAuthenticated.value && call.state.phase !== 'idle');
const activeDialog = computed(() => store.getters['messenger/getActiveDialog']);
const launcherVisible = computed(() => Boolean(isAuthenticated.value && activeDialog.value && router.currentRoute.value.path.startsWith('/messenger') && ['idle','ended'].includes(call.state.phase)));
const peerName = computed(() => call.state.peer?.display_name || call.state.peer?.username || call.state.peer?.name || 'Участник PubChat');
const avatarLetter = computed(() => peerName.value.slice(0,1).toUpperCase());
const title = computed(() => `${call.state.mode === 'video' ? 'Видео' : 'Аудио'}звонок с ${peerName.value}`);
const statusLabel = computed(() => ({ outgoing:'Вызываем…',incoming:'Входящий звонок',connecting:'Соединяем…',active:'На связи',ended:'Звонок завершён',error:'Связь прервана' }[call.state.phase] || 'Звонок'));
const startCall = async (mode) => { if (call.state.phase === 'ended') call.dismiss(); try { await call.start({ uid: activeDialog.value }, mode); } catch (_) {} };
const attachStreams = async () => { await nextTick(); if (remoteVideo.value && call.state.remoteStream && remoteVideo.value.srcObject !== call.state.remoteStream) remoteVideo.value.srcObject = call.state.remoteStream; if (localVideo.value && call.state.localStream && localVideo.value.srcObject !== call.state.localStream) localVideo.value.srcObject = call.state.localStream; };
watch(() => [call.state.phase, call.state.localStream, call.state.remoteStream], attachStreams, { deep:false });
watch(isAuthenticated, (value) => { if (value) call.connect().catch(() => {}); else call.disconnect(); });
onMounted(() => { if (isAuthenticated.value) call.connect().catch(() => {}); });
onBeforeUnmount(() => call.disconnect());
</script>

<style scoped>
.call-launcher{position:fixed;z-index:1450;top:calc(var(--ui-mobile-topbar-height) + .55rem);right:max(.7rem,env(safe-area-inset-right));display:flex;gap:.35rem;padding:.25rem;border:1px solid var(--ui-border);border-radius:999px;background:color-mix(in srgb,var(--ui-surface-raised) 94%,transparent);box-shadow:var(--ui-shadow-md);backdrop-filter:blur(10px)}
.call-launcher button{width:36px;height:36px;display:grid;place-items:center;border:0;border-radius:50%;background:transparent;color:var(--ui-primary);cursor:pointer}.call-launcher button:hover{background:var(--ui-primary-soft)}
.call-overlay{position:fixed;inset:0;z-index:2500;display:grid;place-items:center;padding:1rem;background:rgba(9,10,11,.72);backdrop-filter:blur(12px)}
.call-card{position:relative;width:min(94vw,410px);min-height:360px;display:flex;flex-direction:column;justify-content:flex-end;overflow:hidden;padding:1.4rem;border:1px solid color-mix(in srgb,var(--ui-border) 55%,transparent);border-radius:28px;background:var(--ui-surface-raised);box-shadow:var(--ui-shadow-lg);color:var(--ui-text)}
.call-card--video{width:min(96vw,780px);min-height:min(78vh,650px);background:#111;color:#fff}.call-video{position:absolute;inset:0;background:#111}.call-video__remote{width:100%;height:100%;object-fit:cover}.call-video__local{position:absolute;right:1rem;top:1rem;width:min(28%,150px);aspect-ratio:3/4;object-fit:cover;border:1px solid rgba(255,255,255,.3);border-radius:16px;background:#222;box-shadow:0 8px 24px rgba(0,0,0,.35)}
.call-copy{position:relative;z-index:1;display:grid;justify-items:center;text-align:center;margin:auto 0 1.25rem}.call-card--video .call-copy{margin-top:auto;padding:3.5rem 1rem 0;background:linear-gradient(transparent,rgba(0,0,0,.72))}.call-avatar{width:84px;height:84px;display:grid;place-items:center;margin-bottom:.75rem;border-radius:50%;background:var(--ui-primary-soft);color:var(--ui-primary);font-size:2rem;font-weight:800}.call-card--video .call-avatar{display:none}.call-state{font-size:.75rem;opacity:.75}.call-copy h2{margin:.15rem 0;font-size:1.35rem}.call-copy p{margin:.1rem 0;font-size:.82rem;opacity:.75}.call-error{color:var(--ui-danger)!important;opacity:1!important}
.call-actions{position:relative;z-index:2;display:flex;justify-content:center;gap:.75rem}.call-action{width:52px;height:52px;border:0;border-radius:50%;background:color-mix(in srgb,var(--ui-text) 10%,var(--ui-surface));color:inherit;font-size:1.05rem;cursor:pointer}.call-action.active{background:var(--ui-warning-soft);color:var(--ui-warning)}.call-action--decline{background:var(--ui-danger);color:#fff}.call-action--accept{background:var(--ui-success);color:#fff}.call-actions--incoming{gap:2rem}.call-dismiss{min-height:42px;padding:0 1.1rem;border:1px solid var(--ui-border);border-radius:999px;background:var(--ui-surface);color:var(--ui-text);cursor:pointer}
.call-overlay-enter-active,.call-overlay-leave-active{transition:opacity .18s ease}.call-overlay-enter-from,.call-overlay-leave-to{opacity:0}.call-overlay-enter-active .call-card{transition:transform .22s var(--ui-ease-out)}.call-overlay-enter-from .call-card{transform:translateY(12px) scale(.98)}
@media(min-width:721px){.call-launcher{top:5rem;right:1.25rem}}
@media(max-width:680px){.call-launcher{top:calc(var(--ui-mobile-topbar-height) + 3.05rem);right:.5rem}.call-launcher button{width:32px;height:32px}.call-overlay{padding:0}.call-card{width:100%;min-height:100dvh;border:0;border-radius:0;padding:calc(1rem + env(safe-area-inset-top)) 1rem calc(1.2rem + env(safe-area-inset-bottom))}.call-card--video{min-height:100dvh}.call-action{width:50px;height:50px}.call-video__local{top:calc(.8rem + env(safe-area-inset-top));right:.8rem;width:28%;border-radius:12px}}
</style>
