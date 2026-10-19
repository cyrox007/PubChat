<template>
	<Teleport to="body">
		<Transition name="ui-modal" appear>
		<div v-if="open" class="space-modal" role="dialog" aria-modal="true" aria-labelledby="create-space-title" :aria-busy="submitting ? 'true' : 'false'">
			<button class="space-modal__backdrop" type="button" aria-label="Закрыть" @click="close" />
			<form class="space-modal__panel" @submit.prevent="submit">
				<header class="space-modal__header">
					<div>
						<span class="space-modal__eyebrow">Новое место в PubChat</span>
						<h2 id="create-space-title">Создать пространство</h2>
					</div>
					<button class="icon-button" type="button" aria-label="Закрыть" @click="close">
						<i class="fas fa-xmark" aria-hidden="true"></i>
					</button>
				</header>

				<div class="space-modal__body">
					<label class="field field--wide">
						<span>Название</span>
						<input v-model.trim="form.name" maxlength="80" required placeholder="Например, Кино после полуночи" />
						<small>От 3 до 80 символов. Название можно изменить позже.</small>
					</label>

					<label class="field field--wide">
						<span>О чём это место</span>
						<textarea v-model.trim="form.description" maxlength="500" rows="4" placeholder="Коротко опишите атмосферу, тему и для кого это пространство." />
					</label>

					<label class="field">
						<span>Формат</span>
						<select v-model="form.purpose">
							<option value="community">Сообщество</option>
							<option value="conversation">Разговоры</option>
							<option value="meet_people">Новые знакомства</option>
							<option value="games">Игры и активности</option>
							<option value="local">Локальное место</option>
						</select>
					</label>

					<label class="field">
						<span>Видимость</span>
						<select v-model="form.visibility">
							<option value="public">Публичное</option>
							<option value="unlisted">По ссылке</option>
							<option value="private">Закрытое</option>
						</select>
					</label>

					<label class="field">
						<span>Как присоединяются</span>
						<select v-model="form.join_policy">
							<option value="open">Сразу входят</option>
							<option value="request">По заявке</option>
							<option value="invite">По приглашению</option>
						</select>
					</label>

					<label class="field">
						<span>Лимит участников</span>
						<input v-model.number="form.member_limit" type="number" min="2" max="5000" />
					</label>

					<label class="field">
						<span>Страна</span>
						<input v-model.trim="form.country" maxlength="100" placeholder="Необязательно" />
					</label>

					<label class="field">
						<span>Регион / город</span>
						<input v-model.trim="form.region" maxlength="100" placeholder="Необязательно" />
					</label>

					<fieldset class="field field--wide category-choice">
						<legend>Категории (необязательно, до 3)</legend>
						<p v-if="categoryError" role="status" class="category-choice__note">
							Не удалось загрузить категории. <button type="button" @click="loadCategories">Повторить</button>
						</p>
						<p v-else-if="!categories.length" class="category-choice__note">
							{{ categoriesLoading ? 'Загружаем категории…' : 'Доступных категорий пока нет.' }}
						</p>
						<div v-else class="category-choice__items">
							<label v-for="category in categories" :key="category.slug" class="category-choice__item">
								<input type="checkbox" :checked="selectedCategories.includes(category.slug)"
									:disabled="!selectedCategories.includes(category.slug) && selectedCategories.length >= 3"
									@change="toggleCategory(category.slug)" />
								{{ category.name }}
							</label>
						</div>
					</fieldset>

					<label class="field field--wide">
						<span>Теги</span>
						<input v-model="tagsText" maxlength="240" placeholder="кино, музыка, вильнюс" />
						<small>До 8 тегов, через запятую.</small>
					</label>

					<div v-if="errorMessage" class="form-error" role="alert">
						<i class="fas fa-circle-exclamation" aria-hidden="true"></i>
						<span>{{ errorMessage }}</span>
					</div>
				</div>

				<footer class="space-modal__footer">
					<button type="button" class="ui-button ui-button--ghost" :disabled="submitting" @click="close">Отмена</button>
					<button type="submit" class="ui-button" :disabled="!canSubmit || submitting">
						<span v-if="!submitting">Создать пространство</span>
						<span v-else class="submit-state"><span class="ui-spinner" aria-hidden="true"></span>Создаём…</span>
					</button>
				</footer>
			</form>
		</div>
		</Transition>
	</Teleport>
</template>

<script setup>
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue';

