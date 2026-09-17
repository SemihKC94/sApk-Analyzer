/**
 * sApkAnalyzer - Frontend Application Controller
 * High-performance real-time logcat streaming and analysis engine.
 */

// Application State
const state = {
  logs: [],
  maxLogs: 10000,
  maxDomRows: 1500,
  devices: [],
  selectedDevice: null,
  packages: [],
  selectedPackage: "",
  selectedLevel: "ALL",
  searchTerm: "",
  isRegex: false,
  isCaseSensitive: false,
  isPaused: false,
  autoScroll: true,
  selectedLogEntry: null,
  crashCount: 0,
  sse: null,
  renderedLogIds: new Set(),
};

// DOM Elements Cache
const dom = {};

window.addEventListener("DOMContentLoaded", () => {
  cacheDomElements();
  bindEventListeners();
  loadDevices();
  initEventSource();
});

function cacheDomElements() {
  dom.deviceSelect = document.getElementById("device-select");
  dom.btnRefreshDevices = document.getElementById("btn-refresh-devices");
  dom.btnClearBuffer = document.getElementById("btn-clear-buffer");
  dom.btnWifiConnect = document.getElementById("btn-wifi-connect");
  dom.btnRestartAdb = document.getElementById("btn-restart-adb");

  dom.connectionPill = document.getElementById("connection-pill");
  dom.connectionDot = document.getElementById("connection-dot");
  dom.connectionText = document.getElementById("connection-text");

  dom.tabAllLogs = document.getElementById("tab-all-logs");
  dom.tabCrashes = document.getElementById("tab-crashes");
  dom.crashBadgeCount = document.getElementById("crash-badge-count");
  dom.navTelemetry = document.getElementById("nav-telemetry");
  dom.navCrashes = document.getElementById("nav-crashes");
  dom.navCrashCount = document.getElementById("nav-crash-count");

  dom.packageSelect = document.getElementById("package-select");
  dom.levelBtns = document.querySelectorAll(".level-btn");
  dom.btnFilterCrash = document.getElementById("btn-filter-crash");
  dom.fatalCountPill = document.getElementById("fatal-count-pill");

  dom.searchInput = document.getElementById("search-input");
  dom.btnRegex = document.getElementById("btn-regex");
  dom.btnCase = document.getElementById("btn-case");
  dom.btnClearSearch = document.getElementById("btn-clear-search");

  dom.btnPause = document.getElementById("btn-pause");
  dom.pauseIndicator = document.getElementById("pause-indicator");
  dom.pauseText = document.getElementById("pause-text");
  dom.btnAutoScroll = document.getElementById("btn-autoscroll");

  dom.btnExportTxt = document.getElementById("btn-export-txt");
  dom.btnExportJson = document.getElementById("btn-export-json");

  dom.logViewport = document.getElementById("log-viewport");
  dom.emptyState = document.getElementById("empty-state");
  dom.logRowsContainer = document.getElementById("log-rows-container");

  // Inspector Drawer
  dom.inspectorDrawer = document.getElementById("inspector-drawer");
  dom.btnCloseDrawer = document.getElementById("btn-close-drawer");
  dom.btnCopyRawLog = document.getElementById("btn-copy-raw-log");
  dom.btnCopyStack = document.getElementById("btn-copy-stack");
  dom.drawerCrashBanner = document.getElementById("drawer-crash-banner");
  dom.drawerCrashTitle = document.getElementById("drawer-crash-title");
  dom.drawerCrashSummary = document.getElementById("drawer-crash-summary");
  dom.metaTime = document.getElementById("meta-time");
  dom.metaLevel = document.getElementById("meta-level");
  dom.metaPid = document.getElementById("meta-pid");
  dom.metaTag = document.getElementById("meta-tag");
  dom.metaPackage = document.getElementById("meta-package");
  dom.drawerRawMessage = document.getElementById("drawer-raw-message");

  // Status Bar
  dom.statusTotalLogs = document.getElementById("status-total-logs");
  dom.statusFilteredLogs = document.getElementById("status-filtered-logs");
  dom.statusBufferUsage = document.getElementById("status-buffer-usage");
  dom.pillApp = document.getElementById("pill-app");
  dom.pillLevel = document.getElementById("pill-level");
  dom.statusDeviceModel = document.getElementById("status-device-model");

  // Wi-Fi Modal
  dom.modalWifi = document.getElementById("modal-wifi");
  dom.btnCloseWifiModal = document.getElementById("btn-close-wifi-modal");
  dom.btnCancelWifi = document.getElementById("btn-cancel-wifi");
  dom.btnSubmitWifi = document.getElementById("btn-submit-wifi");
  dom.wifiAddressInput = document.getElementById("wifi-address-input");
}

