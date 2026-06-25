const fs = require('fs');
const path = require('path');

const DIR = 'e:/claude code files/League-of-Layla-AutoDrain-1.2.0_extracted/resources/app_extracted';

// Second pass - using exact Unicode characters from the file
const reps = [

// hub-renderer.js - using exact \u escapes
['hub-renderer.js', '"Checking Throne\\u2026"', '"检查中…"'],
['hub-renderer.js', '"Loading catalog\\u2026"', '"加载目录中…"'],
['hub-renderer.js', '"Unlocking\\u2026"', '"解锁中…"'],
['hub-renderer.js', '"Enabling\\u2026"', '"开启中…"'],
['hub-renderer.js', '"Lifting\\u2026"', '"解除中…"'],
['hub-renderer.js', '"Loading media\\u2026"', '"加载媒体中…"'],

// With — (em dash)
['hub-renderer.js', '"Login cancelled \\u2014 Throne window was closed."', '"登录取消 — Throne 窗口已关闭。"'],
['hub-renderer.js', '"You\'re Mommy Layla \\u2014 these are your items."', '"您是 Mommy Layla — 以下是您的内容。"'],

// Simple missed strings
['hub-renderer.js', '"Spend Submission coins to unlock Mommy Layla\'s content."', '"花费 Submission 币解锁 Mommy Layla 的专属内容。"'],
['hub-renderer.js', '"Browse Mommy Layla\'s catalog of unlockable content."', '"浏览 Mommy Layla 的可解锁内容目录。"'],
['hub-renderer.js', '"Spend Submission coins to unlock. Media plays on the website."', '"花费 Submission 币解锁。媒体在网站播放。"'],
['hub-renderer.js', '"Sign in as a sub to unlock content."', '"以 sub 身份登录以解锁内容。"'],
['hub-renderer.js', '"Browse the catalog. Unlocks are for subs."', '"浏览目录。解锁内容仅供 subs。"'],
['hub-renderer.js', '"Not enough coins"', '"币不足"'],

// Filter labels at line ~1490+
['hub-renderer.js', '{ v: "all", label: "All" }', '{ v: "all", label: "全部" }'],
['hub-renderer.js', '{ v: "on", label: "Censor on" }', '{ v: "on", label: "审查中" }'],
['hub-renderer.js', '{ v: "off", label: "Censor off" }', '{ v: "off", label: "未审查" }'],

// hub.html - title
['hub.html', '<title>League of Layla</title>', '<title>League of Layla</title>'],

];

// Read files
for (const [file, search, replace] of reps) {
  const fp = path.join(DIR, file);
  if (!fs.existsSync(fp)) { console.log('SKIP ' + file); continue; }
  let content = fs.readFileSync(fp, 'utf8');
  if (!content.includes(search)) {
    // Try without backslash escaping for unicode
    const unescaped = search.replace(/\\\\u/g, '\\u');
    if (content.includes(unescaped)) {
      content = content.split(unescaped).join(replace);
      fs.writeFileSync(fp, content, 'utf8');
      console.log('OK (unescaped) ' + file + ': ' + search.substring(0,60));
      continue;
    }
    console.log('NOT FOUND: ' + search.substring(0,80));
    continue;
  }
  content = content.split(search).join(replace);
  fs.writeFileSync(fp, content, 'utf8');
  console.log('OK ' + file + ': ' + search.substring(0,60));
}
console.log('Done!');