import SpacesService from '@/API/SpacesService';

const props = defineProps({
	open: { type: Boolean, default: false },
});

const emit = defineEmits(['close', 'created']);

const initialForm = () => ({
	name: '',
	description: '',
	purpose: 'community',
	visibility: 'public',
	join_policy: 'open',
	member_limit: 250,
	country: '',
	region: '',
});

const form = reactive(initialForm());
const tagsText = ref('');
const categories = ref([]);
const selectedCategories = ref([]);
const categoriesLoading = ref(false);
const categoryError = ref(false);
const loadCategories = async () => {
	if (categoriesLoading.value) return;
	categoriesLoading.value = true;
	categoryError.value = false;
	try {
		const response = await SpacesService.categories();
		categories.value = response.data.categories || [];
	} catch {
		categoryError.value = true;
	} finally {
		categoriesLoading.value = false;
	}
};
const toggleCategory = (slug) => {
	if (selectedCategories.value.includes(slug)) {
		selectedCategories.value = selectedCategories.value.filter((item) => item !== slug);
	} else if (selectedCategories.value.length < 3) {
		selectedCategories.value = [...selectedCategories.value, slug];
	}
};
const submitting = ref(false);
const errorMessage = ref('');

const canSubmit = computed(() => form.name.trim().length >= 3 && form.member_limit >= 2 && form.member_limit <= 5000);

const reset = () => {
	Object.assign(form, initialForm());
	tagsText.value = '';
	selectedCategories.value = [];
	errorMessage.value = '';
};

const close = () => {
	if (submitting.value) return;
	emit('close');
};

const parsedTags = () => [...new Set(
	tagsText.value
		.split(',')
		.map((tag) => tag.trim())
		.filter(Boolean)
		.map((tag) => tag.slice(0, 40)),
)].slice(0, 8);

const submit = async () => {
	if (!canSubmit.value || submitting.value) return;
	submitting.value = true;
	errorMessage.value = '';
	try {
		const response = await SpacesService.create({
			...form,
			description: form.description || null,
			country: form.country || null,
			region: form.region || null,
			tags: parsedTags(),
			category_slugs: selectedCategories.value,
		});
		emit('created', response.data.space);
		reset();
	} catch (error) {
		const type = error.response?.data?.detail?.error_type;
		errorMessage.value = type === 'invalid_space_policy'
			? 'Для закрытого пространства выберите вход по заявке или приглашению.'
			: type === 'invalid_or_inactive_space_category'
				? 'Одна из категорий больше недоступна. Обновите список категорий.'
				: 'Не удалось создать пространство. Проверьте поля и попробуйте ещё раз.';
	} finally {
		submitting.value = false;
	}
};

watch(() => form.visibility, (visibility) => {
	if (visibility === 'private' && form.join_policy === 'open') form.join_policy = 'request';
});

let previousBodyOverflow = '';

watch(() => props.open, (open) => {
	if (open) {
		loadCategories();
		errorMessage.value = '';
		previousBodyOverflow = document.body.style.overflow;
		document.body.style.overflow = 'hidden';
	} else {
		document.body.style.overflow = previousBodyOverflow;
	}
}, { immediate: true });

onBeforeUnmount(() => {
	document.body.style.overflow = previousBodyOverflow;
});
</script>

