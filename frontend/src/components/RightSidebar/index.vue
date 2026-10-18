<template>
	<aside class="space-panel" :class="{ active: isActive || workspaceSection, 'space-panel--workspace': workspaceSection }" aria-label="Информация о пространстве">
		<header class="space-panel__header">
			<div>
				<span>О пространстве</span>
				<strong>{{ roomInfo.name }}</strong>
			</div>
			<button type="button" class="icon-button" aria-label="Закрыть панель" @click="emit('close')">
				<i class="fas fa-xmark" aria-hidden="true"></i>
			</button>
		</header>

		<SpaceContextNavigation :space-uid="String(roomInfo.uid)" :can-manage="canManage" />
		<SpaceWorkspacePanel v-if="workspaceSection" :space-uid="String(roomInfo.uid)" :section="workspaceSection" />
		<template v-else>

		<div class="panel-tabs" :class="{ 'panel-tabs--manager': canManage }" role="tablist" aria-label="Разделы пространства">
			<button type="button" role="tab" :aria-selected="activeTab === 'info'" :class="{ active: activeTab === 'info' }" @click="activeTab = 'info'">
				Обзор
			</button>
			<button type="button" role="tab" :aria-selected="activeTab === 'people'" :class="{ active: activeTab === 'people' }" @click="activeTab = 'people'">
				Люди <span class="count-badge">{{ activeTotal }}</span>
			</button>
			<button v-if="canManage" type="button" role="tab" :aria-selected="activeTab === 'requests'" :class="{ active: activeTab === 'requests' }" @click="activeTab = 'requests'">
				Заявки <span v-if="pendingTotal" class="count-badge count-badge--attention">{{ pendingTotal }}</span>
			</button>
		</div>

		<section v-if="activeTab === 'info'" class="panel-content">
			<div class="space-summary">
				<p>{{ roomInfo.description || 'У этого пространства пока нет описания.' }}</p>
				<div v-if="tags.length" class="tag-list">
					<span v-for="tag in tags" :key="tag" class="ui-chip">{{ tag }}</span>
				</div>
			</div>

			<dl class="space-facts">
				<div v-if="owner?.uid">
					<dt>Создатель</dt>
					<dd><RouterLink :to="`/profile/${owner.uid}`">{{ owner.display_name || owner.handle || 'Участник' }}</RouterLink></dd>
				</div>
				<div>
					<dt>Участники</dt>
					<dd>{{ roomInfo.member_count ?? activeTotal }} / {{ roomInfo.member_limit || '∞' }}</dd>
				</div>
				<div>
					<dt>Вход</dt>
					<dd>{{ joinPolicyLabel }}</dd>
				</div>
				<div v-if="roomInfo.region || roomInfo.country">
					<dt>Регион</dt>
					<dd>{{ [roomInfo.region, roomInfo.country].filter(Boolean).join(', ') }}</dd>
				</div>
				<div v-if="roomInfo.created_at">
					<dt>Здесь с</dt>
					<dd>{{ formatDate(roomInfo.created_at) }}</dd>
				</div>
			</dl>

			<div class="panel-note">
				<i class="fas fa-handshake" aria-hidden="true"></i>
				<div>
					<strong>Локальные роли</strong>
					<span>Создатель и модераторы управляют только этим пространством. Роль здесь не даёт глобального статуса в PubChat.</span>
				</div>
			</div>
			<RouterLink class="room-return" :to="{ name: 'chats' }">← К списку пространств</RouterLink>
			<button v-if="!isOwner" class="room-leave" type="button" :disabled="leaving" @click="leaveSpace">
				{{ leaving ? 'Выходим…' : 'Покинуть пространство' }}
			</button>
			<p v-if="leaveError" class="room-leave-error" role="alert">{{ leaveError }}</p>
		</section>

		<section v-else-if="activeTab === 'people'" class="panel-content panel-content--people">
			<div v-if="loadingActive" class="panel-loading">Загружаем участников…</div>
			<div v-else-if="activeMembers.length" class="people-list">
				<article v-for="member in activeMembers" :key="member.account_uid" class="person-row">
					<RouterLink :to="`/profile/${member.account_uid}`" class="person-link">
						<span class="person-avatar">
							<img v-if="member.persona?.avatar" :src="resolveAvatar(member.persona.avatar)" alt="" />
							<span v-else>{{ avatarFallback(member.persona?.display_name || member.persona?.handle) }}</span>
							<span v-if="isOnline(member.account_uid)" class="online-dot" title="Сейчас в сети"></span>
						</span>
						<span class="person-copy">
							<strong>{{ member.persona?.display_name || member.persona?.handle || 'Участник' }}</strong>
							<small>{{ member.persona?.handle ? `@${member.persona.handle}` : intentLabel(member.persona?.social_intent) }}</small>
						</span>
					</RouterLink>

					<span v-if="member.role === 'owner'" class="role-chip role-chip--owner">Создатель</span>
					<span v-else-if="member.role === 'moderator'" class="role-chip">Модератор</span>

					<div v-if="canManageMember(member)" class="person-actions">
						<button type="button" class="more-button" :aria-expanded="activeUserMenu === member.account_uid" aria-label="Действия с участником" @click.stop="toggleUserMenu(member.account_uid)">
							<i class="fas fa-ellipsis" aria-hidden="true"></i>
						</button>
						<div v-if="activeUserMenu === member.account_uid" class="person-menu">
							<button v-if="isOwner" type="button" :disabled="busyUid === member.account_uid" @click="toggleModerator(member)">
								<i class="fas fa-user-shield" aria-hidden="true"></i>
								{{ member.role === 'moderator' ? 'Снять роль модератора' : 'Сделать модератором' }}
							</button>
							<button type="button" :disabled="busyUid === member.account_uid" @click="removeMember(member)">
								<i class="fas fa-door-open" aria-hidden="true"></i>Удалить из пространства
							</button>
							<button type="button" class="person-menu__danger" @click="restrictUser(member.account_uid)">
								<i class="fas fa-user-slash" aria-hidden="true"></i>Ограничить доступ
							</button>
						</div>
					</div>
				</article>
			</div>
			<div v-else class="people-empty">
				<i class="fas fa-couch" aria-hidden="true"></i>
				<strong>Пока никого</strong>
				<span>Участники пространства появятся здесь независимо от того, находятся ли они сейчас онлайн.</span>
			</div>
			<button v-if="activeMembers.length < activeTotal" type="button" class="load-more" :disabled="loadingMore" @click="loadMoreActive">
				{{ loadingMore ? 'Загружаем…' : 'Показать ещё' }}
			</button>
		</section>

		<section v-else-if="activeTab === 'requests' && canManage" class="panel-content panel-content--people">
			<div v-if="loadingPending" class="panel-loading">Проверяем заявки…</div>
			<div v-else-if="pendingMembers.length" class="people-list">
				<article v-for="member in pendingMembers" :key="member.account_uid" class="person-row person-row--request">
					<RouterLink :to="`/profile/${member.account_uid}`" class="person-link">
						<span class="person-avatar">
							<img v-if="member.persona?.avatar" :src="resolveAvatar(member.persona.avatar)" alt="" />
							<span v-else>{{ avatarFallback(member.persona?.display_name || member.persona?.handle) }}</span>
						</span>
						<span class="person-copy">
							<strong>{{ member.persona?.display_name || member.persona?.handle || 'Участник' }}</strong>
							<small>Хочет присоединиться</small>
						</span>
					</RouterLink>
					<div class="request-actions">
						<button type="button" class="request-action request-action--approve" :disabled="busyUid === member.account_uid" aria-label="Одобрить заявку" @click="manageRequest(member, 'approve')"><i class="fas fa-check"></i></button>
						<button type="button" class="request-action" :disabled="busyUid === member.account_uid" aria-label="Отклонить заявку" @click="manageRequest(member, 'reject')"><i class="fas fa-xmark"></i></button>
					</div>
				</article>
			</div>
			<div v-else class="people-empty">
				<i class="fas fa-inbox" aria-hidden="true"></i>
				<strong>Новых заявок нет</strong>
				<span>Когда кто-то попросится в пространство, запрос появится здесь.</span>
			</div>
		</section>
		</template>
	</aside>
