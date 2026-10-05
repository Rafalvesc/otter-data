"use strict";

// Otter Data UI. All model- and database-derived text is inserted with textContent; never as HTML.

const SUGGESTIONS = [
  "Qual foi a receita recebida em setembro de 2026?",
  "Quais regiões tiveram maior receita recebida em setembro de 2026?",
  "Como a receita recebida evoluiu de janeiro a setembro de 2026?",
  "Qual produto mais vale a pena vender?",
  "Como estão as vendas?",
  "Quantos pedidos existem por status?",
].map((question) => t(question));

const MONEY_COLUMN = /(amount|price|revenue|receita|valor|preco|faturamento)/i;
// Only the sample base documents its currency (BRL); connected sources never assume one.
const isMoney = (data, column) => (!data.source_id || data.source_id === "sample") && MONEY_COLUMN.test(column);

const METRIC_LABELS = {
  received_revenue: t("Receita recebida"),
  new_customers: t("Novos clientes"),
  cancelled_orders: t("Pedidos cancelados"),
};

const ICONS = {
  arrow: "M5 12h14M13 6l6 6-6 6",
  chev: "M9 6l6 6-6 6",
  chevLeft: "M15 6l-6 6 6 6",
  cloud: "M7 18a4.5 4.5 0 0 1-.6-8.96A6 6 0 0 1 17.7 9.2 4.4 4.4 0 0 1 17.5 18z",
  gear: "M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2zM12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z",
  refresh: "M20 11a8 8 0 0 0-14.9-3.9L4 9M4 4v5h5M4 13a8 8 0 0 0 14.9 3.9L20 15M20 20v-5h-5",
  trash: "M4 7h16M10 11v6M14 11v6M5 7l1 13h12l1-13M9 7V4h6v3",
  send: "M12 19V5M6 11l6-6 6 6",
  check: "M5 12.5l4.5 4.5L19 7",
  x: "M6 6l12 12M18 6 6 18",
  alert: "M12 8v5M12 16.5v.01M10.3 3.9 2.4 17.6A2 2 0 0 0 4.1 20.6h15.8a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z",
  list: "M9 6h11M9 12h11M9 18h11M4.5 6h.01M4.5 12h.01M4.5 18h.01",
  db: "M4 6c0-1.7 3.6-3 8-3s8 1.3 8 3-3.6 3-8 3-8-1.3-8-3zM4 6v12c0 1.7 3.6 3 8 3s8-1.3 8-3V6M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3",
  cpu: "M7 7h10v10H7zM10 3v4M14 3v4M10 17v4M14 17v4M3 10h4M3 14h4M17 10h4M17 14h4",
  rows: "M4 5h16v14H4zM4 10h16M4 15h16",
  sparkle: "M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z",
};

const AVATAR_IMG = "/static/assets/otter-face.webp";
const MASCOT_IMG = "/static/assets/otter-mascot.webp";
const $ = (selector) => document.querySelector(selector);
const SVG_NS = "http://www.w3.org/2000/svg";

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value === undefined || value === null || value === false) continue;
    if (key === "class") node.className = value;
    else if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
    else node.setAttribute(key, value === true ? "" : value);
  }
  for (const child of children.flat(Infinity)) {
    if (child === null || child === undefined || child === false) continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}

function svg(tag, attrs = {}) {
  const node = document.createElementNS(SVG_NS, tag);
  for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value);
  return node;
}

function icon(name, className) {
  const node = svg("svg", { viewBox: "0 0 24 24", "aria-hidden": "true" });
  if (className) node.setAttribute("class", className);
  node.append(svg("path", { d: ICONS[name] }));
  return node;
}

/* ---------- Storage (best effort; the page works without it) ---------- */

const store = {
  get(key, fallback) {
    try {
      const value = localStorage.getItem(key);
      return value === null ? fallback : JSON.parse(value);
    } catch {
      return fallback;
    }
  },
  set(key, value) {
    try {
      localStorage.setItem(key, JSON.stringify(value));
    } catch {
      /* storage unavailable */
    }
  },
};

/* ---------- Formatting ---------- */

const LOCALE = I18N.locale;
const brl = new Intl.NumberFormat(LOCALE, { style: "currency", currency: "BRL" });
const integer = new Intl.NumberFormat(LOCALE, { maximumFractionDigits: 0 });
const compactNumber = new Intl.NumberFormat(LOCALE, { notation: "compact", maximumFractionDigits: 1 });
const compactMoney = new Intl.NumberFormat(LOCALE, { style: "currency", currency: "BRL", notation: "compact", maximumFractionDigits: 1 });
const percent = new Intl.NumberFormat(LOCALE, { style: "percent", maximumFractionDigits: 1 });
const signedPercent = new Intl.NumberFormat(LOCALE, { style: "percent", maximumFractionDigits: 1, signDisplay: "exceptZero" });
const oneDecimal = new Intl.NumberFormat(LOCALE, { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const monthShort = new Intl.DateTimeFormat(LOCALE, { month: "short", year: "2-digit", timeZone: "UTC" });
const monthLong = new Intl.DateTimeFormat(LOCALE, { month: "long", year: "numeric", timeZone: "UTC" });
const dayFormat = new Intl.DateTimeFormat(LOCALE, { timeZone: "UTC" });

const isMonetary = (metric) => metric === "received_revenue";
const formatValue = (value, monetary) => (monetary ? brl.format(value) : integer.format(value));
const formatCompact = (value, monetary) => (monetary ? compactMoney : compactNumber).format(value);
const capitalize = (text) => text.charAt(0).toUpperCase() + text.slice(1);
const pad = (number, size = 3) => String(number).padStart(size, "0");

function parseDate(iso) {
  return new Date(`${String(iso).slice(0, 10)}T00:00:00Z`);
}

function formatPeriod(period) {
  if (!period) return null;
  const last = parseDate(period.end_exclusive);
  last.setUTCDate(last.getUTCDate() - 1);
  return t("{start} a {end}", { start: dayFormat.format(parseDate(period.start)), end: dayFormat.format(last) });
}

function formatMonth(iso, long = false) {
  const date = parseDate(iso);
  if (long) return capitalize(monthLong.format(date));
  const month = monthShort.formatToParts(date).find((part) => part.type === "month").value.replace(".", "");
  return `${capitalize(month)}/${String(date.getUTCFullYear()).slice(-2)}`;
}

function toast(message) {
  const node = $("#toast");
  node.replaceChildren(icon("check"), el("span", {}, message));
  node.hidden = false;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => { node.hidden = true; }, 1800);
}

/* ---------- Theme & rail ---------- */

function applyTheme(theme) {
  if (theme) document.documentElement.dataset.theme = theme;
  else delete document.documentElement.dataset.theme;
}

function currentTheme() {
  return document.documentElement.dataset.theme
    || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
}

applyTheme(store.get("otterdata.theme", null));

/* ---------- Confirmation (in-app, never the browser's own dialog) ---------- */

function confirmAction({ kicker = t("Confirmação"), title, message, confirmLabel }) {
  const dialog = $("#confirm-dialog");
  $("#confirm-kicker").textContent = kicker;
  $("#confirm-title").textContent = title;
  $("#confirm-message").textContent = message;
  $("#confirm-accept").textContent = confirmLabel;
  dialog.returnValue = "";
  dialog.showModal();
  return new Promise((resolve) => {
    dialog.addEventListener("close", () => resolve(dialog.returnValue === "confirm"), { once: true });
  });
}

function setRail(open) {
  $("#rail").classList.toggle("open", open);
}

/* ---------- Provider status ---------- */

async function loadStatus() {
  const dot = $("#provider-dot");
  try {
    const response = await fetch("/api/v1/status");
    if (!response.ok) throw new Error(String(response.status));
    const status = await response.json();
    $("#api-dot").className = "pulse ok";
    $("#api-state").textContent = "Online";
    $("#provider-title").textContent = t(status.demo_mode ? "Demonstração" : status.configured ? "Pronto" : "Sem configuração");
    if (!models.length) $("#provider-detail").textContent = status.model || t("não informado");
    dot.className = `pulse ${status.configured ? (status.demo_mode ? "warn" : "ok") : "bad"}`;
    if (models.length) renderModelPill();
  } catch {
    $("#api-dot").className = "pulse bad";
    $("#api-state").textContent = t("Offline");
    $("#provider-title").textContent = t("Sem resposta");
    dot.className = "pulse bad";
    setRunState(t("Offline"));
  }
}

/* ---------- Model picker ---------- */

const LOCATION_LABELS = {
  cloud: t("Na nuvem (Ollama)"),
  local: t("Neste computador (Ollama)"),
  demo: t("Demonstração"),
};
const LOCATION_ICONS = { cloud: "cloud", local: "cpu", demo: "sparkle" };
let models = [];
let defaultModel = null;
let currentModel = store.get("otterdata.model", null);

function modelById(id) {
  return models.find((model) => model.id === id);
}

function selectedModel() {
  return modelById(currentModel) || modelById(defaultModel) || models[0];
}

async function loadModels() {
  try {
    const data = await api("/api/v1/models");
    models = data.models;
    defaultModel = data.default;
  } catch {
    models = [];
  }
  renderModelPill();
}

function renderModelPill() {
  const model = selectedModel();
  const pill = $("#model-button");
  $("#model-label").textContent = model ? model.model : t("Modelo");
  pill.classList.toggle("set", Boolean(model && model.id !== defaultModel));
  pill.replaceChildren(icon(model ? LOCATION_ICONS[model.location] : "cpu"), $("#model-label"));
  if (model) {
    $("#provider-detail").textContent = model.model;
    if ($("#provider-dot").classList.contains("ok")) {
      const where = { local: "Pronto, local", cloud: "Pronto, na nuvem", demo: "Demonstração" };
      $("#provider-title").textContent = t(where[model.location] || "Pronto");
    }
  }
}

function chooseModel(id) {
  currentModel = id;
  store.set("otterdata.model", id);
  renderModelPill();
  const model = selectedModel();
  if (model?.location === "local") toast(t("Modelo local: mais lento e, se for pequeno, erra mais SQL"));
  else toast(t("Modelo: {name}", { name: model?.model }));
}

function toggleModelMenu(open) {
  const menu = $("#model-menu");
  const show = open ?? menu.hidden;
  if (show) {
    const groups = {};
    for (const model of models) (groups[model.location] ||= []).push(model);
    const current = selectedModel();
    menu.replaceChildren(
      ...Object.entries(groups).flatMap(([location, items]) => [
        el("span", { class: "menu-group" }, LOCATION_LABELS[location] || location),
        ...items.map((model) => el("button", {
          type: "button",
          role: "menuitemradio",
          class: "source-option",
          "aria-checked": String(model.id === current?.id),
          onclick: () => {
            toggleModelMenu(false);
            chooseModel(model.id);
          },
        },
        el("span", { class: `kind-badge model-${model.location}` }, icon(LOCATION_ICONS[model.location])),
        el("span", { class: "source-option-text" },
          el("strong", {}, model.model),
          el("small", {}, [
            model.id === defaultModel ? t("padrão") : null,
            model.parameters,
            model.size,
            model.location === "local" ? t("roda nesta máquina") : null,
          ].filter(Boolean).join(" · ") || LOCATION_LABELS[model.location])),
        model.id === current?.id ? icon("check", "tick") : null)),
      ]),
      el("p", { class: "menu-hint" }, t("Modelos locais aparecem aqui depois de "), el("code", {}, t("ollama pull <modelo>")),
        t(". Modelos pequenos (até ~7B) costumam errar mais o SQL; o validador bloqueia o que estiver fora da política.")),
    );
  }
  menu.hidden = !show;
  $("#model-button").setAttribute("aria-expanded", String(show));
}

/* ---------- Reference date calendar ---------- */

const WEEKDAYS = I18N.lang === "en" ? ["S", "M", "T", "W", "T", "F", "S"] : ["D", "S", "T", "Q", "Q", "S", "S"];
const monthTitle = new Intl.DateTimeFormat(LOCALE, { month: "long", year: "numeric", timeZone: "UTC" });
const fullDay = new Intl.DateTimeFormat(LOCALE, { dateStyle: "full", timeZone: "UTC" });
let calendarView = null;

function isoDate(date) {
  return date.toISOString().slice(0, 10);
}

function todayIso() {
  const now = new Date();
  return isoDate(new Date(Date.UTC(now.getFullYear(), now.getMonth(), now.getDate())));
}

function setReferenceDate(value) {
  $("#reference-date").value = value || "";
  $("#date-label").textContent = value ? t("Ref. {date}", { date: dayFormat.format(parseDate(value)) }) : t("Ref. hoje");
  $("#date-button").classList.toggle("set", Boolean(value));
}

function openCalendar() {
  const value = $("#reference-date").value || todayIso();
  const date = parseDate(value);
  calendarView = new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), 1));
  renderCalendar();
  $("#calendar").hidden = false;
  $("#date-button").setAttribute("aria-expanded", "true");
  $("#calendar .day.selected, #calendar .day.today")?.focus();
}

