<template>
	<main v-if="space" class="life-shell">
		<header class="life-hero" :class="[`theme--${appearance.theme_preset}`, `cover--${appearance.cover_preset}`]">
			<div class="ambient">{{ appearance.ambient_icon || '☕' }}</div>
			<div><span class="eyebrow">Жизнь пространства</span><h1>{{ space.name }}</h1><p>{{ appearance.welcome_line || space.description || 'Место для регулярных встреч, разговоров и совместных активностей.' }}</p></div>
			<RouterLink class="ui-button ui-button--ghost" :to="{ name: 'space', params: { uid: space.uid } }">В разговор</RouterLink>
		</header>

		<nav class="life-tabs">
			<button type="button" :class="{ active: tab === 'activities' }" @click="tab = 'activities'">Активности</button>
			<button type="button" :class="{ active: tab === 'appearance' }" @click="tab = 'appearance'">Оформление</button>
		</nav>

		<section v-if="tab === 'activities'" class="content-card">
			<header class="section-head">
				<div><span>Повторные встречи</span><strong>Что происходит здесь</strong></div>
				<button class="ui-button" type="button" @click="showActivityForm = !showActivityForm"><i class="fas fa-plus"></i>Создать</button>
			</header>
			<div v-if="activityNotice" :class="['notice', `notice--${activityNotice.type}`]" role="status">{{ activityNotice.message }}</div>

			<form v-if="showActivityForm" class="activity-form" @submit.prevent="createActivity">
				<label>Название<input v-model.trim="activityDraft.title" maxlength="120" required /></label>
				<label>Формат<select v-model="activityDraft.activity_type"><option value="hangout">Разговор</option><option value="quiz">Викторина</option><option value="game">Игра</option><option value="watch">Совместный просмотр</option><option value="creative">Творчество</option><option value="local">Локальная встреча</option></select></label>
				<label>Когда<input v-model="activityDraft.starts_at" type="datetime-local" required /><small class="timezone-hint">Часовой пояс: {{ activityDraft.timezone }}</small></label>
				<label>Повтор<select v-model="activityDraft.recurrence"><option value="none">Один раз</option><option value="daily">Каждый день</option><option value="weekly">Каждую неделю</option><option value="monthly">Каждый месяц</option></select></label>
				<label class="wide">Описание<textarea v-model.trim="activityDraft.description" rows="3" maxlength="2000"></textarea></label>
				<div class="wide form-actions"><button type="button" @click="showActivityForm = false">Отмена</button><button class="ui-button" type="submit" :disabled="creatingActivity">{{ creatingActivity ? 'Создаём…' : 'Создать активность' }}</button></div>
			</form>

			<div v-if="activitiesLoading" class="state-card">Загружаем активности…</div>
			<div v-else-if="activities.length" class="activity-list">
				<article
					v-for="activity in activities"
					:id="`activity-${activity.uid}`"
					:key="activity.uid"
					class="activity-card"
					:class="{ cancelled: activity.status === 'cancelled', 'pulse-focused': focusedActivityUid === String(activity.uid) }"
				>
					<div class="activity-main">
						<div class="activity-icon"><i :class="activityIcon(activity.activity_type)"></i></div>
						<div class="activity-copy">
							<div class="activity-title"><strong>{{ activity.title }}</strong><span v-if="activity.recurrence !== 'none'">{{ recurrenceLabel(activity.recurrence) }}</span><span v-if="activity.status === 'cancelled'" class="cancelled-label">отменено</span></div>
							<p v-if="activity.description">{{ activity.description }}</p>
							<small>{{ activityTimeLabel(activity) }} · {{ activity.rsvp.going }} идут · {{ activity.rsvp.interested }} интересуются</small>
						</div>
					</div>

					<div v-if="activity.status !== 'cancelled'" class="activity-actions">
						<div class="rsvp-actions">
							<button type="button" :class="{ active: activity.rsvp.viewer === 'interested' }" @click="setRsvp(activity, 'interested')">Интересно</button>
							<button type="button" :class="{ active: activity.rsvp.viewer === 'going' }" @click="setRsvp(activity, 'going')">Иду</button>
							<button v-if="activity.rsvp.viewer" type="button" class="clear" @click="clearRsvp(activity)">Снять</button>
							<button v-if="canManageActivity(activity)" type="button" class="danger-link" @click="cancelActivity(activity)">Отменить</button>
						</div>
						<ActivityReminderControl :activity-uid="activity.uid" :reminder="reminders[activity.uid] || null" @changed="updateReminder(activity.uid, $event)" />
					</div>

					<ConversationRoundsPanel v-if="activity.status !== 'cancelled'" :activity="activity" :can-manage-space="Boolean(space.can_manage)" :current-account-uid="currentUserUid || ''" />
				</article>
			</div>
			<div v-else class="state-card"><strong>Активностей пока нет</strong><span>Создайте первый повод встретиться — достаточно темы и времени.</span></div>
		</section>

		<section v-else class="content-card">
			<header class="section-head"><div><span>Атмосфера</span><strong>Оформление пространства</strong></div></header>
			<div v-if="!space.can_manage" class="state-card"><strong>Оформлением управляет команда пространства</strong><span>Вы видите текущую атмосферу, но изменить её могут owner и moderator.</span></div>
			<form v-else class="appearance-form" @submit.prevent="saveAppearance">
				<label>Тема<select v-model="appearanceDraft.theme_preset"><option value="lounge">Гостиная</option><option value="warm">Тёплая</option><option value="garden">Сад</option><option value="studio">Студия</option><option value="night">Ночь</option></select></label>
				<label>Фон<select v-model="appearanceDraft.cover_preset"><option value="soft-gradient">Мягкий градиент</option><option value="paper">Бумага</option><option value="mist">Туман</option><option value="linen">Лён</option><option value="night">Ночь</option></select></label>
				<label>Символ<input v-model.trim="appearanceDraft.ambient_icon" maxlength="16" placeholder="☕" /></label>
				<label class="wide">Приветственная строка<input v-model.trim="appearanceDraft.welcome_line" maxlength="160" /></label>
				<div class="wide form-actions"><span v-if="appearanceNotice">{{ appearanceNotice }}</span><button class="ui-button" type="submit" :disabled="savingAppearance">{{ savingAppearance ? 'Сохраняем…' : 'Сохранить оформление' }}</button></div>
			</form>
		</section>
	</main>
	<main v-else class="state-card">{{ loading ? 'Загружаем пространство…' : 'Пространство недоступно.' }}</main>
