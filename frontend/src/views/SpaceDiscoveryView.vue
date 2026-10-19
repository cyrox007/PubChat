<template>
	<CreateSpaceModal :open="createOpen" @close="createOpen = false" @created="handleCreated" />

	<main class="discovery-shell">
		<section class="discovery-hero">
			<div class="discovery-hero__copy">
				<span class="eyebrow">Living Spaces</span>
				<h1>Найдите место, куда хочется вернуться</h1>
				<p>Небольшие живые сообщества для разговоров, знакомств, игр и локальных встреч — без бесконечной ленты.</p>
			</div>
			<button class="ui-button discovery-hero__create" type="button" @click="createOpen = true">
				<i class="fas fa-plus" aria-hidden="true"></i>
				Создать пространство
			</button>
		</section>

		<section class="discovery-toolbar" aria-label="Поиск пространств">
			<form class="search-box" @submit.prevent="loadSpaces">
				<i class="fas fa-magnifying-glass" aria-hidden="true"></i>
				<input v-model.trim="searchQuery" type="search" maxlength="80" placeholder="Тема, название или атмосфера" />
				<button v-if="searchQuery" type="button" aria-label="Очистить поиск" @click="clearSearch">
					<i class="fas fa-xmark" aria-hidden="true"></i>
				</button>
			</form>

			<div class="purpose-filter" role="group" aria-label="Режим и формат пространства">
				<button
					type="button"
					class="filter-chip filter-chip--live"
					:class="{ active: liveMode }"
					:aria-pressed="liveMode"
					@click="toggleLiveMode"
				>
					<span class="filter-live-dot" aria-hidden="true"></span>
					Живые сейчас
				</button>
				<span class="filter-separator" aria-hidden="true"></span>
				<button
					v-for="item in purposeOptions.slice(0, 3)"
					:key="item.value || 'all'"
					type="button"
					class="filter-chip"
					:class="{ active: !liveMode && purpose === item.value }"
					@click="setPurpose(item.value)"
				>
					{{ item.label }}
				</button>
				<button type="button" class="filter-chip filter-chip--more" :aria-expanded="filtersOpen" aria-controls="discovery-filters-panel" @click="openFilters">
					<i class="fas fa-sliders" aria-hidden="true"></i> Фильтры<span v-if="purpose || tagFilter" class="filter-active-indicator" aria-hidden="true"></span>
				</button>
				<button v-if="hasActiveFilters" type="button" class="filter-chip filter-chip--reset" @click="resetFilters">
					<i class="fas fa-rotate-left" aria-hidden="true"></i> Сбросить
				</button>
			</div>
		</section>

		<div v-if="filtersOpen" class="filters-backdrop" @click.self="filtersOpen = false">
			<section id="discovery-filters-panel" class="filters-dialog" role="dialog" aria-modal="true" aria-labelledby="discovery-filters-title" @keydown.esc="filtersOpen = false">
				<header class="filters-dialog__heading">
					<h2 id="discovery-filters-title">Фильтры пространств</h2>
					<button type="button" class="filters-close" aria-label="Закрыть фильтры" @click="filtersOpen = false"><i class="fas fa-xmark" aria-hidden="true"></i></button>
				</header>
				<fieldset class="filters-dialog__group">
					<legend>Формат общения</legend>
					<div class="filters-dialog__chips">
						<button v-for="item in purposeOptions" :key="item.value || 'all'" type="button" class="filter-chip"
							:class="{ active: filterDraftPurpose === item.value }" :aria-pressed="filterDraftPurpose === item.value"
							@click="filterDraftPurpose = item.value">{{ item.label }}</button>
					</div>
				</fieldset>
				<fieldset class="filters-dialog__group">
					<legend>Темы и категории</legend>
					<p class="filters-dialog__note">Фильтрация по тегам, которые указаны у реальных пространств.</p>
					<div v-if="availableTopicTags.length" class="filters-dialog__chips">
						<button v-for="tag in availableTopicTags" :key="tag" type="button" class="filter-chip"
							:class="{ active: filterDraftTag === tag }" :aria-pressed="filterDraftTag === tag" @click="filterDraftTag = filterDraftTag === tag ? '' : tag">
							#{{ tag }}
						</button>
					</div>
					<label class="filters-dialog__tag">Найти по тегу
						<input v-model.trim="filterDraftTag" type="text" maxlength="40" placeholder="Например: дизайн" />
					</label>
				</fieldset>
				<footer class="filters-dialog__actions">
					<button type="button" class="ui-button ui-button--ghost" @click="clearFilterDraft">Сбросить</button>
					<button type="button" class="ui-button" @click="applyFilters">Показать пространства</button>
				</footer>
			</section>
		</div>

		<Transition name="ui-state" mode="out-in">
		<section v-if="loading" key="loading" class="discovery-state" role="status">
			<div class="state-orbit"><i class="fas fa-circle-notch fa-spin" aria-hidden="true"></i></div>
			<strong>{{ liveMode ? 'Смотрим, где жизнь идёт прямо сейчас…' : 'Ищем живые пространства…' }}</strong>
		</section>

		<section v-else-if="errorMessage" key="error" class="discovery-state discovery-state--error">
			<div class="state-orbit"><i class="fas fa-triangle-exclamation" aria-hidden="true"></i></div>
			<strong>Не удалось загрузить пространства</strong>
			<span>{{ errorMessage }}</span>
			<button class="ui-button" type="button" @click="loadSpaces">Повторить</button>
		</section>

		<section v-else-if="spaces.length" key="results" class="space-grid" aria-label="Пространства PubChat">
			<article v-for="space in spaces" :key="space.uid" class="space-card" :class="spaceAppearanceClasses(space)">
				<div class="space-card__topline">
					<span class="purpose-badge"><i :class="purposeIcon(space.purpose)" aria-hidden="true"></i>{{ purposeLabel(space.purpose) }}</span>
					<span v-if="space.visibility !== 'public'" class="visibility-badge">
						<i :class="space.visibility === 'private' ? 'fas fa-lock' : 'fas fa-link'" aria-hidden="true"></i>
						{{ space.visibility === 'private' ? 'Закрытое' : 'По ссылке' }}
					</span>
				</div>

				<div class="space-card__body">
					<div class="space-card__title">
						<span v-if="space.appearance?.ambient_icon" class="ambient-icon" aria-hidden="true">{{ space.appearance.ambient_icon }}</span>
						<h2>{{ space.name }}</h2>
					</div>
					<p v-if="space.appearance?.welcome_line" class="welcome-line">{{ space.appearance.welcome_line }}</p>
					<p>{{ space.description || 'Создатель пока не добавил описание — атмосфера формируется людьми.' }}</p>
					<div v-if="space.tags?.length" class="tag-row">
						<button v-for="tag in space.tags.slice(0, 4)" :key="tag" type="button" class="ui-chip" @click="filterByTag(tag)">#{{ tag }}</button>
					</div>

					<div v-if="space.discovery?.reasons?.length" class="reason-block" aria-label="Почему пространство показано">
						<span class="reason-label">Почему здесь</span>
						<div class="reason-row">
							<span v-for="reason in space.discovery.reasons" :key="reason.code" class="reason-chip">{{ reason.label }}</span>
						</div>
					</div>

					<div v-if="space.discovery?.upcoming" class="upcoming-note">
						<i class="far fa-calendar" aria-hidden="true"></i>
						<div>
							<small>{{ space.discovery.upcoming.kind === 'event' ? 'Скоро событие' : 'Скоро активность' }}</small>
							<strong>{{ space.discovery.upcoming.title }}</strong>
							<time :datetime="space.discovery.upcoming.starts_at">{{ formatUpcoming(space.discovery.upcoming.starts_at) }}</time>
						</div>
					</div>
				</div>

				<div class="space-card__meta">
					<span><i class="fas fa-user-group" aria-hidden="true"></i>{{ space.member_count }} участников</span>
					<span v-if="space.region || space.country"><i class="fas fa-location-dot" aria-hidden="true"></i>{{ locationLabel(space) }}</span>
					<span><i class="fas fa-door-open" aria-hidden="true"></i>{{ joinPolicyLabel(space.join_policy) }}</span>
				</div>

				<footer class="space-card__footer">
					<div class="owner-mini">
						<span class="owner-mini__avatar">
							<img v-if="space.owner?.avatar" :src="resolveAvatar(space.owner.avatar)" alt="" />
							<span v-else>{{ avatarFallback(space.owner?.display_name || space.owner?.handle) }}</span>
						</span>
						<span>
							<small>Создатель</small>
							<strong>{{ space.owner?.display_name || space.owner?.handle || 'Участник PubChat' }}</strong>
						</span>
					</div>

					<button
						class="ui-button space-card__action"
						:class="{ 'ui-button--ghost': space.viewer_membership?.status === 'pending' || space.join_policy === 'invite' }"
						type="button"
						:disabled="joiningUid === space.uid || space.viewer_membership?.status === 'pending' || (space.join_policy === 'invite' && !isActiveMember(space))"
						@click="enterSpace(space)"
					>
						<span v-if="joiningUid === space.uid" class="button-pending"><span class="ui-spinner" aria-hidden="true"></span>{{ actionLabel(space) }}</span>
						<span v-else>{{ actionLabel(space) }}</span>
					</button>
				</footer>
			</article>
		</section>

		<section v-else key="empty" class="discovery-state">
			<div class="state-orbit"><i :class="liveMode ? 'fas fa-wave-square' : 'fas fa-compass'" aria-hidden="true"></i></div>
			<strong>{{ liveMode ? 'Сейчас тихо' : 'Подходящих пространств пока нет' }}</strong>
			<span v-if="liveMode && livePresenceAvailable">Новые разговоры и присутствующие участники появятся здесь автоматически.</span>
			<span v-else-if="liveMode">Присутствие людей временно недоступно; активные разговоры всё равно появятся здесь.</span>
			<span v-else-if="hasActiveFilters">По текущим фильтрам ничего нет. Сбросьте их, чтобы снова увидеть все доступные пространства.</span>
			<span v-else>Здесь пока нет доступных пространств. Можно создать своё место с понятной темой и атмосферой.</span>
			<button v-if="hasActiveFilters" class="ui-button" type="button" @click="resetFilters">Сбросить фильтры</button>
			<button v-else class="ui-button" type="button" @click="createOpen = true">Создать первым</button>
		</section>
		</Transition>
	</main>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';

