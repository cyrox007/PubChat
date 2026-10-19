<template>
  <div class="category-admin">
    <header class="category-admin__header">
      <div>
        <span class="category-admin__eyebrow">Living Spaces · Справочники</span>
        <h1>Категории пространств</h1>
        <p>Категории доступны всем платформам. Формат пространства и свободные теги управляются отдельно.</p>
      </div>
      <button type="button" class="ui-button" @click="beginCreate">Новая категория</button>
    </header>

    <p v-if="error" role="alert" class="category-admin__error">{{ error }}</p>
    <div v-if="loading" role="status">Загружаем категории…</div>
    <div v-else-if="!categories.length" class="category-admin__empty">Категорий пока нет. Создайте первую.</div>
    <div v-else class="category-admin__list">
      <article v-for="category in categories" :key="category.slug" class="category-admin__item">
        <div>
          <div class="category-admin__name">
            <i :class="`fas fa-${category.icon}`" aria-hidden="true"></i>
            <strong>{{ category.name }}</strong>
            <span :class="category.is_active ? 'active' : 'inactive'">
              {{ category.is_active ? 'Активна' : 'В архиве' }}
            </span>
          </div>
          <p>{{ category.description || 'Описание не задано' }}</p>
          <small>{{ category.slug }} · {{ category.locale }} · позиция {{ category.position }}</small>
        </div>
        <div class="category-admin__actions">
          <button type="button" class="ui-button ui-button--ghost" @click="beginEdit(category)">Изменить</button>
          <button type="button" class="ui-button ui-button--ghost" :disabled="saving"
            @click="toggleActive(category)">
            {{ category.is_active ? 'Архивировать' : 'Восстановить' }}
          </button>
        </div>
      </article>
    </div>

    <section v-if="editing" class="category-admin__editor" aria-labelledby="category-editor-title">
      <div class="category-admin__editor-head">
        <h2 id="category-editor-title">{{ editing === 'new' ? 'Новая категория' : 'Изменение категории' }}</h2>
        <button type="button" class="ui-button ui-button--ghost" @click="editing = null">Закрыть</button>
      </div>
      <form @submit.prevent="save">
        <label>Slug (латиница, дефисы)
          <input v-model.trim="form.slug" pattern="[a-z][a-z0-9-]*" minlength="2" maxlength="40"
            :readonly="editing !== 'new'" required />
        </label>
        <label>Название
          <input v-model.trim="form.name" minlength="2" maxlength="80" required />
        </label>
        <label>Иконка Font Awesome
          <input v-model.trim="form.icon" maxlength="32" pattern="[a-z][a-z0-9-]*" required />
        </label>
        <label>Язык
          <input v-model.trim="form.locale" maxlength="12" required />
        </label>
        <label>Позиция
          <input v-model.number="form.position" type="number" min="0" max="100000" required />
        </label>
        <label class="full">Описание
          <textarea v-model.trim="form.description" maxlength="300" rows="2" />
        </label>
        <label class="category-admin__check"><input v-model="form.is_active" type="checkbox" /> Показывать в Discovery</label>
        <button type="submit" class="ui-button" :disabled="saving">
          {{ saving ? 'Сохраняем…' : 'Сохранить категорию' }}
        </button>
      </form>
    </section>

    <section class="category-admin__audit" aria-labelledby="category-audit-title">
      <h2 id="category-audit-title">Журнал изменений</h2>
      <p v-if="!events.length" class="category-admin__muted">Изменений пока нет.</p>
      <ol v-else>
        <li v-for="event in events" :key="event.uid">
          <strong>{{ event.category_slug }}</strong> · {{ event.action }} ·
          <time :datetime="event.created_at">{{ new Date(event.created_at).toLocaleString('ru-RU') }}</time>
        </li>
      </ol>
    </section>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue';
import AdminService from '@/API/Admin/AdminService';

const categories = ref([]);
const events = ref([]);
const loading = ref(false);
const saving = ref(false);
const error = ref('');
const editing = ref(null);
const emptyForm = () => ({ slug: '', name: '', icon: 'tag', description: '', locale: 'ru', position: 0, is_active: true });
const form = reactive(emptyForm());

