<template>
	<div class="admin-layout">
		<header class="admin-mobile-bar">
			<button class="menu-button" type="button" aria-label="Открыть меню администратора" @click="sidebarOpen = true">
				<i class="fas fa-bars"></i>
			</button>
			<div>
				<strong>PubChat Admin</strong>
				<span>Управление платформой</span>
			</div>
		</header>

		<div v-if="sidebarOpen" class="sidebar-backdrop" @click="sidebarOpen = false"></div>
		<AdminSidebar :open="sidebarOpen" @navigate="sidebarOpen = false" @close="sidebarOpen = false" />

		<main class="admin-content">
			<router-view />
		</main>
	</div>
</template>

<script setup>
import { ref } from 'vue';
import AdminSidebar from '@/components/AdminComponents/AdminSidebar.vue';

const sidebarOpen = ref(false);
</script>

<style scoped>
.admin-layout {
	display: flex;
	min-height: 100dvh;
	width: 100%;
	background: var(--ui-bg);
}

.admin-content {
	flex: 1 1 auto;
	min-width: 0;
	width: calc(100% - 240px);
	padding: clamp(var(--ui-space-4), 2vw, var(--ui-space-6));
	overflow-x: clip;
}

.admin-mobile-bar,
.sidebar-backdrop {
	display: none;
}

@media (max-width: 900px) {
	.admin-layout {
		display: block;
		padding-top: 58px;
	}

	.admin-mobile-bar {
		position: fixed;
		inset: 0 0 auto 0;
		z-index: 60;
		height: 58px;
		display: flex;
		align-items: center;
		gap: var(--ui-space-3);
		padding: 0 max(var(--ui-space-3), env(safe-area-inset-left));
		background: color-mix(in srgb, var(--ui-surface) 94%, transparent);
		border-bottom: 1px solid var(--ui-border);
		backdrop-filter: blur(16px);
	}

	.admin-mobile-bar strong,
	.admin-mobile-bar span {
		display: block;
	}

	.admin-mobile-bar strong {
		font-size: var(--ui-text-sm);
	}

	.admin-mobile-bar span {
		font-size: var(--ui-text-xs);
		color: var(--ui-text-muted);
	}

	.menu-button {
		width: 42px;
		height: 42px;
		border: 1px solid var(--ui-border);
		border-radius: var(--ui-radius-md);
		background: var(--ui-surface);
		color: var(--ui-text);
	}

	.sidebar-backdrop {
		position: fixed;
		inset: 0;
		z-index: 64;
		display: block;
		background: rgba(0, 0, 0, 0.34);
	}

	.admin-content {
		width: 100%;
		padding: var(--ui-space-3);
	}
}

@media (max-width: 480px) {
	.admin-content {
		padding: var(--ui-space-2);
	}
}
</style>
