<template>
	<main class="community-shell">
		<header class="community-header">
			<div>
				<RouterLink class="back-link" :to="{ name: 'space', params: { uid: spaceUid } }"><i class="fas fa-arrow-left"></i>В разговор</RouterLink>
				<span class="eyebrow">Центр пространства</span>
				<h1>{{ space?.name || 'Пространство' }}</h1>
				<p>{{ space?.description || 'Правила, события и память этого пространства.' }}</p>
			</div>
			<div class="community-header__actions">
				<span v-if="space?.viewer_membership?.role" class="role-badge">{{ roleLabel(space.viewer_membership.role) }}</span>
				<RouterLink v-if="canManage" class="manager-link" :to="{ name: 'space-moderation', params: { uid: spaceUid } }">
					<i class="fas fa-shield-halved" aria-hidden="true"></i>Модерация
				</RouterLink>
			</div>
		</header>

		<nav class="content-tabs" aria-label="Разделы пространства">
			<button v-for="tab in tabs" :key="tab.value" type="button" :class="{ active: activeTab === tab.value }" @click="activeTab = tab.value">
				<i :class="tab.icon"></i>{{ tab.label }}
			</button>
		</nav>

		<section v-if="notice" class="notice" :class="`notice--${notice.type}`" role="status">{{ notice.message }}</section>

		<section v-if="loading" class="state-block"><i class="fas fa-circle-notch fa-spin"></i><strong>Загружаем пространство…</strong></section>

		<template v-else>
			<section v-if="activeTab === 'rules'" class="content-section">
				<form v-if="canManage" class="editor-card" @submit.prevent="createRule">
					<div class="editor-heading"><div><span>Новое правило</span><strong>Зафиксируйте понятную границу сообщества</strong></div></div>
					<input v-model.trim="ruleDraft.title" maxlength="120" required placeholder="Например: Без личных оскорблений" />
					<textarea v-model.trim="ruleDraft.body" maxlength="4000" required rows="3" placeholder="Коротко объясните правило и зачем оно нужно"></textarea>
					<div class="editor-footer"><label>Порядок <input v-model.number="ruleDraft.position" type="number" min="0" max="1000" /></label><button class="ui-button" type="submit" :disabled="saving">Добавить правило</button></div>
				</form>

				<div v-if="rules.length" class="rule-list">
					<article v-for="(rule, index) in rules" :key="rule.uid" class="rule-card">
						<span class="rule-index">{{ index + 1 }}</span>
						<div><h2>{{ rule.title }}</h2><p>{{ rule.body }}</p></div>
						<button v-if="canManage" type="button" class="icon-danger" aria-label="Удалить правило" @click="deleteRule(rule)"><i class="fas fa-trash"></i></button>
					</article>
				</div>
				<div v-else class="state-block state-block--compact"><i class="fas fa-scroll"></i><strong>Правила пока не опубликованы</strong><span>До появления правил действуют общие нормы PubChat и решения команды пространства.</span></div>
			</section>

			<section v-else-if="activeTab === 'events'" class="content-section">
				<form v-if="canManage" class="editor-card" @submit.prevent="createEvent">
					<div class="editor-heading"><div><span>Новое событие</span><strong>Дайте людям повод вернуться одновременно</strong></div></div>
					<input v-model.trim="eventDraft.title" maxlength="120" required placeholder="Квиз, игровая ночь, разговор по теме…" />
					<textarea v-model.trim="eventDraft.description" maxlength="4000" rows="3" placeholder="Что будет происходить"></textarea>
					<div class="date-grid"><label>Начало<input v-model="eventDraft.starts_at" type="datetime-local" required /></label><label>Окончание<input v-model="eventDraft.ends_at" type="datetime-local" /></label></div>
					<div class="editor-footer"><span></span><button class="ui-button" type="submit" :disabled="saving">Создать событие</button></div>
				</form>

				<div v-if="events.length" class="event-list">
					<article
						v-for="event in events"
						:id="`event-${event.uid}`"
						:key="event.uid"
						class="event-card"
						:class="{ 'event-card--cancelled': event.status === 'cancelled', 'pulse-focused': focusedEventUid === String(event.uid) }"
					>
						<div class="event-date"><strong>{{ eventDay(event.starts_at) }}</strong><span>{{ eventMonth(event.starts_at) }}</span></div>
						<div class="event-copy"><div class="event-title"><h2>{{ event.title }}</h2><span v-if="event.status === 'cancelled'">Отменено</span></div><p>{{ event.description || 'Подробности появятся ближе к началу.' }}</p><small><i class="fas fa-clock"></i>{{ formatEventTime(event) }}</small></div>
						<div v-if="canManage" class="event-actions"><button v-if="event.status !== 'cancelled'" type="button" title="Отменить" @click="cancelEvent(event)"><i class="fas fa-ban"></i></button><button type="button" class="danger" title="Удалить" @click="deleteEvent(event)"><i class="fas fa-trash"></i></button></div>
					</article>
				</div>
				<div v-else class="state-block state-block--compact"><i class="fas fa-calendar-days"></i><strong>Событий пока нет</strong><span>События превращают пространство из постоянного чата в место, где есть общий ритм.</span></div>
			</section>

			<section v-else class="content-section">
				<div v-if="historyError" class="state-block state-block--compact"><i class="fas fa-lock"></i><strong>История доступна участникам</strong><span>Вступите в пространство, чтобы видеть журнал изменений.</span></div>
				<div v-else-if="history.length" class="history-list">
					<article v-for="entry in history" :key="entry.uid" class="history-entry">
						<span class="history-dot"><i :class="historyIcon(entry.event_type)"></i></span>
						<div><strong>{{ entry.summary }}</strong><span>{{ actorLabel(entry) }} · {{ formatDateTime(entry.created_at) }}</span></div>
					</article>
				</div>
				<div v-else class="state-block state-block--compact"><i class="fas fa-clock-rotate-left"></i><strong>История только начинается</strong><span>Значимые изменения правил и событий будут появляться здесь автоматически.</span></div>
			</section>
		</template>
	</main>
