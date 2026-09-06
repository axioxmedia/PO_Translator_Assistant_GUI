const AXIOXMEDIA_BRAND = "Axiox Media";
const AIO_WATERMARK = "axioxmedia";
const $ = (id) => document.getElementById(id);

const I18N = {
  zh: {
    appTitle: "凯普勒 186F PO 翻译助手",
    appSubtitle: "提取未翻译条目到 JSON，再按 msgid 安全写回 .po",
    formTitle: "文件与操作",
    poLabel: "原始 PO 文件",
    poPlaceholder: "D:\\loc\\Game.po",
    jsonLabel: "翻译结果 JSON",
    jsonPlaceholder: "D:\\loc\\untranslated.json",
    outLabel: "输出中文 PO 文件",
    outPlaceholder: "D:\\loc\\Game.zh_CN.po",
    browse: "浏览",
    saveAs: "保存位置",
    extractBtn: "① 提取未翻译内容",
    applyBtn: "② 应用翻译",
    statsBtn: "查看进度",
    statsTitle: "进度与日志",
    preferD: "已优先 D 盘",
    noD: "未检测到 D 盘",
    notWin: "非 Windows · 使用用户目录",
    pathHintD: "默认工作目录 {path}。选择原始 PO 后会自动建议输出名。",
    pathHint: "选择原始 .po。未翻译条目会导出为 JSON，应用时只按 msgid 匹配。",
    waiting: "就绪。先选择原始 PO 文件。",
    needPo: "请先选择原始 PO 文件",
    needAll: "请填写原始 PO、翻译 JSON 和输出路径",
    picking: "正在打开系统文件对话框…",
    cancelled: "已取消选择",
    inspectOk: "已读取 {total} 条，待翻译 {pending}，完成度 {percent}%",
    extractAsk: "选择未翻译 JSON 的保存位置",
    extractOk: "提取完成，共 {count} 条未翻译内容 → {path}",
    applyOk: "完成，共应用 {applied} 条翻译 → {path}",
    statsOk: "总条目 {total} · 已翻译 {translated} · 待翻译 {pending} · 完成度 {percent}%",
    fail: "失败：{msg}",
    chipReady: "就绪",
    statTotal: "总条目 {n}",
    statDone: "已翻译 {n}",
    statPending: "待翻译 {n}",
    statPercent: "完成度 {n}%",
  },
  en: {
    appTitle: "Kepler 186F PO Translator Desk",
    appSubtitle: "Extract untranslated strings to JSON, then write them back by msgid",
    formTitle: "Files & actions",
    poLabel: "Source PO file",
    poPlaceholder: "D:\\loc\\Game.po",
    jsonLabel: "Translation JSON",
    jsonPlaceholder: "D:\\loc\\untranslated.json",
    outLabel: "Output zh_CN PO",
    outPlaceholder: "D:\\loc\\Game.zh_CN.po",
    browse: "Browse",
    saveAs: "Save as",
    extractBtn: "1. Extract untranslated",
    applyBtn: "2. Apply translations",
    statsBtn: "Show progress",
    statsTitle: "Progress & log",
    preferD: "Preferring drive D:",
    noD: "Drive D: not found",
    notWin: "Not Windows · using home folder",
    pathHintD: "Default folder {path}. Picking a PO fills the suggested output name.",
    pathHint: "Pick the source .po. Untranslated rows export as JSON. Apply matches msgid only.",
    waiting: "Ready. Pick a source PO file first.",
    needPo: "Pick a source PO file first",
    needAll: "Fill the source PO, translation JSON, and output path",
    picking: "Opening the system file dialog…",
    cancelled: "Cancelled",
    inspectOk: "Read {total} entries, {pending} pending, {percent}% done",
    extractAsk: "Choose where to save the untranslated JSON",
    extractOk: "Extracted {count} untranslated rows → {path}",
    applyOk: "Applied {applied} translations → {path}",
    statsOk: "Total {total} · done {translated} · pending {pending} · {percent}%",
    fail: "Failed: {msg}",
    chipReady: "Ready",
    statTotal: "Total {n}",
    statDone: "Done {n}",
    statPending: "Pending {n}",
    statPercent: "{n}% complete",
  },
};

const state = {
  uiLang: "zh",
  defaults: null,
  busy: false,
};

function detectUiLang() {
  const saved = localStorage.getItem("po_translator_desk_ui_lang");
  if (saved === "zh" || saved === "en") return saved;
  const loc = (navigator.language || "en").toLowerCase();
  return loc.startsWith("zh") ? "zh" : "en";
}

function t(key, vars) {
  const table = I18N[state.uiLang] || I18N.en;
  let text = table[key] || I18N.en[key] || key;
  if (vars) {
    for (const [k, v] of Object.entries(vars)) {
      text = text.replaceAll(`{${k}}`, String(v));
    }
  }
  return text;
}

function applyI18n() {
  document.documentElement.lang = state.uiLang === "zh" ? "zh-CN" : "en";
  document.querySelectorAll("[data-i18n]").forEach((el) => {
    el.textContent = t(el.dataset.i18n);
  });
  document.querySelectorAll("[data-i18n-placeholder]").forEach((el) => {
    el.setAttribute("placeholder", t(el.dataset.i18nPlaceholder));
  });
  document.querySelectorAll("[data-ui-lang]").forEach((btn) => {
    btn.classList.toggle("on", btn.dataset.uiLang === state.uiLang);
  });
  paintDefaults();
}

function paintDefaults() {
  const data = state.defaults;
  if (!data) {
    $("platformChip").textContent = t("chipReady");
    return;
  }
  if (data.prefer_d) $("platformChip").textContent = t("preferD");
  else if (data.is_windows) $("platformChip").textContent = t("noD");
  else $("platformChip").textContent = t("notWin");
  $("pathHint").textContent = data.prefer_d ? t("pathHintD", { path: data.dest_root }) : t("pathHint");
}

