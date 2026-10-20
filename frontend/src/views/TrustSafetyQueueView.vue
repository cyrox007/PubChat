<template>
	<main class="ts-shell">
		<header class="ts-hero">
			<div>
				<span class="eyebrow">Trust & Safety</span>
				<h1>Очередь жалоб платформы</h1>
				<p>Platform-level разбор отделён от модерации конкретного пространства. Evidence открывается только после claim и каждое открытие аудируется.</p>
			</div>
			<div class="hero-note"><i class="fas fa-shield-halved"></i><span>Смотрите только тот материал, который был пожалован. Эта очередь не даёт произвольного доступа к личной переписке.</span></div>
		</header>

		<ModerationLexiconPanel />

		<section class="filters" aria-label="Фильтры очереди">
			<label>Статус<select v-model="filters.status" @change="loadQueue"><option value="">Активные</option><option value="triage">Новые</option><option value="in_review">В работе</option><option value="escalated">Эскалация</option></select></label>
			<label>Приоритет<select v-model="filters.priority" @change="loadQueue"><option value="">Любой</option><option value="high">Высокий</option><option value="normal">Обычный</option><option value="low">Низкий</option></select></label>
			<label>Назначение<select v-model="filters.assigned" @change="loadQueue"><option value="any">Все</option><option value="unassigned">Свободные</option><option value="mine">Мои</option></select></label>
			<button class="ui-button ui-button--ghost" type="button" :disabled="loading" @click="refreshAll"><i class="fas fa-rotate"></i> Обновить</button>
		</section>

		<section v-if="notice" class="notice" :class="`notice--${notice.type}`" role="status">{{ notice.message }}</section>

		<section class="appeal-review operations-panel">
			<header class="section-head">
				<div><span class="eyebrow">Operations</span><h2>Состояние Trust & Safety</h2></div>
				<span>Агрегаты за {{ operationsMetrics?.window_hours || 168 }} ч. без Account ID и содержимого жалоб</span>
			</header>
			<div v-if="metricsLoading" class="state state--compact">Считаем метрики…</div>
			<div v-else-if="operationsMetrics" class="metric-grid">
				<div class="metric-card"><strong>{{ operationsMetrics.queue.open_count }}</strong><span>активных жалоб</span><small>старейшая: {{ durationLabel(operationsMetrics.queue.oldest_age_seconds) }}</small></div>
				<div class="metric-card"><strong>{{ durationLabel(operationsMetrics.queue.average_decision_seconds) }}</strong><span>среднее время решения</span><small>{{ operationsMetrics.queue.resolved_count }} решений в окне</small></div>
				<div class="metric-card"><strong>{{ operationsMetrics.appeals.overturn_rate_percent }}%</strong><span>overturn rate</span><small>апелляции, завершённые в окне</small></div>
				<div class="metric-card"><strong>{{ operationsMetrics.restrictions.active_automation_holds }}</strong><span>активных auto-hold</span><small>режим {{ automationModeLabel(operationsMetrics.automation.mode) }} · {{ operationsMetrics.automation.hold_minutes }} мин. · ≥{{ operationsMetrics.automation.min_high_signals }} high signals</small></div>
				<div class="metric-card"><strong>{{ operationsMetrics.automation.calibration.data_ready ? 'готово' : 'сбор данных' }}</strong><span>калибровка protective holds</span><small>{{ calibrationSummaryLabel(operationsMetrics.automation.calibration) }}</small></div>
				<div class="metric-card"><strong>{{ operationsMetrics.ai.outcome_counts.accepted || 0 }} / {{ operationsMetrics.ai.outcome_counts.modified || 0 }} / {{ operationsMetrics.ai.outcome_counts.rejected || 0 }}</strong><span>AI: принято / изменено / отклонено</span><small>AI остаётся advisory-only</small></div>
				<div class="metric-card"><strong>{{ operationsMetrics.abuse_signals.open_count }}</strong><span>открытых abuse signals</span><small>{{ operationsMetrics.abuse_signals.status_counts.dismissed || 0 }} dismissed в окне</small></div>
				<div class="metric-card"><strong>{{ operationsMetrics.media_retention.due_count }}</strong><span>evidence ждёт expiry</span><small>{{ operationsMetrics.media_retention.purged_count }} очищено · app policy {{ operationsMetrics.media_retention.removed_retention_days }} дн.</small></div>
				<div class="metric-card"><strong>{{ operationsMetrics.media_retention.storage_lifecycle.aligned ? 'согласовано' : 'не подтверждено' }}</strong><span>backup / snapshot retention</span><small>{{ storageLifecycleLabel(operationsMetrics.media_retention.storage_lifecycle) }}</small></div>
			</div>
		</section>

		<section class="appeal-review">
			<header class="section-head">
				<div><span class="eyebrow">Abuse signals</span><h2>Поведенческие сигналы</h2></div>
				<span>{{ abuseSignals.length }} открытых · human labels калибруют shadow policy; shadow не ограничивает пользователей</span>
			</header>
			<div v-if="signalsLoading" class="state state--compact">Загружаем сигналы…</div>
			<div v-else-if="!abuseSignals.length" class="state state--compact"><strong>Открытых сигналов нет</strong><span>Rate-limit и burst-detectors появятся здесь только после достижения порогов.</span></div>
			<div v-else class="restriction-history">
				<article v-for="signal in abuseSignals" :key="signal.uid" class="restriction-row">
					<div>
						<strong>{{ abuseSignalLabel(signal.signal_type) }} · {{ abuseSeverityLabel(signal.severity) }}</strong>
						<span>{{ abuseSurfaceLabel(signal.surface) }} · {{ signal.observed_count }} событий/получателей за {{ abuseWindowLabel(signal.window_seconds) }}</span>
						<small>Account {{ signal.account_uid }} · {{ formatDate(signal.last_seen_at) }}</small>
					</div>
					<div class="review-actions">
						<button class="ui-button ui-button--ghost" type="button" :disabled="busy" @click="reviewSignal(signal, 'reviewed', 'true_positive')">Подтвердить спам</button>
						<button class="ui-button ui-button--ghost" type="button" :disabled="busy" @click="reviewSignal(signal, 'dismissed', 'false_positive')">Ложное срабатывание</button>
						<button class="ui-button ui-button--ghost" type="button" :disabled="busy" @click="reviewSignal(signal, 'reviewed', 'unclear')">Неясно</button>
					</div>
				</article>
			</div>
		</section>

		<section class="appeal-review">
			<header class="section-head">
				<div><span class="eyebrow">Appeals</span><h2>Апелляции на platform-ограничения</h2></div>
				<span>{{ restrictionAppeals.length }} ожидают решения</span>
			</header>
			<div class="appeal-workspace">
				<div class="appeal-list">
					<div v-if="appealsLoading" class="state state--compact">Загружаем апелляции…</div>
					<div v-else-if="!restrictionAppeals.length" class="state state--compact"><strong>Нет ожидающих апелляций</strong><span>Новые обращения появятся здесь.</span></div>
					<button v-for="appeal in restrictionAppeals" :key="appeal.uid" type="button" class="appeal-card" :class="{ active: selectedAppeal?.uid === appeal.uid }" @click="selectAppeal(appeal)">
						<strong>{{ capabilityLabel(appeal.restriction?.capability) }}</strong>
						<span>{{ appeal.reviewer_account_uid ? 'В работе' : 'Свободна' }} · {{ formatDate(appeal.created_at) }}</span>
					</button>
				</div>
				<div class="appeal-detail">
					<div v-if="!selectedAppeal" class="state state--compact"><i class="fas fa-scale-balanced"></i><strong>Выберите апелляцию</strong></div>
					<template v-else>
						<div class="appeal-detail-head"><div><strong>{{ capabilityLabel(selectedAppeal.restriction?.capability) }}</strong><span>{{ selectedAppeal.restriction?.public_explanation }}</span></div><span class="status-pill">{{ selectedAppeal.reviewer_account_uid ? 'В работе' : 'Ожидает claim' }}</span></div>
						<p class="appeal-body">{{ selectedAppeal.body }}</p>
						<small>Ограничение: {{ selectedAppeal.restriction?.scope_type === 'space' ? 'пространство' : 'вся платформа' }} · {{ selectedAppeal.restriction?.expires_at ? `до ${formatDate(selectedAppeal.restriction.expires_at)}` : 'без срока' }}</small>
						<div class="review-actions">
							<button v-if="!selectedAppeal.reviewer_account_uid" class="ui-button" type="button" :disabled="busy" @click="claimRestrictionAppeal">Взять апелляцию</button>
							<button v-else-if="ownsSelectedAppeal" class="ui-button ui-button--ghost" type="button" :disabled="busy" @click="releaseRestrictionAppeal">Освободить</button>
						</div>
						<form v-if="ownsSelectedAppeal" class="appeal-decision" @submit.prevent="resolveRestrictionAppeal">
							<label>Решение<select v-model="appealDecision.decision"><option value="uphold">Оставить ограничение</option><option value="overturn">Отменить ограничение</option></select></label>
							<label>Обоснование<textarea v-model.trim="appealDecision.resolution" maxlength="4000" rows="3" required placeholder="Объясните результат независимого пересмотра. Это увидит пользователь."></textarea></label>
							<button class="ui-button" type="submit" :disabled="busy || appealDecision.resolution.length < 3">Завершить пересмотр</button>
						</form>
					</template>
				</div>
			</div>
		</section>

		<div class="workspace">
			<section class="queue-panel">
				<div v-if="loading" class="state">Загружаем очередь…</div>
				<div v-else-if="!reports.length" class="state"><strong>Очередь пуста</strong><span>По выбранным фильтрам активных жалоб нет.</span></div>
				<button v-for="report in reports" :key="report.uid" type="button" class="report-card" :class="{ active: selected?.uid === report.uid }" @click="selectReport(report)">
					<span class="priority" :class="`priority--${report.priority}`">{{ priorityLabel(report.priority) }}</span>
					<span class="report-copy"><strong>{{ categoryLabel(report.category) }}</strong><span>{{ sourceLabel(report.source_type) }} · {{ report.target?.display_name || report.target?.handle || 'Account' }}</span><small>{{ statusLabel(report.status) }} · {{ formatDate(report.created_at) }}</small></span>
					<i class="fas fa-chevron-right"></i>
				</button>
			</section>

			<section class="review-panel">
				<div v-if="!selected" class="state state--review"><i class="fas fa-shield"></i><strong>Выберите жалобу</strong><span>Evidence не загружается до того, как вы возьмёте жалобу в работу.</span></div>
				<template v-else>
					<header class="review-head">
						<div><span class="eyebrow">{{ sourceLabel(selected.source_type) }}</span><h2>{{ categoryLabel(selected.category) }}</h2><p>{{ selected.description || 'Без комментария пользователя.' }}</p></div>
						<span class="status-pill">{{ statusLabel(selected.status) }}</span>
					</header>

					<div class="review-actions">
						<button v-if="!selected.assigned_to_account_uid" class="ui-button" type="button" :disabled="busy" @click="claim">Взять в работу</button>
						<button v-else-if="ownsSelected && selected.status === 'in_review'" class="ui-button ui-button--ghost" type="button" :disabled="busy" @click="release">Освободить</button>
						<button v-if="ownsSelected" class="ui-button ui-button--ghost" type="button" :disabled="busy" @click="loadEvidence">Показать evidence</button>
					</div>

					<section v-if="evidence" class="evidence">
						<header><strong>Пожалованный объект</strong><span>{{ evidence.available ? 'Доступен' : 'Больше недоступен' }}</span></header>
						<template v-if="evidence.persona"><strong>{{ evidence.persona.display_name || evidence.persona.handle }}</strong><p>@{{ evidence.persona.handle }}</p><p>{{ evidence.persona.bio || 'Описание отсутствует.' }}</p></template>
						<template v-else-if="evidence.message">
							<div class="message-evidence"><small>{{ formatDate(evidence.message.created_at) }}</small><p>{{ evidence.message.content || `[${evidence.message.content_type}]` }}</p></div>
							<div v-if="evidenceMediaFiles.length" class="media-review">
								<div class="media-review__head"><strong>Вложения жалобы</strong><span>Quarantine скрывает файл из публичного /uploads, но сохраняет evidence copy.</span></div>
								<article v-for="(file, index) in evidenceMediaFiles" :key="`${index}-${file.url || file.name || 'attachment'}`" class="media-review__item">
									<div><strong>{{ file.name || `Вложение ${index + 1}` }}</strong><span>{{ file.type || 'unknown type' }} · {{ mediaStatusLabel(mediaRecordFor(index)?.status || file.moderation_status) }}</span><small v-if="mediaRecordFor(index)?.purged_at">Private evidence expired {{ formatDate(mediaRecordFor(index).purged_at) }}</small><small v-else-if="mediaRecordFor(index)?.retention_due_at">Retention due {{ formatDate(mediaRecordFor(index).retention_due_at) }}; active review/appeal can defer cleanup.</small></div>
									<div v-if="ownsSelected" class="review-actions">
										<button v-if="!mediaRecordFor(index) || mediaRecordFor(index)?.status === 'restored'" class="ui-button ui-button--ghost" type="button" :disabled="mediaBusy || mediaReason.trim().length < 3" @click="quarantineMedia(index)">Карантин</button>
										<button v-if="mediaRecordFor(index)?.status === 'quarantined'" class="ui-button ui-button--ghost" type="button" :disabled="mediaBusy" @click="restoreMedia(mediaRecordFor(index))">Восстановить</button>
										<button v-if="mediaRecordFor(index)?.status === 'quarantined'" class="ui-button ui-button--ghost" type="button" :disabled="mediaBusy || mediaReason.trim().length < 3" @click="removeMedia(mediaRecordFor(index))">Удалить из выдачи</button>
									</div>
								</article>
								<label v-if="ownsSelected">Причина действия<textarea v-model.trim="mediaReason" maxlength="1000" rows="2" placeholder="Почему вложение нужно скрыть или удалить"></textarea></label>
							</div>
							<small>{{ evidence.context_policy === 'reported_message_only' ? 'Показано только пожалованное сообщение, без истории диалога.' : '' }}</small>
						</template>
					</section>

					<section v-if="ownsSelected && aiVisible" class="ai-panel">
						<header class="section-head">
							<div><span class="eyebrow">AI copilot</span><h3>Помощник модератора</h3></div>
							<span>Рекомендация справочная. AI не может применить санкцию, снять её или решить апелляцию.</span>
						</header>
						<div class="action-note">
							<span v-if="aiConfig.enabled">Провайдер получает только пожалованный объект без Account ID, handle и истории диалога.</span>
							<span v-else>AI-провайдер сейчас отключён в конфигурации среды.</span>
							<button v-if="aiConfig.enabled" class="ui-button ui-button--ghost" type="button" :disabled="aiBusy || busy" @click="requestAIAssessment">
								{{ aiBusy ? 'Анализируем…' : 'Запросить AI-анализ' }}
							</button>
						</div>
						<div v-if="aiAssessments.length" class="restriction-history">
							<article v-for="item in aiAssessments" :key="item.uid" class="restriction-row">
								<div>
									<strong>{{ aiSeverityLabel(item.severity) }} · уверенность {{ item.confidence_percent }}%</strong>
									<span>{{ categoryLabel(item.category) }} · {{ aiActionLabel(item.recommended_action) }}</span>
									<small>{{ item.summary }}</small>
									<small v-if="item.suggested_capability">Предложение: {{ capabilityLabel(item.suggested_capability) }} · {{ aiDurationLabel(item.suggested_duration_minutes) }}</small>
									<small>Почему: {{ item.rationale }}</small>
									<small>Результат модератора: {{ aiOutcomeLabel(item.outcome) }}</small>
								</div>
								<div v-if="item.outcome === 'not_used'" class="review-actions">
									<button v-if="item.recommended_action === 'temporary_restriction'" class="ui-button ui-button--ghost" type="button" :disabled="aiBusy || busy" @click="useAISuggestion(item, 'accepted')">Принять как черновик</button>
									<button v-if="item.recommended_action === 'temporary_restriction'" class="ui-button ui-button--ghost" type="button" :disabled="aiBusy || busy" @click="useAISuggestion(item, 'modified')">Взять за основу</button>
									<button class="ui-button ui-button--ghost" type="button" :disabled="aiBusy || busy" @click="recordAIOutcome(item, 'rejected')">Отклонить</button>
								</div>
							</article>
						</div>
					</section>

					<section v-if="ownsSelected && selected.target?.account_uid" class="restriction-panel">
						<header class="section-head">
							<div><span class="eyebrow">Platform action</span><h3>Ограничить конкретную возможность</h3></div>
							<span>Иерархия и полномочия проверяются сервером.</span>
						</header>

						<form class="restriction-form" @submit.prevent="createRestriction">
							<div class="restriction-grid">
								<label>Возможность
									<select v-model="restriction.capability" required>
										<option v-for="capability in restrictionCapabilities" :key="capability" :value="capability">{{ capabilityLabel(capability) }}</option>
									</select>
								</label>
								<label>Область
									<select v-model="restriction.scope_type">
										<option value="platform">Вся платформа</option>
										<option v-if="selected.source_space_uid" value="space">Только это пространство</option>
									</select>
								</label>
								<label>Срок
									<select v-model="restriction.duration">
										<option value="60">1 час</option>
										<option value="1440">24 часа</option>
										<option value="10080">7 дней</option>
										<option value="43200">30 дней</option>
										<option value="permanent">Без срока · повышенные права</option>
									</select>
								</label>
								<label>Reason code<input v-model.trim="restriction.reason_code" maxlength="48" required pattern="[a-z0-9_.-]+" placeholder="dm_abuse"></label>
							</div>
							<label>Пояснение пользователю<textarea v-model.trim="restriction.public_explanation" maxlength="1000" rows="3" required placeholder="Какая возможность ограничена и почему. Это увидит пользователь."></textarea></label>
							<div class="action-note"><span>Выдаются только ограничения, которые уже реально проверяются backend. Бессрочная санкция потребует отдельного permission.</span><button class="ui-button" type="submit" :disabled="busy || !restrictionCapabilities.length || restriction.public_explanation.length < 3">Применить ограничение</button></div>
						</form>

						<div v-if="targetRestrictions.length" class="restriction-history">
							<h4>Ограничения Account</h4>
							<article v-for="item in targetRestrictions" :key="item.uid" class="restriction-row">
								<div><strong>{{ capabilityLabel(item.capability) }}</strong><span>{{ restrictionScopeLabel(item) }} · {{ restrictionStatusLabel(item.status) }}</span><small>{{ item.expires_at ? `до ${formatDate(item.expires_at)}` : 'без срока' }} · {{ item.public_explanation }}</small></div>
								<button v-if="item.status === 'active'" class="ui-button ui-button--ghost" type="button" :disabled="busy" @click="startRevoke(item.uid)">Снять</button>
							</article>
							<form v-if="revokeUid" class="revoke-form" @submit.prevent="revokeRestriction">
								<label>Причина снятия<textarea v-model.trim="revokeReason" maxlength="1000" rows="2" required placeholder="Почему ограничение снимается"></textarea></label>
								<div><button type="button" class="ui-button ui-button--ghost" @click="cancelRevoke">Отмена</button><button type="submit" class="ui-button" :disabled="busy || revokeReason.length < 3">Подтвердить снятие</button></div>
							</form>
						</div>
					</section>

					<form v-if="ownsSelected && ['in_review', 'escalated'].includes(selected.status)" class="decision" @submit.prevent="decide">
						<h3>Решение по triage</h3>
						<div class="decision-grid">
							<label>Статус<select v-model="decision.status"><option value="resolved">Решено</option><option value="dismissed">Закрыть без действия</option><option value="escalated">Требуется platform action</option></select></label>
							<label>Код<select v-model="decision.resolution_code"><option value="handled">Обработано</option><option value="no_violation">Нарушение не подтверждено</option><option value="insufficient_context">Недостаточно контекста</option><option value="duplicate">Дубликат</option><option value="needs_platform_action">Нужно действие платформы</option><option value="other">Другое</option></select></label>
						</div>
						<label>Пояснение пользователю<textarea v-model.trim="decision.public_explanation" maxlength="1000" rows="3" required placeholder="Кратко и понятно: что произошло с жалобой. Это увидит отправитель."></textarea></label>
						<button class="ui-button" type="submit" :disabled="busy || decision.public_explanation.length < 3">Сохранить решение</button>
					</form>

					<section v-if="audit.length" class="audit"><h3>Аудит</h3><div v-for="event in audit" :key="event.uid" class="audit-row"><span>{{ auditLabel(event.event_type) }}</span><small>{{ formatDate(event.created_at) }}</small></div></section>
				</template>
			</section>
		</div>
	</main>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue';
