<template>
  <main class="friendship-hub">
    <header class="hub-hero">
      <div>
        <span class="eyebrow">Социальные связи</span>
        <h1>Друзья и заявки</h1>
        <p>Общение начинается по взаимному согласию. Входящие заявки требуют вашего решения; исходящие можно отменить в любой момент.</p>
      </div>
      <RouterLink :to="{ name: 'people' }" class="ui-button ui-button--ghost">Найти людей</RouterLink>
    </header>

    <nav class="hub-tabs" aria-label="Разделы дружбы">
      <button v-for="item in tabs" :key="item.key" type="button"
        :class="{ active: tab === item.key }" :aria-current="tab === item.key ? 'page' : undefined"
        @click="tab = item.key">{{ item.label }}</button>
    </nav>

    <section v-if="error" class="hub-error" role="alert">
      <span>{{ error }}</span>
      <button class="ui-button ui-button--ghost" type="button" @click="load()">Повторить</button>
    </section>

    <section v-if="loading" class="hub-state" role="status">
      <span class="hub-spinner" aria-hidden="true"></span> Загружаем список…
    </section>
    <section v-else-if="!rows.length && !error" class="hub-state">
      <strong>{{ emptyMessage }}</strong>
      <span>Новые знакомства можно найти в разделе «Люди».</span>
      <RouterLink :to="{ name: 'people' }">Перейти к людям</RouterLink>
    </section>

    <section v-else-if="rows.length" class="hub-list" :aria-label="sectionLabel">
      <article v-for="row in rows" :key="row.account_uid" class="hub-person">
        <RouterLink :to="{ name: 'UserProfile', params: { uid: row.account_uid } }" class="hub-person__identity">
          <span class="hub-avatar" aria-hidden="true">{{ (row.persona?.display_name || row.persona?.handle || '?').slice(0, 1).toUpperCase() }}</span>
          <span>
            <strong>{{ row.persona?.display_name || row.persona?.handle || 'Участник PubChat' }}</strong>
            <small v-if="row.persona?.handle">@{{ row.persona.handle }}</small>
          </span>
        </RouterLink>
        <div class="hub-actions">
          <template v-if="tab === 'incoming'">
            <button class="ui-button" type="button" :disabled="busyUid !== null" @click="act(row, 'accept')">Принять</button>
            <button class="ui-button ui-button--ghost" type="button" :disabled="busyUid !== null" @click="act(row, 'reject')">Отклонить</button>
          </template>
          <button v-else-if="tab === 'outgoing'" class="ui-button ui-button--ghost" type="button"
            :disabled="busyUid !== null" @click="act(row, 'remove')">Отменить запрос</button>
          <button v-else class="ui-button ui-button--ghost" type="button"
            :disabled="busyUid !== null" @click="removeFriend(row)">Удалить из друзей</button>
          <span v-if="busyUid === row.account_uid" role="status">Сохраняем…</span>
        </div>
      </article>
    </section>

    <div v-if="rows.length < total" class="hub-more">
      <button class="ui-button ui-button--ghost" type="button" :disabled="loading || loadingMore || busyUid !== null"
        @click="load({ append: true })">{{ loadingMore ? 'Загружаем…' : 'Показать ещё' }}</button>
    </div>
  </main>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue';
import { RouterLink } from 'vue-router';
import SocialService from '@/API/SocialService';

const tabs = [
  { key: 'incoming', label: 'Входящие' },
  { key: 'outgoing', label: 'Исходящие' },
  { key: 'friends', label: 'Друзья' },
];
const tab = ref('incoming');
const rows = ref([]);
const total = ref(0);
const loading = ref(true);
const loadingMore = ref(false);
const busyUid = ref(null);
const error = ref('');
let requestGeneration = 0;

const emptyMessage = computed(() => ({
  incoming: 'Новых заявок в друзья нет.',
  outgoing: 'Вы пока не отправляли заявок.',
  friends: 'Список друзей пока пуст.',
}[tab.value]));
const sectionLabel = computed(() => ({
  incoming: 'Входящие заявки',
  outgoing: 'Исходящие заявки',
  friends: 'Друзья',
}[tab.value]));

