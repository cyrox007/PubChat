<template>
  <section v-if="allowed" class="lexicon">
    <header class="lexicon__head">
      <div>
        <span class="lexicon__eyebrow">Настройки платформы · только администраторы</span>
        <h2>Словари и цензура</h2>
        <p>Проверяйте слова, фразы и варианты до включения. Пока работает только предпросмотр и shadow: сообщения пользователей не изменяются.</p>
      </div>
      <button class="ui-button ui-button--ghost" type="button" @click="expanded = !expanded">
        {{ expanded ? 'Свернуть' : 'Управлять правилами' }}
      </button>
    </header>
    <div class="lexicon__summary" aria-live="polite">
      <strong>Ревизия {{ policy.active_revision }}</strong>
      <span>Режим: {{ policy.mode === 'shadow' ? 'shadow — без блокировок' : 'выключен' }}</span>
      <span>{{ draft.length }} правил в редакторе</span>
      <span v-if="draftDirty" class="lexicon__warning">Есть несохранённые изменения</span>
    </div>
    <div v-if="expanded" class="lexicon__body">
      <p v-if="notice" role="status" :class="['lexicon__notice', error ? 'lexicon__notice--error' : '']">{{ notice }}</p>
      <div class="lexicon__toolbar">
        <label>Загрузить ревизию
          <select v-model.number="selectedRevision" :disabled="busy" @change="loadRevision">
            <option :value="0">Пустой словарь</option>
            <option v-for="rev in policy.revisions" :key="rev.revision" :value="rev.revision">#{{ rev.revision }} · {{ formatDate(rev.created_at) }}</option>
          </select>
        </label>
        <button type="button" class="ui-button ui-button--ghost" :disabled="busy || draft.length >= 200" @click="addRule">Добавить правило</button>
        <button type="button" class="ui-button ui-button--ghost" :disabled="busy" @click="refresh">Обновить</button>
      </div>
      <div class="lexicon__rules">
        <article v-for="(rule, index) in draft" :key="rule.uid" class="lexicon__rule">
          <div class="lexicon__row">
            <strong>Правило {{ index + 1 }}</strong>
            <label class="lexicon__toggle"><input v-model="rule.enabled" type="checkbox" @change="markDirty"> Активно</label>
            <button type="button" class="ui-button ui-button--ghost" :disabled="busy" @click="removeRule(index)">Удалить</button>
          </div>
          <div class="lexicon__grid">
            <label>Слово / фраза / основа
              <input v-model="rule.term" maxlength="120" placeholder="Введите выражение" @input="markDirty">
            </label>
            <label>Способ совпадения
              <select v-model="rule.match_mode" @change="markDirty">
                <option value="token">Точное слово</option>
                <option value="phrase">Фраза</option>
                <option value="stem">Основа слова и формы</option>
              </select>
            </label>
            <label>Язык
              <select v-model="rule.language" @change="markDirty"><option value="ru">Русский</option><option value="en">English</option></select>
            </label>
            <label>Категория
              <select v-model="rule.category" @change="markDirty">
                <option value="profanity">Нецензурная лексика</option>
                <option value="harassment">Оскорбления / травля</option>
                <option value="hate">Ненависть</option>
                <option value="fraud">Мошенничество</option>
                <option value="spam">Спам</option>
                <option value="other">Другое</option>
              </select>
            </label>
            <label>Строгость совпадения
              <select v-model="rule.severity" @change="markDirty"><option value="low">Низкая</option><option value="medium">Средняя</option><option value="high">Высокая</option></select>
            </label>
            <label>Области применения (можно выбрать несколько)
              <select v-model="rule.surfaces" multiple size="4" @change="markDirty">
                <option v-for="option in surfaceOptions" :key="option.value" :value="option.value">{{ option.label }}</option>
              </select>
              <small>«Везде» нельзя совмещать с другими областями.</small>
            </label>
            <label>Предлагаемое действие
              <select v-model="rule.action" @change="markDirty">
                <option value="warn">Предупредить</option>
                <option value="mask">Скрыть выражение</option>
                <option value="reject">Не допустить публикацию</option>
                <option value="hold">На проверку</option>
              </select>
            </label>
            <label>Варианты (каждый с новой строки)
              <textarea v-model="rule.variantsText" rows="2" maxlength="2400" placeholder="Формы и маскированные варианты" @input="markDirty"></textarea>
            </label>
            <label>Исключения (каждое с новой строки)
              <textarea v-model="rule.exceptionsText" rows="2" maxlength="2400" placeholder="Разрешённые выражения" @input="markDirty"></textarea>
            </label>
          </div>
        </article>
        <p v-if="!draft.length" class="lexicon__empty">Словарь пуст. Добавьте первое правило — по умолчанию публикации не фильтруются.</p>
      </div>
      <div class="lexicon__grid">
        <label>Основание изменения
          <input v-model="reason" maxlength="500" placeholder="Почему добавляются или меняются правила">
        </label>
        <div class="lexicon__toolbar">
          <button type="button" class="ui-button" :disabled="busy || !draftDirty" @click="saveDraft">Сохранить новую ревизию</button>
          <button type="button" class="ui-button ui-button--ghost" :disabled="busy || !savedRevision || draftDirty" @click="activateShadow">Опубликовать в shadow</button>
          <button type="button" class="ui-button ui-button--ghost" :disabled="busy" @click="disable">Выключить политику</button>
        </div>
      </div>
      <details class="lexicon__import">
        <summary>Импорт / экспорт JSON и сравнение ревизий</summary>
        <p>Импорт заменяет содержимое локального редактора. Проверьте текст в симуляторе перед сохранением ревизии.</p>
        <textarea v-model="importText" rows="3" maxlength="150000" placeholder="[{...}] — массив правил"></textarea>
        <div class="lexicon__toolbar">
          <button type="button" class="ui-button ui-button--ghost" :disabled="busy" @click="importRules">Импортировать в редактор</button>
          <button type="button" class="ui-button ui-button--ghost" :disabled="busy" @click="exportRules">Скопировать JSON правил</button>
          <button type="button" class="ui-button ui-button--ghost" :disabled="busy" @click="compareRevision">Сравнить с активной</button>
        </div>
        <p v-if="compareSummary" aria-live="polite">{{ compareSummary }}</p>
      </details>
      <section class="lexicon__simulator">
        <h3>Проверка правил на примере</h3>
        <p>Введите тестовое сообщение. Его содержимое отправляется только в привилегированный API предпросмотра, не сохраняется в журнале и не публикуется.</p>
        <label>Область текста
          <select v-model="sampleSurface">
            <option v-for="option in surfaceOptions" :key="option.value" :value="option.value" :disabled="option.value === 'all'">{{ option.label }}</option>
          </select>
        </label>
        <textarea v-model="sample" rows="3" maxlength="4000" placeholder="Пример текста..." aria-label="Текст для проверки"></textarea>
        <button type="button" class="ui-button ui-button--ghost" :disabled="busy || !sample.trim()" @click="simulate">Проверить текст</button>
        <div v-if="simulation" class="lexicon__result" aria-live="polite">
          <strong>Совпадений: {{ simulation.matches.length }}</strong>
          <p>Было бы запрещено: {{ simulation.would_block ? 'да' : 'нет' }} · Реальное применение: нет</p>
          <p class="lexicon__preview">{{ simulation.preview }}</p>
          <ul>
            <li v-for="(match, index) in simulation.matches" :key="index">
              {{ match.category }} · {{ match.action }} · {{ match.match_kind }} · {{ match.start }}–{{ match.end }}
            </li>
          </ul>
        </div>
      </section>
      <details>
        <summary>Журнал изменений политики</summary>
        <button class="ui-button ui-button--ghost" type="button" :disabled="busy" @click="loadAudit">Обновить журнал</button>
        <p v-if="!audit.length">Пока нет загруженных событий.</p>
        <ul>
          <li v-for="event in audit" :key="event.uid">
            {{ formatDate(event.created_at) }} — {{ event.action }}: #{{ event.previous_revision }} → #{{ event.next_revision }}, {{ event.previous_mode }} → {{ event.next_mode }}. {{ event.reason }}
          </li>
        </ul>
      </details>
    </div>
  </section>