import { useStore } from 'vuex';

import ModerationService from '@/API/ModerationService';
import ModerationLexiconPanel from '@/components/AdminComponents/ModerationLexiconPanel.vue';

const store = useStore();
const reports = ref([]);
const selected = ref(null);
const evidence = ref(null);
const audit = ref([]);
const targetRestrictions = ref([]);
const restrictionCapabilities = ref([]);
const restrictionAppeals = ref([]);
const selectedAppeal = ref(null);
const appealsLoading = ref(true);
const abuseSignals = ref([]);
const signalsLoading = ref(true);
const operationsMetrics = ref(null);
const metricsLoading = ref(true);
const loading = ref(true);
const busy = ref(false);
const notice = ref(null);
const revokeUid = ref(null);
const revokeReason = ref('');
const aiConfig = reactive({ enabled: false, provider: 'disabled', schema_version: 'v1' });
const aiVisible = ref(false);
const aiAssessments = ref([]);
const aiBusy = ref(false);
const mediaRecords = ref([]);
const mediaBusy = ref(false);
const mediaReason = ref('Reported attachment requires moderator review.');
const filters = reactive({ status: '', priority: '', assigned: 'any' });
const decision = reactive({ status: 'resolved', resolution_code: 'handled', public_explanation: '' });
const restriction = reactive({ capability: '', scope_type: 'platform', duration: '1440', reason_code: '', public_explanation: '' });
const appealDecision = reactive({ decision: 'uphold', resolution: '' });