function closeCalendar(returnFocus) {
  if ($("#calendar").hidden) return;
  $("#calendar").hidden = true;
  $("#date-button").setAttribute("aria-expanded", "false");
  if (returnFocus) $("#date-button").focus();
}

function shiftMonth(delta) {
  calendarView = new Date(Date.UTC(calendarView.getUTCFullYear(), calendarView.getUTCMonth() + delta, 1));
  renderCalendar();
}

function renderCalendar() {
  const selected = $("#reference-date").value;
  const today = todayIso();
  const year = calendarView.getUTCFullYear();
  const month = calendarView.getUTCMonth();
  const offset = new Date(Date.UTC(year, month, 1)).getUTCDay();
  const length = new Date(Date.UTC(year, month + 1, 0)).getUTCDate();
  const cells = [];
  for (let index = 0; index < offset; index += 1) cells.push(el("span", { class: "day blank", "aria-hidden": "true" }));
  for (let day = 1; day <= length; day += 1) {
    const iso = isoDate(new Date(Date.UTC(year, month, day)));
    const classes = ["day", iso === today ? "today" : "", iso === selected ? "selected" : ""].filter(Boolean).join(" ");
    cells.push(el("button", {
      type: "button",
      class: classes,
      "aria-label": fullDay.format(parseDate(iso)),
      "aria-pressed": String(iso === selected),
      onclick: () => {
        setReferenceDate(iso);
        closeCalendar(true);
      },
    }, String(day)));
  }
  $("#calendar").replaceChildren(
    el("div", { class: "cal-head" },
      el("button", { type: "button", class: "cal-nav", "aria-label": t("Mês anterior"), onclick: () => shiftMonth(-1) }, icon("chevLeft")),
      el("strong", {}, capitalize(monthTitle.format(calendarView))),
      el("button", { type: "button", class: "cal-nav", "aria-label": t("Próximo mês"), onclick: () => shiftMonth(1) }, icon("chev")),
    ),
    el("div", { class: "cal-grid cal-weekdays", "aria-hidden": "true" }, WEEKDAYS.map((name) => el("span", {}, name))),
    el("div", { class: "cal-grid" }, cells),
    el("div", { class: "cal-foot" },
      el("button", { type: "button", class: "cal-link", onclick: () => { setReferenceDate(""); closeCalendar(true); } }, t("Usar hoje")),
      el("span", { class: "cal-hint" }, t("Base para “este mês”, “ontem”…")),
    ),
  );
}

/* ---------- Water loader ---------- */

function wavePath(width, base, amplitude, length) {
  let path = `M0 ${base}`;
  for (let x = 0; x < width; x += length) path += ` q${length / 4} ${-amplitude} ${length / 2} 0 t${length / 2} 0`;
  return path;
}

// The otter floats over moving water while data points cross it: a 1.2 s loop that reads well
// even when an answer arrives after a second.
function otterAfloat() {
  const water = svg("svg", { class: "afloat-water", viewBox: "0 0 240 24", preserveAspectRatio: "none", "aria-hidden": "true" });
  water.append(
    svg("path", { class: "afloat-wave back", d: wavePath(480, 9, 4, 60) }),
    svg("path", { class: "afloat-wave front", d: wavePath(480, 15, 4, 40) }),
    ...[0, 1, 2].map((index) => svg("circle", { class: `afloat-dot d${index}`, cx: -6, cy: 12, r: 1.6 })),
  );
  return el("div", { class: "afloat", "aria-hidden": "true" },
    el("img", { class: "afloat-otter", src: MASCOT_IMG, alt: "", width: 72, height: 48 }),
    water);
}

// Steps shown while the analysis runs, updated from the graph nodes the server reports.
const LOADING_STEPS = ["Interpretação", "Catálogo", "Consulta", "Validação", "Execução", "Evidência"].map((name) => t(name));
const NODE_DONE = { interpret: 0, plan: 1, generate: 2, validate: 3, execute: 4, narrate: 5 };
const STEP_LABELS = { wait: t("aguardando"), run: t("analisando"), ok: t("ok"), skip: t("não necessária") };

/* ---------- Data sources ---------- */

const SAMPLE_SOURCE = "sample";
const KIND_LABELS = { sample: t("Exemplo"), postgres: "PostgreSQL", mysql: "MySQL", mongodb: "MongoDB", csv: "CSV" };
const KIND_ICONS = { sample: "sparkle", postgres: "db", mysql: "db", mongodb: "db", csv: "rows" };
const DEFAULT_PORTS = { postgres: "5432", mysql: "3306", mongodb: "27017" };
let sources = [];
let currentSourceId = store.get("otterdata.source", SAMPLE_SOURCE);

function sourceById(id) {
  return sources.find((source) => source.id === id);
}

function currentSource() {
  return sourceById(currentSourceId);
}

async function api(path, options = {}) {
  const response = await fetch(path, options);
  if (response.status === 204) return null;
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = Array.isArray(data.detail) ? t("Confira os campos preenchidos.") : tm(data.detail);
    throw new Error(detail || t("Não foi possível concluir (erro {status}).", { status: response.status }));
  }
  return data;
}

async function loadSources() {
  try {
    // Names and locations of the built-in sample are server text; the user's own are kept as typed.
    sources = (await api("/api/v1/sources")).sources.map((source) => ({
      ...source,
      name: source.built_in ? tm(source.name) : source.name,
      location: tm(source.location),
    }));
  } catch {
    sources = [];
  }
  renderSourceChip();
  renderSourceList();
}

function renderSourceChip() {
  const source = currentSource();
  $("#source-label").textContent = source ? source.name : t("Base indisponível");
  $("#source-button").title = source ? `${KIND_LABELS[source.kind]} · ${source.location}` : t("Esta base foi removida");
  $("#source-button").classList.toggle("own", Boolean(source && !source.built_in));
  $("#sys-source").textContent = source ? source.name : t("Indisponível");
  $("#sys-source-meta").textContent = source
    ? t("{kind}, {count} tabelas", { kind: KIND_LABELS[source.kind], count: source.tables })
    : t("removida");
  $("#source-dot").className = `pulse ${source ? "ok" : "bad"}`;
  renderStarters();
}

function rememberSource(id) {
  currentSourceId = id;
  store.set("otterdata.source", id);
  renderSourceChip();
  renderSourceList();
}

function chooseSource(id) {
  if (id === currentSourceId) return;
  const conversation = loadConversations().find((item) => item.id === activeId);
  rememberSource(id);
  // A conversation always talks to a single base: switching starts a fresh one.
  if (conversation) resetChat();
  toast(t("Conversando com: {name}", { name: currentSource()?.name ?? t("base") }));
}

function toggleSourceMenu(open) {
  const menu = $("#source-menu");
  const show = open ?? menu.hidden;
  if (show) {
    menu.replaceChildren(
      ...sources.map((source) => el("button", {
        type: "button",
        role: "menuitemradio",
        class: "source-option",
        "aria-checked": String(source.id === currentSourceId),
        onclick: () => {
          toggleSourceMenu(false);
          chooseSource(source.id);
        },
      },
      el("span", { class: `kind-badge ${source.kind}` }, icon(KIND_ICONS[source.kind])),
      el("span", { class: "source-option-text" },
        el("strong", {}, source.name),
        el("small", {}, t("{kind} · {count} tabelas", { kind: KIND_LABELS[source.kind], count: source.tables }))),
      source.id === currentSourceId ? icon("check", "tick") : null)),
      el("button", {
        type: "button",
        class: "source-manage",
        onclick: () => {
          toggleSourceMenu(false);
          openSettings();
        },
      }, icon("gear"), t("Gerenciar bases…")),
    );
  }
  menu.hidden = !show;
  $("#source-button").setAttribute("aria-expanded", String(show));
}

/* ---------- Settings dialog ---------- */

// `pane` ("db-form" or "csv-form") opens the dialog straight on that way of adding a source.
function openSettings(pane) {
  setRail(false);
  loadSources();
  $("#settings").showModal();
  if (typeof pane !== "string") return;
  $(`#add-tabs [data-pane="${pane}"]`).click();
  $(".add-source").scrollIntoView({ block: "start" });
  $(`#${pane}`).querySelector("input:not([type=radio])").focus();
}

function closeSettings() {
  $("#settings").close();
}

function setStatus(form, message, kind) {
  const status = form.querySelector(".form-status");
  status.textContent = message || "";
  status.className = `form-status${kind ? ` ${kind}` : ""}`;
}

function renderSourceList() {
  const list = $("#source-list");
  if (!list) return;
  list.replaceChildren(...sources.map(sourceCard));
}

