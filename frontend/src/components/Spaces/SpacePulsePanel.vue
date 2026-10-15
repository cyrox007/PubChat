<template>
	<section class="pulse-card" aria-labelledby="space-pulse-title">
		<header class="pulse-head">
			<div>
				<span class="pulse-eyebrow">Пульс пространства</span>
				<strong id="space-pulse-title">Что происходит сейчас</strong>
			</div>
			<button type="button" class="pulse-refresh" :disabled="loading" aria-label="Обновить пульс пространства" @click="load">
				<i class="fas fa-rotate" :class="{ 'fa-spin': loading }" aria-hidden="true"></i>
			</button>
		</header>

		<div v-if="loading && !pulse" class="pulse-state">Собираем пульс…</div>
		<div v-else-if="error && !pulse" class="pulse-state pulse-state--error">
			Не удалось загрузить состояние пространства.
		</div>
		<template v-else-if="pulse">
			<div class="pulse-grid">
				<RouterLink
					class="pulse-stat pulse-stat--conversation pulse-stat--link"
					:to="{ name: 'space', params: { uid: spaceUid }, query: { from: 'pulse' } }"
					aria-label="Перейти в текущий разговор пространства"
				>
					<i class="fas fa-comments" aria-hidden="true"></i>
					<div>
						<span>Разговор</span>
						<strong>{{ conversationLabel }}</strong>
						<small>{{ conversationDetail }}</small>
					</div>
					<i class="fas fa-arrow-right pulse-entry-icon" aria-hidden="true"></i>
				</RouterLink>

				<article class="pulse-stat">
					<i class="fas fa-user-group" aria-hidden="true"></i>
					<div>
						<span>Участники</span>
						<strong>{{ pulse.member_count }}</strong>
						<small>{{ liveCount ? `${liveCount} открыты к общению` : 'Сейчас без live-статуса' }}</small>
					</div>
				</article>

				<RouterLink
					v-if="pulse.next_moment"
					class="pulse-stat pulse-stat--next pulse-stat--link"
					:to="nextMomentTarget"
					:aria-label="`Открыть: ${pulse.next_moment.title}`"
				>
					<i :class="nextMomentIcon" aria-hidden="true"></i>
					<div>
						<span>Дальше</span>
						<strong>{{ pulse.next_moment.title }}</strong>
						<small>{{ nextMomentLabel }}</small>
					</div>
					<i class="fas fa-arrow-right pulse-entry-icon" aria-hidden="true"></i>
				</RouterLink>
				<article v-else class="pulse-stat pulse-stat--next">
					<i :class="nextMomentIcon" aria-hidden="true"></i>
					<div>
						<span>Дальше</span>
						<strong>Пока без планов</strong>
						<small>{{ nextMomentLabel }}</small>
					</div>
				</article>
			</div>

			<div v-if="livePeople.length" class="pulse-live">
				<div class="pulse-section-title">
					<span class="live-dot" aria-hidden="true"></span>
					<strong>Открыты к общению сейчас</strong>
				</div>
				<div class="pulse-people">
					<RouterLink
						v-for="person in livePeople"
						:key="person.persona_uid"
						class="pulse-person"
						:to="{
							name: 'UserProfile',
							params: { uid: person.account_uid },
							query: { from: 'space-pulse', space: spaceUid, intent: person.intent || 'open' },
						}"
						:aria-label="`Открыть образ ${person.display_name || person.handle || 'участника'}`"
					>
						<span class="pulse-avatar">
							<img v-if="person.avatar" :src="resolveAvatar(person.avatar)" alt="" />
							<span v-else>{{ avatarFallback(person.display_name || person.handle) }}</span>
						</span>
						<span class="pulse-person-copy">
							<strong>{{ person.display_name || person.handle || 'Участник' }}</strong>
							<small>{{ person.note || intentLabel(person.intent) }}</small>
						</span>
						<i class="fas fa-chevron-right pulse-person-arrow" aria-hidden="true"></i>
					</RouterLink>
				</div>
			</div>

			<div class="pulse-lower">
				<div class="pulse-history">
					<div class="pulse-section-title"><strong>Недавно</strong></div>
					<ul v-if="pulse.recent_history?.length">
						<li v-for="item in pulse.recent_history" :key="item.uid">
							<span>{{ item.summary }}</span>
							<time :datetime="item.created_at">{{ relativeTime(item.created_at) }}</time>
						</li>
					</ul>
					<p v-else>История пространства пока только начинается.</p>
				</div>
				<RouterLink class="pulse-chat-link" :to="{ name: 'space', params: { uid: spaceUid }, query: { from: 'pulse' } }">
					<i class="fas fa-arrow-right" aria-hidden="true"></i>
					<span>Войти в разговор</span>
				</RouterLink>
			</div>
		</template>
	</section>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue';
import { RouterLink } from 'vue-router';

import SpacesService from '@/API/SpacesService';

