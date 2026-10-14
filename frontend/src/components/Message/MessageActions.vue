<template>
  <div v-if="!isDeleted" class="message-actions">
    <div v-if="reactions.length" class="reaction-summary">
      <button v-for="reaction in reactions" :key="reaction.emoji" type="button" :class="{ selected: reaction.selected }" @click="toggleReaction(reaction.emoji)"><span>{{ reaction.emoji }}</span><small>{{ reaction.count }}</small></button>
    </div>
    <button class="message-actions__toggle" type="button" aria-label="Действия с сообщением" :aria-expanded="open" @click.stop="open = !open"><i class="fas fa-ellipsis"></i></button>
    <div v-if="open" class="message-actions__menu" @click.stop>
      <div class="quick-reactions" aria-label="Реакции"><button v-for="emoji in quickReactions" :key="emoji" type="button" @click="toggleReaction(emoji)">{{ emoji }}</button></div>
      <button type="button" @click="beginReply"><i class="fas fa-reply"></i><span>Ответить</span></button>
      <button type="button" @click="copyText"><i class="far fa-copy"></i><span>Копировать</span></button>
      <button type="button" @click="openForward"><i class="fas fa-share"></i><span>Переслать</span></button>
      <button v-if="isOwn" type="button" @click="beginEdit"><i class="far fa-pen-to-square"></i><span>Редактировать</span></button>
      <button v-if="isOwn" class="danger" type="button" @click="removeMessage"><i class="far fa-trash-can"></i><span>Удалить</span></button>
    </div>
    <Teleport to="body">
      <div v-if="replying" class="message-dialog-backdrop" @click.self="replying = false">
        <form class="message-dialog" @submit.prevent="sendReply">
          <h3>Ответить</h3>
          <div class="reply-context"><strong>{{ replyAuthor }}</strong><span>{{ replyExcerpt }}</span></div>
          <textarea v-model="replyText" rows="3" maxlength="1000" placeholder="Ваш ответ" autofocus></textarea>
          <p v-if="error" class="dialog-error">{{ error }}</p>
          <div class="dialog-actions"><button type="button" @click="replying = false">Отмена</button><button class="ui-button" type="submit" :disabled="busy || !replyText.trim()">Отправить</button></div>
        </form>
      </div>
      <div v-if="editing" class="message-dialog-backdrop" @click.self="editing = false">
        <form class="message-dialog" @submit.prevent="saveEdit"><h3>Редактировать сообщение</h3><textarea v-model="editText" rows="4" maxlength="1000" autofocus></textarea><p v-if="error" class="dialog-error">{{ error }}</p><div class="dialog-actions"><button type="button" @click="editing = false">Отмена</button><button class="ui-button" type="submit" :disabled="busy || !editText.trim()">Сохранить</button></div></form>
      </div>
      <div v-if="forwarding" class="message-dialog-backdrop" @click.self="forwarding = false">
        <section class="message-dialog forward-dialog"><header><div><h3>Переслать сообщение</h3><p>Выберите диалог или пространство</p></div><button type="button" aria-label="Закрыть" @click="forwarding = false"><i class="fas fa-times"></i></button></header><input v-model.trim="targetSearch" type="search" placeholder="Найти…" /><div v-if="targetsLoading" class="forward-state">Загружаем…</div><div v-else class="forward-targets"><button v-for="target in filteredTargets" :key="`${target.surface}:${target.uid}`" type="button" @click="forwardTo(target)"><span class="target-icon"><i :class="target.surface === 'room' ? 'fas fa-layer-group' : 'fas fa-user'"></i></span><span><strong>{{ target.name }}</strong><small>{{ target.surface === 'room' ? 'Пространство' : 'Личный диалог' }}</small></span></button><p v-if="!filteredTargets.length" class="forward-state">Подходящих получателей нет.</p></div><p v-if="error" class="dialog-error">{{ error }}</p></section>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue';
import $api from '@/API';
import MessageActionsService from '@/API/MessageActionsService';
import MessengerService from '@/API/MessengerService';