function sourceCard(source) {
  const current = source.id === currentSourceId;
  const structure = el("div", { class: "source-structure", hidden: true });
  const allow = el("input", {
    type: "checkbox",
    checked: source.allow_rows_to_llm,
    disabled: source.built_in,
    onchange: async (event) => {
      const input = event.currentTarget;
      try {
        await api(`/api/v1/sources/${source.id}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ allow_rows_to_llm: input.checked }),
        });
        source.allow_rows_to_llm = input.checked;
        toast(t(input.checked ? "A IA poderá ler os resultados desta base" : "A IA não lerá os resultados desta base"));
      } catch (error) {
        input.checked = !input.checked;
        toast(error.message);
      }
    },
  });
  const facts = [t("{count} tabelas", { count: source.tables }), t("{count} colunas", { count: source.columns })];
  if (source.hidden_columns) facts.push(t("{count} ocultas por privacidade", { count: source.hidden_columns }));
  if (source.metrics) facts.push(t("métricas versionadas"));
  return el("li", { class: `source-card${current ? " current" : ""}` },
    el("div", { class: "source-card-head" },
      el("span", { class: `kind-badge ${source.kind}` }, icon(KIND_ICONS[source.kind]), KIND_LABELS[source.kind]),
      el("strong", {}, source.name),
      current ? el("span", { class: "tag current-tag" }, t("Nesta conversa")) : null,
    ),
    el("p", { class: "source-meta" }, source.location),
    el("p", { class: "source-meta" }, facts.join(" · ")),
    el("label", { class: "switch" }, allow, el("span", { class: "track", "aria-hidden": "true" }),
      el("span", {}, t(source.built_in ? "IA pode ler os resultados (dados sintéticos)" : "IA pode ler os resultados"))),
    el("div", { class: "source-actions" },
      current ? null : el("button", {
        type: "button",
        class: "ghost-button",
        onclick: () => {
          chooseSource(source.id);
          closeSettings();
        },
      }, icon("arrow"), t("Usar nesta conversa")),
      source.built_in ? null : el("button", {
        type: "button",
        class: "ghost-button",
        "aria-expanded": "false",
        onclick: (event) => toggleStructure(source, structure, event.currentTarget),
      }, icon("list"), t("Ver estrutura")),
      source.built_in ? null : el("button", {
        type: "button",
        class: "ghost-button",
        onclick: (event) => refreshSource(source, event.currentTarget),
      }, icon("refresh"), t("Atualizar")),
      source.built_in ? null : el("button", {
        type: "button",
        class: "ghost-button danger",
        onclick: () => removeSource(source),
      }, icon("trash"), t("Remover")),
    ),
    structure,
  );
}

async function toggleStructure(source, container, button) {
  if (!container.hidden) {
    container.hidden = true;
    button.setAttribute("aria-expanded", "false");
    return;
  }
  container.replaceChildren(el("p", { class: "note" }, t("Carregando estrutura…")));
  container.hidden = false;
  button.setAttribute("aria-expanded", "true");
  try {
    const detail = await api(`/api/v1/sources/${source.id}`);
    container.replaceChildren(
      el("ul", { class: "structure-list" }, Object.entries(detail.catalog).map(([table, spec]) =>
        el("li", {},
          el("code", {}, `${detail.schema_name}.${table}`),
          el("span", {}, Object.keys(spec.columns).join(", ")),
          spec.hidden_columns.length ? el("small", {}, t("Ocultas: {columns}", { columns: spec.hidden_columns.join(", ") })) : null))),
      ...(detail.skipped.length
        ? [el("p", { class: "note" }, t("Ignorados (nomes fora do padrão): {items}", { items: detail.skipped.map(tm).join("; ") }))]
        : []),
    );
  } catch (error) {
    container.replaceChildren(el("p", { class: "note" }, error.message));
  }
}

async function refreshSource(source, button) {
  button.disabled = true;
  try {
    await api(`/api/v1/sources/${source.id}/refresh`, { method: "POST" });
    toast(t("Estrutura atualizada"));
    await loadSources();
  } catch (error) {
    toast(error.message);
    button.disabled = false;
  }
}

async function removeSource(source) {
  const confirmed = await confirmAction({
    kicker: t("Bases de dados / remover"),
    title: t("Remover a base \"{name}\"?", { name: source.name }),
    message: t("A conexão e a senha salva serão apagadas deste aparelho. Os dados no seu banco não são alterados."),
    confirmLabel: t("Remover base"),
  });
  if (!confirmed) return;
  try {
    await api(`/api/v1/sources/${source.id}`, { method: "DELETE" });
    if (source.id === currentSourceId) chooseSource(SAMPLE_SOURCE);
    toast(t("Base removida"));
    await loadSources();
  } catch (error) {
    toast(error.message);
  }
}

async function connectDatabase(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const data = new FormData(form);
  const payload = {
    name: data.get("name").trim(),
    kind: data.get("kind"),
    host: data.get("host").trim(),
    port: Number(data.get("port")),
    database: data.get("database").trim(),
    user: data.get("user").trim(),
    password: data.get("password"),
    schema_name: data.get("schema_name").trim() || null,
    allow_rows_to_llm: data.get("allow_rows_to_llm") === "on",
  };
  form.elements.password.value = ""; // never keep the password in the page longer than needed
  const mongodb = payload.kind === "mongodb";
  if (!payload.name || !payload.host || !payload.database || (!payload.user && !mongodb)) {
    setStatus(form, t("Preencha nome, servidor, banco e usuário."), "error");
    return;
  }
  const button = form.querySelector("[type=submit]");
  button.disabled = true;
  setStatus(form, t(mongodb ? "Lendo as coleções e montando a cópia local…" : "Conectando e lendo a estrutura do banco…"), "busy");
  try {
    const created = await api("/api/v1/sources/database", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    form.reset();
    syncDatabaseKind(form);
    setStatus(form, t("Conectado: {count} tabelas encontradas.", { count: created.tables }), "ok");
    await loadSources();
    chooseSource(created.id);
  } catch (error) {
    setStatus(form, error.message, "error");
  } finally {
    button.disabled = false;
  }
}

async function importCsv(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const name = form.elements.name.value.trim();
  const files = [...form.elements.files.files];
  const allow = form.elements.allow_rows_to_llm.checked;
  if (!name || !files.length) {
    setStatus(form, t("Dê um nome e escolha pelo menos um arquivo CSV."), "error");
    return;
  }
  const button = form.querySelector("[type=submit]");
  button.disabled = true;
  let created = null;
  try {
    for (const [index, file] of files.entries()) {
      setStatus(form, t("Importando {file} ({index} de {total})…", { file: file.name, index: index + 1, total: files.length }), "busy");
      const params = new URLSearchParams({ filename: file.name });
      if (!created) {
        params.set("name", name);
        params.set("allow_rows_to_llm", String(allow));
        created = await api(`/api/v1/sources/csv?${params}`, { method: "POST", headers: { "Content-Type": "text/csv" }, body: file });
      } else {
        created = await api(`/api/v1/sources/${created.id}/csv?${params}`, { method: "POST", headers: { "Content-Type": "text/csv" }, body: file });
      }
    }
    form.reset();
    updateFileLabel(form);
    setStatus(form, t("Importado: {tables} tabela(s), {columns} colunas.", { tables: created.tables, columns: created.columns }), "ok");
    await loadSources();
    chooseSource(created.id);
  } catch (error) {
    setStatus(form, created ? t("{message} (os arquivos anteriores foram importados)", { message: error.message }) : error.message, "error");
    if (created) await loadSources();
  } finally {
    button.disabled = false;
  }
}

// The connection form adapts to the database kind: port, the schema field (the authentication
// database for MongoDB), whether a user is required, and the note about MongoDB's local copy.
function syncDatabaseKind(form) {
  const kind = form.elements.kind.value;
  const mongodb = kind === "mongodb";
  const port = form.elements.port;
  if (Object.values(DEFAULT_PORTS).includes(port.value)) port.value = DEFAULT_PORTS[kind];
  $("#schema-label").textContent = mongodb ? t("Banco de autenticação") : "Schema";
  form.elements.schema_name.placeholder = mongodb ? "admin" : kind === "postgres" ? "public" : t("mesmo nome do banco");
  form.elements.user.required = !mongodb;
  $("#user-optional").hidden = !mongodb;
  $("#mongo-help").hidden = !mongodb;
}

function updateFileLabel(form) {
  const files = [...form.elements.files.files];
  form.querySelector(".file-drop-text strong").textContent = files.length
    ? files.map((file) => file.name).join(", ")
    : t("Escolha um ou mais arquivos CSV");
}

function wireSettings() {
  $("#settings-button").addEventListener("click", openSettings);
  $("#settings-close").addEventListener("click", closeSettings);
  $("#settings").addEventListener("click", (event) => {
    if (event.target === event.currentTarget) closeSettings(); // backdrop
  });
  $("#source-button").addEventListener("click", () => toggleSourceMenu());
  const tabs = $("#add-tabs");
  for (const tab of tabs.children) {
    tab.addEventListener("click", () => {
      for (const other of tabs.children) {
        other.setAttribute("aria-selected", String(other === tab));
        $(`#${other.dataset.pane}`).hidden = other !== tab;
      }
    });
  }
  const dbForm = $("#db-form");
  dbForm.addEventListener("submit", connectDatabase);
  dbForm.addEventListener("change", (event) => {
    if (event.target.name === "kind") syncDatabaseKind(dbForm);
  });
  const csvForm = $("#csv-form");
  csvForm.addEventListener("submit", importCsv);
  csvForm.elements.files.addEventListener("change", () => updateFileLabel(csvForm));
}

/* ---------- Conversations (stored only in this browser) ---------- */

const CONVERSATIONS_KEY = "otterdata.conversations";
const MAX_CONVERSATIONS = 30;
const MAX_STORED_ROWS = 200;
const timeFormat = new Intl.DateTimeFormat(LOCALE, { hour: "2-digit", minute: "2-digit" });
const shortDate = new Intl.DateTimeFormat(LOCALE, { day: "2-digit", month: "short" });
let activeId = null;
let pending = null;
let chatStarted = false;

function loadConversations() {
  return store.get(CONVERSATIONS_KEY, []);
}

function saveConversations(list) {
  // When the browser quota is reached, drop the oldest conversations instead of failing.
  let items = list.slice(0, MAX_CONVERSATIONS);
  while (items.length) {
    try {
      localStorage.setItem(CONVERSATIONS_KEY, JSON.stringify(items));
      return;
    } catch {
      if (items.length === 1) return;
      items = items.slice(0, -1);
    }
  }
}

function storable(data) {
  if (!data.query?.rows || data.query.rows.length <= MAX_STORED_ROWS) return data;
  return { ...data, query: { ...data.query, rows: data.query.rows.slice(0, MAX_STORED_ROWS), truncated: true } };
}

function newId() {
  return globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function recordMessage(question, reference, data) {
  const list = loadConversations();
  let conversation = list.find((item) => item.id === activeId);
  if (conversation) {
    list.splice(list.indexOf(conversation), 1);
  } else {
    conversation = {
      id: newId(),
      title: question.slice(0, 90),
      source_id: currentSourceId,
      source_name: currentSource()?.name ?? null,
      messages: [],
    };
    activeId = conversation.id;
  }
  conversation.messages.push({ question, reference_date: reference || null, data: storable(data) });
  conversation.updated_at = Date.now();
  list.unshift(conversation);
  saveConversations(list);
  renderConversations();
}

function relativeTime(timestamp) {
  const minutes = Math.round((Date.now() - timestamp) / 60000);
  if (minutes < 1) return t("agora");
  if (minutes < 60) return t("há {minutes} min", { minutes });
  const then = new Date(timestamp);
  const today = new Date();
  if (then.toDateString() === today.toDateString()) return t("hoje, {time}", { time: timeFormat.format(then) });
  today.setDate(today.getDate() - 1);
  if (then.toDateString() === today.toDateString()) return t("ontem");
  return shortDate.format(then).replace(".", "");
}

function renderConversations() {
  const list = loadConversations();
  $("#history-count").textContent = list.length ? pad(list.length, 2) : "";
  // The composer names the entry it will create, like the next numbered section of a report.
  const open = list.find((item) => item.id === activeId);
  $("#next-entry").textContent = t("Pergunta {number}", { number: pad((open?.messages.length ?? 0) + 1) });
  $("#history").replaceChildren(...list.map((conversation, index) => {
    const count = conversation.messages.length;
    const own = conversation.source_id && conversation.source_id !== SAMPLE_SOURCE;
    return el("li", { class: conversation.id === activeId ? "active" : null },
      el("button", {
        type: "button",
        class: "convo",
        title: conversation.title,
        "aria-current": conversation.id === activeId ? "true" : null,
        onclick: () => openConversation(conversation.id),
      },
      el("span", { class: "h-no", "aria-hidden": "true" }, pad(list.length - index, 2)),
      el("span", { class: "h-text" }, conversation.title),
      el("span", { class: "h-meta" },
        own ? el("span", { class: "h-source" }, conversation.source_name || t("Base própria")) : null,
        el("span", {}, `${count} ${t(count === 1 ? "perg." : "pergs.")}`),
        el("span", {}, relativeTime(conversation.updated_at)))),
      el("button", {
        type: "button",
        class: "convo-delete",
        "aria-label": t("Apagar a conversa \"{title}\"", { title: conversation.title }),
        onclick: () => deleteConversation(conversation.id),
      }, icon("x")),
    );
  }));
  $("#history-empty").hidden = list.length > 0;
}

function deleteConversation(id) {
  saveConversations(loadConversations().filter((item) => item.id !== id));
  if (id === activeId) resetChat();
  else renderConversations();
}

function startThread() {
  if (chatStarted) return;
  chatStarted = true;
  document.body.classList.add("has-chat");
  $("#messages").replaceChildren();
}

function openConversation(id) {
  if (pending) return;
  const conversation = loadConversations().find((item) => item.id === id);
  if (!conversation) return;
  activeId = id;
  rememberSource(conversation.source_id || SAMPLE_SOURCE);
  chatStarted = false;
  startThread();
  conversation.messages.forEach((message, index) => {
    $("#messages").append(
      userMessage(message.question, message.reference_date, index + 1),
      assistantMessage(renderResponse(message.question, message.data, { number: index + 1 })),
    );
  });
  renderConversations();
  setRail(false);
  requestAnimationFrame(() => { $("#thread").scrollTop = $("#thread").scrollHeight; });
}

/* ---------- Chat thread ---------- */

let exampleConversation = null;

function showWelcome() {
  chatStarted = false;
  document.body.classList.remove("has-chat");
  $("#messages").replaceChildren($("#welcome-template").content.cloneNode(true));
  for (const button of document.querySelectorAll("[data-connect]")) {
    button.addEventListener("click", () => openSettings(button.dataset.connect));
  }
  $("#thread").scrollTop = 0;
  renderStarters();
  renderExample();
}

function renderStarters() {
  const box = $("#starter");
  if (!box) return;
  // With the sample selected the screen invites to connect real data; the starter questions are
  // written for the sample only.
  const sample = currentSourceId === SAMPLE_SOURCE;
  box.hidden = !sample;
  $("#intro-title").textContent = t(sample ? "Conecte seus dados e pergunte." : "Pergunte aos seus dados.");
  $("#intro-text").textContent = sample
    ? t("Ligue um banco PostgreSQL, MySQL ou MongoDB, ou importe planilhas CSV. Cada pergunta vira uma consulta só de leitura, validada antes de executar, com as evidências de cada número.")
    : t("Conversando com {name}. Cada pergunta vira uma consulta só de leitura, validada antes de executar, com as evidências de cada número.", { name: currentSource()?.name ?? t("base") });
  $("#starter-list").replaceChildren(...SUGGESTIONS.map((question, index) =>
    el("li", {},
      el("button", { type: "button", onclick: () => ask(question) },
        el("span", { class: "starter-no" }, `Q.${pad(index + 1, 2)}`), question))));
}

async function renderExample() {
  const box = $("#example-thread");
  if (!box) return;
  try {
    exampleConversation ??= await api(`/static/assets/example${I18N.lang === "en" ? "-en" : ""}.json`);
  } catch {
    box.remove();
    return;
  }
  if (!box.isConnected) return;
  const { question, reference_date: reference, data } = exampleConversation;
  box.replaceChildren(
    userMessage(question, reference, 1),
    assistantMessage(renderResponse(question, data, { example: true, number: 1 })),
  );
}

function resetChat() {
  pending?.abort();
  activeId = null;
  const textarea = $("#question");
  textarea.value = "";
  autosize(textarea);
  showWelcome();
  renderConversations();
  setRail(false);
  textarea.focus();
}

function autosize(textarea) {
  if (!textarea.value) {
    textarea.style.height = ""; // natural one-line height; a wrapped placeholder must not count
    return;
  }
  textarea.style.height = "auto";
  textarea.style.height = `${Math.min(textarea.scrollHeight, 200)}px`;
}

function scrollThread(node) {
  const thread = $("#thread");
  // Scroll only the conversation, never the page around it.
  const top = node ? node.offsetTop - 12 : thread.scrollHeight;
  thread.scrollTo({ top, behavior: "smooth" });
}

function userMessage(question, referenceDate, number = 1) {
  return el("section", { class: "message user" },
    el("p", { class: "entry-meta" },
      el("span", {}, t("Pergunta {number}", { number: pad(number) })),
      referenceDate ? el("span", {}, t("Ref. {date}", { date: dayFormat.format(parseDate(referenceDate)) })) : null),
    el("h2", { class: "question" }, question),
  );
}

function assistantMessage(nodes) {
  return el("article", { class: "message assistant" }, el("div", { class: "message-body" }, nodes));
}

const REPORT_STATUS = {
  chat: { text: t("Conversa"), tone: "neutral" },
  success: { text: t("Validada"), tone: "ok" },
  clarification: { text: t("Aguardando detalhes"), tone: "mark" },
  denied: { text: t("Recusada"), tone: "bad" },
  error: { text: t("Erro"), tone: "bad" },
  running: { text: t("Investigando"), tone: "info" },
};

// "Consulta 001" pairs each answer with its "Pergunta 001".
function reportHead(number, status) {
  return el("header", { class: "report-head" },
    el("img", { class: "report-avatar", src: AVATAR_IMG, alt: "", width: 26, height: 26 }),
    el("span", { class: "report-id" }, el("strong", {}, t("Consulta")), ` ${pad(number)}`),
    el("span", { class: `report-status ${status.tone}` }, status.text),
  );
}

function thinking(number) {
  const clock = el("span", { class: "elapsed" }, "00:00");
  const started = Date.now();
  const timer = setInterval(() => {
    if (!clock.isConnected) {
      clearInterval(timer);
      return;
    }
    const total = Math.floor((Date.now() - started) / 1000);
    clock.textContent = `${pad(Math.floor(total / 60), 2)}:${pad(total % 60, 2)}`;
  }, 1000);
  const rows = LOADING_STEPS.map((name, index) => {
    const state = el("span", { class: "load-state" });
    const row = el("li", { class: "load-step" }, el("span", { class: "load-no" }, pad(index + 1, 2)), el("span", { class: "load-name" }, name), state);
    row.state = state;
    return row;
  });
  const title = el("p", { class: "afloat-label" }, el("strong", {}, t("Investigando")));
  const set = (row, state) => {
    row.dataset.state = state;
    row.state.textContent = STEP_LABELS[state];
  };
  rows.forEach((row, index) => set(row, index === 0 ? "run" : "wait"));
  let rewrites = 0;
  const advance = (node) => {
    if (node === "converse") {
      set(rows[0], "ok");
      rows.slice(1).forEach((row) => set(row, "skip"));
      title.firstChild.textContent = t("Respondendo");
      return;
    }
    const done = NODE_DONE[node];
    if (done === undefined) return;
    if (node === "generate" && ++rewrites > 1) rows[2].querySelector(".load-name").textContent = t("Consulta (reescrita)");
    rows.forEach((row, index) => set(row, index <= done ? "ok" : index === done + 1 ? "run" : "wait"));
  };
  return {
    advance,
    nodes: [
      reportHead(number, REPORT_STATUS.running),
      el("div", { class: "thinking", role: "status", "aria-live": "polite" },
        otterAfloat(),
        el("div", { class: "thinking-body" },
          el("div", { class: "thinking-head" }, title, clock),
          el("ol", { class: "load-steps" }, rows))),
    ],
  };
}

function failure(code, title, message) {
  return { status: "error", code, answer: message, notice_title: title };
}

async function ask(question, referenceDate) {
  if (pending) return; // one question at a time, like a chat
  const textarea = $("#question");
  const dateInput = $("#reference-date");
  question = (question ?? textarea.value).trim();
  if (!question) {
    textarea.focus();
    return;
  }
  if (referenceDate !== undefined) setReferenceDate(referenceDate);
  const reference = dateInput.value;
  textarea.value = "";
  autosize(textarea);
  setRail(false);

  startThread();
  const number = (loadConversations().find((item) => item.id === activeId)?.messages.length ?? 0) + 1;
  const userNode = userMessage(question, reference, number);
  const progress = thinking(number);
  const assistant = assistantMessage(progress.nodes);
  const body = assistant.querySelector(".message-body");
  $("#messages").append(userNode, assistant);
  scrollThread();

  const controller = new AbortController();
  pending = controller;
  setBusy(true);
  const payload = { question, language: I18N.lang };
  const history = conversationHistory();
  if (history.length) payload.history = history;
  if (reference) payload.reference_date = reference;
  if (currentSourceId !== SAMPLE_SOURCE) payload.source_id = currentSourceId;
  const model = selectedModel();
  if (model && model.id !== defaultModel) payload.model = model.id;
  let data;
  try {
    const response = await fetch("/api/v1/ask/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: controller.signal,
    });
    if (response.ok && response.body) {
      data = await readAnalysisStream(response.body, progress.advance);
    } else {
      data = await response.json().catch(() => null); // request rejected before the analysis
    }
    if (!data || !data.status) {
      data = failure(`HTTP ${response.status}`, t("Não foi possível enviar a pergunta"),
        t("Confira o texto e a data de referência e tente novamente."));
    }
  } catch (error) {
    if (error.name === "AbortError") return;
    data = failure("network_error", t("Sem conexão com a API"),
      t("O backend não respondeu. Verifique se ele está em execução e tente de novo."));
  } finally {
    if (pending === controller) {
      pending = null;
      setBusy(false);
    }
  }
  body.replaceChildren(...renderResponse(question, data, { number }));
  recordMessage(question, reference, data);
  scrollThread(userNode);
  textarea.focus();
}

// The last exchanges of the open conversation, so follow-ups like "e em agosto?" make sense.
// The server decides what reaches the model (answers are dropped for bases that keep rows private).
const HISTORY_TURNS = 6;

function conversationHistory() {
  const conversation = loadConversations().find((item) => item.id === activeId);
  if (!conversation) return [];
  return conversation.messages.slice(-HISTORY_TURNS).map(({ question, data }) => {
    const answer = (data?.narrative?.answer || data?.answer || "").trim();
    return { question: question.slice(0, 2000), answer: answer ? answer.slice(0, 1500) : null };
  });
}

// NDJSON from /ask/stream: {"type":"stage"} per finished step, then {"type":"result"}.
async function readAnalysisStream(stream, onStage) {
  const reader = stream.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let result = null;
  const handle = (line) => {
    if (!line.trim()) return;
    const event = JSON.parse(line);
    if (event.type === "stage") onStage(event.stage);
    else if (event.type === "result") result = event.data;
  };
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop();
    lines.forEach(handle);
  }
  handle(buffer + decoder.decode());
  return result;
}

