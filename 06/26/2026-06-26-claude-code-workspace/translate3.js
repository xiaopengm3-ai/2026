const fs = require('fs');
const path = require('path');

const DIR = 'e:/claude code files/League-of-Layla-AutoDrain-1.2.0_extracted/resources/app_extracted';

const H = 'hub-renderer.js';
let content = fs.readFileSync(path.join(DIR, H), 'utf8');

// Remaining translations
const reps = [
  ['text: "Close \\u00d7"', 'text: "关闭 \\u00d7"'],
  ['"Loading the machine\\u2026"', '"加载机器中…"'],
  ["${num.toLocaleString()} coin${num === 1 ? \"\" : \"s\"}", "${num.toLocaleString()} 币"],
  ['" unlocked."', '" 已解锁。"'],
  ['${total} item${total === 1 ? "" : "s"} \\u00b7 ${unlocked} unlocked', '${total} 项 \\u00b7 ${unlocked} 已解锁'],
  ['${total} item${total === 1 ? "" : "s"} in the catalog', '${total} 项在目录中'],
  ['Your balance: ${bal} Submission coin${bal === 1 ? "" : "s"}.', '余额：${bal} Submission 币。'],
  ['${ui.bimbo.account.totalPulls || 0} lifetime pull${ui.bimbo.account.totalPulls === 1 ? "" : "s"}.', '${ui.bimbo.account.totalPulls || 0} 次抽卡。'],
  ['text: "Error"', 'text: "错误"'],
  ['"Mommy Layla"', '"Mommy Layla"'], // keep brand name
  // skip short ambiguous strings - handle via context if needed
];

for (const [s, r] of reps) {
  if (content.includes(s)) {
    content = content.split(s).join(r);
    console.log('OK: ' + s.substring(0,60));
  } else {
    console.log('SKIP: ' + s.substring(0,60));
  }
}

fs.writeFileSync(path.join(DIR, H), content, 'utf8');
console.log('\nDone!');
