(function () {
  if (window.unretweetAllLoaded) return;
  window.unretweetAllLoaded = true;

  const AUTOMATION_KEY = "unretweetEnabled";
  const STATS_KEY = "unretweetStats";
  const PROCESSED_FLAG = "urtDone";
  const INTERVAL_MS = 400;
  const CLICK_DELAY_MS = 250;
  const WAIT_MIN_MS = 100;
  const WAIT_MAX_MS = 300;
  const MAX_IDLE_HEIGHT = 5;
  const MAX_NO_ACTION = 20;

  let enabled = false;
  let intervalId = null;
  let idleHeight = 0;
  let noActionCount = 0;
  let lastHeight = 0;
  let busy = false;
  let stopped = false;
  let scanRound = 0;
  const done = new Set();

  log("content script loaded on " + window.location.href);

  // ── Init ────────────────────────────────────────────

  chrome.storage.local.get([AUTOMATION_KEY], (s) => {
    enabled = Boolean(s[AUTOMATION_KEY]);
    if (enabled) start();
  });

  chrome.runtime.onMessage.addListener((msg) => {
    if (msg.action !== "toggleUnretweet") return true;
    enabled = Boolean(msg.enabled);
    done.clear();
    idleHeight = 0;
    noActionCount = 0;
    lastHeight = 0;
    stopped = false;
    scanRound = 0;
    if (enabled) start(); else stop();
    return true;
  });

  // ── Start / Stop ────────────────────────────────────

  function start() {
    stopped = false;
    log("STARTED scanning");
    report("scanning");
    tick();
    if (!intervalId) intervalId = setInterval(tick, INTERVAL_MS);
  }

  function stop() {
    log("STOPPED");
    if (intervalId) { clearInterval(intervalId); intervalId = null; }
  }

  function finish(reason) {
    stopped = true;
    enabled = false;
    stop();
    chrome.storage.local.set({ [AUTOMATION_KEY]: false });
    report(reason);
    log("FINISHED: " + reason);
  }

  // ── Main cycle ──────────────────────────────────────

  async function tick() {
    if (!enabled || busy || stopped) return;
    busy = true;
    scanRound++;
    try {
      const posts = Array.from(document.querySelectorAll("article"));
      let acted = 0;
      let unretweetFound = 0;

      if (scanRound === 1) {
        log("Page has " + posts.length + " articles");
        const testIds = new Set();
        posts.forEach(p => {
          p.querySelectorAll('[data-testid]').forEach(el => testIds.add(el.getAttribute('data-testid')));
        });
        log("data-testids found: " + [...testIds].join(", "));
      }

      for (const post of posts) {
        if (!enabled || stopped) break;

        const id = uid(post);
        if (post.dataset[PROCESSED_FLAG] === "1" || done.has(id)) continue;

        const unretweet = post.querySelector('[data-testid="unretweet"]');
        if (!unretweet) {
          post.dataset[PROCESSED_FLAG] = "1";
          continue;
        }

        unretweetFound++;
        const ok = await undoRetweet(post);
        if (ok) {
          done.add(id);
          acted++;
          log("OK #" + done.size);
        }
      }

      if (scanRound === 1) {
        log("Unretweet buttons found this round: " + unretweetFound);
      }

      advance(acted > 0);
      report(null);
    } finally {
      busy = false;
    }
  }

  // ── Undo one retweet ────────────────────────────────

  async function undoRetweet(post) {
    try {
      post.scrollIntoView({ block: "center" });
      await sleep(150);

      const btn = post.querySelector('[data-testid="unretweet"]');
      if (!btn) return false;

      btn.click();
      await sleep(CLICK_DELAY_MS);

      const ok = await confirmUndo();
      if (!ok) {
        await pressEscape();
        return false;
      }

      post.dataset[PROCESSED_FLAG] = "1";
      await sleep(rand(WAIT_MIN_MS, WAIT_MAX_MS));
      return true;
    } catch (e) {
      return false;
    }
  }

  // ── Confirm dialog ──────────────────────────────────

  async function confirmUndo() {
    let el = await waitFor('[data-testid="unretweetConfirm"]', 2000);
    if (el) { el.click(); await sleep(CLICK_DELAY_MS); return true; }

    const items = document.querySelectorAll('[role="menuitem"]');
    for (const it of items) {
      const t = (it.textContent || "").toLowerCase();
      if (t.includes("undo repost") || t.includes("撤销转推") || t.includes("取消转推")) {
        it.click(); await sleep(CLICK_DELAY_MS); return true;
      }
    }

    const drops = document.querySelectorAll('[data-testid="Dropdown"] span, [role="menu"] span, [role="menuitem"] span');
    for (const sp of drops) {
      const t = (sp.textContent || "").toLowerCase();
      if (t.includes("undo repost") || t.includes("撤销转推")) {
        sp.click(); await sleep(CLICK_DELAY_MS); return true;
      }
    }

    return false;
  }

  // ── Scroll & stop logic ─────────────────────────────

  function advance(acted) {
    const h = document.body.scrollHeight;

    if (acted) {
      idleHeight = 0;
      noActionCount = 0;
    } else {
      if (h === lastHeight) idleHeight++;
      else idleHeight = 0;
      noActionCount++;
    }

    lastHeight = h;

    if (idleHeight >= MAX_IDLE_HEIGHT) {
      finish("页面已到底，共清理 " + done.size + " 条转推");
      return;
    }
    if (noActionCount >= MAX_NO_ACTION) {
      finish("连续 " + MAX_NO_ACTION + " 轮未发现转推，共清理 " + done.size + " 条");
      return;
    }

    window.scrollTo(0, h);
  }

  // ── Helpers ─────────────────────────────────────────

  function uid(post) {
    return (
      post.querySelector('a[href*="/status/"]')?.href ||
      post.getAttribute("aria-labelledby") ||
      post.textContent?.slice(0, 500) ||
      crypto.randomUUID()
    );
  }

  async function waitFor(sel, timeout) {
    const t0 = Date.now();
    while (Date.now() - t0 < timeout) {
      const el = document.querySelector(sel);
      if (el) return el;
      await sleep(60);
    }
    return null;
  }

  async function pressEscape() {
    document.dispatchEvent(new KeyboardEvent("keydown", {
      key: "Escape", code: "Escape", keyCode: 27, which: 27,
      bubbles: true, cancelable: true,
    }));
    await sleep(150);
  }

  function sleep(ms) { return new Promise((r) => setTimeout(r, ms)); }
  function rand(min, max) { return Math.floor(Math.random() * (max - min + 1)) + min; }
  function log(msg) { console.log("[UnretweetAll] " + msg); }

  function report(reason) {
    chrome.storage.local.set({
      [STATS_KEY]: {
        processed: done.size,
        stopped: stopped,
        reason: reason === "scanning" ? "" : (reason || ""),
        scanning: reason === "scanning",
        round: scanRound
      }
    });
  }
})();