const currentAccountUid = computed(() => store.getters.getAccount?.uid || store.getters.getUser?.uid || null);
const ownsSelected = computed(() => Boolean(selected.value?.assigned_to_account_uid && selected.value.assigned_to_account_uid === currentAccountUid.value));
const ownsSelectedAppeal = computed(() => Boolean(selectedAppeal.value?.reviewer_account_uid && selectedAppeal.value.reviewer_account_uid === currentAccountUid.value));
const evidenceMediaFiles = computed(() => Array.isArray(evidence.value?.message?.media_metadata?.files) ? evidence.value.message.media_metadata.files : []);
const mediaRecordFor = (index) => mediaRecords.value.find((item) => item.attachment_index === index) || null;

const flash = (message, type = 'success') => {
	notice.value = { message, type };
	window.setTimeout(() => { if (notice.value?.message === message) notice.value = null; }, 3500);
};

const queueParams = () => Object.fromEntries(Object.entries(filters).filter(([, value]) => value));
const loadCapabilities = async () => {
	try {
		const response = await ModerationService.restrictionCapabilities();
		restrictionCapabilities.value = response.data.capabilities || [];
		if (!restrictionCapabilities.value.includes(restriction.capability)) restriction.capability = restrictionCapabilities.value[0] || '';
	} catch { restrictionCapabilities.value = []; }
};
const loadQueue = async () => {
	loading.value = true;
	try {
		const response = await ModerationService.trustSafetyQueue({ ...queueParams(), limit: 100 });
		reports.value = response.data.reports || [];
		if (selected.value) selected.value = reports.value.find((item) => item.uid === selected.value.uid) || null;
	} catch (error) {
		flash(error.response?.status === 403 ? 'Нет platform Trust & Safety permission.' : 'Не удалось загрузить очередь.', 'error');
	} finally { loading.value = false; }
};
const loadRestrictionAppeals = async () => {
	appealsLoading.value = true;
	try {
		const response = await ModerationService.restrictionAppeals({ status: 'pending', assigned: 'any', limit: 100 });
		restrictionAppeals.value = response.data.appeals || [];
		if (selectedAppeal.value) selectedAppeal.value = restrictionAppeals.value.find((item) => item.uid === selectedAppeal.value.uid) || null;
	} catch (error) {
		if (error.response?.status !== 403) flash('Не удалось загрузить очередь апелляций.', 'error');
		restrictionAppeals.value = [];
	} finally { appealsLoading.value = false; }
};
const loadAbuseSignals = async () => {
	signalsLoading.value = true;
	try {
		const response = await ModerationService.abuseSignals({ status: 'open', limit: 100 });
		abuseSignals.value = response.data.signals || [];
	} catch (error) {
		if (error.response?.status !== 403) flash('Не удалось загрузить поведенческие сигналы.', 'error');
		abuseSignals.value = [];
	} finally { signalsLoading.value = false; }
};
const reviewSignal = async (signal, decision, calibrationLabel) => {
	busy.value = true;
	try {
		await ModerationService.reviewAbuseSignal(signal.uid, { decision, calibration_label: calibrationLabel });
		await Promise.all([loadAbuseSignals(), loadMetrics()]);
		const messages = {
			true_positive: 'Сигнал подтверждён человеком как реальный abuse.',
			false_positive: 'Сигнал помечен как ложное срабатывание для калибровки.',
			unclear: 'Сигнал отмечен как неясный и не влияет на calibration gate.',
		};
		flash(messages[calibrationLabel] || 'Результат проверки сигнала сохранён.');
	} catch { flash('Не удалось обновить поведенческий сигнал.', 'error'); }
	finally { busy.value = false; }
};
const loadMetrics = async () => {
	metricsLoading.value = true;
	try {
		const response = await ModerationService.trustSafetyMetrics({ window_hours: 168 });
		operationsMetrics.value = response.data.metrics || null;
	} catch (error) {
		if (error.response?.status !== 403) flash('Не удалось загрузить агрегированные Trust & Safety метрики.', 'error');
		operationsMetrics.value = null;
	} finally { metricsLoading.value = false; }
};
const refreshAll = async () => { await Promise.all([loadQueue(), loadRestrictionAppeals(), loadAbuseSignals(), loadMetrics()]); };
const loadMediaRecords = async () => {
	mediaRecords.value = [];
	if (!selected.value || !ownsSelected.value || !evidence.value?.message) return;
	try {
		const response = await ModerationService.moderationMediaRecords(selected.value.uid);
		mediaRecords.value = response.data.media_records || [];
	} catch (error) {
		if (error.response?.status !== 403) flash('Не удалось загрузить состояние moderation media.', 'error');
	}
};
const setEvidenceMediaStatus = (index, value) => {
	const file = evidence.value?.message?.media_metadata?.files?.[index];
	if (!file) return;
	if (value) file.moderation_status = value;
	else delete file.moderation_status;
};
const quarantineMedia = async (index) => {
	if (!selected.value || mediaReason.value.trim().length < 3) return;
	mediaBusy.value = true;
	try {
		await ModerationService.quarantineModerationMedia(selected.value.uid, index, { reason: mediaReason.value.trim() });
		setEvidenceMediaStatus(index, 'quarantined');
		await Promise.all([loadMediaRecords(), loadAudit()]);
		flash('Вложение помещено в приватный quarantine storage.');
	} catch (error) {
		const type = error.response?.data?.detail?.error_type;
		const messages = { moderation_media_not_local_upload: 'Можно карантинить только локальные /uploads вложения.', moderation_media_file_missing: 'Исходный файл уже недоступен.', moderation_authority_insufficient: 'Недостаточно authority для действия над этим Account.' };
		flash(messages[type] || 'Не удалось поместить вложение в карантин.', 'error');
	} finally { mediaBusy.value = false; }
};
const restoreMedia = async (record) => {
	mediaBusy.value = true;
	try {
		await ModerationService.restoreModerationMedia(selected.value.uid, record.uid);
		setEvidenceMediaStatus(record.attachment_index, null);
		await Promise.all([loadMediaRecords(), loadAudit()]);
		flash('Вложение восстановлено в публичное хранилище.');
	} catch { flash('Не удалось восстановить вложение.', 'error'); }
	finally { mediaBusy.value = false; }
};
const removeMedia = async (record) => {
	if (mediaReason.value.trim().length < 3) return;
	mediaBusy.value = true;
	try {
		await ModerationService.removeModerationMedia(selected.value.uid, record.uid, { reason: mediaReason.value.trim() });
		setEvidenceMediaStatus(record.attachment_index, 'removed');
		await Promise.all([loadMediaRecords(), loadAudit()]);
		flash('Вложение удалено из публичной выдачи; evidence copy сохранена по retention policy.');
	} catch { flash('Не удалось удалить вложение из публичной выдачи.', 'error'); }
	finally { mediaBusy.value = false; }
};