</template>

<script setup>
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue';
import { RouterLink, useRoute } from 'vue-router';

import SpacesService from '@/API/SpacesService';

const route = useRoute();
const spaceUid = computed(() => String(route.params.uid || ''));
const space = ref(null);
const rules = ref([]);
const events = ref([]);
const history = ref([]);
const loading = ref(true);
const saving = ref(false);
const historyError = ref(false);
const notice = ref(null);
const initialTab = ['rules', 'events', 'history'].includes(String(route.query.tab || '')) ? String(route.query.tab) : 'rules';
const activeTab = ref(initialTab);
const ruleDraft = reactive({ title: '', body: '', position: 0 });
const eventDraft = reactive({ title: '', description: '', starts_at: '', ends_at: '' });
const tabs = [
	{ value: 'rules', label: 'Правила', icon: 'fas fa-scroll' },
	{ value: 'events', label: 'События', icon: 'fas fa-calendar-days' },
	{ value: 'history', label: 'История', icon: 'fas fa-clock-rotate-left' },
];

const canManage = computed(() => Boolean(space.value?.can_manage));
const focusedEventUid = computed(() => String(route.query.focus || ''));
const showNotice = (message, type = 'success') => { notice.value = { message, type }; window.setTimeout(() => { if (notice.value?.message === message) notice.value = null; }, 3200); };

const focusRequestedEvent = async () => {
	if (activeTab.value !== 'events' || !focusedEventUid.value || loading.value) return;
	await nextTick();
	const target = document.getElementById(`event-${focusedEventUid.value}`);
	target?.scrollIntoView({ behavior: 'smooth', block: 'center' });
};

const loadAll = async () => {
	loading.value = true;
	historyError.value = false;
	try {
		const [spaceResponse, rulesResponse, eventsResponse] = await Promise.all([
			SpacesService.get(spaceUid.value),
			SpacesService.rules(spaceUid.value),
			SpacesService.events(spaceUid.value, { limit: 100, offset: 0 }),
		]);
		space.value = spaceResponse.data.space;
		rules.value = rulesResponse.data.rules || [];
		events.value = eventsResponse.data.events || [];
		try {
			const historyResponse = await SpacesService.history(spaceUid.value, { limit: 100, offset: 0 });
			history.value = historyResponse.data.history || [];
		} catch (error) {
			history.value = [];
			historyError.value = error.response?.status === 403;
			if (!historyError.value) throw error;
		}
	} catch (error) {
		console.error('Не удалось загрузить центр пространства:', error);
		showNotice('Не удалось загрузить данные пространства.', 'error');
	} finally { loading.value = false; await focusRequestedEvent(); }
};