function bindEventListeners() {
  // Device Selection
  dom.deviceSelect.addEventListener("change", (e) => {
    selectDevice(e.target.value);
  });

  dom.btnRefreshDevices.addEventListener("click", () => {
    loadDevices();
  });

  dom.btnClearBuffer.addEventListener("click", async () => {
    try {
      await fetch("/api/logs/clear", { method: "POST" });
    } catch (e) {
      console.error(e);
    }
    clearLogs();
  });

  // Navigation Tabs
  dom.tabAllLogs.addEventListener("click", () => {
    setActiveTab("ALL");
  });
  dom.navTelemetry.addEventListener("click", () => {
    setActiveTab("ALL");
  });
  dom.tabCrashes.addEventListener("click", () => {
    setActiveTab("F");
  });
  dom.navCrashes.addEventListener("click", () => {
    setActiveTab("F");
  });

  // Package Filter
  dom.packageSelect.addEventListener("change", (e) => {
    state.selectedPackage = e.target.value;
    updateActiveFilterPill();
    renderFilteredLogs();
  });

  // Level Buttons
  dom.levelBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      setLevelFilter(btn.dataset.level);
    });
  });

  // Search Omnibar
  dom.searchInput.addEventListener("input", (e) => {
    state.searchTerm = e.target.value;
    dom.btnClearSearch.classList.toggle("hidden", !state.searchTerm);
    renderFilteredLogs();
  });

  dom.btnClearSearch.addEventListener("click", () => {
    dom.searchInput.value = "";
    state.searchTerm = "";
    dom.btnClearSearch.classList.add("hidden");
    renderFilteredLogs();
  });

  dom.btnRegex.addEventListener("click", () => {
    state.isRegex = !state.isRegex;
    dom.btnRegex.classList.toggle("bg-primary", state.isRegex);
    dom.btnRegex.classList.toggle("text-surface-lowest", state.isRegex);
    renderFilteredLogs();
  });

  dom.btnCase.addEventListener("click", () => {
    state.isCaseSensitive = !state.isCaseSensitive;
    dom.btnCase.classList.toggle("bg-primary", state.isCaseSensitive);
    dom.btnCase.classList.toggle("text-surface-lowest", state.isCaseSensitive);
    renderFilteredLogs();
  });

  // Playback Controls
  dom.btnPause.addEventListener("click", () => {
    state.isPaused = !state.isPaused;
    if (state.isPaused) {
      dom.pauseText.textContent = "Paused";
      dom.pauseIndicator.classList.remove("bg-tertiary", "animate-pulse");
      dom.pauseIndicator.classList.add("bg-warning");
      dom.btnPause.classList.add("bg-warning/20", "border-warning/50", "text-warning");
      dom.btnPause.classList.remove("bg-tertiary/15", "border-tertiary/40", "text-tertiary");
    } else {
      dom.pauseText.textContent = "Streaming";
      dom.pauseIndicator.classList.add("bg-tertiary", "animate-pulse");
      dom.pauseIndicator.classList.remove("bg-warning");
      dom.btnPause.classList.remove("bg-warning/20", "border-warning/50", "text-warning");
      dom.btnPause.classList.add("bg-tertiary/15", "border-tertiary/40", "text-tertiary");
      renderFilteredLogs();
    }
  });

  dom.btnAutoScroll.addEventListener("click", () => {
    state.autoScroll = !state.autoScroll;
    dom.btnAutoScroll.classList.toggle("text-primary", state.autoScroll);
    dom.btnAutoScroll.classList.toggle("text-outline", !state.autoScroll);
    if (state.autoScroll) scrollToBottom();
  });

  // Scroll detection to disable autoscroll if user scrolls up
  dom.logViewport.addEventListener("scroll", () => {
    const threshold = 60;
    const isAtBottom =
      dom.logViewport.scrollHeight - dom.logViewport.scrollTop - dom.logViewport.clientHeight <= threshold;
    if (!isAtBottom && state.autoScroll) {
      state.autoScroll = false;
      dom.btnAutoScroll.classList.remove("text-primary");
      dom.btnAutoScroll.classList.add("text-outline");
    }
  });

  // Export
  dom.btnExportTxt.addEventListener("click", () => exportLogs("txt"));
  dom.btnExportJson.addEventListener("click", () => exportLogs("json"));

  // Inspector Drawer Actions
  dom.btnCloseDrawer.addEventListener("click", closeInspector);
  dom.btnCopyRawLog.addEventListener("click", () => {
    if (state.selectedLogEntry) {
      copyToClipboard(state.selectedLogEntry.raw || JSON.stringify(state.selectedLogEntry, null, 2));
    }
  });
  dom.btnCopyStack.addEventListener("click", () => {
    if (state.selectedLogEntry) {
      copyToClipboard(state.selectedLogEntry.message);
    }
  });

  // Wi-Fi Modal
  dom.btnWifiConnect.addEventListener("click", () => {
    dom.modalWifi.classList.remove("hidden");
    dom.wifiAddressInput.focus();
  });
  dom.btnCloseWifiModal.addEventListener("click", () => dom.modalWifi.classList.add("hidden"));
  dom.btnCancelWifi.addEventListener("click", () => dom.modalWifi.classList.add("hidden"));
  dom.btnSubmitWifi.addEventListener("click", handleWifiConnect);

  dom.btnRestartAdb.addEventListener("click", () => {
    loadDevices();
  });
}