import DiscoveryService from '@/API/DiscoveryService';
import EngagementService from '@/API/EngagementService';
import SpacesService from '@/API/SpacesService';
import CreateSpaceModal from '@/components/Spaces/CreateSpaceModal.vue';
import { useSpaceDiscoveryLivePolling } from '@/composables/useSpaceDiscoveryLivePolling';
import { publicAssetUrl } from '@/utils/publicAssetUrl';

const router = useRouter();

const spaces = ref([]);
const loading = ref(true);
const errorMessage = ref('');
const searchQuery = ref('');
const purpose = ref(null);
const tagFilter = ref(null);
const liveMode = ref(false);
const livePresenceAvailable = ref(true);
const createOpen = ref(false);
const joiningUid = ref(null);
const filtersOpen = ref(false);
const filterDraftPurpose = ref(null);
const filterDraftTag = ref('');
const availableTopicTags = computed(() => [...new Set(
	spaces.value.flatMap((space) => Array.isArray(space.tags) ? space.tags : [])
		.map((tag) => String(tag || '').trim()).filter(Boolean)
)].sort((a, b) => a.localeCompare(b, 'ru')).slice(0, 16));
const hasActiveFilters = computed(() => Boolean(liveMode.value || purpose.value || tagFilter.value || searchQuery.value));