function setRunState(text, busy = false) {
  $("#run-state-value").textContent = text;
  $("#run-state").classList.toggle("busy", busy);
}

function setBusy(busy) {
  setRunState(t(busy ? "Investigando" : "Pronto"), busy);
  const button = $("#ask-button");
  button.disabled = busy;
  button.classList.toggle("busy", busy);
  button.replaceChildren(...(busy ? [el("span", { class: "spinner" }), t("Analisando")] : [t("Perguntar"), icon("send")]));
}

/* ---------- Where the pipeline stopped (derived only from the response) ---------- */

// Stages: 0 guard, 1 interpretation, 2 catalog, 3 prepared query, 4 validation, 5 execution, 6 evidence.
function traceOutcome(data) {
  const usage = data.usage || {};
  if (data.status === "success") return { index: 6, state: "done" };
  if (data.query?.query_attempted) return { index: 5, state: "fail" };
  if (data.sql_attempts > 0) {
    if (data.status === "denied") return { index: 4, state: "fail" };
    return { index: 3, state: "fail" };
  }
  if ((usage.provider_calls || 0) > 0 || data.status === "clarification") {
    const index = data.code === "clarification" && data.metric ? 2 : 1;
    return { index, state: data.status === "clarification" ? "stop" : "fail" };
  }
  return { index: 0, state: "fail" };
}

