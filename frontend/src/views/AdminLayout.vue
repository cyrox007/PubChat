<template>
	<div class="admin-layout">
		<header class="admin-mobile-bar">
			<button
				class="menu-button"
				type="button"
				aria-label="Открыть меню администратора"
				aria-controls="admin-sidebar"
				:aria-expanded="sidebarOpen ? 'true' : 'false'"
				@click="sidebarOpen = true"
			>
				<i class="fas fa-bars" aria-hidden="true"></i>
			</button>
			<div class="admin-mobile-bar__copy">
				<strong>PubChat Admin</strong>
				<span>Управление платформой</span>
			</div>
		</header>

		<Transition name="admin-backdrop">
			<div v-if="sidebarOpen" class="sidebar-backdrop" aria-hidden="true" @click="sidebarOpen = false"></div>
		</Transition>
		<AdminSidebar :open="sidebarOpen" @navigate="sidebarOpen = false" @close="sidebarOpen = false" />

		<main class="admin-content">
			<router-view />
		</main>
	</div>
</template>

<script setup>
import { onBeforeUnmount, watch, ref } from 'vue';
import { useRoute } from 'vue-router';
import AdminSidebar from '@/components/AdminComponents/AdminSidebar.vue';

const route = useRoute();
const sidebarOpen = ref(false);

const handleEscape = (event) => {
	if (event.key === 'Escape' && sidebarOpen.value) sidebarOpen.value = false;
};

document.addEventListener('keydown', handleEscape);

watch(() => route.fullPath, () => {
	sidebarOpen.value = false;
});

watch(sidebarOpen, (open) => {
	document.documentElement.classList.toggle('admin-drawer-open', open);
});

onBeforeUnmount(() => {
	document.removeEventListener('keydown', handleEscape);
	document.documentElement.classList.remove('admin-drawer-open');
});
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
		--admin-mobile-bar-height: 3.25rem;
		display: block;
		min-height: auto;
	}

	.admin-mobile-bar {
		position: sticky;
		top: var(--ui-mobile-topbar-height);
		z-index: 118;
		height: var(--admin-mobile-bar-height);
		display: flex;
		align-items: center;
		gap: var(--ui-space-3);
		margin-inline: calc(-1 * var(--ui-space-3));
		padding: 0 max(var(--ui-space-3), env(safe-area-inset-left));
		background: color-mix(in srgb, var(--ui-surface) 97%, transparent);
		border-bottom: 1px solid var(--ui-border);
		box-shadow: 0 5px 16px color-mix(in srgb, #000 8%, transparent);
		backdrop-filter: blur(18px);
	}

	.admin-mobile-bar__copy {
		min-width: 0;
	}

	.admin-mobile-bar strong,
	.admin-mobile-bar span {
		display: block;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.admin-mobile-bar strong {
		font-size: var(--ui-text-sm);
	}

	.admin-mobile-bar span {
		margin-top: 1px;
		font-size: var(--ui-text-xs);
		color: var(--ui-text-muted);
	}

	.menu-button {
		width: 40px;
		height: 40px;
		flex: 0 0 40px;
		display: grid;
		place-items: center;
		border: 1px solid var(--ui-border);
		border-radius: var(--ui-radius-md);
		background: var(--ui-surface);
		color: var(--ui-text);
		font-size: 1rem;
		box-shadow: var(--ui-shadow-sm);
		cursor: pointer;
	}

	.sidebar-backdrop {
		position: fixed;
		inset: var(--ui-mobile-topbar-height) 0 calc(var(--ui-mobile-nav-height) + env(safe-area-inset-bottom)) 0;
		z-index: 124;
		display: block;
		background: rgba(0, 0, 0, 0.48);
		backdrop-filter: blur(2px);
	}

	.admin-content {
		width: 100%;
		padding: var(--ui-space-3) 0 calc(var(--ui-space-5) + env(safe-area-inset-bottom));
	}

	.admin-backdrop-enter-active,
	.admin-backdrop-leave-active {
		transition: opacity var(--ui-motion-fast) var(--ui-ease);
	}

	.admin-backdrop-enter-from,
	.admin-backdrop-leave-to {
		opacity: 0;
	}
}

@media (max-width: 480px) {
	.admin-mobile-bar {
		margin-inline: calc(-1 * var(--ui-space-2));
		padding-inline: max(var(--ui-space-2), env(safe-area-inset-left));
	}

	.admin-content {
		padding-top: var(--ui-space-2);
	}
}
</style>

<style>
@media (max-width: 900px) {
	html.admin-drawer-open,
	html.admin-drawer-open body {
		overflow: hidden;
	}
}
</style>