</template>

<script setup>
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue';
import { RouterLink, useRoute } from 'vue-router';
import { useStore } from 'vuex';

import EngagementService from '@/API/EngagementService';
import NotificationService from '@/API/NotificationService';
import SpacesService from '@/API/SpacesService';
import ActivityReminderControl from '@/components/Spaces/ActivityReminderControl.vue';
import ConversationRoundsPanel from '@/components/Spaces/ConversationRoundsPanel.vue';

const route = useRoute();
const store = useStore();
const loading = ref(true);
const space = ref(null);
const appearance = ref({ theme_preset: 'lounge', cover_preset: 'soft-gradient', ambient_icon: null, welcome_line: null });
const appearanceDraft = reactive({ theme_preset: 'lounge', cover_preset: 'soft-gradient', ambient_icon: '', welcome_line: '' });
const reminders = ref({});
const tab = ref(route.query.tab === 'appearance' ? 'appearance' : 'activities');
const activities = ref([]);
const activitiesLoading = ref(false);
const showActivityForm = ref(false);
const creatingActivity = ref(false);
const savingAppearance = ref(false);
const appearanceNotice = ref('');
const activityNotice = ref(null);
const browserTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
const activityDraft = reactive({ title: '', description: '', activity_type: 'hangout', starts_at: '', timezone: browserTimezone, recurrence: 'none' });
const currentUserUid = computed(() => store.getters.getUser?.uid);
const focusedActivityUid = computed(() => String(route.query.focus || ''));

