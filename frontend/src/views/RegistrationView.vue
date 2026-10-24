<template>
	<main class="auth-screen" aria-labelledby="registration-title">
		<section class="auth-card auth-card--wide">
			<div class="auth-brand">
				<span class="auth-brand__mark" aria-hidden="true">P</span>
				<div>
					<p class="auth-eyebrow">Добро пожаловать в PubChat</p>
					<h1 id="registration-title">Создайте свой образ</h1>
				</div>
			</div>

			<p class="auth-lead">
				Не анкета знакомств, а имя, под которым вас встретят в сообществах. Остальное можно настроить позже.
			</p>

			<div class="step-indicator" aria-label="Шаг регистрации">
				<span :class="['step-dot', { 'step-dot--active': step >= 1 }]">1</span>
				<span class="step-line"></span>
				<span :class="['step-dot', { 'step-dot--active': step >= 2 }]">2</span>
				<span class="step-label">{{ step === 1 ? 'Ваш образ' : 'Безопасность' }}</span>
			</div>

			<div v-if="errorMessage" class="ui-notice ui-notice--danger" role="alert">
				{{ errorMessage }}
			</div>

			<Transition name="registration-step" mode="out-in">
			<form v-if="step === 1" key="persona" class="auth-form" @submit.prevent="goToSecurity">
				<label class="field">
					<span class="field__label">Как вас называть?</span>
					<input
						v-model.trim="form.display_name"
						class="ui-input"
						type="text"
						maxlength="80"
						autocomplete="nickname"
						placeholder="Например, Саша"
						required
					/>
					<span class="field__hint">Это имя видно людям. Его можно менять.</span>
				</label>

				<label class="field">
					<span class="field__label">Уникальный адрес</span>
					<div class="handle-input">
						<span aria-hidden="true">@</span>
						<input
							v-model.trim="form.handle"
							class="ui-input ui-input--bare"
							type="text"
							minlength="3"
							maxlength="32"
							autocapitalize="none"
							autocomplete="username"
							placeholder="alex"
							required
						/>
					</div>
					<span v-if="handleError || handleAvailability === 'taken'" class="field__error" role="status">{{ handleError || 'Этот username уже занят.' }}</span>
                    <span v-else-if="handleAvailability === 'checking'" class="field__hint" role="status">Проверяем доступность имени…</span>
                    <span v-else-if="handleAvailability === 'available'" class="field__success" role="status">✓ Username предварительно свободен</span>
                    <span v-else-if="handleAvailability === 'unverified'" class="field__hint" role="status">Не удалось проверить сейчас. Проверим при регистрации.</span>
					<span v-else class="field__hint">Латинские буквы, цифры, точка и подчёркивание.</span>
				</label>

				<fieldset class="field intent-fieldset">
					<legend class="field__label">Что вам сейчас ближе?</legend>
					<div class="intent-grid">
						<button
							v-for="intent in intents"
							:key="intent.value"
							type="button"
							:class="['intent-option', { 'intent-option--selected': form.social_intent === intent.value }]"
							:aria-pressed="form.social_intent === intent.value"
							@click="form.social_intent = intent.value"
						>
							<strong>{{ intent.label }}</strong>
							<span>{{ intent.description }}</span>
						</button>
					</div>
				</fieldset>

				<button class="ui-button ui-button--primary ui-button--block" type="submit">Продолжить</button>
			</form>

			<form v-else key="security" class="auth-form" @submit.prevent="register">
				<label class="field">
					<span class="field__label">Пароль</span>
					<input
						v-model="form.password"
						class="ui-input"
						type="password"
						minlength="8"
						maxlength="128"
						autocomplete="new-password"
						placeholder="Минимум 8 символов"
						required
					/>
                    <div v-if="form.password" class="password-strength" aria-live="polite">
                        <progress :value="strengthScore" max="4" aria-label="Надёжность пароля"></progress>
                        <span>Надёжность: {{ strengthLabel }}</span>
                    </div>
				</label>

				<label class="field">
					<span class="field__label">Повторите пароль</span>
					<input
						v-model="confirmPassword"
						class="ui-input"
						type="password"
						autocomplete="new-password"
						required
					/>
					<span v-if="confirmPassword" :class="passwordsMatch ? 'field__success' : 'field__error'" aria-live="polite">{{ passwordsMatch ? '✓ Пароли совпадают' : 'Пароли не совпадают' }}</span>
						<span v-if="passwordError" class="field__error">{{ passwordError }}</span>
				</label>

				<label class="field">
					<span class="field__label">Email <span class="field__optional">необязательно</span></span>
					<input
						v-model.trim="form.email"
						class="ui-input"
						type="email"
						autocomplete="email"
						placeholder="Для восстановления доступа"
					/>
					<span class="field__hint">Можно добавить и подтвердить позже. Телефон для входа не требуется.</span>
				</label>

				<label class="field">
					<span class="field__label">Пара слов о себе <span class="field__optional">необязательно</span></span>
					<textarea
						v-model.trim="form.bio"
						class="ui-input ui-textarea"
						maxlength="500"
						rows="3"
						placeholder="Например: люблю живую музыку и настолки"
					></textarea>
				</label>

				<div class="auth-actions">
					<button class="ui-button ui-button--secondary" type="button" :disabled="isSubmitting" @click="step = 1">Назад</button>
					<button class="ui-button ui-button--primary" type="submit" :disabled="!canComplete" :aria-busy="isSubmitting ? 'true' : 'false'">
						<span v-if="isSubmitting" class="button-pending"><span class="ui-spinner" aria-hidden="true"></span>Создаём…</span>
						<span v-else>Войти в PubChat</span>
					</button>
				</div>
			</form>
			</Transition>

			<p class="auth-footer">
				Уже есть аккаунт?
				<RouterLink :to="{ name: 'login' }">Войти</RouterLink>
			</p>
		</section>
	</main>