const loadAIConfig = async () => {
	try {
		const response = await ModerationService.moderationAIConfig();
		Object.assign(aiConfig, response.data.ai || { enabled: false, provider: 'disabled', schema_version: 'v1' });
		aiVisible.value = true;
	} catch (error) {
		aiVisible.value = false;
		if (error.response?.status !== 403) flash('Не удалось получить конфигурацию AI-copilot.', 'error');
	}
};
const loadAIAssessments = async () => {
	aiAssessments.value = [];
	if (!selected.value || !ownsSelected.value || !aiVisible.value) return;
	try {
		const response = await ModerationService.moderationAIAssessments(selected.value.uid, { limit: 10 });
		aiAssessments.value = response.data.assessments || [];
	} catch (error) {
		if (error.response?.status !== 403) flash('Не удалось загрузить историю AI-рекомендаций.', 'error');
	}
};
const requestAIAssessment = async () => {
	if (!selected.value || !ownsSelected.value) return;
	aiBusy.value = true;
	try {
		await ModerationService.createModerationAIAssessment(selected.value.uid);
		await Promise.all([loadAIAssessments(), loadAudit()]);
		flash('AI-рекомендация готова. Решение остаётся за модератором.');
	} catch (error) {
		const type = error.response?.data?.detail?.error_type;
		const messages = {
			moderation_ai_not_configured: 'AI-провайдер не настроен.',
			moderation_ai_provider_unavailable: 'AI-провайдер временно недоступен.',
			moderation_ai_assessment_limit_reached: 'Для этой жалобы исчерпан лимит AI-анализов.',
			trust_safety_claim_required: 'Сначала возьмите жалобу в работу.',
		};
		flash(messages[type] || 'Не удалось выполнить AI-анализ.', 'error');
	} finally { aiBusy.value = false; }
};
const recordAIOutcome = async (item, outcome) => {
	aiBusy.value = true;
	try {
		await ModerationService.setModerationAIOutcome(selected.value.uid, item.uid, { outcome });
		await Promise.all([loadAIAssessments(), loadAudit()]);
		flash(outcome === 'rejected' ? 'AI-рекомендация отклонена.' : 'Результат AI-рекомендации сохранён.');
	} catch { flash('Не удалось сохранить результат AI-рекомендации.', 'error'); }
	finally { aiBusy.value = false; }
};
const useAISuggestion = async (item, outcome) => {
	if (!item.suggested_capability || !item.suggested_duration_minutes) return;
	if (!restrictionCapabilities.value.includes(item.suggested_capability)) {
		flash('Предложенную AI возможность нельзя применить с вашими текущими полномочиями.', 'error');
		return;
	}
	restriction.capability = item.suggested_capability;
	restriction.scope_type = item.suggested_scope_type === 'space' && selected.value?.source_space_uid ? 'space' : 'platform';
	restriction.duration = String(item.suggested_duration_minutes);
	restriction.reason_code = selected.value?.category ? `${selected.value.category}_abuse` : 'policy_violation';
	restriction.public_explanation = item.summary;
	await recordAIOutcome(item, outcome);
	flash(outcome === 'accepted' ? 'AI-предложение перенесено в черновик санкции. Проверьте его перед применением.' : 'AI-предложение взято за основу. Отредактируйте черновик перед применением.');
};
const resetRestrictionDraft = () => {
	restriction.capability = restrictionCapabilities.value[0] || '';
	restriction.scope_type = 'platform';
	restriction.duration = '1440';
	restriction.reason_code = selected.value?.category ? `${selected.value.category}_abuse` : '';
	restriction.public_explanation = '';
};
const loadTargetRestrictions = async () => {
	targetRestrictions.value = [];
	const targetUid = selected.value?.target?.account_uid;
	if (!targetUid || !ownsSelected.value) return;
	try {
		const response = await ModerationService.targetRestrictions(targetUid, { include_inactive: true, limit: 50 });
		targetRestrictions.value = response.data.restrictions || [];
	} catch { targetRestrictions.value = []; }
};
const selectReport = (report) => {
	selected.value = report;
	evidence.value = null;
	audit.value = [];
	targetRestrictions.value = [];
	aiAssessments.value = [];
	mediaRecords.value = [];
	decision.public_explanation = '';
	cancelRevoke();
	resetRestrictionDraft();
	if (report.assigned_to_account_uid === currentAccountUid.value) {
		loadAudit();
		loadTargetRestrictions();
		loadAIAssessments();
	}
};
const replaceSelected = (report) => { selected.value = report; const index = reports.value.findIndex((item) => item.uid === report.uid); if (index >= 0) reports.value[index] = report; };