const focusRequestedActivity = async () => {
	if (tab.value !== 'activities' || !focusedActivityUid.value || activitiesLoading.value) return;
	await nextTick();
	const target = document.getElementById(`activity-${focusedActivityUid.value}`);
	target?.scrollIntoView({ behavior: 'smooth', block: 'center' });
};

const applyAppearance = (value = {}) => {
	appearance.value = { theme_preset: value.theme_preset || 'lounge', cover_preset: value.cover_preset || 'soft-gradient', ambient_icon: value.ambient_icon || null, welcome_line: value.welcome_line || null };
	Object.assign(appearanceDraft, { theme_preset: appearance.value.theme_preset, cover_preset: appearance.value.cover_preset, ambient_icon: appearance.value.ambient_icon || '', welcome_line: appearance.value.welcome_line || '' });
};
const updateReminder = (activityUid, reminder) => { const next = { ...reminders.value }; if (reminder) next[activityUid] = reminder; else delete next[activityUid]; reminders.value = next; };

const load = async () => {
	loading.value = true;
	try {
		const [spaceResponse, appearanceResponse] = await Promise.all([SpacesService.get(route.params.uid), EngagementService.spaceAppearance(route.params.uid)]);
		space.value = spaceResponse.data.space;
		applyAppearance(appearanceResponse.data.appearance);
		await loadActivities();
	} catch (error) { console.error(error); }
	finally { loading.value = false; }
};

const loadActivities = async () => {
	activitiesLoading.value = true;
	try {
		const [activityResponse, reminderResponse] = await Promise.all([
			EngagementService.activities(route.params.uid, { limit: 100 }),
			NotificationService.remindersForSpace(route.params.uid),
		]);
		activities.value = activityResponse.data.activities || [];
		reminders.value = Object.fromEntries((reminderResponse.data.reminders || []).map((item) => [item.activity_uid, item]));
	} catch (error) { console.error(error); activityNotice.value = { type: 'error', message: 'Не удалось загрузить активности или напоминания.' }; }
	finally { activitiesLoading.value = false; await focusRequestedActivity(); }
};

const createActivity = async () => {
	creatingActivity.value = true; activityNotice.value = null;
	try {
		await EngagementService.createActivity(route.params.uid, { ...activityDraft, starts_at: new Date(activityDraft.starts_at).toISOString(), description: activityDraft.description || null });
		Object.assign(activityDraft, { title: '', description: '', activity_type: 'hangout', starts_at: '', timezone: browserTimezone, recurrence: 'none' });
		showActivityForm.value = false;
		await loadActivities();
		activityNotice.value = { type: 'success', message: 'Активность создана.' };
	} catch (error) { console.error(error); activityNotice.value = { type: 'error', message: 'Не удалось создать активность.' }; }
	finally { creatingActivity.value = false; }
};