const props = defineProps({ surface:{type:String,required:true}, message:{type:Object,required:true}, isOwn:{type:Boolean,default:false} });
const quickReactions=['👍','❤️','😂','😮','😢','🔥'];
const open=ref(false),replying=ref(false),editing=ref(false),forwarding=ref(false),busy=ref(false),error=ref(''),replyText=ref(''),editText=ref(''),targets=ref([]),targetsLoading=ref(false),targetSearch=ref('');
const reactions=ref(Array.isArray(props.message.media_metadata?.reactions)?props.message.media_metadata.reactions:[]);
const isDeleted=computed(()=>props.message.content_type==='deleted');
const replyAuthor=computed(()=>props.message.sender?.name||props.message.sender?.username||'Участник PubChat');
const replyExcerpt=computed(()=>{const text=String(props.message.content||'Медиа-сообщение');return text.length>120?`${text.slice(0,120)}…`:text;});
const filteredTargets=computed(()=>{const q=targetSearch.value.toLocaleLowerCase();return targets.value.filter(t=>!q||t.name.toLocaleLowerCase().includes(q));});
const loadReactions=async()=>{if(!props.message.uid)return;try{reactions.value=(await MessageActionsService.reactions(props.surface,props.message.uid)).data.reactions||[];}catch(_){}};
const toggleReaction=async emoji=>{if(!props.message.uid||busy.value)return;busy.value=true;try{reactions.value=(await MessageActionsService.react(props.surface,props.message.uid,emoji)).data.reactions||[];}finally{busy.value=false;open.value=false;}};
const beginReply=()=>{replyText.value='';error.value='';replying.value=true;open.value=false;};
const sendReply=async()=>{if(!replyText.value.trim()||busy.value)return;busy.value=true;error.value='';try{await MessageActionsService.reply(props.surface,props.message.uid,replyText.value.trim());replying.value=false;}catch(_){error.value='Не удалось отправить ответ.';}finally{busy.value=false;}};
const copyText=async()=>{const text=props.message.content||'';if(text)try{await navigator.clipboard.writeText(text);}catch(_){}open.value=false;};
const beginEdit=()=>{editText.value=props.message.content||'';error.value='';editing.value=true;open.value=false;};
const saveEdit=async()=>{if(!editText.value.trim()||busy.value)return;busy.value=true;error.value='';try{await MessageActionsService.edit(props.surface,props.message.uid,editText.value.trim());editing.value=false;}catch(_){error.value='Не удалось сохранить изменения.';}finally{busy.value=false;}};
const removeMessage=async()=>{open.value=false;if(!confirm('Удалить это сообщение?'))return;try{await MessageActionsService.remove(props.surface,props.message.uid);}catch(_){}};
const loadForwardTargets=async()=>{targetsLoading.value=true;error.value='';try{const[d,s]=await Promise.all([MessengerService.getDialogs().catch(()=>({data:{dialogs:[]}})),$api.get('/spaces/v1',{params:{limit:50,offset:0}}).catch(()=>({data:{spaces:[]}}))]);const dialogs=d.data?.dialogs||d.data?.data||[];const spaces=s.data?.spaces||[];targets.value=[...dialogs.map(x=>({surface:'messenger',uid:x.partner_id,name:x.partner?.display_name||x.partner?.username||'Личный диалог'})),...spaces.filter(x=>x.viewer_membership?.status==='active'||x.can_manage).map(x=>({surface:'room',uid:x.uid,name:x.name||'Пространство'}))];}finally{targetsLoading.value=false;}};
const openForward=async()=>{open.value=false;forwarding.value=true;targetSearch.value='';await loadForwardTargets();};
const forwardTo=async target=>{if(busy.value)return;busy.value=true;error.value='';try{await MessageActionsService.forward(props.surface,props.message.uid,target.surface,target.uid);forwarding.value=false;}catch(err){error.value=err.response?.data?.detail?.error_type==='dm_not_allowed'?'Получатель не принимает такие личные сообщения.':'Не удалось переслать сообщение.';}finally{busy.value=false;}};
watch(()=>props.message.media_metadata?.reactions,(value)=>{if(Array.isArray(value))reactions.value=value;},{deep:true});
onMounted(loadReactions);
</script>