const purposeOptions = [
	{ value: null, label: 'Все' },
	{ value: 'conversation', label: 'Разговоры' },
	{ value: 'meet_people', label: 'Знакомства' },
	{ value: 'games', label: 'Игры' },
	{ value: 'local', label: 'Рядом' },
	{ value: 'community', label: 'Сообщества' },
];

const openFilters = () => {
	filterDraftPurpose.value = purpose.value;
	filterDraftTag.value = tagFilter.value || '';
	filtersOpen.value = true;
};
const clearFilterDraft = () => {
	filterDraftPurpose.value = null;
	filterDraftTag.value = '';
};
const applyFilters = async () => {
	liveMode.value = false;
	purpose.value = filterDraftPurpose.value;
	tagFilter.value = filterDraftTag.value.trim() || null;
	filtersOpen.value = false;
	await loadSpaces();
};

const defaultAppearance = (spaceUid) => ({
	space_uid: spaceUid,
	theme_preset: 'lounge',
	cover_preset: 'soft-gradient',
	ambient_icon: null,
	welcome_line: null,
});

const discoveryParams = () => ({
	q: searchQuery.value || undefined,
	purpose: purpose.value || undefined,
	tag: tagFilter.value || undefined,
	live_now: liveMode.value || undefined,
	limit: 50,
});

