<template>
	<div class="stat-card" :class="`bg-${color}`">
		<div class="stat-icon" aria-hidden="true">
			<i :class="`fas fa-${icon}`"></i>
		</div>
		<div class="stat-content">
			<h3>{{ title }}</h3>
			<p class="stat-value">{{ value }}</p>
		</div>
	</div>
</template>

<script setup>
defineProps({
	title: String,
	value: [Number, String],
	icon: String,
	color: {
		type: String,
		default: 'blue'
	}
});
</script>

<style scoped>
.stat-card {
	min-width: 0;
	min-height: 108px;
	display: flex;
	align-items: center;
	gap: var(--ui-space-3);
	padding: var(--ui-space-4);
	border-radius: var(--ui-radius-lg);
	color: white;
	box-shadow: var(--ui-shadow-sm);
}

.stat-icon {
	width: 42px;
	flex: 0 0 42px;
	display: grid;
	place-items: center;
	font-size: 1.7rem;
}

.stat-content {
	min-width: 0;
}

.stat-content h3 {
	margin: 0 0 var(--ui-space-1);
	font-size: .92rem;
	line-height: 1.2;
}

.stat-value {
	margin: 0;
	font-size: 1.65rem;
	font-weight: 800;
	line-height: 1;
}

.bg-blue { background-color: #4299E1; }
.bg-green { background-color: #48BB78; }
.bg-purple { background-color: #9F7AEA; }
.bg-orange { background-color: #ED8936; }

@media (max-width: 600px) {
	.stat-card {
		min-height: 88px;
		gap: var(--ui-space-2);
		padding: .75rem;
		border-radius: var(--ui-radius-md);
	}

	.stat-icon {
		width: 32px;
		flex-basis: 32px;
		font-size: 1.3rem;
	}

	.stat-content h3 {
		margin-bottom: .25rem;
		font-size: .78rem;
	}

	.stat-value {
		font-size: 1.4rem;
	}
}
</style>