</template>

<script setup>
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue';
import { RouterLink, useRouter } from 'vue-router';
import { useStore } from 'vuex';

import AuthService from '@/API/AuthService';
import CSRFService from '@/API/CSRFService';

const router = useRouter();
const store = useStore();

const step = ref(1);
const confirmPassword = ref('');
const errorMessage = ref('');
const handleError = ref('');
const passwordError = ref('');
const isSubmitting = ref(false);
const handleAvailability = ref('idle');
let handleCheckTimer = null;
let handleCheckVersion = 0;
watch(() => form.handle, (value) => {
    const version = ++handleCheckVersion;
    if (handleCheckTimer !== null) clearTimeout(handleCheckTimer);
    handleAvailability.value = 'idle';
    if (!/^[A-Za-z0-9_.]{3,32}$/.test(value)) return;
    handleAvailability.value = 'checking';
    handleCheckTimer = setTimeout(async () => {
        try {
            const response = await AuthService.handleAvailability(value);
            if (version !== handleCheckVersion || value !== form.handle) return;
            const data = response.data;
            // Unknown/legacy response shapes must never be interpreted as available.
            if (data?.available === true || data?.is_available === true || data?.isUnique === true) handleAvailability.value = 'available';
            else if (data?.available === false || data?.is_available === false || data?.isUnique === false ||
                     data?.exists === true) handleAvailability.value = 'taken';
            else handleAvailability.value = 'unverified';
        } catch {
            if (version === handleCheckVersion) handleAvailability.value = 'unverified';
        }
    }, 450);
});
onUnmounted(() => {
    ++handleCheckVersion;
    if (handleCheckTimer !== null) clearTimeout(handleCheckTimer);
});

const strengthScore = computed(() => {
    const value = form.password;
    if (!value) return 0;
    return Number(value.length >= 8) + Number(value.length >= 12) +
        Number(/[a-z]/.test(value) && /[A-Z]/.test(value)) +
        Number(/[0-9]/.test(value) && /[^A-Za-z0-9\\s]/.test(value));
});
const strengthLabel = computed(() => ['Не задан', 'Низкая', 'Средняя', 'Хорошая', 'Высокая'][strengthScore.value]);
const passwordsMatch = computed(() => Boolean(confirmPassword.value) && form.password === confirmPassword.value);
const canComplete = computed(() => form.password.length >= 8 &&
    form.password.length <= 128 && passwordsMatch.value && !isSubmitting.value);


const form = reactive({
	handle: '',
	display_name: '',
	password: '',
	email: '',
	bio: '',
	social_intent: 'open',
});

const intents = [
	{ value: 'open', label: 'Хочу пообщаться', description: 'Открыт разговорам без конкретной цели' },
	{ value: 'meet', label: 'Новые знакомства', description: 'Не против познакомиться с новыми людьми' },
	{ value: 'games', label: 'Компания для игры', description: 'Хочу совместные активности и игры' },
	{ value: 'friends', label: 'Только знакомые', description: 'Предпочитаю общение в знакомом кругу' },
	{ value: 'quiet', label: 'Спокойный режим', description: 'Сейчас не ищу новых контактов' },
];

const goToSecurity = () => {
	errorMessage.value = '';
	handleError.value = '';
	const validHandle = /^[A-Za-z0-9_.]{3,32}$/.test(form.handle);
	if (!validHandle) {
		handleError.value = 'Используйте 3–32 латинских символа, цифры, точку или подчёркивание.';
		return;
	}
	if (!form.display_name) return;
    if (handleAvailability.value === 'taken') return;
	step.value = 2;
};