const load = async () => {
  loading.value = true;
  error.value = '';
  try {
    const [categoryResponse, auditResponse] = await Promise.all([
      AdminService.spaceCategories(), AdminService.spaceCategoryAudit(),
    ]);
    categories.value = categoryResponse.data.categories || [];
    events.value = auditResponse.data.events || [];
  } catch {
    error.value = 'Не удалось загрузить категории. Проверьте соединение и повторите.';
  } finally {
    loading.value = false;
  }
};
const beginCreate = () => {
  Object.assign(form, emptyForm());
  editing.value = 'new';
  error.value = '';
};
const beginEdit = (category) => {
  Object.assign(form, { ...category, description: category.description || '' });
  editing.value = category.slug;
  error.value = '';
};
const apiError = (err) => {
  const detail = err.response?.data?.detail;
  if (detail?.error_type === 'category_slug_taken') return 'Такой slug уже существует.';
  if (err.response?.status === 403) return 'Недостаточно прав администратора.';
  if (err.response?.status === 422) return 'Проверьте заполнение полей категории.';
  return 'Сохранить категорию не удалось. Попробуйте ещё раз.';
};
const save = async () => {
  if (saving.value) return;
  saving.value = true;
  error.value = '';
  try {
    const values = {
      name: form.name, icon: form.icon, locale: form.locale,
      description: form.description || null, position: form.position,
      is_active: form.is_active,
    };
    if (editing.value === 'new') {
      await AdminService.createSpaceCategory({ slug: form.slug, ...values });
    } else {
      await AdminService.updateSpaceCategory(editing.value, values);
    }
    editing.value = null;
    await load();
  } catch (err) {
    error.value = apiError(err);
  } finally {
    saving.value = false;
  }
};
const toggleActive = async (category) => {
  if (saving.value) return;
  saving.value = true;
  error.value = '';
  try {
    await AdminService.updateSpaceCategory(category.slug, { is_active: !category.is_active });
    await load();
  } catch (err) {
    error.value = apiError(err);
  } finally {
    saving.value = false;
  }
};
onMounted(load);
</script>

<style scoped>
.category-admin { display: grid; gap: 1.2rem; padding: 1.25rem; min-width: 0; }
.category-admin__header { display: flex; justify-content: space-between; align-items: start; flex-wrap: wrap; gap: 1rem; }
.category-admin__header h1 { margin: 0; font-size: clamp(1.4rem, 3vw, 2rem); }
.category-admin__header p { max-width: 46rem; color: var(--ui-text-muted); margin: .5rem 0; }
.category-admin__eyebrow { font-size: .75rem; color: var(--ui-primary); font-weight: 750; }
.category-admin__list { display: grid; gap: .75rem; }
.category-admin__item { display: flex; justify-content: space-between; flex-wrap: wrap; gap: 1rem; padding: 1rem; border: 1px solid var(--ui-border); border-radius: 18px; background: var(--ui-surface); }
.category-admin__item p { color: var(--ui-text-muted); margin: .35rem 0; }
.category-admin__item small { color: var(--ui-text-subtle); }
.category-admin__name { display: flex; flex-wrap: wrap; align-items: center; gap: .5rem; }
.category-admin__name i { color: var(--ui-primary); }
.category-admin__name span { border-radius: 999px; padding: .2rem .55rem; font-size: .72rem; }
.category-admin__name .active { color: var(--ui-success); background: var(--ui-success-soft); }
.category-admin__name .inactive { color: var(--ui-text-muted); background: var(--ui-surface-muted); }
.category-admin__actions { display: flex; align-items: center; gap: .5rem; flex-wrap: wrap; }
.category-admin__editor,.category-admin__audit { border: 1px solid var(--ui-border); background: var(--ui-surface); border-radius: 20px; padding: 1.25rem; }
.category-admin__editor-head { display: flex; align-items: center; justify-content: space-between; gap: .6rem; }
.category-admin__editor h2,.category-admin__audit h2 { margin: 0 0 1rem; font-size: 1.2rem; }
.category-admin__editor form { display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap: 1rem; }
.category-admin__editor form label { min-width: 0; display: grid; gap: .35rem; font-weight: 650; font-size: .88rem; }
.category-admin__editor form input:not([type="checkbox"]),.category-admin__editor textarea { width: 100%; min-height: 44px; padding: .6rem .75rem; border: 1px solid var(--ui-border); border-radius: 12px; background: var(--ui-surface-soft); color: var(--ui-text); }
.category-admin__editor form .full { grid-column: 1 / -1; }
.category-admin__editor form .category-admin__check { display: flex; align-items: center; gap: .55rem; }
.category-admin__error { padding: .75rem; color: var(--ui-danger); background: var(--ui-danger-soft); border-radius: 12px; }
.category-admin__muted { color: var(--ui-text-muted); }
.category-admin__audit ol { padding-left: 1.25rem; }
.category-admin__audit li { padding: .3rem 0; }
@media(max-width:640px) { .category-admin { padding: .75rem; }.category-admin__editor form { grid-template-columns: minmax(0,1fr); }.category-admin__editor form .full { grid-column: 1; }.category-admin__actions { width: 100%; }.category-admin__actions button { flex: 1 1 auto; white-space: normal; } }
</style>