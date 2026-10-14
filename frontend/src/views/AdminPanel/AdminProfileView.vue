<template>
	<section class="profile-page">
		<header class="page-header">
			<button class="back-button" @click="router.back()"><i class="fas fa-arrow-left"></i></button>
			<div class="identity"><div class="avatar">{{ initials }}</div><div><p class="eyebrow">Карточка пользователя</p><h1>{{ profile.username || 'Пользователь' }}</h1><p>{{ profile.email || profile.uid }}</p></div></div>
			<button class="ui-button ui-button--secondary" :disabled="loading" @click="loadAll"><i class="fas fa-sync-alt" :class="{ spinning: loading }"></i><span>Обновить</span></button>
		</header>

		<div v-if="error" class="error-box ui-surface"><i class="fas fa-exclamation-circle"></i><span>{{ error }}</span><button class="ui-button ui-button--secondary" @click="loadAll">Повторить</button></div>
		<div v-else-if="loading && !profile.uid" class="loading-box"><i class="fas fa-circle-notch spinning"></i> Загружаем данные…</div>

		<template v-else>
			<div class="status-row">
				<span class="badge" :class="profile.is_active ? 'success' : 'danger'">{{ profile.is_active ? 'Активен' : 'Отключён' }}</span>
				<span class="badge role">{{ roleName(profile.global_role) }}</span>
				<span class="badge" :class="profile.is_verified ? 'success' : 'muted'">{{ profile.is_verified ? 'Email подтверждён' : 'Email не подтверждён' }}</span>
				<span v-if="profile.account" class="badge muted">Trust: {{ profile.account.trust_level || 'new' }}</span>
			</div>

			<div class="stats-grid">
				<div v-for="item in statCards" :key="item.label" class="stat-card ui-surface"><span>{{ item.label }}</span><strong>{{ item.value }}</strong></div>
			</div>

			<div class="content-grid">
				<section class="panel ui-surface">
					<div class="panel-title"><div><h2>Профиль и доступ</h2><p>Основные данные и административные параметры.</p></div><button v-if="!editing" class="ui-button ui-button--secondary" @click="beginEdit"><i class="fas fa-pen"></i> Редактировать</button></div>
					<div v-if="editing" class="edit-grid">
						<label>Логин<input v-model="draft.username" class="ui-input"></label><label>Email<input v-model="draft.email" class="ui-input" type="email"></label><label>Телефон<input v-model="draft.phone" class="ui-input"></label><label>Роль<select v-model="draft.global_role" class="ui-input"><option value="user">Пользователь</option><option value="moderator">Модератор</option><option value="senior_moderator">Ст. модератор</option><option value="admin">Администратор</option><option value="superadmin">Супер-админ</option></select></label><label>Страна<input v-model="draft.country" class="ui-input"></label><label>Город<input v-model="draft.city" class="ui-input"></label><label class="wide">Биография<textarea v-model="draft.bio" class="ui-input"></textarea></label>
						<div class="toggle-row wide"><label><input v-model="draft.is_active" type="checkbox"> Аккаунт активен</label><label><input v-model="draft.is_verified" type="checkbox"> Email подтверждён</label></div>
						<div class="form-actions wide"><button class="ui-button" :disabled="saving" @click="saveProfile">Сохранить</button><button class="ui-button ui-button--secondary" @click="editing=false">Отмена</button></div>
					</div>
					<dl v-else class="details"><Info label="UUID" :value="profile.uid" mono/><Info label="Account UUID" :value="profile.account?.uid" mono/><Info label="Persona" :value="profile.persona?.display_name || profile.persona?.handle"/><Info label="Телефон" :value="profile.phone"/><Info label="Имя" :value="fullName"/><Info label="Локация" :value="location"/><Info label="Пол" :value="profile.gender"/><Info label="Профессия" :value="profile.career"/><Info label="Регистрация" :value="formatDateTime(profile.created_at)"/><Info label="Последняя активность" :value="formatDateTime(profile.last_online)"/><Info label="Social intent" :value="profile.persona?.social_intent"/><Info label="Account status" :value="profile.account?.status"/></dl>
				</section>

				<section class="panel ui-surface">
					<div class="panel-title"><div><h2>Назначить ограничение</h2><p>Создать временное наказание для пользователя.</p></div></div>
					<div class="penalty-form"><label>Тип<select v-model="newPenalty.penalty_type" class="ui-input"><option value="mute">Mute</option><option value="ban">Ban</option></select></label><label>До<input v-model="newPenalty.expires_at" class="ui-input" type="datetime-local"></label><label class="wide">Причина<textarea v-model="newPenalty.reason" class="ui-input" placeholder="Причина ограничения"></textarea></label><button class="ui-button wide" :disabled="penaltySaving || !newPenalty.expires_at" @click="assignPenalty">Назначить</button></div>
				</section>
			</div>

			<section class="panel ui-surface section-block">
				<div class="panel-title"><div><h2>Наказания</h2><p>{{ penalties.length ? `Записей: ${penalties.length}` : 'Активность не зафиксирована' }}</p></div></div>
				<div v-if="penalties.length" class="records"><article v-for="penalty in penalties" :key="penalty.id" class="record"><div><strong>{{ penalty.type }}</strong><span>{{ penalty.reason || 'Без причины' }}</span><small>{{ formatDateTime(penalty.issued_at) }} → {{ formatDateTime(penalty.expires_at) }}</small></div><button class="danger-button" @click="removePenalty(penalty.id)"><i class="fas fa-trash"></i><span>Удалить</span></button></article></div>
				<div v-else class="empty">Наказаний за доступный период нет.</div>
			</section>

			<section class="panel ui-surface section-block">
				<div class="panel-title"><div><h2>Созданные комнаты</h2><p>{{ rooms.length ? `Комнат: ${rooms.length}` : 'Комнат нет' }}</p></div></div>
				<div v-if="rooms.length" class="room-grid"><article v-for="room in rooms" :key="room.uid || room.id" class="room-card"><strong>{{ room.name }}</strong><p>{{ room.description || 'Без описания' }}</p><span>{{ [room.city, room.region, room.country].filter(Boolean).join(', ') || 'Локация не указана' }}</span></article></div>
				<div v-else class="empty">Пользователь не создавал комнаты.</div>
			</section>
		</template>
	</section>
