<template>
  <article class="message" :class="[message.isCurrentUser ? 'sent' : 'received', { deleted: isDeleted }]" :data-message-id="message.uid" :data-is-read="message.is_read">
    <div v-if="replyContext" class="reply-preview">
      <div class="reply-header"><i class="fas fa-reply"></i><span>{{ replyContext.sender?.name || replyContext.sender?.username || 'Пользователь' }}</span><time>{{ replyTime }}</time></div>
      <div class="reply-content">{{ truncate(replyContext.content, 70) }}</div>
    </div>
    <div class="message-body">
      <p v-if="isDeleted" class="deleted-copy"><i class="far fa-trash-can"></i> Сообщение удалено</p>
      <p v-else-if="message.content_type === 'text'" class="message-text">{{ message.content }}</p>
      <MediaMessage v-else-if="mediaTypes.has(message.content_type)" :kind="message.content_type" :metadata="message.media_metadata || {}" :content="message.content || ''" />
      <p v-if="!isDeleted && message.content && message.content_type !== 'text'" class="media-caption">{{ message.content }}</p>
    </div>
    <MessageActions v-if="message.uid && !isDeleted" surface="messenger" :message="message" :is-own="Boolean(message.isCurrentUser)" />
    <footer class="message-meta">
      <time class="message-time">{{ formatTime(message.created_at) }}</time>
      <span v-if="message.media_metadata?.edited_at" class="edited-label">изменено</span>
      <span v-if="message.isCurrentUser" class="read-state" :title="message.is_read ? 'Прочитано' : 'Доставлено'"><i :class="message.is_read ? 'fas fa-check-double' : 'fas fa-check'"></i></span>
      <button v-if="!message.isCurrentUser && message.uid && !reportSent && !isDeleted" class="report-toggle" type="button" :aria-expanded="reportOpen" @click="reportOpen = !reportOpen"><i class="far fa-flag"></i><span>Пожаловаться</span></button>
      <span v-if="reportSent" class="report-sent"><i class="fas fa-check"></i> Жалоба отправлена</span>
    </footer>
    <form v-if="reportOpen && !reportSent" class="report-form" @submit.prevent="submitReport">
      <label>Причина<select v-model="reportCategory"><option value="spam">Спам</option><option value="harassment">Преследование / оскорбления</option><option value="sexual">Сексуальный контент</option><option value="violence">Угрозы / насилие</option><option value="privacy">Нарушение приватности</option><option value="impersonation">Выдаёт себя за другого</option><option value="fraud">Мошенничество</option><option value="hate">Травля по признаку группы</option><option value="self_harm">Риск самоповреждения</option><option value="minor_safety">Безопасность несовершеннолетних</option><option value="other">Другое</option></select></label>
      <label>Комментарий <span>необязательно</span><textarea v-model.trim="reportDescription" rows="2" maxlength="2000" placeholder="Коротко опишите проблему"></textarea></label>
      <p class="report-privacy">Trust & Safety получит это сообщение, а не всю историю личного диалога.</p><p v-if="reportError" class="report-error" role="alert">{{ reportError }}</p>
      <div class="report-actions"><button type="button" :disabled="reportSubmitting" @click="reportOpen = false">Отмена</button><button class="ui-button" type="submit" :disabled="reportSubmitting">{{ reportSubmitting ? 'Отправляем…' : 'Отправить' }}</button></div>
    </form>
  </article>
</template>

<script setup>
import { computed, ref } from 'vue';
import MediaMessage from '@/components/Message/MediaMessage.vue';
import MessageActions from '@/components/Message/MessageActions.vue';
import ModerationService from '@/API/ModerationService';
import { formatUTCDate } from '@/utils/dateFormatter';

