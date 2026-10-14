<template>
	<section class="dashboard">
		<header class="dashboard-header">
			<div><p class="eyebrow">Обзор платформы</p><h1>Административная консоль</h1><p>Ключевые показатели PubChat и текущая активность.</p></div>
			<button class="ui-button ui-button--secondary" :disabled="loading" @click="loadStats"><i class="fas fa-sync-alt" :class="{ spinning: loading }"></i><span>Обновить</span></button>
		</header>

		<div v-if="error" class="dashboard-state ui-surface"><i class="fas fa-exclamation-circle"></i><div><strong>Статистика недоступна</strong><span>{{ error }}</span></div><button class="ui-button ui-button--secondary" @click="loadStats">Повторить</button></div>

		<template v-else>
			<div class="stats-grid">
				<StatCard title="Всего пользователей" :value="stats.total_users" icon="users" color="blue" />
				<StatCard title="Онлайн сейчас" :value="stats.online_users" icon="user-check" color="green" />
				<StatCard title="Активных комнат" :value="stats.active_rooms" icon="comments" color="purple" />
				<StatCard title="Новых сегодня" :value="stats.new_today" icon="user-plus" color="orange" />
			</div>

			<div class="charts-grid">
				<ChartContainer title="Пользователи по полу"><GenderChart :data="stats.gender_data" /></ChartContainer>
				<ChartContainer title="География пользователей"><GeoChart :data="stats.geo_data" /></ChartContainer>
				<ChartContainer title="Устройства"><DevicesChart :data="stats.devices_data" /></ChartContainer>
				<ChartContainer title="Активность по времени"><ActivityChart :data="stats.activity_data" /></ChartContainer>
			</div>

			<div class="tables-section">
				<PopularRoomsTable :rooms="stats.popular_rooms" />
				<RecentRegistrationsTable :users="stats.recent_users" />
			</div>
		</template>
	</section>
</template>

<script setup>
import { onMounted, ref } from 'vue';
import StatCard from '@/components/AdminComponents/Cards/StatCard.vue';
import ChartContainer from '@/components/AdminComponents/ChartContainer.vue';
import GenderChart from '@/components/AdminComponents/Charts/GenderChart.vue';
import GeoChart from '@/components/AdminComponents/Charts/GeoChart.vue';
import DevicesChart from '@/components/AdminComponents/Charts/DevicesChart.vue';
import ActivityChart from '@/components/AdminComponents/Charts/ActivityChart.vue';
import PopularRoomsTable from '@/components/AdminComponents/Tables/PopularRoomsTable.vue';
import RecentRegistrationsTable from '@/components/AdminComponents/Tables/RecentRegistrationsTable.vue';
import AdminService from '@/API/Admin/AdminService';

const emptyStats = () => ({ total_users: 0, online_users: 0, active_rooms: 0, new_today: 0, gender_data: [], geo_data: [], devices_data: { browsers: [], os: [], device_types: [], brands: [], active_now: 0 }, activity_data: [], popular_rooms: [], recent_users: [] });
const stats = ref(emptyStats());
const loading = ref(false);
const error = ref('');
const loadStats = async () => { loading.value = true; error.value = ''; try { const response = await AdminService.getDashboardStats(); stats.value = { ...emptyStats(), ...(response.data?.stats || {}) }; } catch (e) { error.value = e?.response?.data?.message || 'Не удалось получить данные панели.'; } finally { loading.value = false; } };
onMounted(loadStats);
</script>

<style scoped>
.dashboard{width:min(100%,1500px);margin:0 auto}.dashboard-header{display:flex;align-items:flex-start;justify-content:space-between;gap:var(--ui-space-4);margin-bottom:var(--ui-space-5)}.dashboard-header h1{margin:0;font-size:clamp(1.55rem,3vw,2rem)}.dashboard-header p:not(.eyebrow){margin:var(--ui-space-2) 0 0;color:var(--ui-text-muted)}.eyebrow{margin:0 0 var(--ui-space-1);color:var(--ui-primary);font-size:var(--ui-text-xs);font-weight:800;text-transform:uppercase;letter-spacing:.08em}.stats-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:var(--ui-space-3);margin-bottom:var(--ui-space-4)}.charts-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:var(--ui-space-4);margin-bottom:var(--ui-space-4)}.charts-grid>*{min-width:0}.tables-section{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:var(--ui-space-4)}.tables-section>*{min-width:0}.dashboard-state{min-height:180px;display:flex;align-items:center;justify-content:center;gap:var(--ui-space-3);padding:var(--ui-space-5);color:var(--ui-danger)}.dashboard-state div strong,.dashboard-state div span{display:block}.spinning{animation:spin .8s linear infinite}@keyframes spin{to{transform:rotate(360deg)}}
@media(max-width:1100px){.stats-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.charts-grid{grid-template-columns:1fr}.tables-section{grid-template-columns:1fr}}
@media(max-width:600px){.dashboard-header{align-items:center}.dashboard-header button span{display:none}.dashboard-header button{width:44px;padding:0}.stats-grid{gap:var(--ui-space-2)}.charts-grid,.tables-section{gap:var(--ui-space-2)}.dashboard-state{flex-direction:column;text-align:center}}
@media(max-width:390px){.stats-grid{grid-template-columns:1fr}}
</style>