</template>

<script setup>
import { onMounted, ref } from 'vue';
import ModerationService from '@/API/ModerationService';

const allowed = ref(false);
const expanded = ref(false);
const busy = ref(false);
const notice = ref('');
const error = ref(false);
const policy = ref({ active_revision: 0, mode: 'off', revisions: [] });
const draft = ref([]);
const draftDirty = ref(false);
const selectedRevision = ref(0);
const savedRevision = ref(0);
const reason = ref('');
const sample = ref('');
const simulation = ref(null);
const audit = ref([]);
const importText = ref('');
const compareSummary = ref('');
const sampleSurface = ref('space_chat');
const surfaceOptions = [
  { value: 'all', label: 'Везде (plaintext)' }, { value: 'space_chat', label: 'Сообщения Space' },
  { value: 'messenger_plaintext', label: 'Обычные личные сообщения' }, { value: 'profile', label: 'Профили' },
  { value: 'activity', label: 'Активности' }, { value: 'post', label: 'Посты' },
  { value: 'comment', label: 'Комментарии' }, { value: 'story', label: 'Истории' },
  { value: 'reel', label: 'Рилсы' }, { value: 'media_caption', label: 'Подписи медиа' },
];

const flash = (message, failed = false) => { notice.value = message; error.value = failed; };
const formatDate = (date) => date ? new Date(date).toLocaleString('ru-RU') : '';
const toEditor = (item) => ({
  ...item, uid: item.uid || crypto.randomUUID(),
  variantsText: (item.variants || []).join('\n'),
  exceptionsText: (item.exceptions || []).join('\n'),
  severity: item.severity || 'medium', surfaces: item.surfaces || ['all'],
});
const toWire = (item) => ({
  uid: item.uid, term: item.term.trim(), language: item.language,
  category: item.category, match_mode: item.match_mode, action: item.action,
  enabled: item.enabled, severity: item.severity, surfaces: item.surfaces,
  variants: item.variantsText.split('\n').map(x => x.trim()).filter(Boolean),
  exceptions: item.exceptionsText.split('\n').map(x => x.trim()).filter(Boolean),
});
const wireRules = () => draft.value.map(toWire);
const markDirty = () => { draftDirty.value = true; simulation.value = null; compareSummary.value = ''; };
const importRules = () => {
  try {
    const parsed = JSON.parse(importText.value);
    if (!Array.isArray(parsed) || parsed.length > 200 || parsed.some(x => !x || typeof x !== 'object' || typeof x.term !== 'string')) throw Error('invalid rules');
    draft.value = parsed.map(toEditor);
    markDirty();
    flash('Правила загружены в редактор. Проверьте их и сохраните ревизию.');
  } catch { flash('Некорректный JSON-массив правил (до 200 элементов).', true); }
};
const exportRules = async () => {
  try { await navigator.clipboard.writeText(JSON.stringify(wireRules(), null, 2)); flash('JSON словаря скопирован.'); }
  catch { flash('Буфер обмена недоступен. Нужен защищённый браузер.', true); }
};
const compareRevision = async () => {
  try {
    const base = (await ModerationService.lexiconRevision(policy.value.active_revision)).data.revision.rules || [];
    const stable = x => JSON.stringify(Object.keys(x).sort().map(key => [key, x[key]]));
    const before = new Map(base.map(x => [x.uid, stable(x)]));
    const after = new Map(wireRules().map(x => [x.uid, stable(x)]));
    const added = [...after.keys()].filter(id => !before.has(id)).length;
    const removed = [...before.keys()].filter(id => !after.has(id)).length;
    const changed = [...after.keys()].filter(id => before.has(id) && before.get(id) !== after.get(id)).length;
    compareSummary.value = `Относительно #${policy.value.active_revision}: добавлено ${added}, удалено ${removed}, изменено ${changed}.`;
  } catch { flash('Сравнение ревизий не удалось.', true); }
};
const addRule = () => {
  draft.value.push(toEditor({ uid: crypto.randomUUID(), term: '', language: 'ru', category: 'profanity', match_mode: 'token', action: 'mask', severity: 'medium', surfaces: ['all'], enabled: true }));
  markDirty();
};
const removeRule = (index) => { draft.value.splice(index, 1); markDirty(); };

