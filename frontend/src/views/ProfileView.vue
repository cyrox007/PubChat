<template>
	<main class="profile-page">
		<section v-if="isLoading" class="profile-card profile-card--loading" aria-live="polite">
			<div class="profile-skeleton profile-skeleton--avatar"></div>
			<div class="profile-skeleton profile-skeleton--title"></div>
			<div class="profile-skeleton"></div>
		</section>

		<section v-else-if="errorMessage" class="profile-card profile-empty" role="alert">
			<h1>Профиль недоступен</h1>
			<p>{{ errorMessage }}</p>
			<RouterLink class="ui-button ui-button--secondary" to="/">Вернуться к пространствам</RouterLink>
		</section>

		<template v-else-if="profile">
			<section class="profile-card profile-hero" :class="profileAppearanceClasses">
				<div class="profile-avatar" :class="avatarFrameClass" aria-hidden="true">
					<img v-if="profile.avatar" :src="avatarUrl" alt="" />
					<span v-else>{{ avatarFallback }}</span>
					<span class="presence-dot" :class="{ 'presence-dot--self': profile.is_self }"></span>
				</div>

				<div class="profile-main">
					<div class="profile-title-row">
						<div>
							<p class="profile-handle">@{{ profile.handle }}</p>
							<h1>{{ profile.display_name }}</h1>
						</div>
						<span class="intent-chip">{{ intentLabel(profile.social_intent) }}</span>
					</div>

					<p class="profile-bio">{{ profile.bio || 'Пока ничего о себе не написал.' }}</p>
					<p v-if="appearance?.status_line" class="persona-status"><i class="fas fa-comment-dots" aria-hidden="true"></i>{{ appearance.status_line }}</p>

					<div class="profile-meta">
						<span v-if="locationLabel">{{ locationLabel }}</span>
						<span v-if="profile.role" class="role-chip">{{ roleLabel(profile.role) }}</span>
						<span v-if="profile.is_self" class="self-chip">Это ваш образ</span>
					</div>
				</div>

				<div class="profile-actions">
					<button v-if="profile.is_self" class="ui-button ui-button--primary" @click="toggleEdit">
						{{ isEditing ? 'Закрыть настройки' : 'Настроить образ' }}
					</button>
					<RouterLink v-if="profile.is_self" class="ui-button ui-button--secondary" :to="{ name: 'persona-style' }">Стиль образа</RouterLink>
					<button v-else class="ui-button ui-button--primary" :disabled="profile.contact_policy === 'nobody'" @click="openChatWithUser">
						{{ profile.contact_policy === 'nobody' ? 'Личные сообщения закрыты' : 'Написать' }}
					</button>
					<button v-if="!profile.is_self && isAdmin" class="ui-button ui-button--secondary" @click="openAdminPanel">
						Управление
					</button>
				</div>
			</section>

			<section v-if="!profile.is_self" class="profile-card contact-context">
				<div>
					<p class="section-eyebrow">Контекст общения</p>
					<h2>{{ contactPolicyTitle }}</h2>
				</div>
				<p>{{ contactPolicyDescription }}</p>
			</section>

			<PersonaSwitcher v-if="profile.is_self" @activated="refreshActivePersona" />

			<AchievementShelf :account-uid="profile.uid" :is-self="profile.is_self" />

			<Transition name="ui-state">
			<section v-if="profile.is_self && isEditing" class="profile-card settings-card">
				<header class="settings-header">
					<div>
						<p class="section-eyebrow">Persona</p>
						<h2>Как вас видят люди</h2>
					</div>
					<p>Account, вход и безопасность сюда не смешиваются — это отдельные настройки.</p>
				</header>

				<div v-if="saveMessage" :class="['ui-notice', saveState === 'error' ? 'ui-notice--danger' : 'ui-notice--success']" role="status">
					{{ saveMessage }}
				</div>

				<form class="settings-grid" @submit.prevent="saveProfile">
					<label class="field">
						<span>Отображаемое имя</span>
						<input v-model.trim="editForm.display_name" class="ui-input" maxlength="80" required />
					</label>

					<label class="field field--wide">
						<span>О себе</span>
						<textarea v-model.trim="editForm.bio" class="ui-input" maxlength="500" rows="4"></textarea>
					</label>

					<label class="field">
						<span>Город</span>
						<input v-model.trim="editForm.city" class="ui-input" maxlength="100" />
					</label>
					<label class="field">
						<span>Страна</span>
						<input v-model.trim="editForm.country" class="ui-input" maxlength="100" />
					</label>

					<label class="field">
						<span>Сейчас я…</span>
						<select v-model="editForm.social_intent" class="ui-input">
							<option value="open">Хочу пообщаться</option>
							<option value="meet">Открыт новым знакомствам</option>
							<option value="games">Ищу компанию для игры</option>
							<option value="friends">Только знакомые</option>
							<option value="quiet">Не ищу новых контактов</option>
						</select>
					</label>

					<label v-if="identity.persona?.is_primary !== false" class="field">
						<span>Кто может начинать личный диалог</span>
						<select v-model="privacyForm.dm_policy" class="ui-input">
							<option value="everyone">Все</option>
							<option value="shared_spaces">Люди из общих пространств</option>
							<option value="mutual">Только взаимные контакты</option>
							<option value="nobody">Никто</option>
						</select>
					</label>

					<label v-if="identity.persona?.is_primary !== false" class="toggle-row field--wide">
						<input v-model="privacyForm.show_location" type="checkbox" />
						<span>
							<strong>Показывать город и страну</strong>
							<small>По умолчанию местоположение скрыто.</small>
						</span>
					</label>

					<p v-if="identity.persona?.is_primary === false" class="field--wide">
						Дополнительный образ пока приватен. Политика личных сообщений остаётся у основного Persona.
					</p>
					<div class="settings-actions field--wide">
						<button class="ui-button ui-button--primary" type="submit" :disabled="isSaving" :aria-busy="isSaving ? 'true' : 'false'">
							<span v-if="isSaving" class="button-pending"><span class="ui-spinner" aria-hidden="true"></span>Сохраняем…</span>
							<span v-else>Сохранить изменения</span>
						</button>
					</div>
				</form>
			</section>
			</Transition>
		</template>
	</main>