function stamp() {
  return new Date().toLocaleTimeString(state.uiLang === "zh" ? "zh-CN" : "en-GB", { hour12: false });
}

function log(message, kind = "info") {
  const line = document.createElement("div");
  line.className = kind;
  line.textContent = `[${stamp()}] ${message}`;
  $("log").appendChild(line);
  $("log").scrollTop = $("log").scrollHeight;
}

function setBusy(on) {
  state.busy = on;
  ["extractBtn", "applyBtn", "statsBtn", "pickPo", "pickJson", "pickOut"].forEach((id) => {
    $(id).disabled = on;
  });
  $("bar").style.width = on ? "55%" : "0%";
}

function paintStats(data) {
  if (!data) return;
  $("statTotal").textContent = t("statTotal", { n: data.total ?? "—" });
  $("statDone").textContent = t("statDone", { n: data.translated ?? "—" });
  $("statPending").textContent = t("statPending", { n: data.pending ?? "—" });
  $("statPercent").textContent = t("statPercent", { n: data.percent ?? "—" });
}

async function api(path, body) {
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const msg = data.detail || data.message || res.statusText || String(res.status);
    throw new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
  }
  return data;
}

async function pick(mode, suggestId) {
  log(t("picking"));
  try {
    const data = await api("/api/pick", { mode, suggest: $(suggestId).value || "" });
    if (!data.path) {
      log(t("cancelled"), "warn");
      return null;
    }
    if (mode === "open-po") {
      $("poPath").value = data.path;
      if (data.output_path && !$("outPath").value) $("outPath").value = data.output_path;
      if (data.json_path && !$("jsonPath").value) $("jsonPath").value = data.json_path;
      await inspectPo();
    } else if (mode === "open-json" || mode === "save-json") {
      $("jsonPath").value = data.path;
    } else if (mode === "save-po") {
      $("outPath").value = data.path;
    }
    return data.path;
  } catch (err) {
    log(t("fail", { msg: err.message }), "error");
    return null;
  }
}

async function inspectPo() {
  const po = $("poPath").value.trim();
  if (!po) return;
  try {
    const data = await api("/api/inspect", { po_path: po });
    if (data.output_path && !$("outPath").value) $("outPath").value = data.output_path;
    if (data.json_path && !$("jsonPath").value) $("jsonPath").value = data.json_path;
    paintStats(data);
    log(t("inspectOk", data), "ok");
  } catch (err) {
    log(t("fail", { msg: err.message }), "error");
  }
}

async function extractFlow() {
  if (!$("poPath").value.trim()) {
    log(t("needPo"), "warn");
    return;
  }
  log(t("extractAsk"));
  const dest = await pick("save-json", "jsonPath");
  if (!dest) return;
  setBusy(true);
  try {
    const data = await api("/api/extract", {
      po_path: $("poPath").value.trim(),
      json_path: dest,
    });
    paintStats(data);
    $("bar").style.width = "100%";
    log(t("extractOk", { count: data.count, path: data.json_path }), "ok");
  } catch (err) {
    log(t("fail", { msg: err.message }), "error");
  } finally {
    setBusy(false);
  }
}

async function applyFlow() {
  const po = $("poPath").value.trim();
  const jsonPath = $("jsonPath").value.trim();
  const out = $("outPath").value.trim();
  if (!po || !jsonPath || !out) {
    log(t("needAll"), "warn");
    return;
  }
  setBusy(true);
  try {
    const data = await api("/api/apply", {
      po_path: po,
      json_path: jsonPath,
      output_path: out,
    });
    paintStats(data);
    $("bar").style.width = "100%";
    log(t("applyOk", { applied: data.applied, path: data.output_path }), "ok");
  } catch (err) {
    log(t("fail", { msg: err.message }), "error");
  } finally {
    setBusy(false);
  }
}

async function statsFlow() {
  if (!$("poPath").value.trim()) {
    log(t("needPo"), "warn");
    return;
  }
  setBusy(true);
  try {
    const data = await api("/api/inspect", { po_path: $("poPath").value.trim() });
    paintStats(data);
    $("bar").style.width = "100%";
    log(t("statsOk", data), "ok");
  } catch (err) {
    log(t("fail", { msg: err.message }), "error");
  } finally {
    setBusy(false);
  }
}

$("pickPo").addEventListener("click", () => pick("open-po", "poPath"));
$("pickJson").addEventListener("click", () => pick("open-json", "jsonPath"));
$("pickOut").addEventListener("click", () => pick("save-po", "outPath"));
$("extractBtn").addEventListener("click", extractFlow);
$("applyBtn").addEventListener("click", applyFlow);
$("statsBtn").addEventListener("click", statsFlow);
$("poPath").addEventListener("change", inspectPo);
$("uiLangSwitch").addEventListener("click", (e) => {
  const btn = e.target.closest("[data-ui-lang]");
  if (!btn) return;
  state.uiLang = btn.dataset.uiLang;
  localStorage.setItem("po_translator_desk_ui_lang", state.uiLang);
  applyI18n();
});

async function boot() {
  state.uiLang = detectUiLang();
  $("log").innerHTML = "";
  try {
    const res = await fetch("/api/defaults");
    state.defaults = await res.json();
  } catch {
    state.defaults = null;
  }
  applyI18n();
  log(t("waiting"));
  paintStats({ total: "—", translated: "—", pending: "—", percent: "—" });
}

boot();
void AXIOXMEDIA_BRAND;
void AIO_WATERMARK;