/* ---------- Rendering responses ---------- */

const NOTICE_TAGS = {
  clarification: t("Faltam detalhes para responder"),
  denied: t("Pedido não permitido"),
};

function followUps(questions, label) {
  if (!questions?.length) return null;
  return el("div", { class: "follow-ups" },
    el("p", { class: "follow-label" }, label),
    el("ul", { class: "suggestions" }, questions.map((question) =>
      el("li", {}, el("button", { type: "button", class: "suggestion", onclick: () => ask(question) },
        el("span", {}, question))))),
  );
}

// Only a mismatch is shown in the answer itself; a clean check is recorded in the trace.
function numberWarning(story) {
  if (!story?.unverified_numbers.length) return null;
  return el("p", { class: "note check warn", title: t("Números do texto que não aparecem nem derivam das linhas retornadas") },
    icon("alert"), t("{count} número(s) do texto não conferem com o resultado: {numbers}. Veja \"Como chegamos aqui?\".", {
      count: story.unverified_numbers.length,
      numbers: story.unverified_numbers.join(", "),
    }));
}

function seconds(ms) {
  return `${oneDecimal.format(ms / 1000)} s`;
}

const DIMENSION_TITLE = { region: t("por região"), month: t("por mês") };

function reportTitle(data) {
  let title = null;
  if (data.analysis_mode === "exploration") title = data.title;
  else if (data.metric) {
    title = [METRIC_LABELS[data.metric.name] || data.metric.name, DIMENSION_TITLE[data.interpretation?.dimension]].filter(Boolean).join(" ");
  }
  if (!title) return null;
  const period = formatPeriod(data.period);
  return el("div", { class: "report-title" },
    el("h3", {}, title),
    period ? el("p", { class: "report-period" }, t("Período {period}", { period })) : null);
}

function renderResponse(question, data, { example = false, number = 1 } = {}) {
  if (data.status === "success" && data.analysis_mode === "chat") {
    return [
      reportHead(number, REPORT_STATUS.chat),
      el("div", { class: "say" }, el("p", { class: "say-text" }, data.answer)),
      followUps(data.follow_ups, t("Você pode perguntar")),
    ].filter(Boolean);
  }
  if (data.status !== "success") {
    return [
      reportHead(number, REPORT_STATUS[data.status] || REPORT_STATUS.error),
      noticeMessage(data, question),
      data.request_id ? inspector(question, data, false, number) : null,
    ].filter(Boolean);
  }
  const story = data.narrative;
  let view = null;
  if (data.analysis_mode === "exploration" && data.query) view = buildExplorationView(data);
  else if (data.metric && data.query?.rows?.length) view = buildResultView(data);
  return [
    reportHead(number, REPORT_STATUS.success),
    reportTitle(data),
    el("div", { class: "say" },
      el("p", { class: "say-text" }, story ? story.answer : tm(data.answer)),
      story?.highlights.length ? el("ul", { class: "say-list" }, story.highlights.map((item) => el("li", {}, item))) : null,
      numberWarning(story),
    ),
    view ? figureBlock(data, view, number) : null,
    followUps(story?.follow_ups, t("Continue a investigação")),
    inspector(question, data, example, number),
  ].filter(Boolean);
}

// Errors that mean Ollama still needs setting up get step-by-step help instead of an error.
const OLLAMA_DOWNLOAD = "https://ollama.com/download";

function ollamaGuide(data) {
  const code = (text) => el("code", {}, text);
  const link = el("a", { href: OLLAMA_DOWNLOAD, target: "_blank", rel: "noopener noreferrer" }, "ollama.com/download");
  const model = data.model || "";
  const guides = {
    provider_connection_error: {
      title: t("Falta ligar o Ollama"),
      intro: t("O Otter Data usa o Ollama para entender as perguntas e escrever as respostas, e ele não está respondendo neste computador. Para começar:"),
      steps: [
        [t("Baixe e instale o Ollama em "), link, t(". Se ele já estiver instalado, abra o app do Ollama.")],
        [t("Para usar o modelo padrão, na nuvem, abra um terminal e rode "), code("ollama signin"),
          t(". Para usar sem internet, baixe um modelo local: "), code("ollama pull qwen2.5:7b"), "."],
        [t("Volte aqui e pergunte de novo.")],
      ],
    },
    provider_model_unavailable: {
      title: t("Este modelo não está no seu Ollama"),
      intro: t("O modelo {model} não foi encontrado no Ollama deste computador.", { model }),
      steps: [
        [t("Para um modelo local, abra um terminal e rode "), code(`ollama pull ${model}`), "."],
        [t("Para um modelo na nuvem (terminado em -cloud), rode "), code("ollama signin"), "."],
        [t("Ou escolha outro modelo no seletor abaixo da caixa de pergunta.")],
      ],
    },
    provider_authentication_error: {
      title: t("Entre na sua conta do Ollama"),
      intro: t("Os modelos na nuvem, como o padrão, pedem login na sua conta do Ollama."),
      steps: [
        [t("Abra um terminal e rode "), code("ollama signin"), "."],
        [t("Ou escolha um modelo local no seletor abaixo da caixa de pergunta.")],
        [t("Volte aqui e pergunte de novo.")],
      ],
    },
  };
  return guides[data.code] || null;
}

function noticeMessage(data, question) {
  const guide = ollamaGuide(data);
  if (guide) {
    return el("div", { class: "say notice setup" },
      el("h3", { class: "notice-title" }, guide.title),
      el("p", { class: "say-text" }, guide.intro),
      el("ol", { class: "setup-steps" }, guide.steps.map((parts) => el("li", {}, parts))),
      question ? el("button", { type: "button", class: "retry-button", onclick: () => ask(question) }, t("Tentar novamente")) : null,
    );
  }
  const failed = data.status === "error";
  const retry = failed && question
    ? el("button", { type: "button", class: "retry-button", onclick: () => ask(question) }, t("Tentar novamente"))
    : null;
  return el("div", { class: `say notice ${data.status}` },
    el("h3", { class: "notice-title" }, data.notice_title || (failed ? t("Não foi possível concluir a consulta") : NOTICE_TAGS[data.status] || t("Aviso"))),
    el("p", { class: "say-text" }, tm(data.answer)),
    retry,
    data.status === "clarification" ? followUps(SUGGESTIONS.slice(0, 3), t("Você pode tentar")) : null,
  );
}

/* ---------- "Como chegamos aqui?": the procedure behind an answer ---------- */

const DIMENSION_TEXT = { total: t("total do período"), region: t("por região"), month: t("por mês") };

function stepState(step, outcome, data) {
  if (step === 1) return "done";
  const stage = step - 1; // 1 interpret, 2 catalog, 3 SQL, 4 validation, 5 execution, 6 evidence
  if (stage === 6 && data.status === "success" && !data.narrative) return "plain";
  if (data.status === "success") return "done";
  const failing = Math.max(outcome.index, 1);
  if (stage < failing) return "done";
  if (stage === failing) return outcome.state;
  return "skip";
}

function fact(term, value) {
  return value ? [el("dt", {}, term), el("dd", {}, value)] : [];
}

function periodText(start, endExclusive) {
  if (!start || !endExclusive) return null;
  return formatPeriod({ start, end_exclusive: endExclusive });
}

function interpretationContent(data) {
  const intent = data.interpretation;
  if (!intent) return el("p", {}, t(data.status === "denied"
    ? "Recusado antes de chegar ao modelo: o pedido envolve escrita ou dados pessoais."
    : "A pergunta não chegou a ser interpretada."));
  if (data.analysis_mode === "exploration") {
    return [
      el("p", {}, t("Exploração livre: {title}.", { title: data.title || t("consulta descritiva") })),
      data.assumptions?.length ? el("p", { class: "proc-note" }, t("Critério escolhido:")) : null,
      data.assumptions?.length ? el("ul", { class: "proc-list" }, data.assumptions.map((item) => el("li", {}, item))) : null,
    ];
  }
  if (intent.action === "analyze" && intent.metric) {
    const parts = [t("Métrica versionada {metric}", { metric: METRIC_LABELS[intent.metric] || intent.metric }), DIMENSION_TEXT[intent.dimension]];
    const period = periodText(intent.start_date, intent.end_date);
    if (period) parts.push(t("de {period}", { period }));
    if (intent.region) parts.push(t("somente a região {region}", { region: intent.region }));
    return el("p", {}, `${parts.filter(Boolean).join(", ")}.`);
  }
  const reasons = {
    denied: "Pedido recusado pela política de leitura.",
    clarification: "Faltou informação para escolher a métrica ou o período.",
    unsupported: "A pergunta depende de dados ou análises fora do alcance desta base.",
  };
  return el("p", {}, t(reasons[intent.action] || "Interpretação concluída."));
}

function catalogContent(data) {
  const groups = new Map();
  for (const field of data.catalog_fields || []) {
    const parts = field.split(".");
    const column = parts.pop();
    const table = parts.join(".");
    if (!groups.has(table)) groups.set(table, []);
    groups.get(table).push(column);
  }
  const items = [];
  if (data.metric) {
    items.push(el("p", {}, t("Definição usada: {description} Versão {version}, unidade {unit}.", {
      description: tm(data.metric.description),
      version: data.metric.version,
      unit: data.metric.unit,
    })));
  }
  if (groups.size) {
    items.push(el("dl", { class: "proc-facts fields" },
      [...groups].map(([table, columns]) => [el("dt", {}, el("code", {}, table)), el("dd", {}, columns.join(", "))])));
  } else if (!data.metric) {
    items.push(el("p", { class: "proc-empty" }, t("Nenhum campo do catálogo foi consultado.")));
  }
  return items;
}

// Confirms an action on the control itself for a moment, instead of a separate popup.
function flash(button, text, ok = true) {
  const original = button.dataset.label ?? button.textContent;
  button.dataset.label = original;
  button.textContent = text;
  button.classList.toggle("done", ok);
  clearTimeout(button.flashTimer);
  button.flashTimer = setTimeout(() => {
    button.textContent = original;
    button.classList.remove("done");
  }, 1600);
}

function sqlBlock(sql) {
  const copy = el("button", { type: "button", class: "code-copy" }, t("Copiar SQL"));
  copy.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(sql);
      flash(copy, t("Copiado ✓"));
    } catch {
      flash(copy, t("Não foi possível copiar"), false);
    }
  });
  return el("div", { class: "code-wrap" }, el("pre", { class: "code" }, highlightSQL(sql)), copy);
}

