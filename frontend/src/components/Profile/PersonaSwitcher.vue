<template>
  <section class="profile-card persona-switcher" aria-labelledby="persona-manager-title">
    <header class="persona-switcher__header">
      <div>
        <p class="section-eyebrow">Account / Persona</p>
        <h2 id="persona-manager-title">Мои образы</h2>
        <p>Один аккаунт и одна безопасность. Каждый браузер или телефон выбирает свой образ.</p>
      </div>
      <button class="ui-button ui-button--secondary" type="button" :disabled="loading || busy" @click="reload">
        Обновить
      </button>
    </header>
    <p v-if="error" class="persona-switcher__error" role="alert">{{ error }}</p>
    <p v-if="loading" role="status">Загружаем ваши образы…</p>
    <ul v-else class="persona-switcher__list">
      <li v-for="persona in personas" :key="persona.uid">
        <div>
          <strong>{{ persona.display_name }}</strong>
          <small>@{{ persona.handle }} · {{ persona.is_primary ? 'Основной' : 'Дополнительный' }}</small>
        </div>
        <span v-if="persona.uid === activeUid" aria-current="true">Активен</span>
        <button v-else class="ui-button ui-button--secondary" type="button" :disabled="busy" @click="activate(persona.uid)">
          Выбрать
        </button>
      </li>
    </ul>
    <form v-if="personas.length < 3 && !loading" class="persona-switcher__create" @submit.prevent="create">
      <h3>Создать ещё один образ</h3>
      <p>Новый образ скрыт от других, пока не появится отдельный публичный режим.</p>
      <label>
        <span>Handle</span>
        <input v-model.trim="handle" class="ui-input" maxlength="32" minlength="3" pattern="[A-Za-z0-9_.]+" required placeholder="second.persona" />
      </label>
      <label>
        <span>Отображаемое имя</span>
        <input v-model.trim="displayName" class="ui-input" maxlength="80" required placeholder="Другой образ" />
      </label>
      <button type="submit" class="ui-button ui-button--primary" :disabled="busy || !handle || !displayName">
        {{ busy ? 'Сохраняем…' : 'Создать образ' }}
      </button>
    </form>
    <p class="persona-switcher__note">
      Блокировки, санкции, переписки и репутация остаются общими для Account.
      Переключение образа не меняет права доступа.
    </p>
  </section>
</template>

<script setup>
import { onMounted, ref } from 'vue';
import { useStore } from 'vuex';
import AuthService from '@/API/AuthService';
import CSRFService from '@/API/CSRFService';

const emit = defineEmits(['activated']);
const store = useStore();
const personas = ref([]);
const activeUid = ref(null);
const loading = ref(true);
const busy = ref(false);
const error = ref('');
const handle = ref('');
const displayName = ref('');

const describe = (err) => {
  const type = err.response?.data?.detail?.error_type;
  if (type === 'handle_taken') return 'Этот handle уже используется.';
  if (type === 'persona_limit_reached') return 'Для одного аккаунта доступно до трёх образов.';
  if (err.response?.status === 401) return 'Сессия истекла. Войдите снова.';
  if (err.response?.status === 403) return 'Операция запрещена для аккаунта.';
  return 'Не удалось выполнить операцию. Повторите попытку.';
};

const reload = async () => {
  loading.value = true;
  error.value = '';
  try {
    const { data } = await AuthService.personas();
    personas.value = data.personas || [];
    activeUid.value = data.active_persona_uid;
  } catch (err) {
    error.value = describe(err);
  } finally {
    loading.value = false;
  }
};

const activate = async (uid) => {
  if (busy.value) return;
  busy.value = true;
  error.value = '';
  try {
    await CSRFService.getCSRF();
    const { data } = await AuthService.activatePersona(uid);
    // Switching a Persona never creates another login or refresh token.
    store.commit('setUser', data.user);
    store.commit('setIdentity', {
      account: data.account, persona: data.persona, privacy: data.privacy,
      role: data.role, access_restriction: data.access_restriction,
    });
    activeUid.value = data.persona?.uid || null;
    emit('activated', data);
  } catch (err) {
    error.value = describe(err);
  } finally {
    busy.value = false;
  }
};

const create = async () => {
  if (busy.value) return;
  busy.value = true;
  error.value = '';
  try {
    await CSRFService.getCSRF();
    await AuthService.createPersona({ handle: handle.value, display_name: displayName.value });
    handle.value = '';
    displayName.value = '';
    await reload();
  } catch (err) {
    error.value = describe(err);
  } finally {
    busy.value = false;
  }
};

onMounted(reload);
</script>

<style scoped>
.persona-switcher { display: grid; gap: 1rem; }
.persona-switcher__header { display: flex; gap: 1rem; align-items: start; justify-content: space-between; }
.persona-switcher__header p, .persona-switcher__note { color: var(--ui-text-muted); font-size: var(--ui-text-sm); }
.persona-switcher__header h2, .persona-switcher__create h3 { margin: .3rem 0; }
.persona-switcher__list { padding: 0; margin: 0; display: grid; gap: .6rem; list-style: none; }
.persona-switcher__list li { display: flex; align-items: center; justify-content: space-between; gap: 1rem; border: 1px solid var(--ui-border); border-radius: var(--ui-radius-lg); padding: .85rem; }
.persona-switcher__list li div { display: grid; gap: .2rem; }
.persona-switcher__list small { color: var(--ui-text-muted); }
.persona-switcher__create { display: grid; gap: .7rem; max-width: 28rem; }
.persona-switcher__create label { display: grid; gap: .25rem; }
.persona-switcher__error { color: var(--ui-danger); }
@media (max-width: 640px) { .persona-switcher__header { flex-direction: column; } .persona-switcher__list li { flex-wrap: wrap; } }
</style>