<style scoped>
.message-actions{position:relative;display:flex;align-items:center;gap:.25rem;min-height:22px;margin-top:.15rem}.message-actions__toggle{width:26px;height:26px;display:grid;place-items:center;margin-left:auto;border:0;border-radius:50%;background:transparent;color:var(--ui-text-subtle);cursor:pointer;opacity:.2}.message-actions:hover .message-actions__toggle,.message-actions__toggle:focus-visible{opacity:.9;background:color-mix(in srgb,currentColor 8%,transparent)}
.reaction-summary{display:flex;gap:.2rem;flex-wrap:wrap}.reaction-summary button{display:inline-flex;align-items:center;gap:.18rem;min-height:24px;padding:.1rem .38rem;border:1px solid var(--ui-border);border-radius:999px;background:var(--ui-surface);color:var(--ui-text);font-size:.72rem;cursor:pointer}.reaction-summary button.selected{border-color:var(--ui-primary);background:var(--ui-primary-soft)}.reaction-summary small{font-size:.62rem;color:var(--ui-text-muted)}
.message-actions__menu{position:absolute;right:0;bottom:28px;z-index:40;width:190px;display:grid;padding:.35rem;border:1px solid var(--ui-border);border-radius:12px;background:var(--ui-surface-raised);box-shadow:var(--ui-shadow-lg)}.message-actions__menu>button{display:flex;align-items:center;gap:.55rem;min-height:36px;padding:0 .55rem;border:0;border-radius:8px;background:transparent;color:var(--ui-text);text-align:left;cursor:pointer}.message-actions__menu>button:hover{background:var(--ui-surface-muted)}.message-actions__menu>button.danger{color:var(--ui-danger)}.message-actions__menu i{width:18px;text-align:center}.quick-reactions{display:grid;grid-template-columns:repeat(6,1fr);gap:1px;padding:.15rem .1rem .35rem;border-bottom:1px solid var(--ui-border);margin-bottom:.2rem}.quick-reactions button{padding:.18rem 0;border:0;border-radius:6px;background:transparent;cursor:pointer}.quick-reactions button:hover{background:var(--ui-surface-muted)}
.message-dialog-backdrop{position:fixed;inset:0;z-index:2700;display:grid;place-items:center;padding:1rem;background:rgba(0,0,0,.55);backdrop-filter:blur(5px)}.message-dialog{width:min(94vw,480px);display:grid;gap:.8rem;padding:1rem;border:1px solid var(--ui-border);border-radius:18px;background:var(--ui-surface-raised);color:var(--ui-text);box-shadow:var(--ui-shadow-lg)}.message-dialog h3,.message-dialog p{margin:0}.message-dialog textarea,.message-dialog input{width:100%;padding:.65rem .75rem;border:1px solid var(--ui-border-strong);border-radius:10px;background:var(--ui-surface);color:var(--ui-text);font:inherit}.reply-context{display:grid;gap:.15rem;padding:.5rem .6rem;border-left:3px solid var(--ui-primary);border-radius:0 8px 8px 0;background:var(--ui-surface-muted)}.reply-context strong{font-size:.72rem;color:var(--ui-primary)}.reply-context span{font-size:.78rem;color:var(--ui-text-muted);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.dialog-actions{display:flex;justify-content:flex-end;gap:.5rem}.dialog-actions>button:not(.ui-button){border:0;background:transparent;color:var(--ui-text-muted);cursor:pointer}.dialog-error{color:var(--ui-danger);font-size:.75rem}
.forward-dialog{max-height:min(80dvh,620px);grid-template-rows:auto auto minmax(0,1fr) auto}.forward-dialog header{display:flex;justify-content:space-between;gap:1rem;align-items:flex-start}.forward-dialog header>div{display:grid;gap:.15rem}.forward-dialog header p{color:var(--ui-text-muted);font-size:.75rem}.forward-dialog header>button{width:32px;height:32px;border:0;border-radius:50%;background:transparent;color:var(--ui-text-muted);cursor:pointer}.forward-targets{min-height:80px;overflow-y:auto;display:grid;align-content:start;gap:.2rem}.forward-targets>button{display:flex;align-items:center;gap:.65rem;min-height:52px;padding:.45rem .55rem;border:0;border-radius:10px;background:transparent;color:var(--ui-text);text-align:left;cursor:pointer}.forward-targets>button:hover{background:var(--ui-surface-muted)}.target-icon{width:36px;height:36px;display:grid;place-items:center;border-radius:50%;background:var(--ui-primary-soft);color:var(--ui-primary)}.forward-targets>button>span:last-child{display:grid}.forward-targets small{color:var(--ui-text-muted);font-size:.68rem}.forward-state{padding:1rem;text-align:center;color:var(--ui-text-muted);font-size:.8rem}
@media(max-width:680px){.message-actions__toggle{opacity:.65}.message-actions__menu{position:fixed;left:.5rem;right:.5rem;bottom:calc(var(--ui-mobile-nav-height) + .5rem + env(safe-area-inset-bottom));width:auto;grid-template-columns:repeat(2,minmax(0,1fr));padding:.45rem;border-radius:16px}.quick-reactions{grid-column:1/-1}.message-dialog-backdrop{padding:.5rem;align-items:end}.message-dialog{width:100%;border-radius:18px 18px 0 0;padding:1rem;margin-bottom:env(safe-area-inset-bottom)}}
</style>