</template>

<script setup>
import { computed, ref, watch } from 'vue';
import { RouterLink, useRoute, useRouter } from 'vue-router';
import { useStore } from 'vuex';

import SpacesService from '@/API/SpacesService';
import SpaceContextNavigation from '@/components/Spaces/SpaceContextNavigation.vue';
import SpaceWorkspacePanel from '@/components/Spaces/SpaceWorkspacePanel.vue';

const props = defineProps({
	isActive: { type: Boolean, default: false },
	roomInfo: { type: Object, default: () => ({}) },
	users: { type: Array, default: () => [] },
});

const emit = defineEmits(['close', 'user-banned', 'membership-changed']);
const store = useStore();
const route = useRoute();
const router = useRouter();
const leaving = ref(false);
const leaveError = ref('');
const leaveSpace = async () => {
	if (isOwner.value || leaving.value || !window.confirm('Покинуть это пространство? Для возвращения потребуется вступить снова.')) return;
	leaving.value = true;
	leaveError.value = '';
	try {
		await SpacesService.leave(props.roomInfo.uid);
		await router.push({ name: 'chats' });
	} catch { leaveError.value = 'Не удалось покинуть пространство. Попробуйте ещё раз.'; }
	finally { leaving.value = false; }
};
const workspaceSection = computed(() => ({
	'space-community': 'community', 'space-life': 'life',
	'space-support': 'support', 'space-moderation': 'moderation',
}[route.name] || ''));
const activeTab = ref('info');
const activeUserMenu = ref(null);
const activeMembers = ref([]);
const pendingMembers = ref([]);
const activeTotal = ref(0);
const pendingTotal = ref(0);
const loadingActive = ref(false);
const loadingPending = ref(false);
const loadingMore = ref(false);
const busyUid = ref(null);
const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/$/, '');