const saveAppearance = async () => {
	savingAppearance.value = true; appearanceNotice.value = '';
	try { const response = await EngagementService.updateSpaceAppearance(route.params.uid, { ...appearanceDraft, ambient_icon: appearanceDraft.ambient_icon || null, welcome_line: appearanceDraft.welcome_line || null }); applyAppearance(response.data.appearance); appearanceNotice.value = 'Оформление сохранено.'; }
	catch { appearanceNotice.value = 'Не удалось сохранить оформление.'; }
	finally { savingAppearance.value = false; }
};
const setRsvp = async (activity, status) => { try { const response = await EngagementService.rsvp(activity.uid, status); replaceActivity(response.data.activity); } catch { activityNotice.value = { type: 'error', message: 'Не удалось обновить участие.' }; } };
const clearRsvp = async (activity) => { try { const response = await EngagementService.clearRsvp(activity.uid); replaceActivity(response.data.activity); } catch { activityNotice.value = { type: 'error', message: 'Не удалось снять участие.' }; } };
const canManageActivity = (activity) => Boolean(space.value?.can_manage || activity.created_by_account_uid === currentUserUid.value);
const cancelActivity = async (activity) => { try { const response = await EngagementService.updateActivity(route.params.uid, activity.uid, { status: 'cancelled' }); replaceActivity(response.data.activity); updateReminder(activity.uid, null); activityNotice.value = { type: 'success', message: 'Активность отменена.' }; } catch { activityNotice.value = { type: 'error', message: 'Не удалось отменить активность.' }; } };
const replaceActivity = (next) => { const index = activities.value.findIndex((item) => item.uid === next.uid); if (index >= 0) activities.value[index] = next; };
const activityIcon = (value) => ({ quiz: 'fas fa-circle-question', game: 'fas fa-gamepad', watch: 'fas fa-film', creative: 'fas fa-palette', local: 'fas fa-location-dot', hangout: 'fas fa-comments' }[value] || 'fas fa-comments');
const recurrenceLabel = (value) => ({ daily: 'каждый день', weekly: 'каждую неделю', monthly: 'каждый месяц' }[value] || '');
const formatDate = (value) => new Intl.DateTimeFormat('ru', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }).format(new Date(value));
const activityTimeLabel = (activity) => `${activity.recurrence === 'none' ? '' : 'Следующая: '}${formatDate(activity.next_starts_at || activity.starts_at)}`;
watch(() => route.query.tab, (value) => { tab.value = value === 'appearance' ? 'appearance' : 'activities'; focusRequestedActivity(); });
watch(() => route.query.focus, focusRequestedActivity);
onMounted(load);
</script>