const refresh = async () => {
  busy.value = true;
  try {
    const response = await ModerationService.lexiconPolicy();
    allowed.value = true;
    policy.value = response.data.policy;
    selectedRevision.value = policy.value.active_revision;
    savedRevision.value = policy.value.active_revision;
    draft.value = (policy.value.active_rules || []).map(toEditor);
    draftDirty.value = false;
    simulation.value = null;
    flash('');
  } catch (exc) {
    if (exc.response?.status === 403) allowed.value = false;
    else flash('Не удалось загрузить словарь. Проверьте соединение и миграции.', true);
  } finally { busy.value = false; }
};
const loadRevision = async () => {
  busy.value = true;
  try {
    const res = await ModerationService.lexiconRevision(selectedRevision.value);
    draft.value = (res.data.revision.rules || []).map(toEditor);
    savedRevision.value = selectedRevision.value;
    draftDirty.value = false;
    simulation.value = null;
  } catch { flash('Не удалось загрузить ревизию.', true); }
  finally { busy.value = false; }
};
const saveDraft = async () => {
  busy.value = true;
  try {
    const res = await ModerationService.saveLexiconRevision({ rules: wireRules(), reason: reason.value });
    savedRevision.value = res.data.revision.revision;
    selectedRevision.value = savedRevision.value;
    draftDirty.value = false;
    flash('Черновик #' + savedRevision.value + ' сохранён. Пока никого не фильтрует.');
    const p = await ModerationService.lexiconPolicy();
    policy.value = p.data.policy;
  } catch (exc) { flash('Не удалось сохранить: проверьте длину выражений, основы слов, варианты и причину.', true); }
  finally { busy.value = false; }
};
const setMode = async (revision, mode) => {
  busy.value = true;
  try {
    await ModerationService.activateLexiconRevision({ revision, mode, reason: reason.value });
    const p = await ModerationService.lexiconPolicy();
    policy.value = p.data.policy;
    flash(mode === 'shadow' ? 'Ревизия активна только в shadow. Автоматической цензуры сообщений пока нет.' : 'Политика выключена.');
  } catch { flash('Не удалось изменить политику. Укажите причину не менее пяти символов.', true); }
  finally { busy.value = false; }
};
const activateShadow = () => setMode(savedRevision.value, 'shadow');
const disable = () => setMode(policy.value.active_revision, 'off');
const simulate = async () => {
  busy.value = true;
  try {
    const result = await ModerationService.simulateLexicon({ text: sample.value, surface: sampleSurface.value, rules: wireRules() });
    simulation.value = result.data.simulation;
    flash('Результат рассчитан. Тестовый текст не был опубликован.');
  } catch { flash('Проверка не выполнена: проверьте корректность правил и соединение.', true); }
  finally { busy.value = false; }
};
const loadAudit = async () => {
  busy.value = true;
  try { audit.value = (await ModerationService.lexiconAudit({ limit: 50 })).data.events || []; }
  catch { flash('Не удалось загрузить аудит.', true); }
  finally { busy.value = false; }
};
onMounted(refresh);
</script>