function inspector(question, data, open = false, number = 1) {
  const outcome = traceOutcome(data);
  const query = data.query;
  const usage = data.usage || {};
  const validated = Boolean(query?.query_attempted || data.catalog_fields?.length);
  const story = data.narrative;
  const steps = [
    [t("Pergunta"), [
      el("blockquote", { class: "proc-quote" }, question),
      el("dl", { class: "proc-facts" },
        fact(t("Base"), data.source_name && data.source_id !== "sample" ? data.source_name : tm(data.source_name || "Exemplo: e-commerce sintético")),
        fact(t("Referência"), data.reference_date ? dayFormat.format(parseDate(data.reference_date)) : null),
        fact(t("Modelo"), data.demo_mode ? t("Demonstração programada") : data.model)),
    ]],
    [t("Interpretação"), interpretationContent(data)],
    [t("Catálogo"), catalogContent(data)],
    [t("Consulta preparada"), query?.sql
      ? [sqlBlock(query.sql),
        data.sql_attempts > 1 ? el("p", { class: "proc-note" }, t("A primeira versão não passou na validação; a consulta foi reescrita uma vez.")) : null,
        query.parameter_names?.length ? el("p", { class: "proc-note" }, t("Valores enviados à parte, como parâmetros: {names}.", { names: query.parameter_names.map((name) => `:${name}`).join(", ") })) : null]
      : el("p", { class: "proc-empty" }, t("Nenhuma consulta foi preparada."))],
    [t("Validação"), validated
      ? el("p", {}, t("Aprovada: um único SELECT, apenas tabelas do catálogo, junções pelas chaves documentadas e nenhuma coluna pessoal."))
      : data.status === "denied" && data.sql_attempts
        ? [el("p", {}, t("Recusada: {reason}", { reason: tm(data.answer) })), el("p", { class: "proc-note" }, t("Código {code}. Nada foi executado.", { code: data.code }))]
        : el("p", { class: "proc-empty" }, t("Não houve consulta para validar."))],
    [t("Execução"), query?.query_attempted
      ? query.status === "success"
        ? el("p", {}, t("{rows} linha(s) em {ms} ms, em transação somente leitura{truncated}.", {
          rows: integer.format(query.row_count),
          ms: Math.round(query.duration_ms),
          truncated: query.truncated ? t("; resultado truncado pelo limite") : "",
        }))
        : el("p", {}, `${tm(query.message)} (${query.code})`)
      : el("p", { class: "proc-empty" }, t("Nada foi executado no banco."))],
    [t("Evidência"), [
      story
        ? el("p", {}, t("A IA leu {rows} linha(s) do resultado para escrever a resposta. {check}", {
          rows: story.rows_shared,
          check: story.unverified_numbers.length
            ? t("{count} número(s) do texto não conferem: {numbers}.", { count: story.unverified_numbers.length, numbers: story.unverified_numbers.join(", ") })
            : t("{count} número(s) do texto conferem com o resultado.", { count: story.numbers_checked }),
        }))
        : el("p", {}, tm(data.narrative_note) || t("A resposta usa apenas os valores calculados pela consulta.")),
      story?.caveats.length ? el("p", { class: "proc-note" }, t("Para considerar:")) : null,
      story?.caveats.length ? el("ul", { class: "proc-list" }, story.caveats.map((item) => el("li", {}, item))) : null,
      data.limitations?.length ? el("p", { class: "proc-note" }, t("Limites da base:")) : null,
      data.limitations?.length ? el("ul", { class: "proc-list" }, data.limitations.map((item) => el("li", {}, tm(item)))) : null,
    ]],
  ];
  const states = { done: t("ok"), stop: t("parou aqui"), fail: t("interrompida"), skip: t("não executada"), plain: t("sem leitura da IA") };
  const tokens = (usage.input_tokens || 0) + (usage.output_tokens || 0);
  const summary = data.status === "success" && query
    ? [[t("Campos"), data.catalog_fields?.length || 0], [t("Linhas"), integer.format(query.row_count)], [t("Total"), seconds(data.duration_ms)]]
    : [[t("Etapa"), t(outcome.state === "stop" ? "interpretação" : "não concluída")]];
  const status = data.status === "success" ? REPORT_STATUS.success : REPORT_STATUS[data.status] || REPORT_STATUS.error;
  const pathNames = ["Pergunta", "Interpretação", "Catálogo", "SQL", "Validação", "Execução", "Evidência"].map((name) => t(name));
  const path = el("ol", { class: "trace-path", "aria-label": t("Caminho da consulta") },
    pathNames.map((name, index) => el("li", { class: stepState(index + 1, outcome, data) }, name)));
  return el("details", { class: "inspector", open },
    el("summary", {},
      el("span", { class: "inspector-id" }, t("Rastro da consulta {number}", { number: pad(number) })),
      el("span", { class: "inspector-title" }, t("Como chegamos aqui?")),
      path,
      el("span", { class: "inspector-summary" },
        el("span", { class: `report-status ${status.tone}` }, status.text),
        summary.map(([term, value]) => el("span", {}, el("b", {}, term), ` ${value}`)))),
    el("ol", { class: "procedure" }, steps.map(([title, content], index) => {
      const state = stepState(index + 1, outcome, data);
      const label = state === "fail" && index === 4 ? t("recusada") : states[state];
      return el("li", { class: `proc ${state}` },
        el("div", { class: "proc-key" },
          el("span", { class: "proc-no" }, pad(index + 1, 2)),
          el("h4", {}, title),
          label ? el("span", { class: "proc-state" }, label) : null),
        el("div", { class: "proc-body" }, state === "skip" ? el("p", { class: "proc-empty" }, "—") : content));
    })),
    el("dl", { class: "inspector-foot" },
      [[t("Requisição"), data.request_id], [t("Chamadas ao modelo"), usage.llm_calls ?? 0], [t("Tokens"), integer.format(tokens)], [t("Total"), seconds(data.duration_ms)]]
        .map(([term, value]) => el("div", {}, el("dt", {}, term), el("dd", {}, value)))),
  );
}

function buildResultView(data) {
  const metric = data.metric.name;
  const monetary = isMonetary(metric);
  const dimension = data.query.columns.find((column) => column !== metric) || null;
  const view = { metric, monetary, dimension, label: METRIC_LABELS[metric] || metric };
  if (!dimension) {
    view.single = { label: tm(data.metric.description), text: formatValue(Number(data.query.rows[0][metric]), monetary) };
    return view;
  }
  view.points = data.query.rows.map((row) => ({
    label: dimension === "month" ? formatMonth(row[dimension]) : String(row[dimension]),
    longLabel: dimension === "month" ? formatMonth(row[dimension], true) : String(row[dimension]),
    value: Number(row[metric]),
  }));
  view.total = view.points.reduce((sum, point) => sum + point.value, 0);
  return view;
}

/* ---------- Exploration ---------- */

const ISO_DATE = /^\d{4}-\d{2}-\d{2}(T00:00:00(\.0+)?([+-]\d{2}:?\d{2}|Z)?)?$/;
const decimal = new Intl.NumberFormat(LOCALE, { maximumFractionDigits: 2 });
const ISO_DATETIME = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2}(\.\d+)?)?([+-]\d{2}:?\d{2}|Z)?$/;
const HAS_OFFSET = /([+-]\d{2}:?\d{2}|Z)$/;
// Values with an offset are shown in São Paulo time; values without one are already wall-clock.
const dateTimeLocal = new Intl.DateTimeFormat(LOCALE, {
  dateStyle: "short", timeStyle: "short", timeZone: "America/Sao_Paulo",
});
const dateTimeWall = new Intl.DateTimeFormat(LOCALE, { dateStyle: "short", timeStyle: "short", timeZone: "UTC" });

function humanize(column) {
  return capitalize(String(column).replaceAll("_", " "));
}

function isNumeric(value) {
  return value !== null && value !== "" && typeof value !== "boolean" && Number.isFinite(Number(value));
}

function formatCell(column, value, money = false) {
  if (value === null || value === undefined) return "—";
  if (typeof value === "boolean") return t(value ? "sim" : "não");
  if (isNumeric(value)) {
    const number = Number(value);
    return money ? brl.format(number) : decimal.format(number);
  }
  if (typeof value === "string" && ISO_DATE.test(value)) return dayFormat.format(parseDate(value));
  if (typeof value === "string" && ISO_DATETIME.test(value)) {
    const offset = HAS_OFFSET.test(value);
    const moment = new Date(offset ? value : `${value}Z`);
    if (!Number.isNaN(moment.getTime())) return (offset ? dateTimeLocal : dateTimeWall).format(moment);
  }
  return String(value);
}

// Chart points from a category or date column and a numeric one; shared by the automatic and
// the requested charts.
function seriesView(view, rows, labelColumn, valueColumn) {
  const dated = rows.every((row) => typeof row[labelColumn] === "string" && ISO_DATE.test(row[labelColumn]));
  const monthly = dated && rows.every((row) => row[labelColumn].slice(8, 10) === "01");
  view.dimension = dated ? "month" : "category";
  view.points = rows.map((row) => {
    const raw = row[labelColumn];
    const text = monthly ? formatMonth(raw) : dated ? dayFormat.format(parseDate(raw)) : String(raw ?? "—");
    return {
      label: text.length > 18 ? `${text.slice(0, 17)}…` : text,
      longLabel: monthly ? formatMonth(raw, true) : text,
      value: Number(row[valueColumn]),
    };
  });
  return view;
}

// A chart the model asked for and the server checked against these rows (data.chart).
function requestedChartView(data, view) {
  const { type, x, y } = data.chart;
  const { rows } = data.query;
  view.chart = type;
  view.label = humanize(y);
  view.monetary = isMoney(data, y);
  if (type === "scatter") {
    view.xLabel = humanize(x);
    view.xMonetary = isMoney(data, x);
    view.scatter = rows.map((row) => ({ x: Number(row[x]), y: Number(row[y]) }));
    view.points = [];
    return view;
  }
  seriesView(view, rows, x, y);
  view.total = view.points.reduce((sum, point) => sum + point.value, 0);
  return view;
}

function buildExplorationView(data) {
  const { columns, rows } = data.query;
  const view = { exploration: true };
  if (data.chart && rows.length) return requestedChartView(data, view);
  const numericColumns = columns.filter((column) => rows.length && rows.every((row) => isNumeric(row[column])));
  if (rows.length === 1 && columns.length === 1 && numericColumns.length === 1) {
    view.single = { label: humanize(columns[0]), text: formatCell(columns[0], rows[0][columns[0]], isMoney(data, columns[0])) };
    return view;
  }
  if (columns.length === 2 && numericColumns.length === 1 && rows.length >= 2 && rows.length <= 30) {
    const valueColumn = numericColumns[0];
    view.monetary = isMoney(data, valueColumn);
    view.label = humanize(valueColumn);
    seriesView(view, rows, columns.find((column) => column !== valueColumn), valueColumn);
  }
  return view;
}

function genericTable(data) {
  const { columns, rows } = data.query;
  const numeric = new Set(columns.filter((column) => rows.every((row) => row[column] === null || isNumeric(row[column]))));
  return el("table", {},
    el("thead", {}, el("tr", {}, columns.map((column) =>
      el("th", { class: numeric.has(column) ? "num" : null }, humanize(column))))),
    el("tbody", {}, rows.map((row) => el("tr", {}, columns.map((column) =>
      el("td", { class: numeric.has(column) ? "num" : null }, formatCell(column, row[column], isMoney(data, column))))))),
  );
}

