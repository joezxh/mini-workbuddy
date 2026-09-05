/**
 * 跨平台构建脚本
 * 解决云效 CI 构建时 vue-tsc + vite build 内存溢出 (OOM) 问题
 *
 * 用法: node scripts/build.js <mode>
 *   mode: production | daily
 */
const { execSync } = require('child_process');

const mode = process.argv[2] || 'production';

// 设置 Node.js 堆上限为 8192MB，防止 vue-tsc 和 vite build OOM
// （代码量增长后 4096MB 已不够用，构建实测达到 ~3.8GB 后 OOM）
const existingOpts = process.env.NODE_OPTIONS || '';
if (!existingOpts.includes('--max-old-space-size')) {
  process.env.NODE_OPTIONS = (existingOpts + ' --max-old-space-size=8192').trim();
}

console.log('[build] mode=' + mode + ', NODE_OPTIONS=' + process.env.NODE_OPTIONS);

const execOpts = { stdio: 'inherit', env: process.env };

try {
  // Step 1: TypeScript 类型检查
  console.log('[build] Running vue-tsc...');
  execSync('npx vue-tsc', execOpts);

  // Step 2: Vite 构建
  console.log('[build] Running vite build --mode ' + mode + '...');
  execSync('npx vite build --mode ' + mode, execOpts);

  console.log('[build] Build complete!');
} catch (err) {
  console.error('[build] Build failed!');
  process.exit(1);
}
