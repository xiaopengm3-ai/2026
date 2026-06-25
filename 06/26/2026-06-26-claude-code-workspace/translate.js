// Safe translation script - only UI display strings, no data values
const fs = require('fs');
const path = require('path');

const DIR = 'e:/claude code files/League-of-Layla-AutoDrain-1.2.0_extracted/resources/app_extracted';

const reps = [

// === hub-renderer.js ===
['hub-renderer.js', 'root.textContent = "Loading League of Layla…"', 'root.textContent = "加载中…"'],

// Auth
['hub-renderer.js', '"Welcome to League of Layla"', '"欢迎来到 League of Layla"'],
['hub-renderer.js', '"Sign in to open the hub, or create an account to get started."', '"登录以打开控制中心，或创建新账户。"'],
['hub-renderer.js', 'text:\n          "Supabase URL / anon key are missing from layla-config.json. Auth will fail until the app is configured. Ping an admin."', 'text: "layla-config.json 缺少 Supabase 配置，请联系管理员。"'],
['hub-renderer.js', 'text: "Sign in"', 'text: "登录"'],
['hub-renderer.js', 'text: "Create account"', 'text: "创建账户"'],
['hub-renderer.js', '"Signing in…"', '"登录中…"'],
['hub-renderer.js', '"Sign-in failed."', '"登录失败。"'],
['hub-renderer.js', '"Creating…"', '"创建中…"'],
['hub-renderer.js', '"Sign-up failed."', '"注册失败。"'],
['hub-renderer.js', '"Email"', '"邮箱"'],
['hub-renderer.js', '"Password"', '"密码"'],
['hub-renderer.js', '"Confirm password"', '"确认密码"'],
['hub-renderer.js', '"Handle"', '"用户名"'],
['hub-renderer.js', '"Display name"', '"显示名称"'],
['hub-renderer.js', '"Avatar emoji (optional)"', '"头像表情 (可选)"'],
['hub-renderer.js', '"Passwords don\'t match."', '"密码不一致。"'],
['hub-renderer.js', '"Handle must be at least 2 characters."', '"用户名至少需要 2 个字符。"'],
['hub-renderer.js', '"Display name is required."', '"显示名称为必填项。"'],
['hub-renderer.js', '"Account created! Check your email for a confirmation link, then come back here and sign in."', '"账户已创建！请查收邮箱中的确认链接，然后返回此处登录。"'],

// Header
['hub-renderer.js', '"Signed in as "', '"已登录："'],
['hub-renderer.js', '"Sign out"', '"退出登录"'],
['hub-renderer.js', '"← Back"', '"← 返回"'],
['hub-renderer.js', '"← Home"', '"← 首页"'],

// View titles
['hub-renderer.js', '? "Content"\n        : ui.view === "bimbo"\n          ? "Bimbo Machine"\n          : "League of Layla"', '? "内容"\n        : ui.view === "bimbo"\n          ? "Bimbo 机器"\n          : "League of Layla"'],

// AutoDrain
['hub-renderer.js', 'text: "Running"', 'text: "运行中"'],
['hub-renderer.js', 'text: "Stopped"', 'text: "已停止"'],
['hub-renderer.js', 'text: "Working…"', 'text: "处理中…"'],
['hub-renderer.js', '"Checking Throne…"', '"检查 Throne 中…"'],
['hub-renderer.js', '"Throne connected"', '"Throne 已连接"'],
['hub-renderer.js', '"Throne not signed in"', '"Throne 未登录"'],
['hub-renderer.js', '"Throne unknown"', '"Throne 状态未知"'],
['hub-renderer.js', '"Login to Throne"', '"登录 Throne"'],
['hub-renderer.js', '"Re-check Throne"', '"重新检查"'],
['hub-renderer.js', '"Logout from Throne"', '"退出 Throne"'],
['hub-renderer.js', '"Start AutoDrain"', '"启动 AutoDrain"'],
['hub-renderer.js', '"Stop AutoDrain"', '"停止 AutoDrain"'],
['hub-renderer.js', '"Login to Throne first"', '"请先登录 Throne"'],

// AutoDrain messages
['hub-renderer.js', '"You\'re signed into Throne."', '"Throne 登录成功。"'],
['hub-renderer.js', '"Login cancelled — Throne window was closed."', '"登录取消 — Throne 窗口已关闭。"'],
['hub-renderer.js', '"A Throne login window is already open."', '"已有一个 Throne 登录窗口打开中。"'],
['hub-renderer.js', '"Couldn\'t confirm login."', '"无法确认登录状态。"'],
['hub-renderer.js', '"Signed out of Throne."', '"已退出 Throne。"'],
['hub-renderer.js', '"Couldn\'t clear Throne session."', '"无法清除 Throne 会话。"'],
['hub-renderer.js', '"You\'re not signed into Throne. Use the Login button first."', '"您尚未登录 Throne，请先点击登录按钮。"'],
['hub-renderer.js', '"Couldn\'t start AutoDrain."', '"无法启动 AutoDrain。"'],

// AutoDrain description
['hub-renderer.js', 'text:\n        "Automates your Throne wishlist donations. You need to be signed into Throne first — the Login button opens Throne and closes itself when it detects you\'re signed in. AutoDrain then opens a Throne window every 1–10 minutes while running; stop any time."', 'text: "自动化您的 Throne 愿望单捐赠。需先登录 Throne — 点击登录按钮后会打开 Throne，检测到登录成功后自动关闭。AutoDrain 运行时每 1-10 分钟打开一次 Throne 窗口，可随时停止。"'],

// Panic
['hub-renderer.js', '"Panic button: "', '"紧急停止： "'],
['hub-renderer.js', '"Press "', '"按下 "'],
['hub-renderer.js', '" anywhere to stop AutoDrain and close all Throne windows immediately."', '" 即可立即停止 AutoDrain 并关闭所有 Throne 窗口。"'],

// Content
['hub-renderer.js', '"Browse content"', '"浏览内容"'],
['hub-renderer.js', '"Open catalog on website"', '"在网站打开目录"'],
['hub-renderer.js', '"No content listed yet."', '"暂无内容。"'],
['hub-renderer.js', '"Loading catalog…"', '"加载目录中…"'],
['hub-renderer.js', '"Loading…"', '"加载中…"'],

// Content - payload kind labels
['hub-renderer.js', 'text: "Image"', 'text: "图片"'],
['hub-renderer.js', 'text: "Video"', 'text: "视频"'],
['hub-renderer.js', 'text: "Photo bundle"', 'text: "图片集"'],
['hub-renderer.js', 'text: "Link"', 'text: "链接"'],
['hub-renderer.js', 'text: "Text"', 'text: "文字"'],

// Content - actions
['hub-renderer.js', 'text: "View"', 'text: "查看"'],
['hub-renderer.js', 'text: "Details"', 'text: "详情"'],
['hub-renderer.js', 'text: "Open on website"', 'text: "在网站打开"'],
['hub-renderer.js', 'text: "Refresh"', 'text: "刷新"'],
['hub-renderer.js', 'text: "Refreshing…"', 'text: "刷新中…"'],
['hub-renderer.js', 'text: "Unlocked"', 'text: "已解锁"'],
['hub-renderer.js', 'text: "Retry"', 'text: "重试"'],
['hub-renderer.js', 'text: "Preview on website"', 'text: "在网站预览"'],
['hub-renderer.js', 'text: "Loading media…"', 'text: "加载媒体中…"'],
['hub-renderer.js', 'text: "Couldn\'t load media"', 'text: "无法加载媒体"'],
['hub-renderer.js', 'text: "Media unavailable."', 'text: "媒体不可用。"'],

// Content status
['hub-renderer.js', 'text: "Locked"', 'text: "已锁定"'],
['hub-renderer.js', 'text: "Could not load content."', 'text: "无法加载内容。"'],
['hub-renderer.js', 'text: "Unlock failed."', 'text: "解锁失败。"'],
['hub-renderer.js', '"Spend Submission coins to unlock Mommy Layla\'s content."', '"花费 Submission 币解锁 Mommy Layla 的专属内容。"'],
['hub-renderer.js', '"Browse Mommy Layla\'s catalog of unlockable content."', '"浏览 Mommy Layla 的可解锁内容目录。"'],
['hub-renderer.js', '"Spend Submission coins to unlock. Media plays on the website."', '"花费 Submission 币解锁。媒体在网站播放。"'],
['hub-renderer.js', '"You\'re Mommy Layla — these are your items."', '"您是 Mommy Layla — 以下是您的内容。"'],
['hub-renderer.js', '"Browse the catalog. Unlocks are for subs."', '"浏览目录。解锁内容仅供 subs。"'],
['hub-renderer.js', '"Sign in as a sub to unlock content."', '"以 sub 身份登录以解锁内容。"'],
['hub-renderer.js', '"Not enough coins"', '"币不足"'],
['hub-renderer.js', '"Unlocking…"', '"解锁中…"'],

// Censor
['hub-renderer.js', '"Censor mode on"', '"审查模式：开"'],
['hub-renderer.js', '"Censor mode off"', '"审查模式：关"'],
['hub-renderer.js', '"Enable censor"', '"开启审查"'],
['hub-renderer.js', '"Enabling…"', '"开启中…"'],
['hub-renderer.js', '"Mommy-only to lift"', '"仅 Mommy 可解除"'],
['hub-renderer.js', '"Only Mommy Layla can lift censor mode."', '"仅 Mommy Layla 可以解除审查模式。"'],
['hub-renderer.js', '"Manage censor (subs)"', '"管理审查 (subs)"'],
['hub-renderer.js', '"Hide censor admin"', '"隐藏审查管理"'],
['hub-renderer.js', '"All"', '"全部"'],
['hub-renderer.js', '"Censor on"', '"审查中"'],
['hub-renderer.js', '"Off"', '"关闭"'],
['hub-renderer.js', '"Lift censor"', '"解除审查"'],
['hub-renderer.js', '"Lifting…"', '"解除中…"'],
['hub-renderer.js', '"Turn on censor"', '"开启审查"'],
['hub-renderer.js', '"No subs yet."', '"暂无 subs。"'],
['hub-renderer.js', '"No subs match the selected filter."', '"没有匹配筛选条件的 subs。"'],
['hub-renderer.js', '"Censor mode is on. Nude-tagged content is blurred."', '"审查模式已开启。标记为 nude 的内容已模糊处理。"'],
['hub-renderer.js', '"Couldn\'t enable censor mode."', '"无法开启审查模式。"'],
['hub-renderer.js', '"Couldn\'t lift censor mode."', '"无法解除审查模式。"'],
['hub-renderer.js', '"Couldn\'t load subs."', '"无法加载 subs 列表。"'],
['hub-renderer.js', '"Blurred (censor)"', '"已模糊（审查）"'],

// Censor long text
['hub-renderer.js', '"This content is tagged nude, so media is blurred until Mommy Layla lifts your censor mode."', '"此内容标记为 nude，媒体已模糊处理，需 Mommy Layla 解除审查。"'],
['hub-renderer.js', '"Turn censor mode on for any sub, or lift it when you\'re ready. Subs can opt in themselves, but only you can turn it off — and you can also force it on."', '"为任意 sub 开启审查模式，或随时解除。Subs 可自行加入，但仅您可关闭 — 也可强制开启。"'],

// Bimbo
['hub-renderer.js', '"Welcome to the Bimbo Machine."', '"欢迎来到 Bimbo 机器。"'],

// (unknown)
['hub-renderer.js', '"(unknown)"', '"(未知)"'],

// Filter labels
['hub-renderer.js', 'text: "All"', 'text: "全部"'],

// === main.cjs ===
['main.cjs', '"App misconfigured"', '"应用配置错误"'],
['main.cjs', '"Missing API base URL in layla-config.json."', '"layla-config.json 中缺少 API 基础 URL。"'],
['main.cjs', '"Not signed in"', '"未登录"'],
['main.cjs', '"Your Layla session has expired. Sign in from the hub and try again."', '"您的 Layla 会话已过期。请从控制中心重新登录后重试。"'],
['main.cjs', '"Network error"', '"网络错误"'],
['main.cjs', '"Claim could not be submitted"', '"无法提交捐赠申领"'],
['main.cjs', '"Sign in to Throne"', '"登录 Throne"'],

// === hub.html ===
['hub.html', 'Loading League of Layla…', '加载中…'],

];

// Apply
const results = {};
for (const [file, search, replace] of reps) {
  const fp = path.join(DIR, file);
  if (!fs.existsSync(fp)) continue;

  let content = fs.readFileSync(fp, 'utf8');
  if (!content.includes(search)) {
    console.log('NOT FOUND in ' + file + ': ' + search.substring(0, 80) + '...');
    continue;
  }
  content = content.split(search).join(replace);
  fs.writeFileSync(fp, content, 'utf8');
  results[file] = (results[file] || 0) + 1;
}

console.log('\n=== Results ===');
for (const [f, c] of Object.entries(results)) {
  console.log(f + ': ' + c + ' replacements');
}
console.log('\nTotal: ' + Object.values(results).reduce((a,b)=>a+b,0) + ' replacements');
console.log('Done!');