const refreshHistory = async () => {
	if (historyError.value) return;
	try {
		const response = await SpacesService.history(spaceUid.value, { limit: 100, offset: 0 });
		history.value = response.data.history || [];
	} catch (error) { console.error('Не удалось обновить историю:', error); }
};

const createRule = async () => {
	saving.value = true;
	try {
		const response = await SpacesService.createRule(spaceUid.value, { ...ruleDraft });
		rules.value = [...rules.value, response.data.rule].sort((a, b) => a.position - b.position);
		Object.assign(ruleDraft, { title: '', body: '', position: rules.value.length });
		await refreshHistory();
		showNotice('Правило опубликовано.');
	} catch (error) { showNotice('Не удалось добавить правило.', 'error'); } finally { saving.value = false; }
};

const deleteRule = async (rule) => {
	try {
		await SpacesService.deleteRule(spaceUid.value, rule.uid);
		rules.value = rules.value.filter((item) => item.uid !== rule.uid);
		await refreshHistory();
		showNotice('Правило удалено.');
	} catch (error) { showNotice('Не удалось удалить правило.', 'error'); }
};

const localDateTimeToIso = (value) => value ? new Date(value).toISOString() : null;
const createEvent = async () => {
	saving.value = true;
	try {
		const payload = { title: eventDraft.title, description: eventDraft.description || null, starts_at: localDateTimeToIso(eventDraft.starts_at), ends_at: localDateTimeToIso(eventDraft.ends_at) };
		const response = await SpacesService.createEvent(spaceUid.value, payload);
		events.value = [...events.value, response.data.event].sort((a, b) => new Date(a.starts_at) - new Date(b.starts_at));
		Object.assign(eventDraft, { title: '', description: '', starts_at: '', ends_at: '' });
		await refreshHistory();
		showNotice('Событие создано.');
	} catch (error) {
		const type = error.response?.data?.detail?.error_type;
		showNotice(type === 'invalid_event_time_range' ? 'Окончание должно быть позже начала.' : 'Не удалось создать событие.', 'error');
	} finally { saving.value = false; }
};

const cancelEvent = async (event) => {
	try {
		const response = await SpacesService.updateEvent(spaceUid.value, event.uid, { status: 'cancelled' });
		Object.assign(event, response.data.event);
		await refreshHistory();
		showNotice('Событие отменено.');
	} catch (error) { showNotice('Не удалось отменить событие.', 'error'); }
};

const deleteEvent = async (event) => {
	try {
		await SpacesService.deleteEvent(spaceUid.value, event.uid);
		events.value = events.value.filter((item) => item.uid !== event.uid);
		await refreshHistory();
		showNotice('Событие удалено.');
	} catch (error) { showNotice('Не удалось удалить событие.', 'error'); }
};