const register = async () => {
	errorMessage.value = '';
	passwordError.value = '';

	if (form.password.length < 8) {
		passwordError.value = 'Пароль должен содержать минимум 8 символов.';
		return;
	}
	if (form.password !== confirmPassword.value) {
		passwordError.value = 'Пароли не совпадают.';
		return;
	}

	isSubmitting.value = true;
	try {
		const payload = {
			handle: form.handle,
			display_name: form.display_name,
			password: form.password,
			social_intent: form.social_intent,
		};
		if (form.email) payload.email = form.email;
		if (form.bio) payload.bio = form.bio;

		const response = await AuthService.registration(payload);
		await store.dispatch('applyIdentitySession', response.data);
		await router.replace({ name: 'chats' });
	} catch (error) {
		const detail = error.response?.data?.detail;
		const errorType = detail?.error_type || detail?.detail?.error_type;
		if (errorType === 'handle_taken') {
			step.value = 1;
			handleError.value = 'Такой адрес уже занят. Попробуйте другой.';
		} else if (errorType === 'email_taken') {
			errorMessage.value = 'Этот email уже связан с другим аккаунтом.';
		} else if (error.response?.status === 422) {
			errorMessage.value = 'Проверьте введённые данные.';
		} else {
			errorMessage.value = 'Не удалось создать аккаунт. Проверьте соединение и попробуйте снова.';
		}
	} finally {
		isSubmitting.value = false;
	}
};

onMounted(async () => {
	try {
		await CSRFService.getCSRF();
	} catch {
		errorMessage.value = 'Не удалось подготовить безопасное соединение с сервером.';
	}
});
</script>

<style scoped>
.auth-screen {
	min-height: calc(100dvh - 64px);
	display: grid;
	place-items: center;
	padding: var(--ui-space-6) var(--ui-space-4);
}

.auth-card {
	width: min(100%, 34rem);
	background: var(--ui-surface);
	border: 1px solid var(--ui-border);
	border-radius: var(--ui-radius-xl);
	box-shadow: var(--ui-shadow-md);
	padding: clamp(1.25rem, 4vw, 2rem);
}

.auth-card--wide { width: min(100%, 42rem); }
.auth-brand { display: flex; gap: var(--ui-space-3); align-items: center; }
.auth-brand__mark { display: grid; place-items: center; width: 2.75rem; height: 2.75rem; border-radius: var(--ui-radius-md); background: var(--ui-primary); color: var(--ui-primary-contrast); font-weight: 800; font-size: var(--ui-text-xl); }
.auth-eyebrow { margin: 0 0 0.125rem; color: var(--ui-primary); font-size: var(--ui-text-sm); font-weight: 700; }
h1 { margin: 0; font-size: clamp(1.5rem, 5vw, 2rem); line-height: var(--ui-leading-tight); }
.auth-lead { color: var(--ui-text-muted); line-height: var(--ui-leading-normal); margin: var(--ui-space-4) 0 var(--ui-space-6); }
.step-indicator { display: flex; align-items: center; gap: var(--ui-space-2); margin-bottom: var(--ui-space-6); color: var(--ui-text-muted); font-size: var(--ui-text-sm); }
.step-dot { display: grid; place-items: center; width: 1.75rem; height: 1.75rem; border-radius: 50%; border: 1px solid var(--ui-border-strong); background: var(--ui-surface-soft); }
.step-dot--active { border-color: var(--ui-primary); background: var(--ui-primary); color: white; }
.step-line { width: 2rem; height: 1px; background: var(--ui-border); }
.step-label { margin-left: var(--ui-space-1); font-weight: 600; }
.step-dot, .step-line, .step-label { transition: background var(--ui-motion-normal) var(--ui-ease), border-color var(--ui-motion-normal) var(--ui-ease), color var(--ui-motion-normal) var(--ui-ease), transform var(--ui-motion-normal) var(--ui-ease); }
.step-dot--active { transform: scale(1.04); }
.registration-step-enter-active, .registration-step-leave-active { transition: opacity var(--ui-motion-medium) var(--ui-ease-out), transform var(--ui-motion-medium) var(--ui-ease-out); }
.registration-step-enter-from { opacity: 0; transform: translateX(10px); }
.registration-step-leave-to { opacity: 0; transform: translateX(-8px); }
.button-pending { display: inline-flex; align-items: center; gap: var(--ui-space-2); }
.auth-form { display: grid; gap: var(--ui-space-5); }
.field { display: grid; gap: var(--ui-space-2); margin: 0; border: 0; padding: 0; }
.field__label { font-size: var(--ui-text-sm); font-weight: 700; }
.field__optional { color: var(--ui-text-subtle); font-weight: 500; }
.field__hint { color: var(--ui-text-muted); font-size: var(--ui-text-xs); }
.field__error { color: var(--ui-danger); font-size: var(--ui-text-sm); }
.field__success { color: var(--ui-success, #18794e); font-size: var(--ui-text-sm); }
.password-strength { display: grid; gap: 0.35rem; color: var(--ui-text-muted); font-size: var(--ui-text-xs); }
.password-strength progress { width: 100%; height: 0.6rem; accent-color: var(--ui-primary); }
.ui-input { width: 100%; min-height: 2.875rem; border: 1px solid var(--ui-border-strong); border-radius: var(--ui-radius-md); background: var(--ui-surface); color: var(--ui-text); padding: 0.7rem 0.8rem; font: inherit; }
.ui-input:focus-visible { outline: none; border-color: var(--ui-focus); box-shadow: var(--ui-focus-ring); }
.ui-input--bare { border: 0; padding-left: 0.25rem; box-shadow: none !important; background: transparent; }
.ui-textarea { resize: vertical; min-height: 5.5rem; }
.handle-input { display: flex; align-items: center; min-height: 2.875rem; border: 1px solid var(--ui-border-strong); border-radius: var(--ui-radius-md); padding-left: 0.8rem; color: var(--ui-text-muted); }
.handle-input:focus-within { border-color: var(--ui-focus); box-shadow: var(--ui-focus-ring); }
.intent-fieldset legend { margin-bottom: var(--ui-space-2); }
.intent-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--ui-space-2); }
.intent-option { text-align: left; border: 1px solid var(--ui-border); border-radius: var(--ui-radius-md); background: var(--ui-surface-soft); color: var(--ui-text); padding: var(--ui-space-3); cursor: pointer; transition: border-color var(--ui-motion-fast) var(--ui-ease), background var(--ui-motion-fast) var(--ui-ease); }
.intent-option strong, .intent-option span { display: block; }
.intent-option span { color: var(--ui-text-muted); font-size: var(--ui-text-xs); margin-top: var(--ui-space-1); }
.intent-option--selected { border-color: var(--ui-primary); background: var(--ui-primary-soft); }
.auth-actions { display: grid; grid-template-columns: auto 1fr; gap: var(--ui-space-2); }
.auth-footer { text-align: center; color: var(--ui-text-muted); margin: var(--ui-space-6) 0 0; }
.auth-footer a { color: var(--ui-primary); font-weight: 700; text-decoration: none; }
.ui-notice { padding: var(--ui-space-3); border-radius: var(--ui-radius-md); margin-bottom: var(--ui-space-4); }
.ui-notice--danger { color: var(--ui-danger); background: var(--ui-danger-soft); }