const hydrateAppearances = async (items, previousItems = []) => {
	if (!items.length) return items;
	const appearances = new Map(previousItems.filter((item) => item.appearance).map((item) => [String(item.uid), item.appearance]));
	const missing = items.filter((item) => !appearances.has(String(item.uid)));
	if (missing.length) {
		try {
			const response = await EngagementService.spaceAppearances(missing.map((item) => item.uid));
			for (const appearance of response.data.appearances || []) appearances.set(String(appearance.space_uid), appearance);
		} catch (error) {
			console.error('Не удалось загрузить оформление пространств:', error);
		}
	}
	return items.map((space) => ({ ...space, appearance: appearances.get(String(space.uid)) || defaultAppearance(space.uid) }));
};

const applyDiscoveryResponse = async (response) => {
	livePresenceAvailable.value = response.data.live_presence_available !== false;
	spaces.value = await hydrateAppearances(response.data.spaces || [], spaces.value);
};

const loadSpaces = async () => {
	loading.value = true;
	errorMessage.value = '';
	try {
		await applyDiscoveryResponse(await DiscoveryService.spaces(discoveryParams()));
	} catch (error) {
		console.error('Не удалось загрузить Living Spaces:', error);
		errorMessage.value = 'Проверьте соединение и попробуйте ещё раз.';
	} finally {
		loading.value = false;
	}
};

async function refreshLiveListing() {
	if (!liveMode.value) return;
	try {
		await applyDiscoveryResponse(await DiscoveryService.spaces(discoveryParams()));
	} catch (error) {
		console.warn('Не удалось обновить режим «Живые сейчас»:', error);
	}
}

useSpaceDiscoveryLivePolling(spaces, { liveMode, refreshLiveListing });

const toggleLiveMode = async () => {
	const next = !liveMode.value;
	liveMode.value = next;
	if (next) {
		purpose.value = null;
		tagFilter.value = null;
	}
	await loadSpaces();
};

const setPurpose = async (value) => {
	liveMode.value = false;
	purpose.value = value;
	tagFilter.value = null;
	await loadSpaces();
};

const clearSearch = async () => {
	searchQuery.value = '';
	tagFilter.value = null;
	await loadSpaces();
};

const filterByTag = async (tag) => {
	liveMode.value = false;
	purpose.value = null;
	tagFilter.value = tag;
	searchQuery.value = '';
	await loadSpaces();
};

const resetFilters = async () => {
	liveMode.value = false;
	purpose.value = null;
	tagFilter.value = null;
	searchQuery.value = '';
	await loadSpaces();
};

