const AUTOMATION_KEY = "unretweetEnabled";
const STATS_KEY = "unretweetStats";

document.addEventListener("DOMContentLoaded", () => {
  const toggleBtn = document.getElementById("toggleBtn");
  const statusDot = document.getElementById("statusDot");
  const statsEl = document.getElementById("stats");
  const scanInfo = document.getElementById("scanInfo");
  let automationEnabled = false;

  if (typeof chrome === "undefined" || !chrome.storage || !chrome.tabs) {
    updateUI(false);
    return;
  }

  // Load initial state
  chrome.storage.local.get([AUTOMATION_KEY, STATS_KEY], (state) => {
    automationEnabled = Boolean(state[AUTOMATION_KEY]);
    updateUI(automationEnabled, state[STATS_KEY]);
  });

  // Real-time updates from content script
  chrome.storage.onChanged.addListener((changes) => {
    if (changes[AUTOMATION_KEY]) {
      automationEnabled = Boolean(changes[AUTOMATION_KEY].newValue);
    }
    const stats = changes[STATS_KEY] ? changes[STATS_KEY].newValue : null;
    updateUI(automationEnabled, stats);
  });

  toggleBtn?.addEventListener("click", toggle);

  function toggle() {
    automationEnabled = !automationEnabled;
    chrome.storage.local.set({
      [AUTOMATION_KEY]: automationEnabled,
      [STATS_KEY]: { processed: 0, stopped: false, reason: "", scanning: false }
    }, () => {
      updateUI(automationEnabled, { processed: 0, stopped: false, reason: "", scanning: automationEnabled });
      chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
        const tab = tabs[0];
        if (!tab?.id) return;
        chrome.tabs.sendMessage(tab.id, {
          action: "toggleUnretweet",
          enabled: automationEnabled
        }, () => { void chrome.runtime.lastError; });
      });
    });
  }

  function updateUI(enabled, stats) {
    const count = stats?.processed || 0;
    const stopped = stats?.stopped;
    const reason = stats?.reason || "";
    const scanning = stats?.scanning;

    if (toggleBtn) {
      if (stopped) {
        toggleBtn.textContent = "清理完成";
        toggleBtn.classList.add("active");
      } else if (enabled) {
        toggleBtn.textContent = "停止清理";
        toggleBtn.classList.add("active");
      } else {
        toggleBtn.textContent = "开始清理转推";
        toggleBtn.classList.remove("active");
      }
    }

    statusDot?.classList.toggle("active", enabled && !stopped);

    if (statsEl) {
      if (stopped && count > 0) {
        statsEl.innerHTML = '共清理 <span class="count">' + count + '</span> 条转推';
      } else if (stopped) {
        statsEl.innerHTML = '未找到转推';
      } else if (enabled && count > 0) {
        statsEl.innerHTML = '已清理 <span class="count">' + count + '</span> 条';
      } else if (enabled) {
        statsEl.textContent = "正在扫描转推...";
      } else {
        statsEl.textContent = "";
      }
    }

    if (scanInfo) {
      scanInfo.textContent = stopped ? reason : "";
    }
  }
});