</template>

<script setup>
import { computed, defineComponent, h, onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import ProfileService from '@/API/Admin/ProfileService';

const Info = defineComponent({ props: { label: String, value: [String, Number], mono: Boolean }, setup(props) { return () => h('div', { class: 'detail-item' }, [h('dt', props.label), h('dd', { class: props.mono ? 'mono' : '' }, props.value || '—')]); } });
const route = useRoute(), router = useRouter();
const profile = ref({}), rooms = ref([]), penalties = ref([]), loading = ref(false), saving = ref(false), penaltySaving = ref(false), error = ref(''), editing = ref(false), draft = ref({});
const newPenalty = ref({ penalty_type: 'mute', expires_at: '', reason: '' });
const initials = computed(() => (profile.value.username || profile.value.email || '?').slice(0, 2).toUpperCase());
const fullName = computed(() => [profile.value.first_name, profile.value.last_name].filter(Boolean).join(' ') || '—');
const location = computed(() => [profile.value.city, profile.value.country].filter(Boolean).join(', ') || '—');
const statCards = computed(() => [{ label: 'Сообщения', value: profile.value.stats?.messages ?? 0 }, { label: 'Личные сообщения', value: profile.value.stats?.dm_sent ?? 0 }, { label: 'Создано комнат', value: profile.value.stats?.rooms_owned ?? 0 }, { label: 'Участие в комнатах', value: profile.value.stats?.rooms_joined ?? 0 }, { label: 'Наказания', value: profile.value.stats?.penalties ?? penalties.value.length }]);
const roleName = (role) => ({ user: 'Пользователь', moderator: 'Модератор', senior_moderator: 'Ст. модератор', admin: 'Администратор', superadmin: 'Супер-админ' }[role] || role || 'Пользователь');
const formatDateTime = (v) => v ? new Date(v).toLocaleString('ru-RU') : '—';
const loadAll = async () => { loading.value = true; error.value = ''; try { const [overview, roomResponse, penaltyResponse] = await Promise.all([ProfileService.getUserOverview(route.params.uid), ProfileService.getUserRooms(route.params.uid), ProfileService.getUserPenalties(route.params.uid)]); profile.value = overview.data.user || {}; rooms.value = roomResponse.data.rooms || []; penalties.value = penaltyResponse.data.penalties || []; } catch (e) { error.value = e?.response?.data?.message || 'Не удалось загрузить карточку пользователя.'; } finally { loading.value = false; } };
const beginEdit = () => { draft.value = { username: profile.value.username || '', email: profile.value.email || '', phone: profile.value.phone || '', global_role: profile.value.global_role || 'user', country: profile.value.country || '', city: profile.value.city || '', bio: profile.value.bio || '', is_active: !!profile.value.is_active, is_verified: !!profile.value.is_verified }; editing.value = true; };
const saveProfile = async () => { saving.value = true; try { await ProfileService.updateAdminProfile(route.params.uid, draft.value); editing.value = false; await loadAll(); } catch (e) { error.value = e?.response?.data?.message || 'Не удалось сохранить изменения.'; } finally { saving.value = false; } };
const assignPenalty = async () => { penaltySaving.value = true; try { await ProfileService.assignPenalty({ user_uid: route.params.uid, penalty_type: newPenalty.value.penalty_type, expires_at: new Date(newPenalty.value.expires_at).toISOString(), reason: newPenalty.value.reason || null }); newPenalty.value = { penalty_type: 'mute', expires_at: '', reason: '' }; await loadAll(); } catch (e) { error.value = e?.response?.data?.message || 'Не удалось назначить ограничение.'; } finally { penaltySaving.value = false; } };
const removePenalty = async (id) => { if (!confirm('Удалить это наказание?')) return; await ProfileService.deletePenalty(id); await loadAll(); };
onMounted(loadAll);
</script>

<style scoped>
.profile-page{width:min(100%,1400px);margin:0 auto}.page-header{display:flex;align-items:center;gap:var(--ui-space-3);margin-bottom:var(--ui-space-4)}.page-header>.ui-button{margin-left:auto}.back-button{flex:0 0 42px;width:42px;height:42px;border:1px solid var(--ui-border);border-radius:var(--ui-radius-md);background:var(--ui-surface);color:var(--ui-text)}.identity{display:flex;align-items:center;gap:var(--ui-space-3);min-width:0}.avatar{flex:0 0 52px;width:52px;height:52px;display:grid;place-items:center;border-radius:50%;background:var(--ui-primary-soft);color:var(--ui-primary);font-weight:850}.identity h1{margin:0;font-size:clamp(1.35rem,3vw,1.9rem)}.identity p{margin:2px 0 0;color:var(--ui-text-muted);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.identity .eyebrow{color:var(--ui-primary);font-size:var(--ui-text-xs);font-weight:800;text-transform:uppercase;letter-spacing:.07em}.status-row{display:flex;flex-wrap:wrap;gap:var(--ui-space-2);margin-bottom:var(--ui-space-4)}.badge{padding:5px 10px;border-radius:var(--ui-radius-pill);font-size:var(--ui-text-xs);font-weight:750}.success{background:var(--ui-success-soft);color:var(--ui-success)}.danger{background:var(--ui-danger-soft);color:var(--ui-danger)}.role{background:var(--ui-primary-soft);color:var(--ui-primary)}.muted{background:var(--ui-surface-muted);color:var(--ui-text-muted)}.stats-grid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:var(--ui-space-2);margin-bottom:var(--ui-space-4)}.stat-card{padding:var(--ui-space-3)}.stat-card span,.stat-card strong{display:block}.stat-card span{color:var(--ui-text-muted);font-size:var(--ui-text-xs)}.stat-card strong{margin-top:var(--ui-space-1);font-size:1.45rem}.content-grid{display:grid;grid-template-columns:minmax(0,2fr) minmax(280px,.85fr);gap:var(--ui-space-4)}.panel{padding:var(--ui-space-4);min-width:0}.panel-title{display:flex;align-items:flex-start;justify-content:space-between;gap:var(--ui-space-3);margin-bottom:var(--ui-space-4)}.panel-title h2{margin:0;font-size:var(--ui-text-lg)}.panel-title p{margin:4px 0 0;color:var(--ui-text-muted);font-size:var(--ui-text-sm)}.details{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:1px;margin:0;background:var(--ui-border);border:1px solid var(--ui-border);border-radius:var(--ui-radius-md);overflow:hidden}.details :deep(.detail-item){min-width:0;padding:var(--ui-space-3);background:var(--ui-surface)}.details :deep(dt){color:var(--ui-text-muted);font-size:var(--ui-text-xs)}.details :deep(dd){margin:4px 0 0;overflow-wrap:anywhere}.details :deep(.mono){font-family:var(--ui-font-mono);font-size:var(--ui-text-xs)}.edit-grid,.penalty-form{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:var(--ui-space-3)}.edit-grid label,.penalty-form label{font-size:var(--ui-text-xs);font-weight:700;color:var(--ui-text-muted)}.edit-grid .ui-input,.penalty-form .ui-input{margin-top:var(--ui-space-1)}.wide{grid-column:1/-1}.toggle-row{display:flex;flex-wrap:wrap;gap:var(--ui-space-4);color:var(--ui-text);font-size:var(--ui-text-sm)}.form-actions{display:flex;gap:var(--ui-space-2)}.section-block{margin-top:var(--ui-space-4)}.records{display:grid;gap:var(--ui-space-2)}.record{display:flex;align-items:center;justify-content:space-between;gap:var(--ui-space-3);padding:var(--ui-space-3);border:1px solid var(--ui-border);border-radius:var(--ui-radius-md)}.record strong,.record span,.record small{display:block}.record span{margin-top:3px}.record small{margin-top:4px;color:var(--ui-text-muted)}.danger-button{display:flex;align-items:center;gap:var(--ui-space-2);min-height:38px;padding:0 var(--ui-space-3);border:1px solid var(--ui-danger);border-radius:var(--ui-radius-md);background:transparent;color:var(--ui-danger)}.room-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:var(--ui-space-2)}.room-card{padding:var(--ui-space-3);border:1px solid var(--ui-border);border-radius:var(--ui-radius-md);background:var(--ui-surface-soft)}.room-card p{margin:var(--ui-space-2) 0;color:var(--ui-text-muted);font-size:var(--ui-text-sm)}.room-card span{font-size:var(--ui-text-xs);color:var(--ui-text-muted)}.empty,.loading-box,.error-box{padding:var(--ui-space-5);color:var(--ui-text-muted);text-align:center}.error-box{display:flex;align-items:center;justify-content:center;gap:var(--ui-space-3);color:var(--ui-danger)}.spinning{animation:spin .8s linear infinite}@keyframes spin{to{transform:rotate(360deg)}}
@media(max-width:1050px){.stats-grid{grid-template-columns:repeat(3,minmax(0,1fr))}.content-grid{grid-template-columns:1fr}.room-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:650px){.page-header>.ui-button span{display:none}.page-header>.ui-button{width:44px;padding:0}.avatar{display:none}.stats-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.panel{padding:var(--ui-space-3)}.details,.edit-grid,.penalty-form{grid-template-columns:1fr}.wide{grid-column:auto}.room-grid{grid-template-columns:1fr}.record{align-items:flex-start}.danger-button span{display:none}.danger-button{width:38px;padding:0;justify-content:center}.panel-title{align-items:center}.panel-title>.ui-button{padding-inline:var(--ui-space-3)}.error-box{flex-direction:column}}
@media(max-width:390px){.stats-grid{grid-template-columns:1fr}.status-row{gap:var(--ui-space-1)}}
</style>