function setActiveTab(level) {
  if (level === "F") {
    dom.tabAllLogs.classList.remove("text-primary", "border-b-2", "border-primary");
    dom.tabAllLogs.classList.add("text-on-surface-variant");
    dom.tabCrashes.classList.add("text-primary", "border-b-2", "border-primary");
    dom.tabCrashes.classList.remove("text-on-surface-variant");

    dom.navTelemetry.classList.remove("bg-surface-high", "text-primary", "border-l-2", "border-primary");
    dom.navTelemetry.classList.add("text-on-surface-variant");
    dom.navCrashes.classList.add("bg-surface-high", "text-crash", "border-l-2", "border-crash");

    setLevelFilter("F");
  } else {
    dom.tabCrashes.classList.remove("text-primary", "border-b-2", "border-primary");
    dom.tabCrashes.classList.add("text-on-surface-variant");
    dom.tabAllLogs.classList.add("text-primary", "border-b-2", "border-primary");
    dom.tabAllLogs.classList.remove("text-on-surface-variant");

    dom.navCrashes.classList.remove("bg-surface-high", "text-crash", "border-l-2", "border-crash");
    dom.navTelemetry.classList.add("bg-surface-high", "text-primary", "border-l-2", "border-primary");

    setLevelFilter("ALL");
  }
}

function setLevelFilter(lvl) {
  state.selectedLevel = lvl;

  dom.levelBtns.forEach((b) => {
    const isSelected = b.dataset.level === lvl;
    b.classList.toggle("active", isSelected);
    b.classList.toggle("text-white", isSelected);
    b.classList.toggle("bg-surface-highest", isSelected);
  });

  updateActiveFilterPill();
  renderFilteredLogs();
}

