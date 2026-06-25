const asar = require('C:/Users/Administrator/AppData/Roaming/npm/node_modules/@electron/asar');
const asarPath = 'E:/claude code files/League-of-Layla-AutoDrain-1.2.0_extracted/resources/app.asar';

// List all files
const files = asar.listPackage(asarPath);
console.log('Files in asar:');
files.forEach(f => console.log(' ', f));

// Try to read each file and check if it's intact
const testFiles = ['overlay.html', 'hub.html', 'package.json', 'layla-config.json', 'hub-renderer.js', 'preload.cjs', 'main.cjs'];
testFiles.forEach(f => {
  try {
    const content = asar.extractFile(asarPath, f);
    const str = content.toString('utf8');
    console.log(`\n=== ${f} ===`);
    console.log('First 120 chars:', JSON.stringify(str.substring(0, 120)));
    console.log('Length:', str.length);
  } catch(e) {
    console.log(`\n=== ${f} ERROR: ${e.message} ===`);
  }
});