const selectAppeal = (appeal) => {
	selectedAppeal.value = appeal;
	appealDecision.decision = 'uphold';
	appealDecision.resolution = '';
};
const replaceSelectedAppeal = (appeal) => {
	selectedAppeal.value = appeal;
	const index = restrictionAppeals.value.findIndex((item) => item.uid === appeal.uid);
	if (index >= 0) restrictionAppeals.value[index] = appeal;
};
const claimRestrictionAppeal = async () => {
	if (!selectedAppeal.value) return;
	busy.value = true;
	try {
		const response = await ModerationService.claimRestrictionAppeal(selectedAppeal.value.uid);
		replaceSelectedAppeal(response.data.appeal);
		flash('Апелляция закреплена за вами для независимого пересмотра.');
	} catch (error) {
		const type = error.response?.data?.detail?.error_type;
		const messages = {
			independent_appeal_reviewer_required: 'Эту апелляцию должен проверить другой доступный модератор.',
			appeal_reviewer_authority_insufficient: 'Ваш уровень полномочий ниже уровня, требуемого для пересмотра этой санкции.',
			platform_restriction_appeal_already_claimed: 'Апелляцию уже взял другой модератор.',
		};
		flash(messages[type] || 'Не удалось взять апелляцию.', 'error');
		await loadRestrictionAppeals();
	} finally { busy.value = false; }
};
const releaseRestrictionAppeal = async () => {
	if (!selectedAppeal.value) return;
	busy.value = true;
	try {
		const response = await ModerationService.releaseRestrictionAppeal(selectedAppeal.value.uid);
		replaceSelectedAppeal(response.data.appeal);
		flash('Апелляция возвращена в общую очередь.');
	} catch { flash('Не удалось освободить апелляцию.', 'error'); }
	finally { busy.value = false; }
};
const resolveRestrictionAppeal = async () => {
	if (!selectedAppeal.value) return;
	busy.value = true;
	try {
		await ModerationService.resolveRestrictionAppeal(selectedAppeal.value.uid, { ...appealDecision });
		const overturned = appealDecision.decision === 'overturn';
		selectedAppeal.value = null;
		appealDecision.resolution = '';
		await Promise.all([loadRestrictionAppeals(), loadTargetRestrictions()]);
		flash(overturned ? 'Апелляция удовлетворена, активное ограничение снято.' : 'Апелляция рассмотрена, ограничение оставлено.');
	} catch (error) {
		const type = error.response?.data?.detail?.error_type;
		flash(type === 'platform_restriction_appeal_claim_required' ? 'Сначала возьмите апелляцию в работу.' : 'Не удалось завершить пересмотр.', 'error');
	} finally { busy.value = false; }
};