function updateActiveFilterPill() {
  const pkgText = state.selectedPackage ? state.selectedPackage.split(".").pop() : "All";
  dom.pillApp.textContent = pkgText;
  dom.pillLevel.textContent = state.selectedLevel;
}

// ================= API CALLS =================

async function loadDevices() {
  try {
    const res = await fetch("/api/devices");
    const data = await res.json();
    state.devices = data.devices || [];
    state.selectedDevice = data.selected || null;

    dom.deviceSelect.innerHTML = "";

    if (state.devices.length === 0) {
      dom.deviceSelect.innerHTML = '<option value="">Searching for devices...</option>';
      dom.connectionDot.className = "w-2 h-2 rounded-full bg-warning animate-pulse";
      dom.connectionText.textContent = "Searching Devices";
      dom.statusDeviceModel.textContent = "No Device Connected";
      return;
    }

    state.devices.forEach((d) => {
      const opt = document.createElement("option");
      opt.value = d.serial;
      const connType = d.is_wifi ? "Wi-Fi" : d.is_emulator ? "Emulator" : "USB";
      opt.textContent = `${d.model} [${connType}]`;
      if (d.serial === state.selectedDevice) opt.selected = true;
      dom.deviceSelect.appendChild(opt);
    });

    const current = state.devices.find((d) => d.serial === state.selectedDevice) || state.devices[0];
    if (current) {
      dom.connectionDot.className = "w-2 h-2 rounded-full bg-tertiary animate-ping";
      dom.connectionText.textContent = `Connected (${current.is_wifi ? "Wi-Fi" : "USB"})`;
      dom.statusDeviceModel.textContent = `${current.model} (${current.serial})`;
    }

    loadPackages();
  } catch (err) {
    console.error("Failed to fetch devices:", err);
    dom.connectionDot.className = "w-2 h-2 rounded-full bg-error";
    dom.connectionText.textContent = "Connection Error";
  }
}

async function selectDevice(serial) {
  if (!serial) return;
  try {
    await fetch("/api/device/select", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ serial }),
    });
    state.selectedDevice = serial;
    clearLogs();
    loadDevices();
  } catch (err) {
    console.error("Failed to select device:", err);
  }
}

async function loadPackages() {
  try {
    const res = await fetch("/api/packages");
    const data = await res.json();
    state.packages = data.packages || [];

    dom.packageSelect.innerHTML = '<option value="">All Applications &amp; System</option>';

    // Sort running packages first
    state.packages.sort((a, b) => (b.is_running ? 1 : 0) - (a.is_running ? 1 : 0));

    state.packages.forEach((pkg) => {
      const opt = document.createElement("option");
      opt.value = pkg.package;
      const statusIcon = pkg.is_running ? `🟢 Running (PID: ${pkg.pids.join(",")})` : "⚪";
      opt.textContent = `${statusIcon} ${pkg.name} (${pkg.package})`;
      dom.packageSelect.appendChild(opt);
    });
  } catch (err) {
    console.error("Failed to fetch packages:", err);
  }
}

async function handleWifiConnect() {
  const address = dom.wifiAddressInput.value.trim();
  if (!address) return;

  dom.btnSubmitWifi.textContent = "Connecting...";
  dom.btnSubmitWifi.disabled = true;

  try {
    const res = await fetch("/api/adb/connect", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ address }),
    });
    const data = await res.json();
    if (data.success) {
      dom.modalWifi.classList.add("hidden");
      dom.wifiAddressInput.value = "";
      loadDevices();
    } else {
      alert(`Wi-Fi Connection Failed: ${data.message || "Unknown error"}`);
    }
  } catch (err) {
    alert(`Error: ${err}`);
  } finally {
    dom.btnSubmitWifi.textContent = "Connect";
    dom.btnSubmitWifi.disabled = false;
  }
}

// ================= SSE STREAMING =================

