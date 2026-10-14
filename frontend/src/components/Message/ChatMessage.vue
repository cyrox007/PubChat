<template>
  <article v-if="safeMessage" :class="['message', messageType, { 'has-reply': safeMessage.reply_to, deleted: isDeleted }]">
    <button v-if="!isDeleted" class="reply-button" type="button" @click="handleReply" :aria-label="`Ответить на сообщение от ${safeMessage.sender.name}`"><i class="fas fa-reply"></i></button>
    <div v-if="safeMessage.reply_to" class="reply-preview">
      <div class="reply-header"><i class="fas fa-reply"></i><span>{{ safeMessage.reply_to.sender.name }}</span></div>
      <div class="reply-content">{{ truncate(safeMessage.reply_to.content, 70) }}</div>
    </div>
    <header class="message-header"><img :src="avatarUrl" alt="" class="avatar" /><div class="user-info"><strong>{{ safeMessage.sender.name }}</strong><time class="timestamp">{{ formattedTimestamp }}</time><span v-if="safeMessage.media_metadata?.edited_at" class="edited-label">изменено</span></div></header>
    <div class="message-body">
      <p v-if="isDeleted" class="deleted-copy"><i class="far fa-trash-can"></i> Сообщение удалено</p>
      <p v-else-if="safeMessage.content && safeMessage.content_type === 'text'" class="message-text">{{ safeMessage.content }}</p>
      <MediaMessage v-else-if="!isDeleted && mediaTypes.has(safeMessage.content_type)" :kind="safeMessage.content_type" :metadata="safeMessage.media_metadata" :content="safeMessage.content" />
      <p v-if="!isDeleted && safeMessage.content && safeMessage.content_type !== 'text'" class="media-caption">{{ safeMessage.content }}</p>
      <p v-if="!isDeleted && !safeMessage.content && !mediaTypes.has(safeMessage.content_type)" class="unsupported">Неподдерживаемый тип сообщения</p>
    </div>
    <MessageActions v-if="safeMessage.uid && !isDeleted" surface="room" :message="safeMessage" :is-own="isOwn" />
    <div v-if="safeMessage.status" class="message-status" :aria-label="safeMessage.status"><i v-if="safeMessage.status === 'sending'" class="fas fa-spinner fa-spin"></i><i v-else-if="safeMessage.status === 'error'" class="fas fa-exclamation-circle error"></i><i v-else class="fas fa-check"></i></div>
  </article>
  <div v-else class="loading-message">Загрузка сообщения…</div>
</template>

<script setup>
import { computed } from 'vue';
import { useStore } from 'vuex';
import MediaMessage from '@/components/Message/MediaMessage.vue';
import MessageActions from '@/components/Message/MessageActions.vue';
import { formatUTCDate } from '@/utils/dateFormatter';

const emit = defineEmits(['reply']);
const props = defineProps({ message: { type: Object, required: true } });
const store = useStore();
const apiBaseUrl = String(import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '');
const mediaTypes = new Set(['image', 'video', 'audio', 'voice', 'file']);
const currentUser = computed(() => store.getters.getUser || {});
const safeMessage = computed(() => {
  if (!props.message) return null;
  const sender = props.message.sender || {};
  const metadata = props.message.media_metadata && typeof props.message.media_metadata === 'object' ? props.message.media_metadata : {};
  const reply = props.message.reply_to || metadata.reply_to || null;
  return {
    uid: props.message.uid || null,
    frontId: props.message.frontId || props.message.tempId || null,
    content: props.message.content ?? props.message.text ?? '',
    content_type: props.message.content_type || 'text',
    media_metadata: metadata,
    sender: { uid: sender.uid || null, name: sender.username || sender.name || 'Неизвестный пользователь', avatar: sender.avatar || '/images/default-avatar.png' },
    room_uid: props.message.room_uid || null,
    created_at: props.message.created_at || new Date().toISOString(),
    status: props.message.status || 'sent',
    reply_to: reply ? { uid: reply.uid || null, content: reply.content || '', sender: { uid: reply.sender?.uid || null, name: reply.sender?.name || reply.sender?.username || 'Пользователь' } } : null,
  };
});
const absoluteUrl = (url) => { if (!url) return '/images/default-avatar.png'; if (/^(?:https?:|blob:|data:)/i.test(url)) return url; return `${apiBaseUrl}${url.startsWith('/') ? '' : '/'}${url}`; };
const avatarUrl = computed(() => absoluteUrl(safeMessage.value?.sender.avatar));
const formattedTimestamp = computed(() => safeMessage.value ? formatUTCDate(safeMessage.value.created_at, { showSeconds:false,showDate:true }) : '');
const isOwn = computed(() => String(safeMessage.value?.sender.uid) === String(currentUser.value?.uid));
const isDeleted = computed(() => safeMessage.value?.content_type === 'deleted');
const messageType = computed(() => isOwn.value ? 'sender' : 'other-user');
const truncate = (text,length) => String(text||'').length>length ? `${String(text).slice(0,length)}…` : String(text||'');
const handleReply = () => emit('reply',{uid:safeMessage.value.uid,content:safeMessage.value.content,sender:safeMessage.value.sender});
</script>