</template>

<script setup>
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue';
import { RouterLink, useRoute, useRouter } from 'vue-router';
import { useStore } from 'vuex';

import AuthService from '@/API/AuthService';
import CSRFService from '@/API/CSRFService';
import EngagementService from '@/API/EngagementService';
import AchievementShelf from '@/components/Profile/AchievementShelf.vue';
import PersonaSwitcher from '@/components/Profile/PersonaSwitcher.vue';

const route = useRoute();
const router = useRouter();
const store = useStore();

const profile = ref(null);
const appearance = ref(null);
const isLoading = ref(true);
const errorMessage = ref('');
const isEditing = ref(false);
const isSaving = ref(false);
const saveMessage = ref('');
const saveState = ref('success');

const editForm = reactive({ display_name: '', bio: '', city: '', country: '', social_intent: 'open' });
const privacyForm = reactive({ dm_policy: 'shared_spaces', show_location: false });

const currentUser = computed(() => store.getters.getUser || {});
const identity = computed(() => store.getters.getIdentity || {});
const isAdmin = computed(() => ['admin', 'superadmin'].includes(currentUser.value.global_role));
const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/$/, '');

const avatarUrl = computed(() => {
	if (!profile.value?.avatar) return '';
	if (/^https?:\/\//.test(profile.value.avatar)) return profile.value.avatar;
	return `${apiBaseUrl}${profile.value.avatar}`;
});
const avatarFallback = computed(() => (profile.value?.display_name || profile.value?.handle || '?').slice(0, 1).toUpperCase());
const locationLabel = computed(() => [profile.value?.city, profile.value?.country].filter(Boolean).join(', '));
const profileAppearanceClasses = computed(() => {
	const accent = ['plum', 'berry', 'forest', 'ocean', 'sand'].includes(appearance.value?.accent_preset)
		? appearance.value.accent_preset
		: 'plum';
	const background = ['soft', 'paper', 'mist', 'night'].includes(appearance.value?.background_preset)
		? appearance.value.background_preset
		: 'soft';
	return [`profile-hero--accent-${accent}`, `profile-hero--background-${background}`];
});
const avatarFrameClass = computed(() => {
	const frame = ['none', 'soft', 'double', 'badge'].includes(appearance.value?.avatar_frame_preset)
		? appearance.value.avatar_frame_preset
		: 'none';
	return `profile-avatar--frame-${frame}`;
});

const intentLabel = (intent) => ({
	open: 'Хочу пообщаться', meet: 'Открыт знакомствам', games: 'Ищу компанию для игры', friends: 'Только знакомые', quiet: 'Спокойный режим',
}[intent] || 'Хочу пообщаться');
const roleLabel = (role) => ({ admin: 'Команда PubChat', moderator: 'Trust & Safety' }[role] || role);

const contactPolicyTitle = computed(() => ({
	everyone: 'Можно написать напрямую',
	shared_spaces: 'Лучше познакомиться в общем пространстве',
	mutual: 'Личные сообщения после взаимного контакта',
	nobody: 'Сейчас не принимает новые личные сообщения',
}[profile.value?.contact_policy] || 'Общение по контексту'));
const contactPolicyDescription = computed(() => ({
	everyone: 'Persona открыта новым личным диалогам.',
	shared_spaces: 'PubChat показывает этот выбор, чтобы новые разговоры начинались из общего контекста.',
	mutual: 'Пользователь предпочитает сначала установить взаимный контакт.',
	nobody: 'Уважайте выбранный режим — начать новый личный диалог сейчас нельзя.',
}[profile.value?.contact_policy] || 'Учитывайте социальную доступность человека перед новым контактом.'));

const hydrateEditForms = () => {
	if (!profile.value) return;
	editForm.display_name = profile.value.display_name || '';
	editForm.bio = profile.value.bio || '';
	editForm.city = profile.value.city || '';
	editForm.country = profile.value.country || '';
	editForm.social_intent = profile.value.social_intent || 'open';
	privacyForm.dm_policy = identity.value.privacy?.dm_policy || profile.value.contact_policy || 'shared_spaces';
	privacyForm.show_location = Boolean(identity.value.privacy?.show_location);
};

const loadProfileAppearance = async () => {
	appearance.value = null;
	if (!profile.value?.persona_uid) return;
	try {
		const response = await EngagementService.personaAppearance(profile.value.persona_uid);
		appearance.value = response.data.appearance || null;
	} catch (error) {
		console.error('Не удалось загрузить оформление Persona:', error);
	}
};

const loadProfile = async (uid) => {
	if (!uid) return;
	isLoading.value = true;
	errorMessage.value = '';
	try {
		if (uid === currentUser.value.uid && identity.value.persona?.is_primary === false) {
			const persona = identity.value.persona;
			profile.value = {
				...persona, uid, persona_uid: persona.uid,
				is_self: true, contact_policy: identity.value.privacy?.dm_policy || 'nobody',
			};
		} else {
			const response = await AuthService.getProfile(uid);
			profile.value = response.data.profile;
		}
		document.title = `${profile.value.display_name} — PubChat`;
		hydrateEditForms();
		await loadProfileAppearance();
	} catch (error) {
		profile.value = null;
		appearance.value = null;
		if (error.response?.status === 403) errorMessage.value = 'Этот образ доступен только выбранному кругу людей.';
		else if (error.response?.status === 404) errorMessage.value = 'Такого профиля больше нет.';
		else errorMessage.value = 'Не удалось загрузить профиль.';
	} finally {
		isLoading.value = false;
	}
};

const resolveProfileUid = async () => {
	const uid = route.params.uid || currentUser.value.uid;
	if (!uid) return;
	if (!route.params.uid) {
		await router.replace({ name: 'UserProfile', params: { uid } });
		return;
	}
	await loadProfile(uid);
};

const refreshActivePersona = async () => {
	isEditing.value = false;
	saveMessage.value = '';
	await loadProfile(currentUser.value.uid);
};

const toggleEdit = () => {
	isEditing.value = !isEditing.value;
	saveMessage.value = '';
	if (isEditing.value) hydrateEditForms();
};

const saveProfile = async () => {
	isSaving.value = true;
	saveMessage.value = '';
	try {
		await CSRFService.getCSRF();
		const personaResponse = await AuthService.updatePersona({ ...editForm });
		const data = identity.value.persona?.is_primary === false
			? personaResponse.data
			: (await AuthService.updatePrivacy({ ...privacyForm })).data;
		store.commit('setUser', data.user || personaResponse.data.user);
		store.commit('setIdentity', {
			account: data.account,
			persona: data.persona,
			privacy: data.privacy,
			role: data.role,
		});
		saveState.value = 'success';
		saveMessage.value = 'Изменения сохранены.';
		await loadProfile(currentUser.value.uid);
	} catch {
		saveState.value = 'error';
		saveMessage.value = 'Не удалось сохранить изменения.';
	} finally {
		isSaving.value = false;
	}
};

const openChatWithUser = async () => {
	if (!profile.value || profile.value.contact_policy === 'nobody') return;
	await store.dispatch('messenger/setActiveDialog', profile.value.uid);
	await router.push({ name: 'messenger' });
};
const openAdminPanel = () => router.push(`/admin/profile/${profile.value.uid}`);

watch(() => route.params.uid, async (uid) => {
	if (uid) {
		await loadProfile(uid);
		if (uid !== currentUser.value.uid) store.dispatch('messenger/subscribeToStatuses', [uid]);
	}
});

onMounted(resolveProfileUid);
onUnmounted(() => {
	const uid = route.params.uid;
	if (uid && uid !== currentUser.value.uid) store.dispatch('messenger/unsubscribeFromStatuses', [uid]);
});
</script>

<style scoped>
.profile-page { width: min(100%, 62rem); margin: 0 auto; padding: var(--ui-space-5) 0 var(--ui-space-10); display: grid; gap: var(--ui-space-4); }
.profile-card { background: var(--ui-surface); border: 1px solid var(--ui-border); border-radius: var(--ui-radius-xl); box-shadow: var(--ui-shadow-sm); padding: clamp(1rem, 3vw, 1.5rem); }
.profile-hero { display: grid; grid-template-columns: auto minmax(0, 1fr) auto; align-items: center; gap: var(--ui-space-5); overflow: hidden; }
.profile-hero--background-soft { background: linear-gradient(145deg, var(--ui-surface) 45%, var(--ui-primary-soft) 190%); }
.profile-hero--background-paper { background: color-mix(in srgb, var(--ui-surface) 92%, var(--ui-warning-soft)); }
.profile-hero--background-mist { background: color-mix(in srgb, var(--ui-surface) 90%, var(--ui-info-soft)); }
.profile-hero--background-night { background: color-mix(in srgb, var(--ui-surface) 80%, var(--ui-text) 20%); }
.profile-hero--accent-berry { border-color: color-mix(in srgb, var(--ui-danger) 30%, var(--ui-border)); }
.profile-hero--accent-forest { border-color: color-mix(in srgb, var(--ui-success) 30%, var(--ui-border)); }
.profile-hero--accent-ocean { border-color: color-mix(in srgb, var(--ui-info) 30%, var(--ui-border)); }
.profile-hero--accent-sand { border-color: color-mix(in srgb, var(--ui-warning) 30%, var(--ui-border)); }
.profile-avatar { position: relative; width: clamp(5rem, 12vw, 7rem); aspect-ratio: 1; border-radius: 32%; display: grid; place-items: center; overflow: visible; background: var(--ui-primary-soft); color: var(--ui-primary); font-size: 2rem; font-weight: 800; border: 1px solid var(--ui-border); }
.profile-avatar img { width: 100%; height: 100%; object-fit: cover; border-radius: inherit; }
.profile-avatar--frame-soft { box-shadow: 0 0 0 .35rem color-mix(in srgb, var(--ui-primary) 16%, transparent); }
.profile-avatar--frame-double { box-shadow: 0 0 0 .2rem var(--ui-surface), 0 0 0 .42rem color-mix(in srgb, var(--ui-primary) 38%, var(--ui-border)); }
.profile-avatar--frame-badge::before { content: '✦'; position: absolute; top: -.45rem; right: -.45rem; z-index: 2; width: 1.65rem; height: 1.65rem; display: grid; place-items: center; border: 2px solid var(--ui-surface); border-radius: 50%; background: var(--ui-primary); color: var(--ui-primary-contrast); font-size: .72rem; }
.presence-dot { position: absolute; right: 0.35rem; bottom: 0.35rem; width: 0.9rem; height: 0.9rem; border-radius: 50%; background: var(--ui-success); border: 3px solid var(--ui-surface); }
.presence-dot--self { background: var(--ui-primary); }
.profile-main { min-width: 0; }
.profile-title-row { display: flex; justify-content: space-between; align-items: flex-start; gap: var(--ui-space-3); }
.profile-handle, .section-eyebrow { margin: 0; color: var(--ui-text-muted); font-size: var(--ui-text-sm); }
h1 { margin: 0.1rem 0 0; font-size: clamp(1.5rem, 4vw, 2rem); line-height: var(--ui-leading-tight); }
h2 { margin: 0.15rem 0 0; font-size: var(--ui-text-lg); }
.profile-bio { margin: var(--ui-space-3) 0; color: var(--ui-text-muted); white-space: pre-wrap; }
.persona-status { display: inline-flex; align-items: center; gap: var(--ui-space-2); margin: 0 0 var(--ui-space-3); padding: .45rem .7rem; border: 1px solid color-mix(in srgb, var(--ui-primary) 22%, var(--ui-border)); border-radius: var(--ui-radius-pill); background: color-mix(in srgb, var(--ui-surface) 82%, transparent); color: var(--ui-text); font-size: var(--ui-text-sm); font-weight: 650; }
.persona-status i { color: var(--ui-primary); }
.profile-meta { display: flex; flex-wrap: wrap; gap: var(--ui-space-2); align-items: center; color: var(--ui-text-muted); font-size: var(--ui-text-sm); }
.intent-chip, .role-chip, .self-chip { display: inline-flex; align-items: center; min-height: 2rem; padding: 0 var(--ui-space-3); border-radius: var(--ui-radius-pill); font-size: var(--ui-text-xs); font-weight: 700; }
.intent-chip { background: var(--ui-primary-soft); color: var(--ui-primary); }
.role-chip { background: var(--ui-info-soft); color: var(--ui-info); }
.self-chip { background: var(--ui-surface-muted); color: var(--ui-text-muted); }
.profile-actions { display: flex; flex-direction: column; gap: var(--ui-space-2); min-width: 10rem; }
.profile-actions a { text-decoration: none; }
.button-pending { display: inline-flex; align-items: center; gap: var(--ui-space-2); }
.ui-button:disabled { cursor: not-allowed; opacity: 0.55; }
.contact-context { display: grid; grid-template-columns: minmax(12rem, 0.8fr) 1.2fr; gap: var(--ui-space-5); align-items: center; }
.contact-context p { margin: 0; color: var(--ui-text-muted); }
.settings-header { display: flex; justify-content: space-between; gap: var(--ui-space-6); margin-bottom: var(--ui-space-5); }
.settings-header > p { max-width: 28rem; margin: 0; color: var(--ui-text-muted); }
.settings-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--ui-space-4); }
.field { display: grid; gap: var(--ui-space-2); font-size: var(--ui-text-sm); font-weight: 650; }
.field--wide { grid-column: 1 / -1; }
.toggle-row { display: flex; gap: var(--ui-space-3); align-items: flex-start; padding: var(--ui-space-3); border-radius: var(--ui-radius-md); background: var(--ui-surface-soft); font-weight: 400; }
.toggle-row input { margin-top: 0.25rem; width: 1.1rem; height: 1.1rem; accent-color: var(--ui-primary); }
.toggle-row strong, .toggle-row small { display: block; }
.toggle-row small { margin-top: var(--ui-space-1); color: var(--ui-text-muted); }
.settings-actions { display: flex; justify-content: flex-end; }
.ui-notice { padding: var(--ui-space-3); border-radius: var(--ui-radius-md); margin-bottom: var(--ui-space-4); }
.ui-notice--success { color: var(--ui-success); background: var(--ui-success-soft); }
.ui-notice--danger { color: var(--ui-danger); background: var(--ui-danger-soft); }
.profile-empty { text-align: center; padding-block: var(--ui-space-10); }
.profile-empty p { color: var(--ui-text-muted); }
.profile-card--loading { min-height: 12rem; display: grid; gap: var(--ui-space-3); align-content: center; }
.profile-skeleton { height: 1rem; border-radius: var(--ui-radius-pill); background: var(--ui-surface-muted); animation: pulse 1.2s ease-in-out infinite alternate; }
.profile-skeleton--avatar { width: 5rem; height: 5rem; border-radius: 32%; }
.profile-skeleton--title { width: 45%; height: 1.75rem; }
@keyframes pulse { to { opacity: 0.45; } }
@media (max-width: 760px) {
	.profile-page { padding: var(--ui-space-3) 0 var(--ui-space-8); }
	.profile-hero { grid-template-columns: auto 1fr; align-items: start; }
	.profile-actions { grid-column: 1 / -1; flex-direction: row; flex-wrap: wrap; min-width: 0; }
	.profile-actions .ui-button { flex: 1; }
	.profile-title-row { display: block; }
	.intent-chip { margin-top: var(--ui-space-2); }
	.contact-context, .settings-grid { grid-template-columns: 1fr; }
	.field--wide { grid-column: auto; }
	.settings-header { display: block; }
	.settings-header > p { margin-top: var(--ui-space-2); }
}
@media (prefers-reduced-motion: reduce) { .profile-skeleton { animation: none; } }
</style>