function initEventSource() {
  if (state.sse) {
    state.sse.close();
  }

  state.sse = new EventSource("/api/stream");

  state.sse.onopen = () => {
    dom.connectionDot.className = "w-2 h-2 rounded-full bg-tertiary animate-ping";
    dom.connectionText.textContent = "Streaming";
  };

  state.sse.onmessage = (e) => {
    if (state.isPaused) return;

    try {
      const data = JSON.parse(e.data);
      if (data.batch && Array.isArray(data.batch)) {
        processIncomingBatch(data.batch);
      }
    } catch (err) {
      console.error("SSE parse error:", err);
    }
  };

  state.sse.onerror = () => {
    dom.connectionDot.className = "w-2 h-2 rounded-full bg-warning animate-pulse";
    dom.connectionText.textContent = "Reconnecting...";
  };
}

function processIncomingBatch(batch) {
  batch.forEach((entry) => {
    state.logs.push(entry);
    if (entry.is_crash) {
      state.crashCount++;
    }
  });

  if (state.logs.length > state.maxLogs) {
    state.logs = state.logs.slice(-state.maxLogs);
  }

  updateCounters();

  // Fast path: filter batch and append directly
  const matches = batch.filter(matchesFilter);
  if (matches.length > 0) {
    dom.emptyState.classList.add("hidden");
    const fragment = document.createDocumentFragment();

    matches.forEach((entry) => {
      fragment.appendChild(buildLogRow(entry));
    });

    dom.logRowsContainer.appendChild(fragment);

    // Prune DOM rows if too many to keep UI silky smooth
    while (dom.logRowsContainer.children.length > state.maxDomRows) {
      dom.logRowsContainer.removeChild(dom.logRowsContainer.firstChild);
    }

    if (state.autoScroll) {
      scrollToBottom();
    }
  }
}

function updateCounters() {
  dom.statusTotalLogs.textContent = `Total: ${state.logs.length.toLocaleString()} logs`;
  dom.statusBufferUsage.textContent = `Buffer: ${state.logs.length.toLocaleString()}/${state.maxLogs.toLocaleString()}`;
  dom.crashBadgeCount.textContent = state.crashCount;
  dom.fatalCountPill.textContent = `${state.crashCount} Crash`;
  dom.navCrashCount.textContent = state.crashCount;
}

function clearLogs() {
  state.logs = [];
  state.crashCount = 0;
  state.selectedLogEntry = null;
  dom.logRowsContainer.innerHTML = "";
  dom.emptyState.classList.remove("hidden");
  closeInspector();
  updateCounters();
  dom.statusFilteredLogs.innerHTML = 'Filtered: <strong class="text-on-surface">0 logs</strong>';
}

// ================= FILTERING & RENDERING =================

function matchesFilter(entry) {
  // Level filter
  if (state.selectedLevel !== "ALL") {
    if (state.selectedLevel === "F") {
      if (!entry.is_crash && entry.level !== "F") return false;
    } else if (entry.level !== state.selectedLevel) {
      return false;
    }
  }

  // Package filter
  if (state.selectedPackage) {
    const matchesPkg =
      entry.package === state.selectedPackage ||
      entry.message.includes(state.selectedPackage) ||
      entry.tag.includes(state.selectedPackage);
    if (!matchesPkg) return false;
  }

  // Search filter (text / regex)
  if (state.searchTerm) {
    const targetText = `${entry.tag} ${entry.message} ${entry.pid || ""} ${entry.package || ""}`;
    if (state.isRegex) {
      try {
        const flags = state.isCaseSensitive ? "" : "i";
        const re = new RegExp(state.searchTerm, flags);
        if (!re.test(targetText)) return false;
      } catch {
        // Fallback to substring on malformed regex
        const needle = state.isCaseSensitive ? state.searchTerm : state.searchTerm.toLowerCase();
        const haystack = state.isCaseSensitive ? targetText : targetText.toLowerCase();
        if (!haystack.includes(needle)) return false;
      }
    } else {
      const needle = state.isCaseSensitive ? state.searchTerm : state.searchTerm.toLowerCase();
      const haystack = state.isCaseSensitive ? targetText : targetText.toLowerCase();
      if (!haystack.includes(needle)) return false;
    }
  }

  return true;
}