<style scoped>
.life-shell{display:grid;gap:var(--ui-space-5);padding-bottom:var(--ui-space-8)}.life-hero{display:grid;grid-template-columns:auto minmax(0,1fr) auto;align-items:center;gap:var(--ui-space-5);padding:clamp(1.4rem,4vw,2.4rem);border:1px solid var(--ui-border);border-radius:var(--ui-radius-xl);background:linear-gradient(135deg,var(--ui-surface),var(--ui-primary-soft))}.ambient{width:4rem;height:4rem;display:grid;place-items:center;border-radius:1.25rem;background:var(--ui-surface);font-size:1.8rem;box-shadow:var(--ui-shadow-sm)}.eyebrow{color:var(--ui-primary);font-size:var(--ui-text-xs);font-weight:800;text-transform:uppercase}.life-hero h1{margin:.25rem 0;font-size:clamp(1.7rem,4vw,2.6rem)}.life-hero p{margin:0;color:var(--ui-text-muted)}.life-tabs{display:flex;gap:var(--ui-space-2);border-bottom:1px solid var(--ui-border)}.life-tabs button{padding:.8rem 1rem;border:0;border-bottom:2px solid transparent;background:transparent;color:var(--ui-text-muted);font:inherit;font-weight:700;cursor:pointer}.life-tabs button.active{border-bottom-color:var(--ui-primary);color:var(--ui-text)}.content-card{display:grid;gap:var(--ui-space-4);padding:var(--ui-space-5);border:1px solid var(--ui-border);border-radius:var(--ui-radius-xl);background:var(--ui-surface)}.section-head{display:flex;justify-content:space-between;gap:var(--ui-space-4);align-items:center}.section-head div{display:grid}.section-head span{color:var(--ui-text-subtle);font-size:var(--ui-text-xs);text-transform:uppercase}.section-head strong{font-size:var(--ui-text-xl)}.notice{padding:var(--ui-space-3);border-radius:var(--ui-radius-md);background:var(--ui-success-soft);color:var(--ui-success)}.notice--error{background:var(--ui-danger-soft);color:var(--ui-danger)}.activity-form,.appearance-form{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:var(--ui-space-3);padding:var(--ui-space-4);border:1px solid var(--ui-border);border-radius:var(--ui-radius-lg);background:var(--ui-surface-muted)}.activity-form label,.appearance-form label{display:grid;gap:.35rem;font-size:var(--ui-text-sm);font-weight:700}.timezone-hint{color:var(--ui-text-subtle);font-size:var(--ui-text-xs);font-weight:500}.activity-form input,.activity-form select,.activity-form textarea,.appearance-form input,.appearance-form select{width:100%;padding:.75rem;border:1px solid var(--ui-border);border-radius:var(--ui-radius-md);background:var(--ui-surface);color:var(--ui-text);font:inherit}.wide{grid-column:1/-1}.form-actions{display:flex;align-items:center;justify-content:flex-end;gap:var(--ui-space-3)}.activity-list{display:grid;gap:var(--ui-space-3)}.activity-card{display:grid;gap:var(--ui-space-3);padding:var(--ui-space-4);border:1px solid var(--ui-border);border-radius:var(--ui-radius-lg);scroll-margin-top:6rem;transition:border-color .2s ease,box-shadow .2s ease,background .2s ease}.activity-card.pulse-focused{border-color:color-mix(in srgb,var(--ui-primary) 52%,var(--ui-border));background:color-mix(in srgb,var(--ui-primary-soft) 24%,var(--ui-surface));box-shadow:0 0 0 3px color-mix(in srgb,var(--ui-primary) 12%,transparent)}.activity-card.cancelled{opacity:.62}.activity-main{display:grid;grid-template-columns:auto minmax(0,1fr);gap:var(--ui-space-3);align-items:center}.activity-icon{width:2.8rem;height:2.8rem;display:grid;place-items:center;border-radius:.9rem;background:var(--ui-primary-soft);color:var(--ui-primary)}.activity-copy p{margin:.35rem 0;color:var(--ui-text-muted)}.activity-copy small{color:var(--ui-text-subtle)}.activity-title{display:flex;gap:var(--ui-space-2);align-items:center;flex-wrap:wrap}.activity-title span{padding:.2rem .45rem;border-radius:var(--ui-radius-pill);background:var(--ui-surface-muted);font-size:.7rem}.activity-title .cancelled-label{background:var(--ui-danger-soft);color:var(--ui-danger)}.activity-actions{display:flex;align-items:flex-start;justify-content:space-between;gap:var(--ui-space-3);flex-wrap:wrap}.rsvp-actions{display:flex;gap:.35rem;flex-wrap:wrap}.rsvp-actions button{min-height:2.25rem;padding:0 .7rem;border:1px solid var(--ui-border);border-radius:var(--ui-radius-pill);background:var(--ui-surface);color:var(--ui-text-muted);cursor:pointer}.rsvp-actions button.active{background:var(--ui-primary-soft);border-color:var(--ui-primary);color:var(--ui-primary)}.rsvp-actions .clear,.rsvp-actions .danger-link{border:0;background:transparent}.rsvp-actions .danger-link{color:var(--ui-danger)}.state-card{display:grid;gap:.25rem;padding:var(--ui-space-5);border:1px dashed var(--ui-border);border-radius:var(--ui-radius-lg);color:var(--ui-text-muted)}.state-card strong{color:var(--ui-text)}@media(max-width:760px){.life-hero{grid-template-columns:auto 1fr}.life-hero .ui-button{grid-column:1/-1}.activity-form,.appearance-form{grid-template-columns:1fr}.wide{grid-column:auto}.section-head{align-items:stretch;flex-direction:column}.activity-actions{display:grid;grid-template-columns:1fr}.form-actions{flex-direction:column;align-items:stretch}}@media(prefers-reduced-motion:reduce){.activity-card{transition:none}}
</style>