function figureBlock(data, view, number = 1) {
  const exploration = data.analysis_mode === "exploration";
  const title = exploration
    ? data.title || t("Resultado")
    : [view.label, DIMENSION_TITLE[view.dimension]].filter(Boolean).join(" ");
  const caption = [];
  const period = formatPeriod(data.period);
  if (period) caption.push(t("Período de {period}", { period }));
  for (const [name, value] of Object.entries(data.filters || {})) caption.push(`${name}: ${value}`);
  caption.push(exploration ? t("consulta exploratória validada") : t("métrica {name}, versão {version}", { name: data.metric.name, version: data.metric.version }));
  if (data.source_name && data.source_id !== "sample") caption.push(t("base {name}", { name: data.source_name }));
  if (data.query.truncated) caption.push(t("lista truncada pelo limite de retorno"));
  const tables = data.query.sources?.length ? data.query.sources : data.sources;

  const actions = [];
  let body;
  if (view.single) {
    body = el("p", { class: "big-number" }, el("strong", {}, view.single.text), el("span", {}, view.single.label));
  } else if (view.points) {
    const chartBox = el("div", { class: "chart-wrap" });
    const tableBox = el("div", { class: "table-scroll", hidden: true }, exploration ? genericTable(data) : dataTable(view));
    const toggle = el("button", {
      type: "button",
      class: "text-action",
      "aria-pressed": "false",
      onclick: (event) => {
        const showTable = chartBox.hidden === false;
        chartBox.hidden = showTable;
        tableBox.hidden = !showTable;
        event.currentTarget.textContent = t(showTable ? "Gráfico" : "Tabela");
        event.currentTarget.setAttribute("aria-pressed", String(showTable));
      },
    }, t("Tabela"));
    actions.push(toggle);
    const drawer = { bar: drawBars, line: drawArea, scatter: drawScatter, pie: drawPie }[view.chart]
      ?? (view.dimension === "month" ? drawArea : drawBars);
    const draw = () => drawer(chartBox, view);
    requestAnimationFrame(draw);
    observeWidth(chartBox, draw);
    body = [chartBox, tableBox];
  } else if (data.query.rows.length) {
    body = el("div", { class: "table-scroll" }, genericTable(data));
  } else {
    body = el("p", { class: "note" }, t("A consulta não retornou registros."));
  }
  if (data.query.rows.length) {
    actions.push(el("button", {
      type: "button",
      class: "text-action",
      onclick: (event) => {
        exportCSV(data, view);
        flash(event.currentTarget, t("CSV baixado ✓"));
      },
    }, "CSV"));
  }
  return el("figure", { class: "figure" },
    el("div", { class: "figure-head" },
      el("span", { class: "fig-no" }, t("Fig. {number}", { number: pad(number, 2) })),
      el("h3", {}, title),
      actions.length ? el("div", { class: "figure-actions" }, actions) : null),
    el("div", { class: "figure-body" }, body),
    el("figcaption", {},
      el("p", {}, `${capitalize(caption.join("; "))}.`),
      tables?.length ? el("p", { class: "fig-source" }, t("Fonte: {tables}", { tables: tables.join(", ") })) : null),
  );
}

function dataTable(view) {
  return el("table", {},
    el("thead", {}, el("tr", {},
      el("th", {}, t(view.dimension === "month" ? "Mês" : "Região")),
      el("th", { class: "num" }, view.label),
      el("th", { class: "num" }, t("Participação")),
    )),
    el("tbody", {}, view.points.map((point) => el("tr", {},
      el("td", {}, point.longLabel),
      el("td", { class: "num" }, formatValue(point.value, view.monetary)),
      el("td", { class: "num" }, view.total ? percent.format(point.value / view.total) : "—"),
    ))),
  );
}

function exportCSV(data, view) {
  const columns = data.query.columns;
  const escape = (value) => {
    const text = String(value ?? "");
    return /[",\n;]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
  };
  const lines = [columns.join(","), ...data.query.rows.map((row) => columns.map((column) => escape(row[column])).join(","))];
  const blob = new Blob([`${lines.join("\n")}\n`], { type: "text/csv;charset=utf-8" });
  const name = view.exploration ? "exploracao" : `${view.metric}-${view.dimension}`;
  const link = el("a", { href: URL.createObjectURL(blob), download: `otterdata-${name}.csv` });
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(link.href), 1000);
  toast(t("CSV exportado"));
}

/* ---------- Charts (single series, inline SVG) ---------- */

function observeWidth(node, draw) {
  let lastWidth = 0;
  new ResizeObserver(([entry]) => {
    const width = Math.round(entry.contentRect.width);
    if (width && lastWidth && Math.abs(width - lastWidth) > 4) draw();
    if (width) lastWidth = width;
  }).observe(node);
}

function niceMax(value) {
  if (value <= 0) return 1;
  const magnitude = 10 ** Math.floor(Math.log10(value));
  for (const step of [1, 1.2, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10]) {
    if (step * magnitude >= value) return step * magnitude;
  }
  return 10 * magnitude;
}

// Horizontal bar with a 4px rounded data-end and a square end on the baseline.
function barPath(x, y, width, height) {
  const r = Math.min(1, width / 2, height / 2);
  return `M${x},${y}h${width - r}a${r},${r} 0 0 1 ${r},${r}v${height - 2 * r}a${r},${r} 0 0 1 -${r},${r}h-${width - r}z`;
}

function showTooltip(anchor, lines) {
  const tooltip = $("#tooltip");
  tooltip.replaceChildren(
    el("span", {}, lines[0]),
    el("strong", {}, lines[1]),
    lines[2] ? el("em", {}, lines[2]) : null,
  );
  const box = anchor.getBoundingClientRect();
  tooltip.style.left = `${box.left + box.width / 2}px`;
  tooltip.style.top = `${box.top}px`;
  tooltip.hidden = false;
}

function hideTooltip() {
  $("#tooltip").hidden = true;
}

function bindHover(container, hit, onEnter, onLeave, label) {
  const enter = () => {
    container.classList.add("hovering");
    onEnter();
  };
  const leave = () => {
    container.classList.remove("hovering");
    onLeave();
    hideTooltip();
  };
  hit.addEventListener("mouseenter", enter);
  hit.addEventListener("mouseleave", leave);
  hit.addEventListener("focus", enter);
  hit.addEventListener("blur", leave);
  hit.setAttribute("tabindex", "0");
  hit.setAttribute("role", "img");
  hit.setAttribute("aria-label", label);
}

function drawBars(container, view) {
  const { points, monetary } = view;
  const width = Math.max(container.clientWidth, 280);
  const narrow = width < 480;
  const labelWidth = narrow ? 92 : 116;
  const valueWidth = monetary ? (narrow ? 84 : 124) : 64;
  const barHeight = 16;
  const gap = 14;
  const height = points.length * (barHeight + gap) + 22;
  const plotWidth = width - labelWidth - valueWidth - 14;
  const max = niceMax(Math.max(...points.map((point) => point.value)));
  const chart = svg("svg", { viewBox: `0 0 ${width} ${height}`, role: "group", "aria-label": t("{label} por categoria", { label: view.label }) });

  for (let index = 0; index <= 4; index += 1) {
    const x = labelWidth + (plotWidth * index) / 4;
    chart.append(svg("line", { class: "grid", x1: x, x2: x, y1: 0, y2: height - 20 }));
    if (narrow && index % 2) continue;
    const tick = svg("text", { x, y: height - 4, "text-anchor": "middle" });
    tick.textContent = formatCompact((max * index) / 4, monetary);
    chart.append(tick);
  }
  points.forEach((point, index) => {
    const y = index * (barHeight + gap) + 4;
    const barWidth = Math.max((point.value / max) * plotWidth, 2);
    const label = svg("text", { class: "label", x: labelWidth - 12, y: y + barHeight / 2 + 4, "text-anchor": "end" });
    label.textContent = point.label;
    const bar = svg("path", { class: "bar grow-x", d: barPath(labelWidth, y, barWidth, barHeight) });
    bar.style.animationDelay = `${index * 60}ms`;
    const value = svg("text", { class: "value fade-in", x: width - 2, y: y + barHeight / 2 + 4, "text-anchor": "end" });
    value.textContent = narrow ? formatCompact(point.value, monetary) : formatValue(point.value, monetary);
    const hit = svg("rect", { class: "hit", x: 0, y: y - gap / 2, width, height: barHeight + gap });
    chart.append(label, bar, value, hit);
    const share = view.total ? t("{share} do total", { share: percent.format(point.value / view.total) }) : null;
    bindHover(container, hit,
      () => { bar.classList.add("active"); showTooltip(bar, [point.longLabel, formatValue(point.value, monetary), share]); },
      () => bar.classList.remove("active"),
      `${point.longLabel}: ${formatValue(point.value, monetary)}`);
  });
  chart.append(svg("line", { class: "baseline", x1: labelWidth, x2: labelWidth, y1: 0, y2: height - 20 }));
  container.replaceChildren(chart);
}

function drawArea(container, view) {
  const { points, monetary } = view;
  const width = Math.max(container.clientWidth, 280);
  const height = width < 480 ? 240 : 300;
  const left = 62;
  const right = 18;
  const top = 26;
  const bottom = 30;
  const plotWidth = width - left - right;
  const plotHeight = height - top - bottom;
  const max = niceMax(Math.max(...points.map((point) => point.value)));
  const step = points.length > 1 ? plotWidth / (points.length - 1) : 0;
  const xy = points.map((point, index) => [
    left + (points.length > 1 ? step * index : plotWidth / 2),
    top + plotHeight - (point.value / max) * plotHeight,
  ]);
  const chart = svg("svg", { viewBox: `0 0 ${width} ${height}`, role: "group", "aria-label": t("{label} ao longo do tempo", { label: view.label }) });

  for (let index = 0; index <= 4; index += 1) {
    const y = top + plotHeight - (plotHeight * index) / 4;
    chart.append(svg("line", { class: index === 0 ? "baseline" : "grid", x1: left, x2: width - right, y1: y, y2: y }));
    const tick = svg("text", { x: left - 10, y: y + 4, "text-anchor": "end" });
    tick.textContent = formatCompact((max * index) / 4, monetary);
    chart.append(tick);
  }

  const linePath = xy.map(([x, y], index) => `${index ? "L" : "M"}${x.toFixed(1)},${y.toFixed(1)}`).join("");
  const baseY = top + plotHeight;
  chart.append(svg("path", { class: "area fade-in", d: `${linePath}L${xy.at(-1)[0]},${baseY}L${xy[0][0]},${baseY}Z` }));
  const line = svg("path", { class: "line draw", d: linePath });
  chart.append(line);
  const crosshair = svg("line", { class: "crosshair", x1: 0, x2: 0, y1: top, y2: baseY });
  chart.append(crosshair);

  const labelEvery = Math.max(1, Math.ceil(54 / Math.max(step, 1)));
  const peak = points.reduce((best, point, index) => (point.value > points[best].value ? index : best), 0);
  const pointNodes = xy.map(([x, y], index) => {
    if (index % labelEvery === 0 || index === points.length - 1) {
      const label = svg("text", { x, y: height - 8, "text-anchor": "middle" });
      label.textContent = points[index].label;
      chart.append(label);
    }
    if (index === peak || index === points.length - 1) {
      const value = svg("text", { class: "value fade-in", x: Math.min(x, width - right - 24), y: y - 12, "text-anchor": "middle" });
      value.textContent = formatCompact(points[index].value, monetary);
      chart.append(value);
    }
    const point = svg("rect", { class: "point fade-in", x: x - 3.5, y: y - 3.5, width: 7, height: 7 });
    chart.append(point);
    return point;
  });

  xy.forEach(([x], index) => {
    const half = step / 2 || plotWidth / 2;
    const hit = svg("rect", { class: "hit", x: x - half, y: top, width: half * 2, height: plotHeight });
    chart.append(hit);
    const point = points[index];
    const previous = points[index - 1];
    const change = previous && previous.value > 0
      ? t("{change} vs. mês anterior", { change: signedPercent.format(point.value / previous.value - 1) })
      : null;
    bindHover(container, hit,
      () => {
        crosshair.setAttribute("x1", x);
        crosshair.setAttribute("x2", x);
        crosshair.classList.add("on");
        pointNodes[index].classList.add("active");
        showTooltip(pointNodes[index], [point.longLabel, formatValue(point.value, monetary), change]);
      },
      () => {
        crosshair.classList.remove("on");
        pointNodes[index].classList.remove("active");
      },
      `${point.longLabel}: ${formatValue(point.value, monetary)}`);
  });

  container.replaceChildren(chart);
  const length = Math.ceil(line.getTotalLength()) + 2;
  line.style.setProperty("--len", length);
  line.style.strokeDasharray = length;
}

