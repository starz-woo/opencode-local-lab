import contextlib
import io
import json
import os
import subprocess
import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import lab

class Compact(unittest.TestCase):
    def test_real_fixture_output_reaches_real_plugin_without_inference(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            work=lab.prepare(root/'task')
            raw=subprocess.check_output([sys.executable,'public_test.py'],cwd=work)
            self.assertGreater(len(raw),8000)
            self.assertLess(len(raw),50000) # Below upstream byte truncation, also <2000 lines.
            self.assertLess(raw.count(b'\n'),2000)
            self.assertFalse(lab.grade(work)['passed'])
            source=root/'fixture.txt'
            source.write_bytes(raw)
            js = """
import plugin from './plugins/compact.mjs';
import {readFile} from 'node:fs/promises';
const raw = await readFile(process.argv[1], 'utf8');
const hooks = await plugin({});
const result = {output:raw,metadata:{exit:0},title:'fixture'};
await hooks['tool.execute.after']({tool:'bash',args:{command:'python public_test.py'}},result);
const archive=JSON.parse(result.output.match(/Archive: (.+)/)[1]);
if(await readFile(archive,'utf8') !== raw) throw new Error('archive mismatch');
if(!result.output.includes('ERROR solution.py:4:')) throw new Error('lost diagnostic');
console.log(JSON.stringify({input:raw.length,output:result.output.length,exit:result.metadata.exit}));
"""
            env=dict(os.environ,OPENCODE_COMPACT_STATE=str(root/'state'))
            result=json.loads(subprocess.check_output(['node','--input-type=module','-e',js,str(source)],cwd=lab.ROOT,env=env))
            self.assertLess(result['output'],result['input'])
            self.assertLessEqual(result['output'],6000)
            self.assertEqual(result['exit'],0)

    def test_metrics_are_numeric_only_corrupt_data_stays_unknown(self):
        with tempfile.TemporaryDirectory() as d:
            file=Path(d)/'metrics.jsonl'
            self.assertEqual(lab.plugin_metrics(file),{})
            file.write_text(json.dumps({'input_chars':12000,'output_chars':3000,'reduced':True})+'\n')
            self.assertEqual(lab.plugin_metrics(file)['plugin_reduced_events'],1)
            self.assertEqual(lab.plugin_metrics(file)['plugin_input_chars'],12000)
            for value in ['broken', '{}', json.dumps({'input_chars':'SENSITIVE','output_chars':1,'reduced':True})]:
                file.write_text(value)
                self.assertEqual(lab.plugin_metrics(file),{})

    def test_compare_dry_run_never_launches(self):
        with patch.object(lab, 'process', side_effect=AssertionError('inference forbidden')), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(lab.main(['compare']), 0)

    def test_variants_only_change_plugin_and_same_noisy_task(self):
        baseline = lab.config('same','http://localhost/v1',10, 'baseline')
        compact = lab.config('same','http://localhost/v1',10, 'compact')
        plugin = compact.pop('plugin')
        self.assertTrue(plugin[0].endswith('/plugins/compact.mjs'))
        baseline.pop('plugin')
        self.assertEqual(baseline,compact)
        with tempfile.TemporaryDirectory() as d:
            work=lab.prepare(Path(d)/'task')
            text=(work/'public_test.py').read_text()
            self.assertIn('diagnostic', text)
            self.assertIn('public_test.py',lab.TASK)

    def test_counterbalanced_failures_retained_and_metrics_unknown(self):
        order=[]
        def fake(command,cwd,env,timeout,data=None):
            if command[-1]=='--version': return {'status':'ok','code':0,'stdout':lab.VERSION}
            cfg=json.loads(env['OPENCODE_CONFIG_CONTENT'])
            order.append('compact' if cfg['plugin'] else 'baseline')
            return {'status':'timeout','code':-1,'stdout':''}
        with tempfile.TemporaryDirectory() as d, patch.object(lab,'process',side_effect=fake), patch.object(lab,'resolve_command',return_value=['opencode']), contextlib.redirect_stdout(io.StringIO()):
            out=Path(d)/'results'
            rc=lab.main(['compare','--execute','--model','mock','--base-url','http://localhost/v1','--runtime','mock','--repeats','2','--output',str(out)])
            self.assertEqual(rc,1)
            self.assertEqual(order,['baseline','compact','compact','baseline'])
            rows=json.loads((out/'results.json').read_text())
            self.assertEqual(len(rows),4)
            self.assertTrue(all(r['status']=='timeout' and r['plugin_input_chars'] is None for r in rows))