const roleLabel = (role) => ({ owner: 'Создатель', moderator: 'Модератор', member: 'Участник' }[role] || 'Участник');
const eventDay = (value) => new Intl.DateTimeFormat('ru', { day: '2-digit' }).format(new Date(value));
const eventMonth = (value) => new Intl.DateTimeFormat('ru', { month: 'short' }).format(new Date(value));
const formatEventTime = (event) => {
	const formatter = new Intl.DateTimeFormat('ru', { day: 'numeric', month: 'long', hour: '2-digit', minute: '2-digit' });
	return event.ends_at ? `${formatter.format(new Date(event.starts_at))} — ${formatter.format(new Date(event.ends_at))}` : formatter.format(new Date(event.starts_at));
};
const formatDateTime = (value) => new Intl.DateTimeFormat('ru', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' }).format(new Date(value));
const actorLabel = (entry) => entry.actor?.display_name || (entry.actor?.handle ? `@${entry.actor.handle}` : 'Система');
const historyIcon = (type) => type.startsWith('rule_') ? 'fas fa-scroll' : type.startsWith('event_') ? 'fas fa-calendar-days' : 'fas fa-circle';

watch(spaceUid, loadAll);
watch(() => route.query.tab, (value) => {
	activeTab.value = ['rules', 'events', 'history'].includes(String(value || '')) ? String(value) : 'rules';
	focusRequestedEvent();
});
watch(() => route.query.focus, focusRequestedEvent);
onMounted(loadAll);
</script>

<style scoped>
.community-shell { display: grid; gap: var(--ui-space-5); padding-bottom: var(--ui-space-8); }.community-header { display: flex; align-items: flex-end; justify-content: space-between; gap: var(--ui-space-5); padding: clamp(1.4rem, 4vw, 2.4rem); border: 1px solid var(--ui-border); border-radius: var(--ui-radius-xl); background: linear-gradient(135deg, var(--ui-surface) 0%, var(--ui-primary-soft) 180%); }.community-header > div:first-child { max-width: 44rem; }.community-header__actions { display: flex; align-items: center; gap: var(--ui-space-2); flex-wrap: wrap; justify-content: flex-end; }.back-link { display: inline-flex; align-items: center; gap: .4rem; margin-bottom: var(--ui-space-3); color: var(--ui-text-muted); text-decoration: none; font-size: var(--ui-text-sm); }.eyebrow { display: block; color: var(--ui-primary); font-size: var(--ui-text-xs); font-weight: 800; letter-spacing: .08em; text-transform: uppercase; }.community-header h1 { margin: .25rem 0 0; font-size: clamp(1.8rem, 4vw, 2.7rem); letter-spacing: -.035em; }.community-header p { margin: var(--ui-space-2) 0 0; color: var(--ui-text-muted); line-height: 1.55; }.role-badge { padding: .4rem .7rem; border-radius: var(--ui-radius-pill); background: var(--ui-surface); color: var(--ui-primary); font-size: var(--ui-text-xs); font-weight: 800; }.manager-link { min-height: 2.45rem; display: inline-flex; align-items: center; gap: .45rem; padding: 0 var(--ui-space-3); border: 1px solid color-mix(in srgb, var(--ui-primary) 30%, var(--ui-border)); border-radius: var(--ui-radius-pill); background: var(--ui-primary-soft); color: var(--ui-primary); text-decoration: none; font-size: var(--ui-text-xs); font-weight: 800; }
.content-tabs { display: flex; gap: var(--ui-space-2); overflow-x: auto; }.content-tabs button { min-height: 2.7rem; display: inline-flex; align-items: center; gap: var(--ui-space-2); padding: 0 var(--ui-space-4); border: 1px solid var(--ui-border); border-radius: var(--ui-radius-pill); background: var(--ui-surface); color: var(--ui-text-muted); font: inherit; font-weight: 700; cursor: pointer; }.content-tabs button.active { background: var(--ui-primary-soft); color: var(--ui-primary); border-color: color-mix(in srgb, var(--ui-primary) 30%, var(--ui-border)); }.notice { padding: var(--ui-space-3) var(--ui-space-4); border-radius: var(--ui-radius-lg); background: var(--ui-success-soft); color: var(--ui-success); }.notice--error { background: var(--ui-danger-soft); color: var(--ui-danger); }.content-section { display: grid; gap: var(--ui-space-4); }
.editor-card { display: grid; gap: var(--ui-space-3); padding: var(--ui-space-5); border: 1px solid var(--ui-border); border-radius: var(--ui-radius-xl); background: var(--ui-surface); }.editor-heading div { display: grid; gap: .2rem; }.editor-heading span { color: var(--ui-primary); font-size: var(--ui-text-xs); font-weight: 800; text-transform: uppercase; }.editor-card > input, .editor-card textarea, .editor-card label input { width: 100%; border: 1px solid var(--ui-border); border-radius: var(--ui-radius-md); background: var(--ui-bg); color: var(--ui-text); font: inherit; }.editor-card > input { min-height: 2.9rem; padding: 0 var(--ui-space-3); }.editor-card textarea { padding: var(--ui-space-3); resize: vertical; }.editor-footer { display: flex; align-items: center; justify-content: space-between; gap: var(--ui-space-3); }.editor-footer label, .date-grid label { display: grid; gap: .3rem; color: var(--ui-text-muted); font-size: var(--ui-text-xs); }.editor-footer label input { width: 6rem; min-height: 2.4rem; padding: 0 var(--ui-space-2); }.date-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: var(--ui-space-3); }.date-grid input { min-height: 2.8rem; padding: 0 var(--ui-space-3); border: 1px solid var(--ui-border); border-radius: var(--ui-radius-md); background: var(--ui-bg); color: var(--ui-text); }
.rule-list, .event-list, .history-list { display: grid; gap: var(--ui-space-3); }.rule-card { display: grid; grid-template-columns: auto minmax(0, 1fr) auto; gap: var(--ui-space-3); align-items: start; padding: var(--ui-space-4); border: 1px solid var(--ui-border); border-radius: var(--ui-radius-lg); background: var(--ui-surface); }.rule-index { width: 2rem; height: 2rem; display: grid; place-items: center; border-radius: 50%; background: var(--ui-primary-soft); color: var(--ui-primary); font-weight: 800; }.rule-card h2, .event-card h2 { margin: 0; font-size: var(--ui-text-md); }.rule-card p, .event-card p { margin: .45rem 0 0; color: var(--ui-text-muted); line-height: 1.55; white-space: pre-wrap; }.icon-danger { width: 2.3rem; height: 2.3rem; border: 0; border-radius: var(--ui-radius-md); background: transparent; color: var(--ui-text-subtle); cursor: pointer; }.icon-danger:hover { background: var(--ui-danger-soft); color: var(--ui-danger); }
.event-card { display: grid; grid-template-columns: auto minmax(0, 1fr) auto; gap: var(--ui-space-4); align-items: center; padding: var(--ui-space-4); border: 1px solid var(--ui-border); border-radius: var(--ui-radius-lg); background: var(--ui-surface); scroll-margin-top:6rem; transition:border-color .2s ease,box-shadow .2s ease,background .2s ease; }.event-card.pulse-focused { border-color:color-mix(in srgb,var(--ui-primary) 52%,var(--ui-border)); background:color-mix(in srgb,var(--ui-primary-soft) 24%,var(--ui-surface)); box-shadow:0 0 0 3px color-mix(in srgb,var(--ui-primary) 12%,transparent); }.event-card--cancelled { opacity: .65; }.event-date { width: 3.7rem; height: 3.7rem; display: grid; place-items: center; align-content: center; border-radius: var(--ui-radius-lg); background: var(--ui-primary-soft); color: var(--ui-primary); line-height: 1; }.event-date strong { font-size: var(--ui-text-lg); }.event-date span { margin-top: .25rem; font-size: .68rem; text-transform: uppercase; }.event-title { display: flex; align-items: center; gap: var(--ui-space-2); }.event-title span { padding: .2rem .45rem; border-radius: var(--ui-radius-pill); background: var(--ui-danger-soft); color: var(--ui-danger); font-size: .65rem; font-weight: 800; }.event-copy small { display: inline-flex; align-items: center; gap: .35rem; margin-top: var(--ui-space-2); color: var(--ui-text-subtle); }.event-actions { display: flex; gap: var(--ui-space-1); }.event-actions button { width: 2.3rem; height: 2.3rem; border: 1px solid var(--ui-border); border-radius: var(--ui-radius-md); background: transparent; color: var(--ui-text-muted); cursor: pointer; }.event-actions button.danger:hover { background: var(--ui-danger-soft); color: var(--ui-danger); }
.history-entry { display: grid; grid-template-columns: auto 1fr; gap: var(--ui-space-3); padding: var(--ui-space-3) var(--ui-space-4); border-left: 2px solid var(--ui-border); }.history-dot { width: 2rem; height: 2rem; display: grid; place-items: center; margin-left: -1.08rem; border-radius: 50%; background: var(--ui-surface); border: 1px solid var(--ui-border); color: var(--ui-primary); }.history-entry div { display: grid; gap: .25rem; }.history-entry span { color: var(--ui-text-subtle); font-size: var(--ui-text-xs); }.state-block { min-height: 18rem; display: grid; place-items: center; align-content: center; gap: var(--ui-space-2); color: var(--ui-text-muted); text-align: center; }.state-block--compact { min-height: 12rem; padding: var(--ui-space-5); border: 1px dashed var(--ui-border); border-radius: var(--ui-radius-xl); }.state-block > i { color: var(--ui-primary); font-size: 2rem; }.state-block strong { color: var(--ui-text); }
@media (max-width: 700px) { .community-header { align-items: stretch; flex-direction: column; }.community-header__actions { justify-content: flex-start; }.date-grid { grid-template-columns: 1fr; }.editor-footer { align-items: stretch; flex-direction: column; }.editor-footer .ui-button { width: 100%; }.event-card { grid-template-columns: auto 1fr; }.event-actions { grid-column: 1 / -1; justify-content: flex-end; } }
@media (prefers-reduced-motion: reduce) { .event-card { transition:none; } }
</style>