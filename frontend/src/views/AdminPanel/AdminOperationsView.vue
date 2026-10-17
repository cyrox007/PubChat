<template>
	<section class="operations-view">
		<header class="operations-header">
			<div>
				<p class="eyebrow">Наблюдаемость</p>
				<h1>Операции</h1>
				<p>Состояние PostgreSQL, realtime Redis и внешней доставки уведомлений.</p>
			</div>
			<button class="ui-button ui-button--secondary" type="button" :disabled="loading" @click="loadMetrics">
				<i class="fas fa-sync-alt" :class="{ spinning: loading }" aria-hidden="true"></i>
				<span>Обновить</span>
			</button>
		</header>

		<div v-if="error" class="ui-surface operations-error" role="alert">
			<i class="fas fa-triangle-exclamation" aria-hidden="true"></i>
			<div><strong>Не удалось получить операционные метрики</strong><span>{{ error }}</span></div>
			<button class="ui-button ui-button--secondary" type="button" @click="loadMetrics">Повторить</button>
		</div>

		<div v-else class="operations-grid" :aria-busy="loading ? 'true' : 'false'">
			<article v-for="section in sections" :key="section.key" class="ui-surface metric-card">
				<header>
					<span class="metric-icon"><i :class="section.icon" aria-hidden="true"></i></span>
					<div><h2>{{ section.title }}</h2><p>{{ section.description }}</p></div>
				</header>
				<dl v-if="section.rows.length" class="metric-list">
					<div v-for="row in section.rows" :key="row.label">
						<dt>{{ row.label }}</dt><dd>{{ row.value }}</dd>
					</div>
				</dl>
				<p v-else class="metric-empty">Метрики пока не получены.</p>
			</article>
		</div>
	</section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue';
import AdminService from '@/API/Admin/AdminService';

const loading = ref(false);
const error = ref('');
const postgres = ref(null);
const realtime = ref(null);
const delivery = ref(null);

const LABELS = {
	status: 'Статус', state: 'Состояние', healthy: 'Исправно',
	pool_size: 'Размер пула', checked_out: 'Занято соединений', checked_in: 'Свободно соединений',
	overflow: 'Overflow', max_overflow: 'Макс. overflow', utilization: 'Загрузка', utilization_percent: 'Загрузка',
	connections: 'Соединения', active_connections: 'Активные соединения',
	max_connections: 'Лимит соединений', failures: 'Ошибки', failure_count: 'Ошибки',
	delivered: 'Доставлено', sent: 'Отправлено', pending: 'В очереди', failed: 'Не доставлено',
	attempted: 'Попыток', success_rate: 'Успешность', window_hours: 'Окно, часов',
};

const prettyKey = (key) => LABELS[key] || String(key).replaceAll('_', ' ');
const prettyValue = (value, key = '') => {
	if (value === null || value === undefined) return '—';
	if (typeof value === 'boolean') return value ? 'Да' : 'Нет';
	if (typeof value === 'number' && (String(key).includes('rate') || String(key).includes('percent'))) {
		return value <= 1 ? `${Math.round(value * 100)}%` : `${Math.round(value)}%`;
	}
	if (typeof value === 'object') return JSON.stringify(value);
	return String(value);
};
const metricRows = (value) => {
	if (!value || typeof value !== 'object') return [];
	return Object.entries(value)
		.filter(([, item]) => ['string', 'number', 'boolean'].includes(typeof item) || item == null)
		.slice(0, 12)
		.map(([key, item]) => ({ label: prettyKey(key), value: prettyValue(item, key) }));
};

const sections = computed(() => [
	{ key: 'postgres', title: 'PostgreSQL', description: 'Пул соединений основного хранилища.', icon: 'fas fa-database', rows: metricRows(postgres.value) },
	{ key: 'realtime', title: 'Realtime Redis', description: 'Пул realtime/presence и состояние Redis.', icon: 'fas fa-bolt', rows: metricRows(realtime.value) },
	{ key: 'delivery', title: 'Внешняя доставка', description: 'Email, push и другие внешние каналы за последние 24 часа.', icon: 'fas fa-paper-plane', rows: metricRows(delivery.value) },
]);

const loadMetrics = async () => {
	loading.value = true;
	error.value = '';
	try {
		const [postgresResponse, realtimeResponse, deliveryResponse] = await Promise.all([
			AdminService.getPostgresPoolMetrics(),
			AdminService.getRealtimeRedisMetrics(),
			AdminService.getExternalDeliveryMetrics(24),
		]);
		postgres.value = postgresResponse.data?.metrics || {};
		realtime.value = realtimeResponse.data?.metrics || {};
		delivery.value = deliveryResponse.data?.metrics || {};
	} catch (err) {
		error.value = err?.response?.data?.detail?.message || err?.response?.data?.message || 'Проверьте соединение и права администратора.';
	} finally {
		loading.value = false;
	}
};

onMounted(loadMetrics);
</script>

<style scoped>
.operations-view{width:min(100%,1500px);margin:0 auto}.operations-header{display:flex;align-items:flex-start;justify-content:space-between;gap:var(--ui-space-4);margin-bottom:var(--ui-space-5)}.operations-header h1{margin:0;font-size:clamp(1.55rem,3vw,2rem)}.operations-header p:not(.eyebrow){margin:var(--ui-space-2) 0 0;color:var(--ui-text-muted)}.eyebrow{margin:0 0 var(--ui-space-1);color:var(--ui-primary);font-size:var(--ui-text-xs);font-weight:800;text-transform:uppercase;letter-spacing:.08em}.operations-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:var(--ui-space-4)}.metric-card{min-width:0;padding:var(--ui-space-4)}.metric-card header{display:flex;align-items:flex-start;gap:var(--ui-space-3);margin-bottom:var(--ui-space-4)}.metric-card h2{margin:0;font-size:var(--ui-text-lg)}.metric-card header p{margin:.25rem 0 0;color:var(--ui-text-muted);font-size:var(--ui-text-sm)}.metric-icon{width:42px;height:42px;display:grid;place-items:center;flex:0 0 auto;border-radius:var(--ui-radius-md);background:var(--ui-primary-soft);color:var(--ui-primary)}.metric-list{display:grid;margin:0}.metric-list>div{display:flex;justify-content:space-between;gap:var(--ui-space-3);padding:.6rem 0;border-top:1px solid var(--ui-border)}.metric-list dt{color:var(--ui-text-muted);text-transform:capitalize}.metric-list dd{margin:0;font-weight:700;text-align:right;overflow-wrap:anywhere}.metric-empty{color:var(--ui-text-muted)}.operations-error{display:flex;align-items:center;gap:var(--ui-space-3);padding:var(--ui-space-4);color:var(--ui-danger)}.operations-error div{display:grid;gap:.2rem;flex:1}.spinning{animation:spin .8s linear infinite}@keyframes spin{to{transform:rotate(360deg)}}@media(max-width:1100px){.operations-grid{grid-template-columns:1fr}}@media(max-width:600px){.operations-header{align-items:center;margin-bottom:var(--ui-space-3)}.operations-header button span{display:none}.operations-header button{width:44px;padding:0}.metric-card{padding:var(--ui-space-3)}.operations-error{align-items:flex-start;flex-wrap:wrap}}