const isActiveMember = (space) => space.viewer_membership?.status === 'active' || space.viewer_membership?.role === 'owner';
const actionLabel = (space) => {
	if (joiningUid.value === space.uid) return 'Подключаем…';
	if (isActiveMember(space)) return 'Открыть';
	if (space.viewer_membership?.status === 'pending') return 'Заявка отправлена';
	if (space.join_policy === 'request') return 'Подать заявку';
	if (space.join_policy === 'invite') return 'По приглашению';
	return 'Войти';
};

const enterSpace = async (space) => {
	if (isActiveMember(space)) {
		await router.push({ name: 'space', params: { uid: space.uid } });
		return;
	}
	if (space.join_policy === 'invite') return;
	joiningUid.value = space.uid;
	try {
		const response = await SpacesService.join(space.uid);
		const updated = response.data.space;
		const index = spaces.value.findIndex((item) => item.uid === updated.uid);
		if (index >= 0) spaces.value[index] = { ...spaces.value[index], ...updated };
		if (updated.viewer_membership?.status === 'active') await router.push({ name: 'space', params: { uid: updated.uid } });
	} catch (error) {
		console.error('Не удалось присоединиться к пространству:', error);
		errorMessage.value = error.response?.data?.detail?.error_type === 'space_full' ? 'В этом пространстве сейчас нет свободных мест.' : 'Не удалось присоединиться к пространству.';
	} finally {
		joiningUid.value = null;
	}
};

const handleCreated = async (space) => { createOpen.value = false; await router.push({ name: 'space', params: { uid: space.uid } }); };
const purposeLabel = (value) => ({ community: 'Сообщество', conversation: 'Разговоры', meet_people: 'Знакомства', games: 'Игры', local: 'Локальное' }[value] || 'Сообщество');
const purposeIcon = (value) => ({ community: 'fas fa-people-group', conversation: 'fas fa-comments', meet_people: 'fas fa-handshake', games: 'fas fa-gamepad', local: 'fas fa-location-dot' }[value] || 'fas fa-people-group');
const joinPolicyLabel = (value) => ({ open: 'Открытый вход', request: 'Вход по заявке', invite: 'Только по приглашению' }[value] || 'Открытый вход');
const spaceAppearanceClasses = (space) => {
	const theme = ['lounge', 'warm', 'garden', 'studio', 'night'].includes(space.appearance?.theme_preset) ? space.appearance.theme_preset : 'lounge';
	const cover = ['soft-gradient', 'paper', 'mist', 'linen', 'night'].includes(space.appearance?.cover_preset) ? space.appearance.cover_preset : 'soft-gradient';
	return [`space-card--theme-${theme}`, `space-card--cover-${cover}`];
};
const locationLabel = (space) => [space.region, space.country].filter(Boolean).join(', ');
const resolveAvatar = publicAssetUrl;
const avatarFallback = (value = '?') => String(value || '?').slice(0, 1).toUpperCase();
const formatUpcoming = (value) => new Intl.DateTimeFormat('ru', { weekday: 'short', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }).format(new Date(value));

onMounted(loadSpaces);
</script>