const claim = async () => {
	busy.value = true;
	try { const response = await ModerationService.claimTrustSafetyReport(selected.value.uid); replaceSelected(response.data.report); await Promise.all([loadAudit(), loadTargetRestrictions(), loadAIAssessments()]); flash('Жалоба закреплена за вами.'); }
	catch (error) { flash(error.response?.data?.detail?.error_type === 'trust_safety_report_already_claimed' ? 'Жалобу уже взял другой модератор.' : 'Не удалось взять жалобу.', 'error'); await loadQueue(); }
	finally { busy.value = false; }
};
const release = async () => {
	busy.value = true;
	try { const response = await ModerationService.releaseTrustSafetyReport(selected.value.uid); replaceSelected(response.data.report); evidence.value = null; audit.value = []; targetRestrictions.value = []; aiAssessments.value = []; mediaRecords.value = []; flash('Жалоба возвращена в общую очередь.'); }
	catch { flash('Не удалось освободить жалобу.', 'error'); }
	finally { busy.value = false; }
};
const loadEvidence = async () => {
	busy.value = true;
	try { const response = await ModerationService.trustSafetyEvidence(selected.value.uid); evidence.value = response.data.evidence; await Promise.all([loadAudit(), loadMediaRecords()]); }
	catch { flash('Evidence доступен только владельцу claim.', 'error'); }
	finally { busy.value = false; }
};
const loadAudit = async () => {
	if (!selected.value) return;
	try { const response = await ModerationService.trustSafetyAudit(selected.value.uid); audit.value = response.data.events || []; } catch { audit.value = []; }
};
const createRestriction = async () => {
	if (!selected.value?.target?.account_uid) return;
	busy.value = true;
	try {
		const payload = {
			target_account_uid: selected.value.target.account_uid,
			capability: restriction.capability,
			scope_type: restriction.scope_type,
			scope_uid: restriction.scope_type === 'space' ? selected.value.source_space_uid : null,
			reason_code: restriction.reason_code,
			public_explanation: restriction.public_explanation,
			duration_minutes: restriction.duration === 'permanent' ? null : Number(restriction.duration),
			report_uid: selected.value.uid,
		};
		await ModerationService.createRestriction(payload);
		resetRestrictionDraft();
		await Promise.all([loadTargetRestrictions(), loadAudit()]);
		flash('Ограничение применено. Жалоба остаётся открытой до явного решения.');
	} catch (error) {
		const type = error.response?.data?.detail?.error_type;
		const messages = {
			moderation_authority_insufficient: 'Нельзя ограничить Account с равным или более высоким уровнем полномочий.',
			permanent_restriction_permission_required: 'Для бессрочного ограничения нужны повышенные права.',
			account_access_permission_required: 'Для полного ограничения Account нужны повышенные права.',
			trust_safety_claim_required: 'Сначала возьмите жалобу в работу.',
			moderation_capability_not_enforced_yet: 'Эта санкция ещё не имеет полного server-side enforcement.',
		};
		flash(messages[type] || 'Не удалось применить ограничение.', 'error');
	} finally { busy.value = false; }
};
const startRevoke = (uid) => { revokeUid.value = uid; revokeReason.value = ''; };
const cancelRevoke = () => { revokeUid.value = null; revokeReason.value = ''; };
const revokeRestriction = async () => {
	if (!revokeUid.value) return;
	busy.value = true;
	try {
		await ModerationService.revokeRestriction(revokeUid.value, revokeReason.value);
		cancelRevoke();
		await loadTargetRestrictions();
		flash('Ограничение снято; история решения сохранена.');
	} catch (error) {
		const type = error.response?.data?.detail?.error_type;
		flash(type === 'moderation_authority_insufficient' ? 'Недостаточный уровень полномочий для снятия этой санкции.' : 'Не удалось снять ограничение.', 'error');
	} finally { busy.value = false; }
};
const decide = async () => {
	busy.value = true;
	try { const response = await ModerationService.decideTrustSafetyReport(selected.value.uid, { ...decision }); replaceSelected(response.data.report); await loadAudit(); flash(decision.status === 'escalated' ? 'Жалоба эскалирована.' : 'Решение сохранено.'); await loadQueue(); }
	catch (error) { const type = error.response?.data?.detail?.error_type; flash(type === 'trust_safety_claim_required' ? 'Claim больше не принадлежит вам.' : 'Не удалось сохранить решение.', 'error'); }
	finally { busy.value = false; }
};

watch(() => decision.status, (value) => { if (value === 'escalated') decision.resolution_code = 'needs_platform_action'; else if (decision.resolution_code === 'needs_platform_action') decision.resolution_code = value === 'dismissed' ? 'no_violation' : 'handled'; });
watch(() => selected.value?.source_space_uid, (value) => { if (!value && restriction.scope_type === 'space') restriction.scope_type = 'platform'; });