<style scoped>
.message{position:relative;width:fit-content;max-width:min(78%,680px);margin:.2rem 0;padding:.55rem .65rem .3rem;border:1px solid color-mix(in srgb,var(--ui-border) 70%,transparent);border-radius:16px;box-shadow:var(--ui-shadow-sm);text-align:left}.message.sender{align-self:flex-end;background:var(--sent-message-bg);color:var(--sent-message-text)}.message.other-user{align-self:flex-start;background:var(--received-message-bg);color:var(--received-message-text)}.message.deleted{opacity:.82}.message-header{display:flex;align-items:center;gap:.5rem;min-height:32px;padding-right:2rem;margin-bottom:.3rem}.avatar{width:32px;height:32px;flex:0 0 32px;border-radius:50%;object-fit:cover;border:1px solid var(--profile-avatar-border)}.user-info{min-width:0;display:flex;align-items:baseline;gap:.45rem;flex-wrap:wrap}.user-info strong{font-size:.88rem;line-height:1.1}.timestamp,.edited-label{color:var(--ui-text-muted);font-size:.67rem;white-space:nowrap}.edited-label{font-style:italic}.message-body{min-width:0}.message-text,.media-caption{margin:0;white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.38}.message-text{font-size:.94rem}.media-caption{margin-top:.4rem;font-size:.86rem}.unsupported,.deleted-copy{margin:0;color:var(--ui-text-muted);font-size:.8rem}.deleted-copy{display:flex;align-items:center;gap:.35rem;font-style:italic}.reply-button{position:absolute;top:.42rem;right:.45rem;width:30px;height:30px;display:grid;place-items:center;border:0;border-radius:50%;background:color-mix(in srgb,var(--ui-surface) 68%,transparent);color:currentColor;cursor:pointer;opacity:0;transition:opacity var(--ui-motion-fast)}.message:hover .reply-button,.reply-button:focus-visible{opacity:1}.reply-preview{margin:-.05rem 2rem .4rem 0;padding:.35rem .5rem;border-left:3px solid var(--ui-primary);border-radius:0 8px 8px 0;background:color-mix(in srgb,var(--ui-surface) 65%,transparent)}.reply-header{display:flex;gap:.3rem;align-items:center;color:var(--ui-primary);font-size:.7rem;font-weight:700}.reply-content{margin-top:.1rem;color:var(--ui-text-muted);font-size:.76rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.message-status{display:flex;justify-content:flex-end;height:11px;color:var(--ui-text-muted);font-size:.62rem}.message-status .error{color:var(--ui-danger)}.loading-message{padding:.5rem;color:var(--ui-text-muted);font-size:.8rem}
@media(max-width:680px){.message{max-width:88%;margin:.1rem 0;padding:.4rem .5rem .22rem;border-radius:14px;box-shadow:none}.message-header{min-height:27px;gap:.38rem;margin-bottom:.18rem}.avatar{width:27px;height:27px;flex-basis:27px}.user-info strong{font-size:.8rem}.timestamp,.edited-label{font-size:.61rem}.message-text{font-size:.89rem;line-height:1.3}.reply-button{opacity:.68;width:27px;height:27px;top:.28rem;right:.3rem}.reply-preview{padding:.25rem .4rem;margin-bottom:.25rem}.message-status{height:9px}}
</style>
