// OpenCode v1.2.27: only export plugin functions (loader invokes every export).
import {mkdir, mkdtemp, writeFile, open, lstat} from 'node:fs/promises';
import os from 'node:os';
import {constants} from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const LIMIT = 6000;
// OpenCode bash uses POSIX quoting, including Git Bash on Windows.
const quote = (s) => "'" + s.replaceAll("'", "'\\''") + "'";

export default async function CompactPlugin(input = {}) {
  // Outside project by default. Opt-in override must also be outside sensitive workspaces.
  const state = path.resolve(process.env.OPENCODE_COMPACT_STATE || path.join(os.homedir(), '.opencode-compact'));
  const inWorkspace = [input.directory, input.worktree].filter(Boolean).some(root => {
    const relative = path.relative(path.resolve(root),state);
    return relative === '' || (!relative.startsWith('..' + path.sep) && relative !== '..' && !path.isAbsolute(relative));
  });
  const retrieve = fileURLToPath(new URL('../scripts/recover.mjs', import.meta.url));
  return {'tool.execute.after': async (input, result) => {
    if (inWorkspace || !result || typeof result.output !== 'string') return;
    const raw = result.output;
    const noisy = input.tool === 'grep' || input.tool === 'glob' ||
      (input.tool === 'bash' && /^(?:python(?:3)?\s+public_test\.py|npm\s+test|(?:npm|pnpm)\s+run\s+(?:test|build)|pytest|cargo\s+(?:test|build)|go\s+test)(?:\s+--[a-zA-Z0-9=-]+)*$/.test(input.args?.command?.trim() || ''));
    const eligible = noisy && !result.metadata?.truncated && raw.length > 8000 &&
      (input.tool !== 'bash' || result.metadata?.exit === 0);
    let output = raw;
    try {
      await mkdir(state, {recursive:true, mode:0o700});
      const info = await lstat(state);
      if (!info.isDirectory() || info.isSymbolicLink() ||
          (process.platform !== 'win32' && ((info.mode & 0o077) || info.uid !== process.getuid()))) return;
    } catch { return; }
    if (eligible) {
      try {
        const dir = await mkdtemp(path.join(state, 'output-'));
        const archive = path.join(dir, 'raw.txt');
        await writeFile(archive, raw, {encoding:'utf8', flag:'wx', mode:0o600});
        // Code-point selection never splits surrogate pairs. Offsets/metrics are UTF-16 characters.
        const points = Array.from(raw);
        const keep = new Set();
        const add = (a,b) => { for(let i=Math.max(0,a); i<Math.min(points.length,b); i++) keep.add(i); };
        add(0, 1200); add(points.length-1200, points.length);
        let unsafe = false, diagnostics = 0;
        for (const diagnostic of raw.matchAll(/^.*(?:error|failed|exception|traceback|:\d+:).*$/gim)) {
          if (++diagnostics > 3 || diagnostic[0].length > 700) { unsafe = true; break; }
          const at = Array.from(raw.slice(0, diagnostic.index)).length;
          add(at-150,at+Array.from(diagnostic[0]).length+350);
        }
        const indices = [...keep].sort((a,b)=>a-b);
        let selected = '', previous = -1, kept = 0;
        for (const i of indices) {
          if(i !== previous+1) selected += '\n[... omitted ...]\n';
          selected += points[i]; kept += points[i].length; previous=i;
        }
        const marker = `\n[compact: ${raw.length-kept} UTF-16 characters omitted; raw hook input archived, may already be natively truncated]\nArchive: ${JSON.stringify(archive)}\nRecover via bash (code-point range, start/count): node ${quote(retrieve)} ${quote(archive)} 0 2000\n`;
        output = selected + marker;
        if (unsafe || output.length > LIMIT) output = raw; // Long paths / unusual Unicode: fail open.
      } catch { output = raw; } // Never lose output on archive/permission failure.
    }
    result.output = output; // Mutable hook result is returned to AI SDK, not just UI metadata.
    try {
      // No args, command, model text, raw content, IDs, or secrets in metrics.
      const file = await open(path.join(state, 'metrics.jsonl'), constants.O_APPEND | constants.O_CREAT | constants.O_WRONLY | (constants.O_NOFOLLOW || 0), 0o600);
      try { await file.write(JSON.stringify({input_chars:raw.length, output_chars:output.length, reduced:output !== raw})+'\n'); }
      finally { await file.close(); }
    } catch { /* Metrics unavailable is not a tool failure. */ }
  }};
}
