<template>
	<aside class="admin-sidebar" :class="{ open }">
		<div class="sidebar-heading">
			<div>
				<strong>Администрирование</strong>
				<span>PubChat</span>
			</div>
			<button class="close-button" type="button" aria-label="Закрыть меню" @click="$emit('close')">
				<i class="fas fa-times"></i>
			</button>
		</div>

		<nav>
			<router-link :to="{ name: 'AdminDashboardHome' }" class="sidebar-link" active-class="active" @click="$emit('navigate')">
				<i class="fas fa-tachometer-alt"></i>
				<span>Консоль</span>
			</router-link>
			<router-link :to="{ name: 'AdminProfileList' }" class="sidebar-link" active-class="active" @click="$emit('navigate')">
				<i class="fas fa-users"></i>
				<span>Пользователи</span>
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

.sidebar-link:hover {
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
		inset: 0 auto 0 0;
		z-index: 65;
		width: min(82vw, 300px);
		height: 100dvh;
		padding-top: max(var(--ui-space-4), env(safe-area-inset-top));
		transform: translateX(-105%);
		transition: transform var(--ui-motion-medium) var(--ui-ease-out);
		box-shadow: var(--ui-shadow-lg);
	}

	.admin-sidebar.open {
		transform: translateX(0);
	}

	.close-button {
		display: inline-grid;
		place-items: center;
	}
}
</style>