@media (max-width: 560px) {
	.auth-screen { place-items: start stretch; padding: var(--ui-space-3); }
	.auth-card { border-radius: var(--ui-radius-lg); box-shadow: var(--ui-shadow-sm); }
	.intent-grid { grid-template-columns: 1fr; }
	.auth-actions { grid-template-columns: 1fr; }
	.auth-actions .ui-button--secondary { order: 2; }
}

/* Design reference 2026-10-18: mobile-first auth, no dead controls. */
.auth-screen {
  position: relative;
  isolation: isolate;
  min-height: calc(100dvh - 64px);
  background: radial-gradient(ellipse at 12% 12%, var(--ui-primary-soft), transparent 48%),
              radial-gradient(ellipse at 90% 85%, color-mix(in srgb, var(--ui-brand-cyan, #12bcd5) 13%, transparent), transparent 42%);
}
.auth-card {
  position: relative;
  width: min(100%, 34rem);
  padding: clamp(1.25rem, 3.8vw, 2.5rem);
  border-radius: 24px;
  box-shadow: 0 16px 55px rgba(42, 36, 118, .12), 0 2px 10px rgba(42, 36, 118, .04);
}
.auth-brand__mark {
  width: 3.5rem;
  height: 3.5rem;
  border-radius: 18px;
  background: var(--ui-brand-gradient);
  box-shadow: 0 8px 22px rgba(99, 71, 245, .22);
}
.ui-input, .handle-input { min-height: 3rem; border-radius: 12px; }
.ui-button--primary { min-height: 3rem; border-radius: 12px; background: var(--ui-brand-gradient); }
.ui-button--primary:disabled { background: var(--ui-surface-muted); color: var(--ui-text-muted); }
.password-toggle {
  align-self: end; justify-self: start; border: none; padding: .3rem 0;
  background: none; font: inherit; font-size: var(--ui-text-sm);
  color: var(--ui-primary); cursor: pointer;
}
@media (max-width: 560px) {
  .auth-screen { padding: 12px; place-items: center stretch; }
  .auth-card { border-radius: 20px; box-shadow: var(--ui-shadow-sm); padding: 20px 16px; }
}
@media (prefers-reduced-motion: reduce) {
  .auth-card, .ui-button { animation: none !important; transition-duration: .01ms !important; }
}

</style>
