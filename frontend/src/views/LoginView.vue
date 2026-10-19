<template>
	<main class="auth-screen" aria-labelledby="login-title">
		<section class="auth-card">
			<div class="auth-brand">
				<span class="auth-brand__mark" aria-hidden="true">P</span>
				<div>
					<p class="auth-eyebrow">PubChat</p>
					<h1 id="login-title">С возвращением</h1>
				</div>
			</div>

			<p class="auth-lead">Продолжите разговоры, вернитесь в свои пространства и к знакомым людям.</p>

			<div v-if="errorMessage" class="ui-notice ui-notice--danger" role="alert">
				{{ errorMessage }}
			</div>

			<form class="auth-form" @submit.prevent="handleLogin">
				<label class="field">
					<span class="field__label">Логин или email</span>
					<input
						v-model.trim="identifier"
						class="ui-input"
						type="text"
						autocomplete="username"
						autocapitalize="none"
						placeholder="@handle или email"
						required
					/>
				</label>

				<label class="field">
					<span class="field__label">Пароль</span>
					<input
						v-model="password"
						class="ui-input"
						:type="showPassword ? 'text' : 'password'"
						autocomplete="current-password"
						placeholder="Ваш пароль"
						required
					/>
					<button class="password-toggle" type="button" :aria-pressed="showPassword" :aria-label="showPassword ? 'Скрыть ввод' : 'Показать ввод'" @click="showPassword = !showPassword">{{ showPassword ? 'Скрыть' : 'Показать' }}</button>
				</label>

				<button class="ui-button ui-button--primary ui-button--block" type="submit" :disabled="isSubmitting" :aria-busy="isSubmitting ? 'true' : 'false'">
					<span v-if="isSubmitting" class="button-pending"><span class="ui-spinner" aria-hidden="true"></span>Входим…</span>
					<span v-else>Войти</span>
				</button>
			</form>

			<div class="auth-divider"><span>или</span></div>

			<RouterLink class="ui-button ui-button--secondary ui-button--block auth-link-button" :to="{ name: 'registration' }">
				Создать образ
			</RouterLink>

			<p class="auth-footnote">Телефон не нужен. Если вы раньше входили по телефону, старый способ пока продолжает поддерживаться.</p>
		</section>
	</main>
</template>

<script setup>
import { onMounted, ref } from 'vue';
import { RouterLink, useRouter } from 'vue-router';
import { useStore } from 'vuex';

import AuthService from '@/API/AuthService';
import CSRFService from '@/API/CSRFService';

const router = useRouter();
const store = useStore();

const identifier = ref('');
const password = ref('');
const showPassword = ref(false);
const errorMessage = ref('');
const isSubmitting = ref(false);

const handleLogin = async () => {
	errorMessage.value = '';
	isSubmitting.value = true;
	try {
		const response = await AuthService.login({
			identifier: identifier.value,
			password: password.value,
		});
		await store.dispatch('applyIdentitySession', response.data);
		await router.replace({ name: 'chats' });
	} catch (error) {
		const errorType = error.response?.data?.detail?.error_type;
		if (errorType === 'invalid_credentials' || error.response?.status === 401) {
			errorMessage.value = 'Не удалось войти. Проверьте логин и пароль.';
		} else if (errorType === 'account_unavailable' || error.response?.status === 403) {
			errorMessage.value = 'Аккаунт сейчас недоступен. Подробности можно узнать в центре поддержки.';
		} else {
			errorMessage.value = 'Сервер недоступен. Попробуйте ещё раз.';
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
	min-height: 0;
	flex: 1 0 auto;
	display: grid;
	place-items: center;
	padding: var(--ui-space-6) var(--ui-space-4);
}
.auth-card {
	width: min(100%, 30rem);
	background: var(--ui-surface);
	border: 1px solid var(--ui-border);
	border-radius: var(--ui-radius-xl);
	box-shadow: var(--ui-shadow-md);
	padding: clamp(1.25rem, 4vw, 2rem);
}
.auth-brand { display: flex; gap: var(--ui-space-3); align-items: center; }
.auth-brand__mark { display: grid; place-items: center; width: 2.75rem; height: 2.75rem; border-radius: var(--ui-radius-md); background: var(--ui-primary); color: var(--ui-primary-contrast); font-weight: 800; font-size: var(--ui-text-xl); }
.auth-eyebrow { margin: 0 0 0.125rem; color: var(--ui-primary); font-size: var(--ui-text-sm); font-weight: 700; }
h1 { margin: 0; font-size: clamp(1.5rem, 5vw, 2rem); line-height: var(--ui-leading-tight); }
.auth-lead { color: var(--ui-text-muted); line-height: var(--ui-leading-normal); margin: var(--ui-space-4) 0 var(--ui-space-6); }
.auth-form { display: grid; gap: var(--ui-space-5); }
.field { display: grid; gap: var(--ui-space-2); }
.field__label { font-size: var(--ui-text-sm); font-weight: 700; }
.ui-input { width: 100%; min-height: 2.875rem; border: 1px solid var(--ui-border-strong); border-radius: var(--ui-radius-md); background: var(--ui-surface); color: var(--ui-text); padding: 0.7rem 0.8rem; font: inherit; }
.ui-input:focus-visible { outline: none; border-color: var(--ui-focus); box-shadow: var(--ui-focus-ring); }
.ui-notice { padding: var(--ui-space-3); border-radius: var(--ui-radius-md); margin-bottom: var(--ui-space-4); }
.ui-notice--danger { color: var(--ui-danger); background: var(--ui-danger-soft); }
.auth-divider { display: flex; align-items: center; gap: var(--ui-space-3); color: var(--ui-text-subtle); margin: var(--ui-space-5) 0; font-size: var(--ui-text-xs); }
.auth-divider::before, .auth-divider::after { content: ''; height: 1px; flex: 1; background: var(--ui-border); }
.button-pending { display: inline-flex; align-items: center; gap: var(--ui-space-2); }
.auth-link-button { text-decoration: none; }
.auth-footnote { margin: var(--ui-space-5) 0 0; color: var(--ui-text-subtle); font-size: var(--ui-text-xs); line-height: var(--ui-leading-normal); text-align: center; }
@media (max-width: 560px) {
	.auth-screen { place-items: start stretch; padding: var(--ui-space-3); }
	.auth-card { border-radius: var(--ui-radius-lg); box-shadow: var(--ui-shadow-sm); }
}

/* Design reference 2026-10-18: mobile-first auth, no dead controls. */
.auth-screen {
  position: relative;
  isolation: isolate;
  min-height: 0;
  background-color: var(--ui-bg);
  background-image: radial-gradient(ellipse at 12% 12%, var(--ui-primary-soft), transparent 48%),
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
