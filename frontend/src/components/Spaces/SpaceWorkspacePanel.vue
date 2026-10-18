<template>
	<section class="space-workspace" aria-label="Раздел пространства">
		<SpacePulsePanel v-if="section === 'life'" :space-uid="spaceUid" />
		<component :is="sections[section]" :key="`${spaceUid}:${section}`" />
	</section>
</template>

<script setup>
import { defineAsyncComponent } from 'vue';
import SpacePulsePanel from './SpacePulsePanel.vue';

defineProps({ spaceUid: { type: String, required: true }, section: { type: String, required: true } });
const sections = {
	community: defineAsyncComponent(() => import('@/views/SpaceCommunityView.vue')),
	life: defineAsyncComponent(() => import('@/views/SpaceLifeView.vue')),
	support: defineAsyncComponent(() => import('@/views/SpaceSupportView.vue')),
	moderation: defineAsyncComponent(() => import('@/views/SpaceModerationView.vue')),
};
</script>

<style scoped>
.space-workspace { min-height: 0; flex: 1; overflow-y: auto; padding: var(--ui-space-4); }
.space-workspace :deep(main) { min-width: 0; }
.space-workspace :deep(.community-header), .space-workspace :deep(.life-hero),
.space-workspace :deep(.support-hero), .space-workspace :deep(.moderation-header) {
	padding: var(--ui-space-4); flex-direction: column; align-items: stretch;
}
.space-workspace :deep(.action-form), .space-workspace :deep(.date-grid) { grid-template-columns: 1fr; }
.space-workspace :deep(input), .space-workspace :deep(textarea), .space-workspace :deep(select) { min-width: 0; max-width: 100%; }
</style>