// Axis bounds rounded to a readable step, for ranges that do not start at zero.
function niceRange(min, max) {
  if (min === max) return { min: min - 1, max: max + 1, step: 0.5 };
  const rough = (max - min) / 4;
  const magnitude = 10 ** Math.floor(Math.log10(rough));
  const step = [1, 2, 2.5, 5, 10].map((factor) => factor * magnitude).find((value) => value >= rough);
  return { min: Math.floor(min / step) * step, max: Math.ceil(max / step) * step, step };
}

function drawScatter(container, view) {
  const width = Math.max(container.clientWidth, 280);
  const height = width < 480 ? 260 : 320;
  const left = 56;
  const right = 16;
  const top = 14;
  const bottom = 42;
  const xs = niceRange(Math.min(...view.scatter.map((point) => point.x)), Math.max(...view.scatter.map((point) => point.x)));
  const ys = niceRange(Math.min(...view.scatter.map((point) => point.y)), Math.max(...view.scatter.map((point) => point.y)));
  const px = (value) => left + ((value - xs.min) / (xs.max - xs.min)) * (width - left - right);
  const py = (value) => top + (1 - (value - ys.min) / (ys.max - ys.min)) * (height - top - bottom);
  const chart = svg("svg", {
    viewBox: `0 0 ${width} ${height}`,
    role: "img",
    "aria-label": t("Dispersão de {label} por {x}, {count} pontos", { label: view.label, x: view.xLabel, count: view.scatter.length }),
  });
  for (let value = ys.min; value <= ys.max + ys.step / 2; value += ys.step) {
    chart.append(svg("line", { class: value === ys.min ? "baseline" : "grid", x1: left, x2: width - right, y1: py(value), y2: py(value) }));
    const tick = svg("text", { x: left - 8, y: py(value) + 4, "text-anchor": "end" });
    tick.textContent = formatCompact(value, view.monetary);
    chart.append(tick);
  }
  for (let value = xs.min; value <= xs.max + xs.step / 2; value += xs.step) {
    chart.append(svg("line", { class: "grid", x1: px(value), x2: px(value), y1: top, y2: height - bottom }));
    const tick = svg("text", { x: px(value), y: height - bottom + 16, "text-anchor": "middle" });
    tick.textContent = formatCompact(value, view.xMonetary);
    chart.append(tick);
  }
  chart.append(svg("line", { class: "baseline", x1: left, x2: left, y1: top, y2: height - bottom }));
  const xTitle = svg("text", { class: "axis-title", x: width - right, y: height - 6, "text-anchor": "end" });
  xTitle.textContent = view.xLabel;
  const yTitle = svg("text", { class: "axis-title", x: left, y: top - 2 });
  yTitle.textContent = view.label;
  chart.append(xTitle, yTitle);
  // Hover only: hundreds of points must not become hundreds of tab stops.
  for (const point of view.scatter) {
    const dot = svg("circle", { class: "dot fade-in", cx: px(point.x), cy: py(point.y), r: 3 });
    dot.addEventListener("mouseenter", () => {
      dot.classList.add("active");
      showTooltip(dot, [view.xLabel, `${formatValue(point.x, view.xMonetary)} · ${formatValue(point.y, view.monetary)}`, view.label]);
    });
    dot.addEventListener("mouseleave", () => {
      dot.classList.remove("active");
      hideTooltip();
    });
    chart.append(dot);
  }
  container.replaceChildren(chart);
}

function drawPie(container, view) {
  const size = Math.min(Math.max(container.clientWidth, 280) * 0.42, 220);
  const radius = size / 2;
  const chart = svg("svg", { viewBox: `0 0 ${size} ${size}`, role: "group", "aria-label": t("{label}: partes do total", { label: view.label }), class: "pie" });
  const total = view.total || 1;
  let angle = -Math.PI / 2;
  const legend = el("ol", { class: "pie-legend" });
  view.points.forEach((point, index) => {
    const share = point.value / total;
    const end = angle + share * Math.PI * 2;
    const tone = `s${index % 8}`;
    const slice = share >= 0.9999
      ? svg("circle", { class: `slice ${tone}`, cx: radius, cy: radius, r: radius - 1 })
      : svg("path", {
        class: `slice ${tone}`,
        d: `M${radius},${radius} L${radius + (radius - 1) * Math.cos(angle)},${radius + (radius - 1) * Math.sin(angle)} `
          + `A${radius - 1},${radius - 1} 0 ${share > 0.5 ? 1 : 0} 1 ${radius + (radius - 1) * Math.cos(end)},${radius + (radius - 1) * Math.sin(end)} Z`,
      });
    angle = end;
    const text = t("{share} do total", { share: percent.format(share) });
    bindHover(container, slice,
      () => { slice.classList.add("active"); showTooltip(slice, [point.longLabel, formatValue(point.value, view.monetary), text]); },
      () => slice.classList.remove("active"),
      `${point.longLabel}: ${formatValue(point.value, view.monetary)}, ${text}`);
    chart.append(slice);
    legend.append(el("li", {},
      el("span", { class: `swatch ${tone}`, "aria-hidden": "true" }),
      el("span", { class: "pie-name" }, point.longLabel),
      el("span", { class: "pie-value" }, formatValue(point.value, view.monetary)),
      el("span", { class: "pie-share" }, percent.format(share))));
  });
  container.replaceChildren(el("div", { class: "pie-wrap" }, chart, legend));
}

/* ---------- Evidence ---------- */

const SQL_KEYWORDS = new Set(
  ("select from where and or as join inner left right outer full cross on group by order asc desc sum count "
    + "coalesce date_trunc at time zone between in is not null case when then else end limit distinct with")
    .split(" "),
);

function highlightSQL(sql) {
  const fragment = document.createDocumentFragment();
  const tokens = sql.match(/'(?:[^']|'')*'|"(?:[^"]|"")*"|:[A-Za-z_]\w*|\b\d+(?:\.\d+)?\b|\b[A-Za-z_]\w*\b|\s+|./g) || [];
  // Display-only line breaks; the copy button keeps the exact executed text.
  const breaks = { from: "\n", where: "\n", group: "\n", order: "\n", limit: "\n", join: "\n  ", and: "\n  " };
  const joiners = ["left", "right", "inner", "outer", "full", "cross"];
  tokens.forEach((token, index) => {
    const next = tokens[index + 1]?.toLowerCase();
    if (/^\s+$/.test(token) && next in breaks && !(next === "join" && joiners.includes(tokens[index - 1]?.toLowerCase()))) {
      tokens[index] = breaks[next];
    }
  });
  for (const token of tokens) {
    let className = null;
    if (token.startsWith("'")) className = "str";
    else if (token.startsWith(":")) className = "param";
    else if (/^\d/.test(token)) className = "num";
    else if (SQL_KEYWORDS.has(token.toLowerCase())) className = "kw";
    fragment.append(className ? el("span", { class: className }, token) : document.createTextNode(token));
  }
  return fragment;
}

/* ---------- Wiring ---------- */

document.addEventListener("DOMContentLoaded", () => {
  try {
    localStorage.removeItem("otterdata.history"); // pre-conversation history format
  } catch {
    /* storage unavailable */
  }
  showWelcome();
  renderConversations();
  loadStatus();
  loadSources();
  wireSettings();
  loadModels();
  $("#model-button").addEventListener("click", () => toggleModelMenu());
  // A click outside a menu closes it.
  document.addEventListener("mousedown", ({ target }) => {
    if (!target.closest(".source-picker")) toggleSourceMenu(false);
    if (!target.closest(".model-field")) toggleModelMenu(false);
    if (!target.closest(".date-field")) closeCalendar(false);
  });

  const textarea = $("#question");
  $("#ask-form").addEventListener("submit", (event) => {
    event.preventDefault();
    ask();
  });
  textarea.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
      event.preventDefault();
      ask();
    }
  });
  textarea.addEventListener("input", () => autosize(textarea));
  $("#new-analysis").addEventListener("click", resetChat);
  $("#clear-history").addEventListener("click", async () => {
    const count = loadConversations().length;
    if (!count) return;
    const confirmed = await confirmAction({
      kicker: t("Conversas / limpar"),
      title: count === 1 ? t("Apagar a conversa salva?") : t("Apagar as {count} conversas salvas?", { count }),
      message: t("Elas ficam guardadas só neste aparelho e não poderão ser recuperadas. As bases de dados não são afetadas."),
      confirmLabel: t("Apagar conversas"),
    });
    if (!confirmed) return;
    saveConversations([]);
    resetChat();
    toast(t("Conversas apagadas"));
  });
  // A click on the backdrop cancels, like Esc.
  $("#confirm-dialog").addEventListener("click", (event) => {
    if (event.target === event.currentTarget) event.currentTarget.close("cancel");
  });
  $("#theme-button").addEventListener("click", () => {
    const next = currentTheme() === "dark" ? "light" : "dark";
    applyTheme(next);
    store.set("otterdata.theme", next);
  });
  for (const button of document.querySelectorAll("#language-switch button")) {
    button.setAttribute("aria-pressed", String(button.dataset.lang === I18N.lang));
    button.addEventListener("click", () => {
      if (!pending) I18N.setLanguage(button.dataset.lang);
    });
  }
  $("#menu-button").addEventListener("click", () => setRail(true));
  $("#date-button").addEventListener("click", () => ($("#calendar").hidden ? openCalendar() : closeCalendar(true)));
  $("#scrim").addEventListener("click", () => setRail(false));
  document.addEventListener("keydown", (event) => {
    const typing = /^(INPUT|TEXTAREA)$/.test(document.activeElement?.tagName);
    if (event.key === "/" && !typing) {
      event.preventDefault();
      textarea.focus();
    } else if (event.key === "Escape") {
      toggleSourceMenu(false);
      toggleModelMenu(false);
      closeCalendar(true);
      setRail(false);
    }
  });
  $("#thread").addEventListener("scroll", hideTooltip, { passive: true });
});