function renderFilteredLogs() {
  dom.logRowsContainer.innerHTML = "";
  const filtered = state.logs.filter(matchesFilter);

  dom.statusFilteredLogs.innerHTML = `Filtered: <strong class="text-on-surface">${filtered.length.toLocaleString()} logs</strong>`;

  if (filtered.length === 0) {
    dom.emptyState.classList.remove("hidden");
    return;
  }

  dom.emptyState.classList.add("hidden");
  const fragment = document.createDocumentFragment();

  // Render recent rows up to maxDomRows
  const displaySlice = filtered.slice(-state.maxDomRows);
  displaySlice.forEach((entry) => {
    fragment.appendChild(buildLogRow(entry));
  });

  dom.logRowsContainer.appendChild(fragment);

  if (state.autoScroll) {
    scrollToBottom();
  }
}

function buildLogRow(entry) {
  const row = document.createElement("div");
  row.className =
    "log-row flex items-center h-[28px] border-b border-border-subtle/50 px-2 cursor-pointer transition-colors select-text log-row-hover";

  // Level & Crash styling
  if (entry.is_crash) {
    row.className += " bg-red-950/25 border-l-2 border-crash";
  } else if (entry.level === "E") {
    row.className += " bg-red-950/15 border-l-2 border-error";
  } else if (entry.level === "W") {
    row.className += " border-l-2 border-warning";
  }

  if (state.selectedLogEntry && state.selectedLogEntry.id === entry.id) {
    row.classList.add("log-row-selected");
  }

  // Column 1: Time
  const colTime = document.createElement("div");
  colTime.className = "w-24 shrink-0 text-outline font-mono text-[10px]";
  colTime.textContent = entry.timestamp ? entry.timestamp.split(" ")[1] || entry.timestamp : "--:--:--";

  // Column 2: Level Badge
  const colLevel = document.createElement("div");
  colLevel.className = "w-10 shrink-0 text-center";
  colLevel.appendChild(createLevelBadge(entry));

  // Column 3: PID:TID
  const colPid = document.createElement("div");
  colPid.className = "w-24 shrink-0 text-outline font-mono text-[10px] truncate";
  colPid.textContent = entry.pid ? `${entry.pid}:${entry.tid || entry.pid}` : "-";

  // Column 4: Tag
  const colTag = document.createElement("div");
  colTag.className = "w-32 shrink-0 font-medium truncate pr-1";
  colTag.style.color = getTagColor(entry.tag, entry.level);
  colTag.textContent = entry.tag || "";
  colTag.title = entry.tag || "";

  // Column 5: Package / App
  const colPkg = document.createElement("div");
  colPkg.className = "w-48 shrink-0 text-outline truncate hidden md:block pr-2";
  colPkg.textContent = entry.package || "";
  colPkg.title = entry.package || "";

  // Column 6: Message
  const colMsg = document.createElement("div");
  colMsg.className = "flex-1 truncate";
  colMsg.style.color = getMessageColor(entry.level, entry.is_crash);
  colMsg.textContent = entry.message;

  row.appendChild(colTime);
  row.appendChild(colLevel);
  row.appendChild(colPid);
  row.appendChild(colTag);
  row.appendChild(colPkg);
  row.appendChild(colMsg);

  row.addEventListener("click", () => {
    document.querySelectorAll(".log-row-selected").forEach((el) => el.classList.remove("log-row-selected"));
    row.classList.add("log-row-selected");
    openInspector(entry);
  });

  return row;
}