<style scoped>
.space-modal { position: fixed; inset: 0; z-index: 1400; display: grid; place-items: center; padding: var(--ui-space-4); }
.space-modal__backdrop { position: absolute; inset: 0; border: 0; background: rgba(15, 23, 42, 0.54); backdrop-filter: blur(4px); }
.space-modal__panel { position: relative; width: min(100%, 44rem); max-height: calc(100dvh - 2rem); display: flex; flex-direction: column; overflow: hidden; border: 1px solid var(--ui-border); border-radius: var(--ui-radius-xl); background: var(--ui-surface-raised); box-shadow: var(--ui-shadow-lg); }
.space-modal__header { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--ui-space-4); padding: var(--ui-space-5); border-bottom: 1px solid var(--ui-border); }
.space-modal__eyebrow { display: block; margin-bottom: .25rem; color: var(--ui-primary); font-size: var(--ui-text-xs); font-weight: 800; letter-spacing: .06em; text-transform: uppercase; }
.space-modal h2 { margin: 0; font-size: var(--ui-text-xl); }
.icon-button { width: 2.5rem; height: 2.5rem; display: grid; place-items: center; border: 1px solid var(--ui-border); border-radius: var(--ui-radius-md); background: var(--ui-surface); color: var(--ui-text-muted); cursor: pointer; }
.space-modal__body { min-height: 0; overflow-y: auto; display: grid; grid-template-columns: 1fr 1fr; gap: var(--ui-space-4); padding: var(--ui-space-5); }
.field { min-width: 0; display: grid; gap: var(--ui-space-2); }
.field--wide { grid-column: 1 / -1; }
.field > span { color: var(--ui-text); font-size: var(--ui-text-sm); font-weight: 700; }
.field small { color: var(--ui-text-subtle); font-size: var(--ui-text-xs); }
.field input, .field textarea, .field select { width: 100%; border: 1px solid var(--ui-border); border-radius: var(--ui-radius-md); background: var(--ui-surface); color: var(--ui-text); padding: .72rem .8rem; font: inherit; outline: none; }
.field input:focus, .field textarea:focus, .field select:focus { border-color: var(--ui-primary); box-shadow: 0 0 0 3px var(--ui-primary-soft); }
.field textarea { resize: vertical; min-height: 6rem; }
.form-error { grid-column: 1 / -1; display: flex; gap: var(--ui-space-2); padding: var(--ui-space-3); border-radius: var(--ui-radius-md); background: var(--ui-danger-soft); color: var(--ui-danger); font-size: var(--ui-text-sm); }
.space-modal__footer { display: flex; justify-content: flex-end; gap: var(--ui-space-2); padding: var(--ui-space-4) var(--ui-space-5); border-top: 1px solid var(--ui-border); background: var(--ui-surface-soft); }
.submit-state { display: inline-flex; align-items: center; gap: var(--ui-space-2); }
.ui-modal-enter-active, .ui-modal-leave-active { transition: opacity var(--ui-motion-medium) var(--ui-ease-out); }
.ui-modal-enter-active .space-modal__backdrop, .ui-modal-leave-active .space-modal__backdrop { transition: opacity var(--ui-motion-medium) var(--ui-ease-out), backdrop-filter var(--ui-motion-medium) var(--ui-ease-out); }
.ui-modal-enter-active .space-modal__panel, .ui-modal-leave-active .space-modal__panel { transition: opacity var(--ui-motion-medium) var(--ui-ease-out), transform var(--ui-motion-slow) var(--ui-ease-emphasized); }
.ui-modal-enter-from, .ui-modal-leave-to { opacity: 0; }
.ui-modal-enter-from .space-modal__backdrop, .ui-modal-leave-to .space-modal__backdrop { opacity: 0; backdrop-filter: blur(0); }
.ui-modal-enter-from .space-modal__panel, .ui-modal-leave-to .space-modal__panel { opacity: 0; transform: translateY(14px) scale(.985); }
.ui-button--ghost { background: transparent; color: var(--ui-text-muted); border: 1px solid var(--ui-border); }
@media (max-width: 640px) {
	.space-modal { padding: 0; align-items: end; }
	.space-modal__panel { max-height: 94dvh; border-radius: var(--ui-radius-xl) var(--ui-radius-xl) 0 0; }
	.ui-modal-enter-from .space-modal__panel, .ui-modal-leave-to .space-modal__panel { transform: translateY(28px); }
	.space-modal__body { grid-template-columns: 1fr; padding: var(--ui-space-4); }
	.field--wide { grid-column: auto; }
	.space-modal__header, .space-modal__footer { padding-inline: var(--ui-space-4); }
	.space-modal__footer { position: sticky; bottom: 0; }
}
</style>

<style scoped>
.category-choice { min-width: 0; margin: 0; padding: .85rem; border: 1px solid var(--ui-border); border-radius: 14px; }
.category-choice legend { padding: 0 .25rem; font-size: .85rem; font-weight: 750; }
.category-choice__items { display: flex; flex-wrap: wrap; gap: .5rem; }
.category-choice__item { display: inline-flex; align-items: center; gap: .4rem; padding: .5rem .65rem; min-height: 44px; border-radius: 999px; background: var(--ui-surface-muted); color: var(--ui-text); font-size: .85rem; }
.category-choice__item input { width: 1rem; height: 1rem; min-height: 0; accent-color: var(--ui-primary); }
.category-choice__note { color: var(--ui-text-muted); font-size: .8rem; }
.category-choice__note button { color: var(--ui-primary); text-decoration: underline; }
</style>
