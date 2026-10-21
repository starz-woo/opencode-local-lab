import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp, readFile, rm, stat} from 'node:fs/promises';
import os from 'node:os';
import {execFileSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import path from 'node:path';

test('real exported hook reduces long test logs, preserves middle diagnostics and archives exact UTF8', async () => {
  const {default: plugin} = await import('../plugins/compact.mjs');
  const dir = await mkdtemp(path.join(os.tmpdir(), "compact test's-"));
  try {
    process.env.OPENCODE_COMPACT_STATE = dir;
    const hooks = await plugin({directory: path.join(dir,'workspace')});
    const raw = 'ok 한글 😀\n'.repeat(1400) + 'ERROR src/solution.py:42: wrong boundary\n' + 'ok 한글 😀\n'.repeat(1400);
    const metadata = {exit: 0, truncated: false};
    const result = {title:'tests', output:raw, metadata};
    await hooks['tool.execute.after']({tool:'bash', args:{command:'python public_test.py'}}, result);
    assert.ok(result.output.length <= 6000);
    assert.match(result.output, /ERROR src\/solution.py:42/);
    assert.equal(result.metadata, metadata);
    const archive = JSON.parse(result.output.match(/Archive: (.+)/)[1]);
    assert.equal(await readFile(archive, 'utf8'), raw);
    if (process.platform !== 'win32') {
      assert.equal((await stat(archive)).mode & 0o777,0o600);
      assert.equal((await stat(path.dirname(archive))).mode & 0o777,0o700);
    }
    assert.match(result.output, /omitted/);
    if (process.platform !== 'win32') {
      const command = result.output.split('Recover via bash (code-point range, start/count): ')[1].trim();
      const text = execFileSync('bash',['-c',command],{encoding:'utf8'});
      assert.equal(text,Array.from(raw).slice(0,2000).join(''));
    }
    const recovered = execFileSync(process.execPath, [fileURLToPath(new URL('../scripts/recover.mjs', import.meta.url)), archive, '3', '29'], {encoding:'utf8'});
    assert.equal(recovered, Array.from(raw).slice(3,32).join(''));
    const unchanged = [
      ['bash', 'python public_test.py', 'short', {exit:0}],
      ['bash', 'python public_test.py', raw, {exit:1}],
      ['bash', 'python public_test.py', raw, {exit:0,truncated:true,outputPath:'/native/raw'}],
      ['bash', 'cat source.py', raw, {exit:0}],
      ['read', '', raw, {}], ['apply_patch','',raw,{}]
    ];
    for (const [tool,command,text,meta] of unchanged) {
      const r = {title:'unchanged',output:text,metadata:meta};
      await hooks['tool.execute.after']({tool,args:{command}}, r);
      assert.deepEqual(r, {title:'unchanged',output:text,metadata:meta});
    }
    const copies = await Promise.all(Array.from({length:8}, async () => {
      const r = {output:raw,metadata:{}};
      await hooks['tool.execute.after']({tool:'grep'},r);
      return JSON.parse(r.output.match(/Archive: (.+)/)[1]);
    }));
    assert.equal(new Set(copies).size,8);
    const multiple = {output:'noise\n'.repeat(1800)+'ERROR first.js:9: bad\n'+'noise\n'.repeat(500)+'ERROR second.js:10: bad\n'+'noise\n'.repeat(1800), metadata:{exit:0}};
    await hooks['tool.execute.after']({tool:'bash',args:{command:'npm test'}},multiple);
    assert.match(multiple.output,/ERROR first.js:9/);
    assert.match(multiple.output,/ERROR second.js:10/);
    const combined = {output:raw,metadata:{exit:0}};
    await hooks['tool.execute.after']({tool:'bash',args:{command:'npm test && cat source.py'}},combined);
    assert.equal(combined.output,raw);
    const inside = await plugin({directory:dir});
    const internal = {output:raw,metadata:{exit:0}};
    await inside['tool.execute.after']({tool:'bash',args:{command:'npm test'}},internal);
    assert.equal(internal.output,raw, 'reject archives inside workspace');
    process.env.OPENCODE_COMPACT_STATE = archive; // Existing file => archive write fails.
    const broken = await plugin({});
    const original = {output:raw,metadata:{exit:0}};
    await broken['tool.execute.after']({tool:'bash',args:{command:'npm test'}},original);
    assert.equal(original.output, raw);
  } finally { delete process.env.OPENCODE_COMPACT_STATE; await rm(dir,{recursive:true,force:true}); }
});