function createLevelBadge(entry) {
  const span = document.createElement("span");
  span.className = "inline-block px-1.5 py-0.2 rounded font-mono text-[10px] font-bold";

  if (entry.is_crash) {
    span.className += " bg-crash text-white shadow-xs";
    span.textContent = "F";
  } else {
    switch (entry.level) {
      case "V":
        span.className += " bg-surface-high text-outline";
        span.textContent = "V";
        break;
      case "D":
        span.className += " bg-sky-500/15 text-primary border border-sky-500/30";
        span.textContent = "D";
        break;
      case "I":
        span.className += " bg-emerald-500/15 text-tertiary border border-emerald-500/30";
        span.textContent = "I";
        break;
      case "W":
        span.className += " bg-amber-500/15 text-warning border border-amber-500/30";
        span.textContent = "W";
        break;
      case "E":
        span.className += " bg-red-500/20 text-error border border-red-500/30";
        span.textContent = "E";
        break;
      default:
        span.className += " bg-surface-high text-on-surface";
        span.textContent = entry.level || "?";
    }
  }

  return span;
}

function getTagColor(tag, level) {
  if (level === "E" || level === "F") return "#f87171";
  if (level === "W") return "#fbbf24";
  if (level === "D") return "#38bdf8";
  return "#dfe2ef";
}

function getMessageColor(level, isCrash) {
  if (isCrash) return "#ffffff";
  if (level === "E") return "#fca5a5";
  if (level === "W") return "#fef08a";
  if (level === "V") return "#94a3b8";
  return "#e2e8f0";
}

function scrollToBottom() {
  dom.logViewport.scrollTop = dom.logViewport.scrollHeight;
}

// ================= INSPECTOR DRAWER =================

function openInspector(entry) {
  state.selectedLogEntry = entry;
  dom.inspectorDrawer.classList.remove("hidden");

  dom.metaTime.textContent = entry.timestamp || "--";
  dom.metaLevel.textContent = `${entry.level_name || entry.level} (${entry.level})`;
  dom.metaLevel.style.color = entry.is_crash ? "#ff1744" : entry.level === "E" ? "#ef4444" : entry.level === "W" ? "#f59e0b" : "#38bdf8";
  dom.metaPid.textContent = `${entry.pid || "-"} / TID: ${entry.tid || "-"}`;
  dom.metaTag.textContent = entry.tag || "(no tag)";
  dom.metaPackage.textContent = entry.package || "(system process)";
  dom.drawerRawMessage.textContent = entry.raw || entry.message;

  if (entry.is_crash) {
    dom.drawerCrashBanner.classList.remove("hidden");
    dom.drawerCrashTitle.textContent = entry.tag === "AndroidRuntime" ? "Android Runtime Fatal Crash" : "Crash / Fatal Exception";
    dom.drawerCrashSummary.textContent = entry.message;
  } else {
    dom.drawerCrashBanner.classList.add("hidden");
  }
}

function closeInspector() {
  state.selectedLogEntry = null;
  dom.inspectorDrawer.classList.add("hidden");
  document.querySelectorAll(".log-row-selected").forEach((el) => el.classList.remove("log-row-selected"));
}

// ================= EXPORT & UTILITIES =================

function exportLogs(format) {
  const filtered = state.logs.filter(matchesFilter);
  if (filtered.length === 0) {
    alert("No logs found to export.");
    return;
  }

  let content = "";
  let mime = "text/plain";
  let ext = "txt";

  if (format === "json") {
    content = JSON.stringify(filtered, null, 2);
    mime = "application/json";
    ext = "json";
  } else {
    content = filtered.map((e) => e.raw || `[${e.timestamp}] [${e.level}] ${e.tag}: ${e.message}`).join("\n");
  }

  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
  a.href = url;
  a.download = `sApkAnalyzer_logs_${timestamp}.${ext}`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function copyToClipboard(text) {
  navigator.clipboard.writeText(text).then(() => {
    alert("Copied to clipboard!");
  }).catch(() => {
    const ta = document.createElement("textarea");
    ta.value = text;
    document.body.appendChild(ta);
    ta.select();
    document.execCommand("copy");
    document.body.removeChild(ta);
    alert("Copied to clipboard!");
  });
}