const props = defineProps({
	spaceUid: { type: String, required: true },
});

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/$/, '');
const pulse = ref(null);
const loading = ref(false);
const error = ref(false);

const livePeople = computed(() => pulse.value?.available_now?.people || []);
const liveCount = computed(() => Number(pulse.value?.available_now?.count || 0));
const conversationLabel = computed(() => ({
	lively: 'Очень живо',
	active: 'Идёт разговор',
	warming: 'Разговор начинается',
	quiet: 'Сейчас тихо',
}[pulse.value?.conversation?.state] || 'Сейчас тихо'));
const conversationDetail = computed(() => {
	const conversation = pulse.value?.conversation;
	if (!conversation?.message_count) return 'Можно начать новую тему';
	const authors = conversation.contributor_count || 0;
	return `${authors} ${pluralize(authors, ['участник', 'участника', 'участников'])} за последние ${conversation.window_minutes} мин.`;
});
const nextMomentIcon = computed(() => pulse.value?.next_moment?.kind === 'event' ? 'fas fa-calendar-day' : 'fas fa-bolt');
const nextMomentLabel = computed(() => {
	const item = pulse.value?.next_moment;
	if (!item?.starts_at) return 'Создайте повод встретиться';
	return new Intl.DateTimeFormat('ru', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }).format(new Date(item.starts_at));
});
const nextMomentTarget = computed(() => {
	const item = pulse.value?.next_moment;
	if (!item) return { name: 'space-life', params: { uid: props.spaceUid } };
	if (item.kind === 'event') {
		return {
			name: 'space-community',
			params: { uid: props.spaceUid },
			query: { tab: 'events', focus: item.uid, from: 'pulse' },
		};
	}
	return {
		name: 'space-life',
		params: { uid: props.spaceUid },
		query: { tab: 'activities', focus: item.uid, from: 'pulse' },
	};
});

const load = async () => {
	if (!props.spaceUid || loading.value) return;
	loading.value = true;
	error.value = false;
	try {
		const response = await SpacesService.pulse(props.spaceUid);
		pulse.value = response.data.pulse;
	} catch (requestError) {
		console.error('Не удалось загрузить пульс пространства:', requestError);
		error.value = true;
	} finally {
		loading.value = false;
	}
};

const resolveAvatar = (avatar) => /^https?:\/\//.test(avatar) ? avatar : `${apiBaseUrl}${avatar}`;
const avatarFallback = (value = '?') => String(value || '?').slice(0, 1).toUpperCase();
const intentLabel = (value) => ({ open: 'Хочет пообщаться', meet: 'Открыт знакомствам', games: 'Ищет компанию для игры' }[value] || 'Открыт к общению');
const pluralize = (value, forms) => {
	const n = Math.abs(Number(value)) % 100;
	const n1 = n % 10;
	if (n > 10 && n < 20) return forms[2];
	if (n1 > 1 && n1 < 5) return forms[1];
	if (n1 === 1) return forms[0];
	return forms[2];
};
const relativeTime = (value) => {
	const diffMinutes = Math.max(0, Math.round((Date.now() - new Date(value).getTime()) / 60000));
	if (diffMinutes < 1) return 'только что';
	if (diffMinutes < 60) return `${diffMinutes} мин. назад`;
	const hours = Math.floor(diffMinutes / 60);
	if (hours < 24) return `${hours} ч. назад`;
	return new Intl.DateTimeFormat('ru', { day: 'numeric', month: 'short' }).format(new Date(value));
};

watch(() => props.spaceUid, load);
onMounted(load);
</script>