const currentUserUid = computed(() => store.getters.getUser?.uid);
const owner = computed(() => props.roomInfo.owner || (props.roomInfo.owner_uid ? { uid: props.roomInfo.owner_uid } : null));
const isOwner = computed(() => props.roomInfo.owner_uid === currentUserUid.value || props.roomInfo.viewer_membership?.role === 'owner');
const isCurrentUserModerator = computed(() => props.roomInfo.viewer_membership?.status === 'active' && props.roomInfo.viewer_membership?.role === 'moderator');
const canManage = computed(() => Boolean(props.roomInfo.can_manage || isOwner.value || isCurrentUserModerator.value));
const tags = computed(() => Array.isArray(props.roomInfo.tags)
	? props.roomInfo.tags
	: String(props.roomInfo.tags || '').split(',').map((tag) => tag.trim()).filter(Boolean));
const joinPolicyLabel = computed(() => ({
	open: 'Свободный вход',
	request: 'По заявке',
	invite: 'По приглашению',
}[props.roomInfo.join_policy] || 'По правилам пространства'));
const onlineIds = computed(() => new Set(props.users.map((user) => String(user.uid || user.account_uid || '')).filter(Boolean)));

const isOnline = (uid) => onlineIds.value.has(String(uid));
const canManageMember = (member) => {
	if (!canManage.value || member.account_uid === currentUserUid.value || member.role === 'owner') return false;
	if (isCurrentUserModerator.value && member.role === 'moderator') return false;
	return true;
};
const resolveAvatar = (avatar) => /^https?:\/\//.test(avatar) ? avatar : `${apiBaseUrl}${avatar}`;
const avatarFallback = (value = '?') => String(value || '?').slice(0, 1).toUpperCase();
const intentLabel = (intent) => ({
	open: 'Хочет пообщаться',
	meet: 'Открыт новым знакомствам',
	games: 'Ищет компанию для игры',
	friends: 'Общается со знакомыми',
	quiet: 'Спокойный режим',
}[intent] || 'В PubChat');
const formatDate = (dateString) => new Intl.DateTimeFormat('ru', { day: 'numeric', month: 'long', year: 'numeric' }).format(new Date(dateString));