<style scoped>
.discovery-shell { display: grid; gap: var(--ui-space-5); padding-bottom: var(--ui-space-8); }
.discovery-hero { display: flex; align-items: flex-end; justify-content: space-between; gap: var(--ui-space-6); padding: clamp(1.4rem, 4vw, 2.6rem); border: 1px solid var(--ui-border); border-radius: var(--ui-radius-xl); background: linear-gradient(135deg, var(--ui-surface) 0%, var(--ui-primary-soft) 160%); box-shadow: var(--ui-shadow-sm); }
.discovery-hero__copy { max-width: 44rem; }
.eyebrow { display: block; margin-bottom: .45rem; color: var(--ui-primary); font-size: var(--ui-text-xs); font-weight: 800; letter-spacing: .08em; text-transform: uppercase; }
.discovery-hero h1 { margin: 0; max-width: 42rem; font-size: clamp(1.75rem, 4vw, 3rem); line-height: 1.03; letter-spacing: -.035em; }
.discovery-hero p { max-width: 39rem; margin: var(--ui-space-3) 0 0; color: var(--ui-text-muted); line-height: 1.6; }
.discovery-hero__create { flex: 0 0 auto; }
.discovery-toolbar { display: grid; gap: var(--ui-space-3); }
.search-box { min-height: 3.2rem; display: flex; align-items: center; gap: var(--ui-space-3); padding: 0 var(--ui-space-4); border: 1px solid var(--ui-border); border-radius: var(--ui-radius-pill); background: var(--ui-surface); box-shadow: var(--ui-shadow-sm); color: var(--ui-text-subtle); }
.search-box input { min-width: 0; flex: 1; border: 0; outline: 0; background: transparent; color: var(--ui-text); font: inherit; }
.search-box button { border: 0; background: transparent; color: var(--ui-text-subtle); cursor: pointer; }
.purpose-filter { display: flex; flex-wrap: wrap; align-items: center; gap: var(--ui-space-2); min-width: 0; overflow-x: visible; padding-bottom: .15rem; }
.filter-chip--more { color: var(--ui-primary); border-color: var(--ui-primary); }
.filter-active-indicator { width: .45rem; height: .45rem; background: var(--ui-primary); border-radius: 50%; }
.filters-backdrop { position: fixed; inset: 0; display: grid; place-items: center; z-index: 1800; padding: 1rem; background: rgba(15, 20, 44, .54); }
.filters-dialog { width: min(100%, 31rem); max-height: min(85dvh, 760px); overflow-y: auto; display: grid; gap: 1.2rem; padding: 1.25rem; border-radius: 24px; background: var(--ui-surface-raised); color: var(--ui-text); box-shadow: var(--ui-shadow-lg); }
.filters-dialog__heading { display: flex; align-items: center; justify-content: space-between; gap: 1rem; }
.filters-dialog__heading h2 { margin: 0; font-size: var(--ui-text-xl); }
.filters-close { display: grid; place-items: center; flex: 0 0 44px; height: 44px; border: 0; border-radius: 12px; background: var(--ui-surface-muted); color: var(--ui-text); cursor: pointer; }
.filters-dialog__group { min-width: 0; margin: 0; padding: 0; border: 0; }
.filters-dialog__group legend { margin-bottom: .65rem; font-weight: 750; }
.filters-dialog__chips { display: flex; flex-wrap: wrap; gap: .5rem; }
.filters-dialog__note { margin: 0 0 .7rem; color: var(--ui-text-muted); font-size: .85rem; }
.filters-dialog__tag { display: grid; gap: .45rem; margin-top: 1rem; font-size: .875rem; font-weight: 650; }
.filters-dialog__tag input { min-width: 0; width: 100%; min-height: 44px; padding: .6rem .8rem; border: 1px solid var(--ui-border); border-radius: 12px; background: var(--ui-surface); color: var(--ui-text); }
.filters-dialog__actions { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: .65rem; }
.filters-dialog__actions .ui-button { min-height: 44px; white-space: normal; text-align: center; }
@media (max-width: 560px) {
  .filters-backdrop { align-items: end; padding: 0; }
  .filters-dialog { width: 100%; max-height: 88dvh; border-radius: 24px 24px 0 0; padding-bottom: calc(1rem + env(safe-area-inset-bottom)); }
  .purpose-filter { gap: .35rem; }
}
.filter-chip { flex: 0 0 auto; max-width: 100%; min-height: 44px; display: inline-flex; align-items: center; justify-content: center; gap: .4rem; padding: .45rem .75rem; border: 1px solid var(--ui-border); border-radius: var(--ui-radius-pill); background: var(--ui-surface); color: var(--ui-text-muted); font: inherit; font-size: .82rem; line-height: 1.2; font-weight: 700; white-space: normal; text-align: center; overflow-wrap: anywhere; cursor: pointer; }
.filter-chip.active { border-color: color-mix(in srgb, var(--ui-primary) 35%, var(--ui-border)); background: var(--ui-primary-soft); color: var(--ui-primary); }
.filter-chip--live.active { border-color: color-mix(in srgb, var(--ui-success) 42%, var(--ui-border)); background: var(--ui-success-soft); color: var(--ui-success); }
.filter-chip--reset { margin-left: auto; color: var(--ui-text-subtle); }
.filter-live-dot { width: .52rem; height: .52rem; border-radius: 50%; background: currentColor; box-shadow: 0 0 0 .2rem color-mix(in srgb, currentColor 13%, transparent); }
.filter-separator { width: 1px; height: 1.5rem; flex: 0 0 auto; background: var(--ui-border); }
.space-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--ui-space-4); }
.button-pending { display: inline-flex; align-items: center; gap: var(--ui-space-2); }
.space-card { min-width: 0; display: flex; flex-direction: column; gap: var(--ui-space-4); padding: var(--ui-space-5); border: 1px solid var(--ui-border); border-radius: var(--ui-radius-xl); background: var(--ui-surface); box-shadow: var(--ui-shadow-sm); transition: transform var(--ui-motion-normal) var(--ui-ease), box-shadow var(--ui-motion-normal) var(--ui-ease); }
.space-card:hover { transform: translateY(-2px); box-shadow: var(--ui-shadow-md); }
.space-card--cover-soft-gradient { background: linear-gradient(145deg, var(--ui-surface) 40%, var(--ui-primary-soft) 190%); }
.space-card--cover-paper { background: color-mix(in srgb, var(--ui-surface) 92%, var(--ui-warning-soft)); }
.space-card--cover-mist { background: color-mix(in srgb, var(--ui-surface) 91%, var(--ui-info-soft)); }
.space-card--cover-linen { background: color-mix(in srgb, var(--ui-surface) 92%, var(--ui-surface-muted)); }
.space-card--cover-night { background: color-mix(in srgb, var(--ui-surface) 82%, var(--ui-text) 18%); }
.space-card--theme-warm { border-color: color-mix(in srgb, var(--ui-warning) 28%, var(--ui-border)); }
.space-card--theme-garden { border-color: color-mix(in srgb, var(--ui-success) 28%, var(--ui-border)); }
.space-card--theme-studio { border-color: color-mix(in srgb, var(--ui-info) 28%, var(--ui-border)); }
.space-card--theme-night { border-color: color-mix(in srgb, var(--ui-text-muted) 36%, var(--ui-border)); }
.space-card__topline { display: flex; justify-content: space-between; gap: var(--ui-space-2); }
.purpose-badge, .visibility-badge { display: inline-flex; align-items: center; gap: var(--ui-space-1); font-size: var(--ui-text-xs); font-weight: 800; }
.purpose-badge { color: var(--ui-primary); }.visibility-badge { color: var(--ui-text-subtle); }.space-card__body { min-height: 7rem; }.space-card__title { display: flex; align-items: center; gap: var(--ui-space-2); }
.ambient-icon { width: 2rem; height: 2rem; flex: 0 0 auto; display: grid; place-items: center; border: 1px solid var(--ui-border); border-radius: var(--ui-radius-md); background: color-mix(in srgb, var(--ui-surface) 82%, transparent); font-size: 1rem; }
.space-card h2 { margin: 0; font-size: var(--ui-text-xl); letter-spacing: -.02em; }.space-card__body > p { display: -webkit-box; overflow: hidden; -webkit-box-orient: vertical; -webkit-line-clamp: 3; margin: var(--ui-space-2) 0 0; color: var(--ui-text-muted); line-height: 1.55; }.space-card__body .welcome-line { color: var(--ui-text); font-size: var(--ui-text-sm); font-weight: 700; -webkit-line-clamp: 2; }
.tag-row { display: flex; flex-wrap: wrap; gap: var(--ui-space-1); margin-top: var(--ui-space-3); }.tag-row .ui-chip { border: 0; cursor: pointer; }.reason-block { display: grid; gap: .4rem; margin-top: var(--ui-space-3); }.reason-label { color: var(--ui-text-subtle); font-size: .68rem; font-weight: 800; letter-spacing: .05em; text-transform: uppercase; }.reason-row { display: flex; flex-wrap: wrap; gap: .35rem; }.reason-chip { padding: .35rem .55rem; border: 1px solid color-mix(in srgb, var(--ui-primary) 20%, var(--ui-border)); border-radius: var(--ui-radius-pill); background: color-mix(in srgb, var(--ui-primary-soft) 45%, transparent); color: var(--ui-text-muted); font-size: .7rem; font-weight: 650; }
.upcoming-note { display: grid; grid-template-columns: auto minmax(0,1fr); gap: var(--ui-space-2); align-items: start; margin-top: var(--ui-space-3); padding: var(--ui-space-3); border-radius: var(--ui-radius-lg); background: color-mix(in srgb, var(--ui-info-soft) 55%, var(--ui-surface)); }.upcoming-note > i { margin-top: .2rem; color: var(--ui-info); }.upcoming-note > div { min-width: 0; display: grid; gap: .1rem; }.upcoming-note small, .upcoming-note time { color: var(--ui-text-subtle); font-size: .7rem; }.upcoming-note strong { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: var(--ui-text-sm); }
.space-card__meta { display: flex; flex-wrap: wrap; gap: var(--ui-space-3); color: var(--ui-text-subtle); font-size: var(--ui-text-xs); }.space-card__meta span { display: inline-flex; align-items: center; gap: var(--ui-space-1); }.space-card__footer { margin-top: auto; display: flex; align-items: center; justify-content: space-between; gap: var(--ui-space-4); padding-top: var(--ui-space-3); border-top: 1px solid var(--ui-border); }.owner-mini { min-width: 0; display: flex; align-items: center; gap: var(--ui-space-2); }.owner-mini__avatar { width: 2.2rem; height: 2.2rem; display: grid; place-items: center; flex: 0 0 auto; overflow: hidden; border-radius: 50%; background: var(--ui-primary-soft); color: var(--ui-primary); font-weight: 800; }.owner-mini__avatar img { width: 100%; height: 100%; object-fit: cover; }.owner-mini > span:last-child { min-width: 0; display: grid; }.owner-mini small { color: var(--ui-text-subtle); font-size: .66rem; }.owner-mini strong { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: var(--ui-text-sm); }.space-card__action { flex: 0 0 auto; }.ui-button--ghost { border: 1px solid var(--ui-border); background: transparent; color: var(--ui-text-muted); }
.discovery-state { min-height: 22rem; display: grid; place-items: center; align-content: center; gap: var(--ui-space-2); padding: var(--ui-space-7); text-align: center; color: var(--ui-text-muted); }.discovery-state strong { color: var(--ui-text); font-size: var(--ui-text-lg); }.discovery-state span { max-width: 31rem; }.state-orbit { width: 4rem; height: 4rem; display: grid; place-items: center; margin-bottom: var(--ui-space-2); border-radius: 1.4rem; background: var(--ui-primary-soft); color: var(--ui-primary); font-size: var(--ui-text-xl); transform: rotate(4deg); }.discovery-state--error .state-orbit { background: var(--ui-danger-soft); color: var(--ui-danger); }
@media (max-width: 860px) { .space-grid { grid-template-columns: 1fr; }.discovery-hero { align-items: flex-start; flex-direction: column; } }
@media (max-width: 560px) { .discovery-shell { margin-inline: calc(var(--ui-space-3) * -1); }.discovery-hero { border-inline: 0; border-radius: 0; }.discovery-toolbar { padding-inline: var(--ui-space-3); }.space-grid { gap: var(--ui-space-2); }.space-card { border-inline: 0; border-radius: 0; padding: var(--ui-space-4); }.space-card__footer { align-items: stretch; flex-direction: column; }.space-card__action { width: 100%; } }
@media (prefers-reduced-motion: reduce) { .space-card { transition: none; }.space-card:hover { transform: none; } }
</style>