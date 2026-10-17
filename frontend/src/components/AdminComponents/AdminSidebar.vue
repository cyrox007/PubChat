<template>
	<aside id="admin-sidebar" class="admin-sidebar" :class="{ open }" :aria-hidden="open ? 'false' : undefined">
		<div class="sidebar-heading">
			<div>
				<strong>Администрирование</strong>
				<span>PubChat</span>
			</div>
			<button class="close-button" type="button" aria-label="Закрыть меню" @click="$emit('close')">
				<i class="fas fa-times" aria-hidden="true"></i>
			</button>
		</div>

		<nav aria-label="Разделы администрирования">
			<router-link :to="{ name: 'AdminDashboardHome' }" class="sidebar-link" active-class="active" @click="$emit('navigate')">
				<i class="fas fa-tachometer-alt" aria-hidden="true"></i>
				<span>Консоль</span>
			</router-link>
			<router-link :to="{ name: 'AdminProfileList' }" class="sidebar-link" active-class="active" @click="$emit('navigate')">
				<i class="fas fa-users" aria-hidden="true"></i>
				<span>Пользователи</span>
			</router-link>
			<router-link :to="{ name: 'trust-safety-queue' }" class="sidebar-link" active-class="active" @click="$emit('navigate')">
				<i class="fas fa-shield-halved" aria-hidden="true"></i>
				<span>Trust & Safety</span>
			</router-link>
			<router-link :to="{ name: 'AdminOperations' }" class="sidebar-link" active-class="active" @click="$emit('navigate')">
				<i class="fas fa-chart-line" aria-hidden="true"></i>
				<span>Операции</span>
			</router-link>
		</nav>
	</aside>
</template>

<script setup>
defineProps({
	open: { type: Boolean, default: false }
});
defineEmits(['close', 'navigate']);
</script>

<style scoped>
.admin-sidebar {
	position: sticky;
	top: 0;
	flex: 0 0 240px;
	width: 240px;
	height: 100dvh;
	background: var(--sidebar-bg-light);
	border-right: 1px solid var(--ui-border);
	padding: var(--ui-space-4) var(--ui-space-3);
	backdrop-filter: blur(16px);
}

.sidebar-heading {
	display: flex;
	align-items: center;
	justify-content: space-between;
	gap: var(--ui-space-3);
	padding: var(--ui-space-2) var(--ui-space-3) var(--ui-space-5);
}

.sidebar-heading strong,
.sidebar-heading span {
	display: block;
}

.sidebar-heading span {
	margin-top: 2px;
	font-size: var(--ui-text-xs);
	color: var(--ui-text-muted);
}

.close-button {
	display: none;
	width: 38px;
	height: 38px;
	border: 1px solid var(--ui-border);
	border-radius: var(--ui-radius-md);
	background: var(--ui-surface);
	color: var(--ui-text);
	cursor: pointer;
}

nav {
	display: grid;
	gap: var(--ui-space-1);
}

.sidebar-link {
	display: flex;
	align-items: center;
	gap: var(--ui-space-3);
	min-height: 44px;
	padding: var(--ui-space-2) var(--ui-space-3);
	border-radius: var(--ui-radius-md);
	color: var(--ui-text-muted);
	text-decoration: none;
	transition: background var(--ui-motion-fast) var(--ui-ease), color var(--ui-motion-fast) var(--ui-ease);
}

.sidebar-link:hover,
.sidebar-link:focus-visible {
	background: var(--ui-surface-muted);
	color: var(--ui-text);
}

.sidebar-link.active {
	background: var(--ui-primary-soft);
	color: var(--ui-primary);
	font-weight: 700;
}

.sidebar-link i {
	width: 20px;
	text-align: center;
}

@media (max-width: 900px) {
	.admin-sidebar {
		position: fixed;
		top: var(--ui-mobile-topbar-height);
		bottom: calc(var(--ui-mobile-nav-height) + env(safe-area-inset-bottom));
		left: 0;
		z-index: 126;
		width: min(86vw, 320px);
		height: auto;
		padding: var(--ui-space-3);
		overflow-y: auto;
		overscroll-behavior: contain;
		background: var(--ui-surface-raised);
		border-right: 1px solid var(--ui-border);
		border-radius: 0 var(--ui-radius-xl) var(--ui-radius-xl) 0;
		transform: translateX(-105%);
		visibility: hidden;
		transition:
			transform var(--ui-motion-medium) var(--ui-ease-out),
			visibility 0s linear var(--ui-motion-medium);
		box-shadow: var(--ui-shadow-lg);
	}

	.admin-sidebar.open {
		transform: translateX(0);
		visibility: visible;
		transition-delay: 0s;
	}

	.sidebar-heading {
		position: sticky;
		top: 0;
		z-index: 1;
		margin: calc(-1 * var(--ui-space-3)) calc(-1 * var(--ui-space-3)) var(--ui-space-2);
		padding: var(--ui-space-4) var(--ui-space-4) var(--ui-space-3);
		background: var(--ui-surface-raised);
		border-bottom: 1px solid var(--ui-border);
	}

	.close-button {
		display: inline-grid;
		place-items: center;
		flex: 0 0 38px;
	}

	.sidebar-link {
		min-height: 48px;
		font-size: var(--ui-text-sm);
	}
}

@media (max-width: 420px) {
	.admin-sidebar {
		width: min(90vw, 300px);
	}
}

@media (prefers-reduced-motion: reduce) {
	.admin-sidebar {
		transition: none;
	}
}
</style>