<style scoped>
.lexicon { border:1px solid var(--ui-border);border-radius:var(--ui-radius-xl);background:var(--ui-surface);padding:clamp(1rem,2vw,1.5rem);display:grid;gap:1rem }
.lexicon__head,.lexicon__toolbar,.lexicon__row {display:flex;align-items:center;justify-content:space-between;gap:.75rem;flex-wrap:wrap}
.lexicon__head h2{margin:.3rem 0}.lexicon__head p,.lexicon__simulator p{color:var(--ui-text-muted);margin:.3rem 0;max-width:54rem}
.lexicon__eyebrow{font-weight:700;font-size:.73rem;color:var(--ui-primary);text-transform:uppercase}
.lexicon__summary{display:flex;gap:.7rem;align-items:center;flex-wrap:wrap;font-size:.84rem;color:var(--ui-text-muted)}
.lexicon__summary>*{padding:.25rem .5rem;border-radius:.5rem;background:var(--ui-surface-muted)}
.lexicon__warning{color:var(--ui-danger)!important}
.lexicon__body,.lexicon__rules,.lexicon__rule,.lexicon__simulator{display:grid;gap:.75rem}
.lexicon__rule,.lexicon__simulator{border:1px solid var(--ui-border);border-radius:var(--ui-radius-lg);padding:1rem}
.lexicon__grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,13rem),1fr));gap:.75rem}
.lexicon label{display:grid;gap:.35rem;font-size:.83rem}
.lexicon input,.lexicon select,.lexicon textarea{width:100%;border:1px solid var(--ui-border);border-radius:var(--ui-radius-md);padding:.55rem .65rem;background:var(--ui-surface);color:var(--ui-text)}
.lexicon .lexicon__toggle{display:flex;align-items:center}.lexicon__toggle input{width:auto}
.lexicon__notice{padding:.65rem;border-radius:var(--ui-radius-md);background:var(--ui-primary-soft)}.lexicon__notice--error{background:var(--ui-danger-soft);color:var(--ui-danger)}
.lexicon__result{padding:.85rem;border-radius:var(--ui-radius-md);background:var(--ui-surface-muted)}
.lexicon__preview{white-space:pre-wrap;overflow-wrap:anywhere}
.lexicon__empty{color:var(--ui-text-muted)}
@media(max-width:700px){.lexicon__head{display:grid}.lexicon__head button{justify-self:start}.lexicon__toolbar>*{max-width:100%}}
</style>