const automationModeLabel = (value) => ({ off: 'выключен', shadow: 'shadow — без санкций', enforce: 'enforce' }[value] || value || 'выключен');
const calibrationSummaryLabel = (calibration) => {
	if (!calibration) return 'нет данных';
	const dm = calibration.signal_types?.dm_distinct_recipient_burst;
	const invites = calibration.signal_types?.space_invite_recipient_burst;
	const dmLabel = dm ? `DM: ${dm.would_hold_labeled_count} labels / FP ${dm.false_positive_percent}%` : 'DM: нет данных';
	const inviteLabel = invites ? `invites: ${invites.would_hold_labeled_count} labels / FP ${invites.false_positive_percent}%` : 'invites: нет данных';
	return `${dmLabel} · ${inviteLabel} · approval ${calibration.enforcement_approved ? 'да' : 'нет'}`;
};
const storageLifecycleLabel = (value) => {
	if (!value?.declared) return 'production backup/snapshot сроки ещё не объявлены';
	return `backup ${value.backup_retention_days} дн. · snapshot ${value.snapshot_retention_days} дн.`;
};
const abuseSignalLabel = (value) => ({ message_rate_limit: 'Повторное превышение лимита сообщений', dm_distinct_recipient_burst: 'Массовые личные контакты', space_invite_recipient_burst: 'Массовые приглашения' }[value] || value);
const abuseSeverityLabel = (value) => ({ low: 'низкий риск', medium: 'средний риск', high: 'высокий риск', critical: 'критический риск' }[value] || value);
const abuseSurfaceLabel = (value) => ({ messenger: 'Messenger', space: 'Space chat', space_invitation: 'Приглашения в Space' }[value] || value);
const abuseWindowLabel = (seconds) => seconds % 60 === 0 ? `${Math.round(seconds / 60)} мин.` : `${seconds} сек.`;
const priorityLabel = (value) => ({ high: 'Высокий', normal: 'Обычный', low: 'Низкий' }[value] || value);
const statusLabel = (value) => ({ triage: 'Новая', in_review: 'В работе', escalated: 'Эскалация', resolved: 'Решено', dismissed: 'Закрыто' }[value] || value);
const sourceLabel = (value) => ({ persona: 'Профиль', messenger_message: 'Личное сообщение', space_message: 'Сообщение пространства' }[value] || value);
const categoryLabel = (value) => ({ spam: 'Спам', harassment: 'Преследование', sexual: 'Сексуальный контент', violence: 'Угрозы / насилие', privacy: 'Приватность', impersonation: 'Выдача себя за другого', fraud: 'Мошенничество', hate: 'Ненависть / травля группы', self_harm: 'Риск самоповреждения', minor_safety: 'Безопасность несовершеннолетних', other: 'Другое' }[value] || value);
const capabilityLabel = (value) => ({ 'messenger.send': 'Отправка личных сообщений', 'space.chat.send': 'Сообщения в пространствах', 'media.upload': 'Загрузка медиа' }[value] || value);
const aiSeverityLabel = (value) => ({ low: 'Низкий риск', medium: 'Средний риск', high: 'Высокий риск', critical: 'Критический риск' }[value] || value);
const aiActionLabel = (value) => ({ none: 'без санкции', temporary_restriction: 'временное ограничение' }[value] || value);
const aiOutcomeLabel = (value) => ({ not_used: 'ещё не оценено', accepted: 'принято как черновик', modified: 'взято за основу и изменяется', rejected: 'отклонено' }[value] || value);
const aiDurationLabel = (value) => ({ 60: '1 час', 1440: '24 часа', 10080: '7 дней', 43200: '30 дней' }[value] || (value ? `${value} мин.` : '—'));
const restrictionStatusLabel = (value) => ({ active: 'активно', expired: 'завершено', revoked: 'снято' }[value] || value);
const restrictionScopeLabel = (item) => item.scope_type === 'space' ? 'конкретное пространство' : 'вся платформа';
const mediaStatusLabel = (value) => ({ quarantined: 'в карантине', restored: 'восстановлено', removed: 'удалено из публичной выдачи' }[value] || 'активно');
const auditLabel = (value) => ({ report_created: 'Жалоба создана', duplicate_submission: 'Повторная отправка', report_claimed: 'Взято в работу', report_released: 'Возвращено в очередь', evidence_viewed: 'Evidence просмотрен', restriction_issued: 'Применено ограничение', restriction_appeal_created: 'Создана апелляция', restriction_appeal_resolved: 'Апелляция рассмотрена', media_quarantined: 'Вложение помещено в карантин', media_restored: 'Вложение восстановлено', media_removed: 'Вложение удалено из публичной выдачи', media_evidence_expired: 'Private evidence очищено по retention policy', report_decided: 'Решение сохранено' }[value] || value);
const formatDate = (value) => value ? new Intl.DateTimeFormat('ru', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }).format(new Date(value)) : '';
const durationLabel = (seconds) => {
	const value = Math.max(0, Number(seconds) || 0);
	if (value < 60) return `${Math.round(value)} сек.`;
	if (value < 3600) return `${Math.round(value / 60)} мин.`;
	if (value < 86400) return `${(value / 3600).toFixed(1)} ч.`;
	return `${(value / 86400).toFixed(1)} дн.`;
};

onMounted(async () => { await Promise.all([loadQueue(), loadCapabilities(), loadRestrictionAppeals(), loadAbuseSignals(), loadMetrics(), loadAIConfig()]); resetRestrictionDraft(); });
</script>

