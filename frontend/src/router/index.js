import { createRouter, createWebHistory } from 'vue-router';
import { useStore } from 'vuex';

const router = createRouter({
	history: createWebHistory(import.meta.env.BASE_URL),
	routes: [
		{ path: '/login', name: 'login', component: () => import('../views/LoginView.vue'), meta: { title: 'Вход — PubChat', requestGuest: true } },
		{ path: '/registration', name: 'registration', component: () => import('../views/RegistrationView.vue'), meta: { title: 'Создать образ — PubChat', requestGuest: true } },
		{ path: '/', name: 'chats', component: () => import('../views/SpaceDiscoveryView.vue'), meta: { title: 'Пространства — PubChat', requestAuth: true } },
		{ path: '/people', name: 'people', component: () => import('../views/PeopleDiscoveryView.vue'), meta: { title: 'Люди — PubChat', requestAuth: true } },
		{ path: '/invitations', name: 'invitations', component: () => import('../views/InvitationsView.vue'), meta: { title: 'Приглашения — PubChat', requestAuth: true } },
		{ path: '/notifications', name: 'notifications', component: () => import('../views/NotificationsView.vue'), meta: { title: 'Напоминания — PubChat', requestAuth: true } },
		{ path: '/safety', name: 'safety', component: () => import('../views/SafetyCenterView.vue'), meta: { title: 'Безопасность — PubChat', requestAuth: true } },
		{ path: '/safety/restricted', name: 'restricted-safety', component: () => import('../views/RestrictedSafetyCenterView.vue'), meta: { title: 'Ограничение доступа — PubChat', requestAuth: true } },
		{ path: '/trust-safety', name: 'trust-safety-queue', component: () => import('../views/TrustSafetyQueueView.vue'), meta: { title: 'Trust & Safety — PubChat', requestAuth: true, requiresPlatformModerator: true } },
		{ path: '/persona-style', name: 'persona-style', component: () => import('../views/PersonaStyleView.vue'), meta: { title: 'Стиль образа — PubChat', requestAuth: true } },
		{ path: '/achievements', name: 'achievements', component: () => import('../views/AchievementsView.vue'), meta: { title: 'Достижения — PubChat', requestAuth: true } },
		{ path: '/spaces/:uid', name: 'space', component: () => import('../views/MainView.vue'), meta: { title: 'Разговор — PubChat', requestAuth: true } },
		{ path: '/spaces/:uid/community', name: 'space-community', component: () => import('../views/SpaceCommunityView.vue'), meta: { title: 'Центр пространства — PubChat', requestAuth: true } },
		{ path: '/spaces/:uid/life', name: 'space-life', component: () => import('../views/SpaceLifeView.vue'), meta: { title: 'Жизнь пространства — PubChat', requestAuth: true } },
		{ path: '/spaces/:uid/support', name: 'space-support', component: () => import('../views/SpaceSupportView.vue'), meta: { title: 'Поддержка пространства — PubChat', requestAuth: true } },
		{ path: '/spaces/:uid/moderation', name: 'space-moderation', component: () => import('../views/SpaceModerationView.vue'), meta: { title: 'Модерация пространства — PubChat', requestAuth: true } },
		{ path: '/profile', name: 'Profile', component: () => import('../views/ProfileView.vue'), meta: { title: 'Мой образ — PubChat', requestAuth: true } },
		{ path: '/profile/:uid', name: 'UserProfile', component: () => import('../views/ProfileView.vue'), meta: { title: 'Образ — PubChat', requestAuth: true } },
		{ path: '/messenger', name: 'messenger', component: () => import('../views/MessengerView.vue'), meta: { title: 'Личные разговоры — PubChat', requestAuth: true } },
		{
			path: '/admin',
			name: 'AdminDashboard',
			component: () => import('../views/AdminLayout.vue'),
			meta: { requestAuth: true, requiresAdmin: true },
			children: [
				{ path: '', name: 'AdminDashboardHome', component: () => import('../views/AdminPanel/DashboardView.vue'), meta: { title: 'Управление — PubChat' } },
				{ path: 'profiles', name: 'AdminProfileList', component: () => import('../views/AdminPanel/AdminProfileList.vue'), meta: { title: 'Участники — PubChat', requestAuth: true, requiresAdmin: true } },
				{ path: 'profile/:uid', name: 'AdminProfileView', component: () => import('../views/AdminPanel/AdminProfileView.vue'), meta: { title: 'Управление профилем — PubChat', requestAuth: true, requiresAdmin: true } },
				{ path: 'operations', name: 'AdminOperations', component: () => import('../views/AdminPanel/AdminOperationsView.vue'), meta: { title: 'Операции — PubChat', requestAuth: true, requiresAdmin: true } },
			],
		},
		{ path: '/:pathMatch(.*)*', name: 'NotFound', component: () => import('../views/NotFoundView.vue'), meta: { title: 'Страница не найдена — PubChat' } },
	],
});

router.beforeEach((to, from, next) => {
	document.title = to.meta.title || 'PubChat';
	const store = useStore();
	const isAuthenticated = Boolean(store.getters.isAuth);
	const userRole = store.getters.getUser?.global_role;
	const accessRestricted = Boolean(store.getters.getAccessRestriction);

	if (to.matched.some((record) => record.meta.requestGuest)) {
		return isAuthenticated
			? next({ name: accessRestricted ? 'restricted-safety' : 'chats' })
			: next();
	}
	if (to.matched.some((record) => record.meta.requestAuth)) {
		if (!isAuthenticated) return next({ name: 'login' });
		if (accessRestricted && to.name !== 'restricted-safety') {
			return next({ name: 'restricted-safety' });
		}
		if (!accessRestricted && to.name === 'restricted-safety') {
			return next({ name: 'safety' });
		}
		if (to.matched.some((record) => record.meta.requiresAdmin)) {
			if (userRole !== 'admin' && userRole !== 'superadmin') return next({ name: 'chats' });
		}
		if (to.matched.some((record) => record.meta.requiresPlatformModerator)) {
			if (!['moderator', 'admin', 'superadmin'].includes(userRole)) return next({ name: 'chats' });
		}
	}
	next();
});

export default router;