const props=defineProps({message:{type:Object,required:true}});
const mediaTypes=new Set(['image','video','audio','voice','file']);
const isDeleted=computed(()=>props.message.content_type==='deleted');
const replyContext=computed(()=>props.message.reply_to||props.message.media_metadata?.reply_to||null);
const reportOpen=ref(false),reportSubmitting=ref(false),reportSent=ref(false),reportError=ref(''),reportCategory=ref('harassment'),reportDescription=ref('');
const truncate=(text,length)=>String(text||'').length>length?`${String(text).slice(0,length)}…`:String(text||'');
const submitReport=async()=>{if(!props.message.uid||props.message.isCurrentUser)return;reportSubmitting.value=true;reportError.value='';try{await ModerationService.createTrustSafetyReport({source_type:'messenger_message',source_uid:props.message.uid,category:reportCategory.value,description:reportDescription.value||null});reportSent.value=true;reportOpen.value=false;}catch(error){reportError.value=error.response?.data?.detail?.error_type==='trust_safety_report_rate_limited'?'Слишком много новых жалоб. Попробуйте позже.':'Не удалось отправить жалобу.';}finally{reportSubmitting.value=false;}};
const formatTime=value=>formatUTCDate(value,{showSeconds:false,showDate:false});
const replyTime=computed(()=>replyContext.value?.created_at?formatUTCDate(replyContext.value.created_at,{showSeconds:false,showDate:false}):'');
</script>

<style scoped>
.message{width:fit-content;max-width:min(76%,680px);margin:.14rem 0}.message.sent{margin-left:auto}.message.received{margin-right:auto}.message.deleted{opacity:.82}.message-body{min-width:0;padding:.45rem .62rem;border:1px solid var(--ui-border);border-radius:16px;text-align:left;box-shadow:var(--ui-shadow-sm)}.message.sent .message-body{background:var(--sent-message-bg);color:var(--sent-message-text);border-color:color-mix(in srgb,var(--ui-primary) 24%,var(--ui-border))}.message.received .message-body{background:var(--received-message-bg);color:var(--received-message-text)}.message-text,.media-caption{margin:0;white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.34}.message-text{font-size:.93rem}.media-caption{margin-top:.35rem;font-size:.84rem}.deleted-copy{display:flex;align-items:center;gap:.35rem;margin:0;color:var(--ui-text-muted);font-size:.8rem;font-style:italic}.message-meta{display:flex;align-items:center;gap:.32rem;min-height:17px;margin-top:.04rem;padding:0 .2rem;color:var(--ui-text-subtle)}.message.sent .message-meta{justify-content:flex-end}.message-time,.read-state,.edited-label{font-size:.64rem}.edited-label{font-style:italic}.read-state{color:var(--ui-primary)}
.report-toggle{display:inline-flex;align-items:center;gap:.25rem;padding:.1rem .25rem;border:0;background:transparent;color:var(--ui-text-subtle);font-size:.65rem;cursor:pointer}.report-toggle:hover{color:var(--ui-danger)}.report-sent{color:var(--ui-success);font-size:.65rem}.reply-preview{margin-bottom:.28rem;padding:.32rem .48rem;border-left:3px solid var(--ui-primary);border-radius:0 8px 8px 0;background:var(--ui-surface-muted)}.reply-header{display:flex;align-items:center;gap:.3rem;color:var(--ui-primary);font-size:.68rem;font-weight:700}.reply-header time{margin-left:auto;color:var(--ui-text-subtle);font-weight:400}.reply-content{margin-top:.1rem;color:var(--ui-text-muted);font-size:.75rem;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.report-form{display:grid;gap:.55rem;margin-top:.4rem;padding:.65rem;border:1px solid var(--ui-border);border-radius:12px;background:var(--ui-surface);color:var(--ui-text);text-align:left}.report-form label{display:grid;gap:.25rem;font-size:.72rem;font-weight:700}.report-form label span{font-weight:400;color:var(--ui-text-subtle)}.report-form select,.report-form textarea{width:100%;padding:.45rem .5rem;border:1px solid var(--ui-border);border-radius:8px;background:var(--ui-surface);color:var(--ui-text);font:inherit}.report-privacy,.report-error{margin:0;font-size:.68rem}.report-privacy{color:var(--ui-text-muted)}.report-error{color:var(--ui-danger)}.report-actions{display:flex;justify-content:flex-end;gap:.4rem}.report-actions>button:not(.ui-button){border:0;background:transparent;color:var(--ui-text-muted);cursor:pointer}
@media(max-width:680px){.message{max-width:89%;margin:.08rem 0}.message-body{padding:.36rem .5rem;border-radius:14px;box-shadow:none}.message-text{font-size:.89rem;line-height:1.3}.message-meta{min-height:15px}.report-toggle span{display:none}.report-form{min-width:min(17rem,84vw)}}
</style>