<style scoped>
.ts-shell{display:grid;gap:var(--ui-space-5);padding-bottom:var(--ui-space-8)}.ts-hero{display:grid;grid-template-columns:minmax(0,1fr) minmax(15rem,22rem);gap:var(--ui-space-5);padding:clamp(1.25rem,4vw,2.3rem);border:1px solid var(--ui-border);border-radius:var(--ui-radius-xl);background:linear-gradient(135deg,var(--ui-surface),var(--ui-primary-soft))}.eyebrow{color:var(--ui-primary);font-size:var(--ui-text-xs);font-weight:800;letter-spacing:.08em;text-transform:uppercase}.ts-hero h1,.review-head h2,.section-head h2{margin:.3rem 0 0}.ts-hero p,.review-head p{color:var(--ui-text-muted);line-height:1.55}.hero-note{align-self:center;display:flex;gap:.7rem;padding:1rem;border:1px solid var(--ui-border);border-radius:var(--ui-radius-lg);background:var(--ui-surface);color:var(--ui-text-muted);line-height:1.45}.hero-note i{color:var(--ui-primary)}.filters{display:flex;gap:.75rem;align-items:end;flex-wrap:wrap}.filters label,.decision label,.restriction-form label,.revoke-form label,.appeal-decision label{display:grid;gap:.35rem;color:var(--ui-text-muted);font-size:var(--ui-text-sm)}select,textarea,input{border:1px solid var(--ui-border);border-radius:var(--ui-radius-md);background:var(--ui-surface);color:var(--ui-text);padding:.65rem .75rem}.workspace{display:grid;grid-template-columns:minmax(17rem,25rem) minmax(0,1fr);gap:var(--ui-space-4);align-items:start}.queue-panel,.review-panel{display:grid;gap:.65rem}.review-panel{min-height:24rem;padding:var(--ui-space-4);border:1px solid var(--ui-border);border-radius:var(--ui-radius-xl);background:var(--ui-surface)}.report-card{display:grid;grid-template-columns:auto minmax(0,1fr) auto;align-items:center;gap:.7rem;width:100%;padding:.8rem;border:1px solid var(--ui-border);border-radius:var(--ui-radius-lg);background:var(--ui-surface);color:var(--ui-text);text-align:left;cursor:pointer}.report-card.active{border-color:var(--ui-primary);box-shadow:0 0 0 2px var(--ui-primary-soft)}.report-copy{min-width:0;display:grid;gap:.15rem}.report-copy span,.report-copy small{color:var(--ui-text-muted);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.priority{padding:.2rem .45rem;border-radius:var(--ui-radius-pill);font-size:.65rem;font-weight:800}.priority--high{background:var(--ui-danger-soft);color:var(--ui-danger)}.priority--normal{background:var(--ui-primary-soft);color:var(--ui-primary)}.priority--low{background:var(--ui-surface-muted);color:var(--ui-text-muted)}.review-head{display:flex;justify-content:space-between;gap:1rem}.review-head>div{min-width:0}.status-pill{align-self:start;padding:.3rem .6rem;border-radius:var(--ui-radius-pill);background:var(--ui-surface-muted);font-size:var(--ui-text-xs);font-weight:800}.review-actions{display:flex;gap:.5rem;flex-wrap:wrap}.evidence,.decision,.audit,.restriction-panel,.appeal-review,.ai-panel{display:grid;gap:.75rem;padding:1rem;border:1px solid var(--ui-border);border-radius:var(--ui-radius-lg);background:var(--ui-surface-muted)}.evidence header,.section-head{display:flex;justify-content:space-between;gap:1rem}.section-head h3{margin:.2rem 0 0}.section-head>span{max-width:18rem;color:var(--ui-text-muted);font-size:var(--ui-text-xs);text-align:right}.appeal-workspace{display:grid;grid-template-columns:minmax(15rem,22rem) minmax(0,1fr);gap:.75rem}.appeal-list,.appeal-detail{display:grid;gap:.5rem;align-content:start}.appeal-detail{min-height:9rem;padding:.75rem;border:1px solid var(--ui-border);border-radius:var(--ui-radius-md);background:var(--ui-surface)}.appeal-card{display:grid;gap:.2rem;padding:.7rem;border:1px solid var(--ui-border);border-radius:var(--ui-radius-md);background:var(--ui-surface);color:var(--ui-text);text-align:left;cursor:pointer}.appeal-card.active{border-color:var(--ui-primary)}.appeal-card span,.appeal-detail small,.appeal-detail-head span{color:var(--ui-text-muted);font-size:var(--ui-text-xs)}.appeal-detail-head{display:flex;justify-content:space-between;gap:.75rem}.appeal-detail-head>div{display:grid;gap:.2rem}.appeal-body{margin:.25rem 0;color:var(--ui-text);line-height:1.5;white-space:pre-wrap}.appeal-decision{display:grid;gap:.6rem;margin-top:.5rem}.message-evidence{padding:.8rem;border-radius:var(--ui-radius-md);background:var(--ui-surface)}.message-evidence p{white-space:pre-wrap;overflow-wrap:anywhere}.media-review{display:grid;gap:.6rem;padding:.75rem;border:1px solid var(--ui-border);border-radius:var(--ui-radius-md);background:var(--ui-surface)}.media-review__head,.media-review__item{display:flex;justify-content:space-between;gap:.75rem;align-items:center}.media-review__head span,.media-review__item span{color:var(--ui-text-muted);font-size:var(--ui-text-xs)}.media-review__item>div:first-child{display:grid;gap:.15rem}.media-review label{display:grid;gap:.35rem;color:var(--ui-text-muted);font-size:var(--ui-text-sm)}.decision-grid,.restriction-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:.75rem}.restriction-form{display:grid;gap:.75rem}.action-note{display:flex;align-items:center;justify-content:space-between;gap:1rem}.action-note span{color:var(--ui-text-muted);font-size:var(--ui-text-xs);line-height:1.45}.restriction-history{display:grid;gap:.55rem;padding-top:.25rem}.restriction-history h4{margin:.25rem 0}.restriction-row{display:flex;align-items:center;justify-content:space-between;gap:1rem;padding:.75rem;border:1px solid var(--ui-border);border-radius:var(--ui-radius-md);background:var(--ui-surface)}.restriction-row>div{display:grid;gap:.15rem}.restriction-row span,.restriction-row small{color:var(--ui-text-muted)}.revoke-form{display:grid;gap:.65rem;padding:.75rem;border:1px solid var(--ui-border);border-radius:var(--ui-radius-md);background:var(--ui-surface)}.revoke-form>div{display:flex;justify-content:flex-end;gap:.5rem}.audit-row{display:flex;justify-content:space-between;gap:1rem;padding:.45rem 0;border-bottom:1px solid var(--ui-border)}.state{display:grid;place-items:center;align-content:center;gap:.4rem;min-height:10rem;padding:1rem;color:var(--ui-text-muted);text-align:center}.state--review{min-height:20rem}.state--compact{min-height:7rem}.notice{padding:.75rem 1rem;border-radius:var(--ui-radius-md);background:var(--ui-success-soft);color:var(--ui-success)}.notice--error{background:var(--ui-danger-soft);color:var(--ui-danger)}.metric-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:.65rem}.metric-card{display:grid;gap:.2rem;padding:.8rem;border:1px solid var(--ui-border);border-radius:var(--ui-radius-md);background:var(--ui-surface)}.metric-card strong{font-size:var(--ui-text-xl)}.metric-card span{font-weight:700}.metric-card small{color:var(--ui-text-muted)}
@media(max-width:860px){.ts-hero,.workspace,.appeal-workspace{grid-template-columns:1fr}.metric-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.queue-panel{max-height:20rem;overflow:auto}.decision-grid,.restriction-grid{grid-template-columns:1fr}.section-head,.action-note{display:grid}.section-head>span{text-align:left;max-width:none}}@media(max-width:560px){.metric-grid{grid-template-columns:1fr}.filters>*{width:100%}.review-head,.appeal-detail-head{display:grid}.review-actions{display:grid}.review-actions .ui-button{width:100%}.restriction-row{align-items:stretch;display:grid}.revoke-form>div{display:grid}.action-note .ui-button{width:100%}}
</style>