const loadActive = async ({ append = false } = {}) => {
	if (!props.roomInfo.uid) return;
	append ? loadingMore.value = true : loadingActive.value = true;
	try {
		const offset = append ? activeMembers.value.length : 0;
		const response = await SpacesService.members(props.roomInfo.uid, { status: 'active', limit: 100, offset });
		const items = response.data.members || [];
		activeMembers.value = append ? [...activeMembers.value, ...items] : items;
		activeTotal.value = response.data.pagination?.total ?? activeMembers.value.length;
	} catch (error) {
		console.error('Не удалось загрузить участников пространства:', error);
	} finally {
		loadingActive.value = false;
		loadingMore.value = false;
	}
};

const loadPending = async () => {
	pendingMembers.value = [];
	pendingTotal.value = 0;
	if (!props.roomInfo.uid || !canManage.value) return;
	loadingPending.value = true;
	try {
		const response = await SpacesService.members(props.roomInfo.uid, { status: 'pending', limit: 100, offset: 0 });
		pendingMembers.value = response.data.members || [];
		pendingTotal.value = response.data.pagination?.total ?? pendingMembers.value.length;
	} catch (error) {
		console.error('Не удалось загрузить заявки пространства:', error);
	} finally {
		loadingPending.value = false;
	}
};

const refreshMemberships = async () => Promise.all([loadActive(), loadPending()]);
const loadMoreActive = () => loadActive({ append: true });
const toggleUserMenu = (userId) => { activeUserMenu.value = activeUserMenu.value === userId ? null : userId; };

const toggleModerator = async (member) => {
	busyUid.value = member.account_uid;
	try {
		const role = member.role === 'moderator' ? 'member' : 'moderator';
		await SpacesService.updateMemberRole(props.roomInfo.uid, member.account_uid, role);
		await refreshMemberships();
		emit('membership-changed');
	} catch (error) {
		console.error('Не удалось изменить роль участника:', error);
	} finally {
		busyUid.value = null;
		activeUserMenu.value = null;
	}
};

const manageRequest = async (member, action) => {
	busyUid.value = member.account_uid;
	try {
		await SpacesService.manageMembership(props.roomInfo.uid, member.account_uid, action);
		await refreshMemberships();
		emit('membership-changed');
	} catch (error) {
		console.error('Не удалось обработать заявку:', error);
	} finally {
		busyUid.value = null;
	}
};

const removeMember = async (member) => {
	busyUid.value = member.account_uid;
	try {
		await SpacesService.manageMembership(props.roomInfo.uid, member.account_uid, 'remove');
		await refreshMemberships();
		emit('membership-changed');
	} catch (error) {
		console.error('Не удалось удалить участника из пространства:', error);
	} finally {
		busyUid.value = null;
		activeUserMenu.value = null;
	}
};

const restrictUser = (userId) => {
	emit('user-banned', userId);
	activeUserMenu.value = null;
};

watch(
	() => [props.roomInfo.uid, props.roomInfo.member_count, props.roomInfo.can_manage],
	() => {
		activeTab.value = 'info';
		activeUserMenu.value = null;
		refreshMemberships();
	},
	{ immediate: true },
);
</script>