<style scoped>
.pulse-card{display:grid;gap:var(--ui-space-4);margin-bottom:var(--ui-space-5);padding:clamp(1rem,2.5vw,1.5rem);border:1px solid var(--ui-border);border-radius:var(--ui-radius-xl);background:linear-gradient(145deg,var(--ui-surface),color-mix(in srgb,var(--ui-primary-soft) 35%,var(--ui-surface)));box-shadow:var(--ui-shadow-sm)}
.pulse-head{display:flex;align-items:center;justify-content:space-between;gap:var(--ui-space-3)}.pulse-head>div{display:grid;gap:.15rem}.pulse-eyebrow{color:var(--ui-primary);font-size:var(--ui-text-xs);font-weight:800;letter-spacing:.06em;text-transform:uppercase}.pulse-head strong{font-size:var(--ui-text-lg)}.pulse-refresh{width:2.45rem;height:2.45rem;display:grid;place-items:center;border:1px solid var(--ui-border);border-radius:50%;background:var(--ui-surface);color:var(--ui-text-muted);cursor:pointer}.pulse-refresh:disabled{opacity:.6;cursor:default}
.pulse-state{padding:var(--ui-space-5);text-align:center;color:var(--ui-text-muted)}.pulse-state--error{color:var(--ui-danger)}
.pulse-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:var(--ui-space-3)}.pulse-stat{min-width:0;display:flex;align-items:center;gap:var(--ui-space-3);padding:var(--ui-space-4);border:1px solid var(--ui-border);border-radius:var(--ui-radius-lg);background:var(--ui-surface)}.pulse-stat>i:first-child{width:2.4rem;height:2.4rem;display:grid;place-items:center;flex:0 0 auto;border-radius:.8rem;background:var(--ui-primary-soft);color:var(--ui-primary)}.pulse-stat>div{min-width:0;display:grid;gap:.15rem;flex:1}.pulse-stat span,.pulse-stat small{color:var(--ui-text-subtle);font-size:var(--ui-text-xs)}.pulse-stat strong{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.pulse-stat--conversation>i:first-child{background:var(--ui-success-soft);color:var(--ui-success)}.pulse-stat--next>i:first-child{background:var(--ui-info-soft);color:var(--ui-info)}.pulse-stat--link{color:inherit;text-decoration:none;transition:transform .16s ease,border-color .16s ease,box-shadow .16s ease}.pulse-stat--link:hover,.pulse-stat--link:focus-visible{transform:translateY(-1px);border-color:color-mix(in srgb,var(--ui-primary) 36%,var(--ui-border));box-shadow:var(--ui-shadow-sm);outline:none}.pulse-entry-icon{flex:0 0 auto;color:var(--ui-text-subtle);font-size:.8rem}
.pulse-live{display:grid;gap:var(--ui-space-3)}.pulse-section-title{display:flex;align-items:center;gap:.5rem;color:var(--ui-text)}.live-dot{width:.55rem;height:.55rem;border-radius:50%;background:var(--ui-success);box-shadow:0 0 0 .22rem color-mix(in srgb,var(--ui-success) 15%,transparent)}.pulse-people{display:flex;gap:var(--ui-space-2);overflow-x:auto;padding-bottom:.2rem;scrollbar-width:none}.pulse-person{min-width:12.5rem;max-width:16rem;display:flex;align-items:center;gap:.65rem;padding:.65rem .75rem;border:1px solid var(--ui-border);border-radius:var(--ui-radius-lg);background:var(--ui-surface);color:var(--ui-text);text-decoration:none;transition:border-color .16s ease,transform .16s ease}.pulse-person:hover,.pulse-person:focus-visible{transform:translateY(-1px);border-color:color-mix(in srgb,var(--ui-primary) 36%,var(--ui-border));outline:none}.pulse-avatar{width:2.25rem;height:2.25rem;display:grid;place-items:center;flex:0 0 auto;overflow:hidden;border-radius:50%;background:var(--ui-primary-soft);color:var(--ui-primary);font-weight:800}.pulse-avatar img{width:100%;height:100%;object-fit:cover}.pulse-person-copy{min-width:0;display:grid;flex:1}.pulse-person-copy strong,.pulse-person-copy small{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.pulse-person-copy small{color:var(--ui-text-muted);font-size:var(--ui-text-xs)}.pulse-person-arrow{flex:0 0 auto;color:var(--ui-text-subtle);font-size:.7rem}
.pulse-lower{display:grid;grid-template-columns:minmax(0,1fr) auto;align-items:end;gap:var(--ui-space-4)}.pulse-history{min-width:0;display:grid;gap:var(--ui-space-2)}.pulse-history ul{display:grid;gap:.35rem;margin:0;padding:0;list-style:none}.pulse-history li{display:flex;align-items:baseline;justify-content:space-between;gap:var(--ui-space-3);color:var(--ui-text-muted);font-size:var(--ui-text-sm)}.pulse-history li span{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.pulse-history time{flex:0 0 auto;color:var(--ui-text-subtle);font-size:var(--ui-text-xs)}.pulse-history p{margin:0;color:var(--ui-text-subtle);font-size:var(--ui-text-sm)}.pulse-chat-link{display:inline-flex;align-items:center;gap:.55rem;min-height:2.7rem;padding:0 var(--ui-space-4);border-radius:var(--ui-radius-pill);background:var(--ui-primary);color:var(--ui-on-primary);text-decoration:none;font-weight:800}
@media(max-width:820px){.pulse-card{gap:var(--ui-space-3);margin-bottom:var(--ui-space-3);padding:.85rem;border-radius:var(--ui-radius-lg)}.pulse-grid{grid-template-columns:1fr}.pulse-stat{padding:.75rem}.pulse-stat--link:hover{transform:none}.pulse-lower{grid-template-columns:1fr}.pulse-chat-link{justify-content:center}.pulse-history li{align-items:flex-start;flex-direction:column;gap:.1rem}.pulse-person{min-width:11.5rem}.pulse-head strong{font-size:var(--ui-text-md)}}
@media(prefers-reduced-motion:reduce){.pulse-stat--link,.pulse-person{transition:none}.pulse-stat--link:hover,.pulse-person:hover{transform:none}}
</style>
