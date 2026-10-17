<template>
	<nav class="space-context-nav" aria-label="Навигация пространства">
		<div class="space-context-nav__inner">
			<RouterLink class="space-context-nav__identity" :to="spaceRoute" :title="spaceName">
				<span class="space-context-nav__dot" aria-hidden="true"></span>
				<strong>{{ spaceName }}</strong>
			</RouterLink>
			<span class="space-context-nav__divider" aria-hidden="true"></span>
			<div class="space-context-nav__links">
				<RouterLink :to="spaceRoute">Разговор</RouterLink>
				<RouterLink :to="communityRoute">Центр</RouterLink>
				<RouterLink :to="lifeRoute">Жизнь</RouterLink>
				<RouterLink :to="supportRoute">Поддержка</RouterLink>
			</div>
		</div>
	</nav>
</template>

<script setup>
import { computed } from 'vue';
import { RouterLink } from 'vue-router';
import { useStore } from 'vuex';

const props = defineProps({
	spaceUid: { type: String, required: true },
});

const store = useStore();
const currentRoom = computed(() => store.getters['chat/getCurrentRoom'] || null);
const spaceName = computed(() => {
	const room = currentRoom.value;
	if (room && String(room.uid || '') === String(props.spaceUid) && room.name) return String(room.name).trim();
	return 'Пространство';
});
const routeParams = computed(() => ({ uid: props.spaceUid }));
const spaceRoute = computed(() => ({ name: 'space', params: routeParams.value }));
const communityRoute = computed(() => ({ name: 'space-community', params: routeParams.value }));
const lifeRoute = computed(() => ({ name: 'space-life', params: routeParams.value }));
const supportRoute = computed(() => ({ name: 'space-support', params: routeParams.value }));
</script>

<style scoped>
.space-context-nav {
	position: sticky;
	top: 3.75rem;
	z-index: 110;
	border-bottom: 1px solid var(--ui-border);
	background: color-mix(in srgb, var(--ui-surface) 96%, transparent);
	backdrop-filter: blur(14px);
}
.space-context-nav__inner {
	width: min(100%, var(--ui-container-max, 1200px));
	min-height: 2.85rem;
	margin: 0 auto;
	display: flex;
	align-items: center;
	gap: var(--ui-space-2);
	padding: .25rem var(--ui-space-4);
	overflow-x: auto;
	overflow-y: hidden;
	overscroll-behavior-inline: contain;
	scrollbar-width: none;
	white-space: nowrap;
}
.space-context-nav__inner::-webkit-scrollbar { display: none; }
.space-context-nav__identity {
	min-width: 0;
	max-width: 15rem;
	display: inline-flex;
	align-items: center;
	gap: .45rem;
	flex: 0 1 auto;
	padding: 0 .3rem;
	color: var(--ui-text);
	text-decoration: none;
}
.space-context-nav__identity strong {
	min-width: 0;
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
	font-size: var(--ui-text-sm);
}
.space-context-nav__dot {
	width: .48rem;
	height: .48rem;
	flex: 0 0 .48rem;
	border-radius: 50%;
	background: var(--ui-success);
	box-shadow: 0 0 0 .16rem color-mix(in srgb, var(--ui-success) 12%, transparent);
}
.space-context-nav__divider {
	width: 1px;
	height: 1.4rem;
	flex: 0 0 1px;
	background: var(--ui-border);
}
.space-context-nav__links {
	display: flex;
	align-items: center;
	gap: .15rem;
	flex: 0 0 auto;
}
.space-context-nav__links a {
	min-height: 2.15rem;
	display: inline-flex;
	align-items: center;
	padding: 0 .7rem;
	border-radius: var(--ui-radius-md);
	color: var(--ui-text-muted);
	text-decoration: none;
	font-size: var(--ui-text-sm);
	font-weight: 650;
}
.space-context-nav__links a:hover,
.space-context-nav__links a.router-link-exact-active {
	background: var(--ui-primary-soft);
	color: var(--ui-primary);
}
@media (max-width: 720px) {
	.space-context-nav { top: var(--ui-mobile-topbar-height); }
	.space-context-nav__inner { min-height: 2.6rem; padding: .2rem var(--ui-space-3); gap: .35rem; }
	.space-context-nav__identity { max-width: 8.5rem; }
	.space-context-nav__identity strong,
	.space-context-nav__links a { font-size: .72rem; }
	.space-context-nav__links a { min-height: 2rem; padding: 0 .55rem; }
}
</style>