<style scoped>
.space-panel { position: relative; width: 21rem; min-width: 21rem; height: 100%; display: flex; flex-direction: column; border-left: 1px solid var(--ui-border); background: var(--ui-surface); }
.space-panel--workspace { position: absolute; inset: 0 0 0 auto; z-index: 45; width: min(44rem, 100%); min-width: 0; box-shadow: var(--ui-shadow-lg); }
.space-panel__header { min-height: 4.25rem; display: flex; align-items: center; justify-content: space-between; gap: var(--ui-space-3); padding: var(--ui-space-3) var(--ui-space-4); }
.space-panel__header > div { min-width: 0; display: grid; }
.space-panel__header span { color: var(--ui-text-subtle); font-size: var(--ui-text-xs); }
.space-panel__header strong { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.icon-button { width: 2.5rem; height: 2.5rem; display: grid; place-items: center; border: 1px solid var(--ui-border); border-radius: var(--ui-radius-md); background: var(--ui-surface); color: var(--ui-text-muted); cursor: pointer; }
.icon-button:hover { background: var(--ui-surface-muted); color: var(--ui-text); }
.panel-tabs { display: grid; grid-template-columns: 1fr 1fr; gap: var(--ui-space-1); margin: 0 var(--ui-space-3); padding: var(--ui-space-1); border-radius: var(--ui-radius-md); background: var(--ui-surface-muted); }
.panel-tabs--manager { grid-template-columns: repeat(3, 1fr); }
.panel-tabs button { min-width: 0; min-height: 2.35rem; display: flex; align-items: center; justify-content: center; gap: .25rem; padding: 0 .35rem; border: 0; border-radius: calc(var(--ui-radius-md) - .2rem); background: transparent; color: var(--ui-text-muted); font: inherit; font-size: var(--ui-text-xs); font-weight: 700; cursor: pointer; }
.panel-tabs button.active { background: var(--ui-surface); color: var(--ui-text); box-shadow: var(--ui-shadow-sm); }
.count-badge { min-width: 1.25rem; padding: 0 .3rem; border-radius: var(--ui-radius-pill); background: var(--ui-primary-soft); color: var(--ui-primary); font-size: .68rem; }
.count-badge--attention { background: var(--ui-warning-soft); color: var(--ui-warning); }
.panel-content { min-height: 0; flex: 1; overflow-y: auto; padding: var(--ui-space-4); }
.space-summary p { margin: 0; color: var(--ui-text-muted); line-height: 1.55; }
.tag-list { display: flex; flex-wrap: wrap; gap: var(--ui-space-1); margin-top: var(--ui-space-3); }
.space-facts { display: grid; gap: var(--ui-space-3); margin: var(--ui-space-5) 0; }
.space-facts div { display: grid; gap: .15rem; }
.space-facts dt { color: var(--ui-text-subtle); font-size: var(--ui-text-xs); }
.space-facts dd { margin: 0; color: var(--ui-text); font-size: var(--ui-text-sm); }
.space-facts a { color: var(--ui-primary); text-decoration: none; font-weight: 700; }
.panel-note { display: flex; gap: var(--ui-space-3); padding: var(--ui-space-3); border: 1px solid var(--ui-border); border-radius: var(--ui-radius-lg); background: var(--ui-surface-soft); color: var(--ui-text-muted); }
.panel-note > i { margin-top: .15rem; color: var(--ui-primary); }
.panel-note div { display: grid; gap: .2rem; }
.panel-note strong { color: var(--ui-text); font-size: var(--ui-text-sm); }
.panel-note span { font-size: var(--ui-text-xs); line-height: 1.45; }
.room-return, .room-leave { display: block; width: 100%; margin-top: var(--ui-space-3); padding: .7rem; border: 1px solid var(--ui-border); border-radius: var(--ui-radius-md); background: transparent; color: var(--ui-text-muted); text-align: center; text-decoration: none; font: inherit; cursor: pointer; }
.room-leave, .room-leave-error { color: var(--ui-danger); }
.panel-content--people { padding-inline: var(--ui-space-2); }
.panel-loading, .people-empty { min-height: 11rem; display: grid; place-items: center; align-content: center; gap: var(--ui-space-2); padding: var(--ui-space-4); color: var(--ui-text-subtle); text-align: center; }
.people-empty i { font-size: 1.5rem; color: var(--ui-primary); }
.people-empty strong { color: var(--ui-text); }
.people-empty span { font-size: var(--ui-text-xs); line-height: 1.45; }
.people-list { display: grid; gap: var(--ui-space-1); }
.person-row { position: relative; min-height: 3.7rem; display: flex; align-items: center; gap: var(--ui-space-2); padding: var(--ui-space-2); border-radius: var(--ui-radius-lg); }
.person-row:hover { background: var(--ui-surface-muted); }
.person-row--request { border: 1px solid var(--ui-border); }
.person-link { min-width: 0; flex: 1; display: flex; align-items: center; gap: var(--ui-space-2); color: var(--ui-text); text-decoration: none; }
.person-avatar { position: relative; width: 2.4rem; height: 2.4rem; display: grid; place-items: center; flex: 0 0 auto; overflow: visible; border-radius: 50%; background: var(--ui-primary-soft); color: var(--ui-primary); font-weight: 800; }
.person-avatar img { width: 100%; height: 100%; object-fit: cover; border-radius: inherit; }
.online-dot { position: absolute; right: -.05rem; bottom: -.05rem; width: .65rem; height: .65rem; border: 2px solid var(--ui-surface); border-radius: 50%; background: var(--ui-success); }
.person-copy { min-width: 0; display: grid; }
.person-copy strong, .person-copy small { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.person-copy small { color: var(--ui-text-subtle); font-size: .7rem; }
.role-chip { flex: 0 0 auto; padding: .2rem .45rem; border-radius: var(--ui-radius-pill); background: var(--ui-info-soft); color: var(--ui-info); font-size: .65rem; font-weight: 700; }
.role-chip--owner { background: var(--ui-primary-soft); color: var(--ui-primary); }
.person-actions { position: relative; }
.more-button { width: 2rem; height: 2rem; display: grid; place-items: center; border: 0; border-radius: var(--ui-radius-md); background: transparent; color: var(--ui-text-subtle); cursor: pointer; }
.more-button:hover { background: var(--ui-surface); color: var(--ui-text); }
.person-menu { position: absolute; right: 0; top: calc(100% + var(--ui-space-1)); z-index: 20; width: 15rem; display: grid; padding: var(--ui-space-1); border: 1px solid var(--ui-border); border-radius: var(--ui-radius-lg); background: var(--ui-surface-raised); box-shadow: var(--ui-shadow-lg); }
.person-menu button { min-height: 2.55rem; display: flex; align-items: center; gap: var(--ui-space-2); padding: 0 var(--ui-space-3); border: 0; border-radius: var(--ui-radius-md); background: transparent; color: var(--ui-text); text-align: left; cursor: pointer; }
.person-menu button:hover:not(:disabled) { background: var(--ui-surface-muted); }
.person-menu button:disabled { opacity: .5; }
.person-menu__danger { color: var(--ui-danger) !important; }
.request-actions { display: flex; gap: .25rem; }
.request-action { width: 2rem; height: 2rem; display: grid; place-items: center; border: 1px solid var(--ui-border); border-radius: var(--ui-radius-md); background: var(--ui-surface); color: var(--ui-text-muted); cursor: pointer; }
.request-action--approve { background: var(--ui-success-soft); color: var(--ui-success); border-color: transparent; }
.load-more { width: calc(100% - var(--ui-space-2)); min-height: 2.5rem; margin: var(--ui-space-3) var(--ui-space-1) 0; border: 1px solid var(--ui-border); border-radius: var(--ui-radius-md); background: var(--ui-surface); color: var(--ui-text-muted); cursor: pointer; }
@media (max-width: 1100px) { .space-panel { position: absolute; top: 0; right: 0; z-index: 40; width: min(21rem, 92vw); min-width: 0; transform: translateX(105%); box-shadow: var(--ui-shadow-lg); transition: transform var(--ui-motion-normal) var(--ui-ease); } .space-panel.active { transform: translateX(0); } }
@media (max-width: 1100px) { .space-panel--workspace { width: min(44rem, 100%); z-index: 45; } }
</style>
