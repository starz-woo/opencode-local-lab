// Explicit CLI, not an automatically registered OpenCode tool. Prints only requested range.
import {readFile} from 'node:fs/promises';
const [archive, startText='0', countText='2000', ...extra] = process.argv.slice(2);
if (!archive || extra.length || !/^\d+$/.test(startText) || !/^\d+$/.test(countText) ||
    !Number.isSafeInteger(Number(startText)) || Number(countText) < 1 || Number(countText) > 4000) {
  console.error('Usage: node scripts/recover.mjs ARCHIVE START COUNT (code points; count 1..4000)');
  process.exitCode=2;
} else {
  try {
    const text = await readFile(archive, 'utf8');
    process.stdout.write(Array.from(text).slice(Number(startText),Number(startText)+Number(countText)).join(''));
  } catch { console.error('Archive unavailable; check path and permissions.'); process.exitCode=1; }
}