const load = async ({ append = false } = {}) => {
  if (loadingMore.value || (append && loading.value)) return;
  const generation = ++requestGeneration;
  const selected = tab.value;
  if (append) loadingMore.value = true;
  else { loading.value = true; error.value = ''; }
  try {
    const offset = append ? rows.value.length : 0;
    const response = selected === 'friends'
      ? await SocialService.friends({ limit: 50, offset })
      : await SocialService.friendRequests({ direction: selected, limit: 50, offset });
    if (generation !== requestGeneration || selected !== tab.value) return;
    const items = selected === 'friends' ? response.data.friends : response.data.requests;
    const fetched = Array.isArray(items) ? items : [];
    if (append) {
      const known = new Set(rows.value.map((item) => item.account_uid));
      rows.value = [...rows.value, ...fetched.filter((item) => !known.has(item.account_uid))];
    } else rows.value = fetched;
    total.value = Number(response.data.pagination?.total ?? rows.value.length);
  } catch {
    if (generation === requestGeneration && selected === tab.value) {
      error.value = 'Не удалось загрузить список. Попробуйте повторить.';
    }
  } finally {
    if (generation === requestGeneration) {
      loading.value = false;
      loadingMore.value = false;
    }
  }
};

const act = async (row, action) => {
  if (busyUid.value) return;
  busyUid.value = row.account_uid;
  error.value = '';
  try {
    // Server enforces privacy, block rules and consent; do not optimistically grant friendship.
    await SocialService.friendAction(row.account_uid, action);
    await load();
  } catch {
    error.value = 'Не удалось обработать заявку. Проверьте доступ и повторите.';
  } finally {
    busyUid.value = null;
  }
};

const removeFriend = async (row) => {
  if (!window.confirm('Удалить этого человека из друзей?')) return;
  await act(row, 'remove');
};
watch(tab, () => { rows.value = []; total.value = 0; loadingMore.value = false; load(); });
onMounted(() => load());
</script>

<style scoped>
.friendship-hub { display: grid; gap: var(--ui-space-4); padding-bottom: var(--ui-space-8); }
.hub-hero { display: flex; justify-content: space-between; align-items: center; gap: var(--ui-space-5); padding: clamp(1.4rem, 4vw, 2.5rem); border: 1px solid var(--ui-border); border-radius: var(--ui-radius-xl); background: linear-gradient(135deg, var(--ui-surface), var(--ui-primary-soft) 180%); }
.hub-hero h1 { margin: .25rem 0 .5rem; font-size: clamp(1.7rem, 4vw, 2.7rem); }
.hub-hero p { margin: 0; max-width: 42rem; color: var(--ui-text-muted); line-height: 1.5; }
.eyebrow { color: var(--ui-primary); font-size: var(--ui-text-xs); font-weight: 800; text-transform: uppercase; letter-spacing: .06em; }
.hub-tabs { display: flex; gap: var(--ui-space-2); flex-wrap: wrap; }
.hub-tabs button { min-height: 2.5rem; padding: 0 var(--ui-space-4); background: var(--ui-surface); border: 1px solid var(--ui-border); border-radius: var(--ui-radius-pill); color: var(--ui-text); cursor: pointer; }
.hub-tabs button.active { background: var(--ui-primary-soft); color: var(--ui-primary); border-color: var(--ui-primary); font-weight: 700; }
.hub-list { display: grid; gap: var(--ui-space-3); }
.hub-person { display: flex; justify-content: space-between; align-items: center; gap: var(--ui-space-4); padding: var(--ui-space-4); border: 1px solid var(--ui-border); border-radius: var(--ui-radius-lg); background: var(--ui-surface); }
.hub-person__identity { display: flex; gap: var(--ui-space-3); align-items: center; min-width: 0; text-decoration: none; color: var(--ui-text); }
.hub-person__identity > span:last-child { display: grid; gap: 3px; overflow: hidden; }
.hub-person__identity strong { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.hub-person__identity small { color: var(--ui-text-subtle); }
.hub-avatar { display: grid; place-items: center; width: 3rem; height: 3rem; border-radius: 50%; flex: 0 0 auto; background: var(--ui-primary-soft); color: var(--ui-primary); font-weight: 800; }
.hub-actions { display: flex; flex-wrap: wrap; align-items: center; gap: var(--ui-space-2); }
.hub-actions span { font-size: var(--ui-text-xs); color: var(--ui-text-muted); }
.hub-state, .hub-error { display: grid; gap: var(--ui-space-2); justify-items: center; text-align: center; padding: var(--ui-space-8); border: 1px solid var(--ui-border); border-radius: var(--ui-radius-lg); background: var(--ui-surface); color: var(--ui-text-muted); }
.hub-state strong { color: var(--ui-text); }.hub-error { color: var(--ui-danger); }
.hub-more { display: flex; justify-content: center; }
@media (max-width: 720px) { .hub-hero, .hub-person { align-items: stretch; flex-direction: column; }.hub-actions .ui-button { flex: 1; } }
</style>
