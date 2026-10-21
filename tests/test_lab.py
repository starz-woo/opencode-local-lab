import json
import tempfile
import unittest
from pathlib import Path
import lab


class Preparation(unittest.TestCase):
    def test_prepare_is_offline_fresh_and_has_public_task(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / 'trial'
            lab.prepare(root)
            self.assertTrue((root / 'workspace' / 'solution.py').is_file())
            self.assertIn('stdin', (root / 'workspace' / 'TASK.md').read_text())
            self.assertFalse((root / 'workspace' / 'grader.py').exists())
            with self.assertRaises(FileExistsError):
                lab.prepare(root)


class Grading(unittest.TestCase):
    def test_starter_and_forged_success_fail_real_external_grader(self):
        with tempfile.TemporaryDirectory() as d:
            w = lab.prepare(Path(d) / 'trial')
            self.assertGreater(lab.grade(w)['total'], 0)
            self.assertFalse(lab.grade(w)['passed'])
            (w / 'solution.py').write_text('raise SystemExit(0)\n')
            self.assertFalse(lab.grade(w)['passed'])

    def test_correct_solution_passes_external_cases(self):
        with tempfile.TemporaryDirectory() as d:
            w = lab.prepare(Path(d) / 'trial')
            (w / 'solution.py').write_text('import json,sys\nr=[]\nfor v in sorted(set(json.load(sys.stdin))):\n if r and r[-1][1]+1==v: r[-1][1]=v\n else: r.append([v,v])\nprint(json.dumps(r))\n')
            self.assertTrue(lab.grade(w)['passed'])
            (w / 'TASK.md').write_text('tamper')
            self.assertFalse(lab.grade(w)['passed'])


class Runtime(unittest.TestCase):
    def setUp(self):
        import contextlib
        import io
        stack = contextlib.ExitStack()
        stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
        stack.enter_context(contextlib.redirect_stderr(io.StringIO()))
        self.addCleanup(stack.close)

    def test_config_and_environment_are_isolated_no_global_key(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as d, patch.dict('os.environ', {'OPENCODE_CONFIG': 'bad', 'OTHER_API_KEY': 'secret'}):
            env = lab.environment(Path(d), 'supplied')
            self.assertNotIn('OTHER_API_KEY', env)
            self.assertNotIn('OPENCODE_CONFIG', env)
            self.assertEqual(env['LAB_KEY'], 'supplied')
            self.assertEqual(env['OPENCODE_DISABLE_PROJECT_CONFIG'], 'true')
            cfg = lab.config('model', 'http://localhost:8000/v1', 8)
            self.assertEqual(cfg['model'], 'lab/model')
            self.assertEqual(cfg['provider']['lab']['options']['apiKey'], '{env:LAB_KEY}')

    def test_events_require_completion_and_reject_errors(self):
        self.assertFalse(lab.events('')['completed'])
        event = json.dumps({'type':'step_finish', 'part': {'reason':'stop'}})
        self.assertTrue(lab.events(event)['completed'])
        self.assertIsNone(lab.events(event)['tokens'])
        self.assertFalse(lab.events(event + '\n' + json.dumps({'type':'error'}))['completed'])
        tool = json.dumps({'type':'step_finish', 'part': {'reason':'tool-calls'}})
        self.assertFalse(lab.events(tool)['completed'])

    def test_mocked_agent_success_requires_real_grader_and_no_raw_secret(self):
        from unittest.mock import patch
        real_process = lab.process
        solution = 'import json,sys\nr=[]\nfor v in sorted(set(json.load(sys.stdin))):\n if r and r[-1][1]+1==v: r[-1][1]=v\n else: r.append([v,v])\nprint(json.dumps(r))\n'
        def fake(command, cwd, env, timeout, data=None):
            if command[-1] == '--version':
                return {'status':'ok','code':0,'stdout':lab.VERSION}
            if 'run' in command:
                (Path(cwd)/'solution.py').write_text(solution)
                self.assertNotIn('grader.py', [p.name for p in Path(cwd).iterdir()])
                return {'status':'ok','code':0,'stdout':json.dumps({'type':'text','part':{'text':'SENSITIVE_OUTPUT'}})+'\n'+json.dumps({'type':'step_finish','part':{'reason':'stop','tokens':{'total':23}}})}
            return real_process(command,cwd,env,timeout,data)
        with tempfile.TemporaryDirectory() as d, patch.object(lab,'process',side_effect=fake), patch.object(lab,'resolve_command',return_value=['opencode']):
            out = Path(d)/'result'
            args = ['run','--execute','--model','mock','--base-url','http://localhost:8000/v1','--runtime','mock-only','--output',str(out)]
            self.assertEqual(lab.main(args),0)
            rows = json.loads((out/'results.json').read_text())
            self.assertEqual(rows[0]['correct'],6)
            self.assertEqual(rows[0]['tokens'],23)
            self.assertNotIn('SENSITIVE_OUTPUT',''.join(p.read_text() for p in out.iterdir()))
            self.assertEqual(lab.main(['report','--output',str(out)]),0)
            with self.assertRaises(FileExistsError): lab.main(args)

    def test_wrong_version_never_runs_agent_and_timeout_is_recorded(self):
        from unittest.mock import patch
        for response, expected in [({'status':'ok','code':0,'stdout':'9.9.9'}, 'version_mismatch'), ({'status':'timeout','code':None,'stdout':''}, 'timeout')]:
            with tempfile.TemporaryDirectory() as d, patch.object(lab,'process',return_value=response) as proc, patch.object(lab,'resolve_command',return_value=['opencode']):
                out = Path(d)/'result'
                self.assertEqual(lab.main(['run','--execute','--model','mock','--base-url','http://localhost:8000/v1','--runtime','mock-only','--output',str(out)]),1)
                self.assertEqual(proc.call_count,1)
                self.assertEqual(json.loads((out/'results.json').read_text())[0]['status'],expected)

    def test_rejects_invalid_and_secret_url_inputs(self):
        for args in [['--timeout','nan'],['--repeats','0'],['--key-env','not a variable']]:
            with self.assertRaises(SystemExit): lab.main(['run']+args)
        for url in ['http://user:password@localhost/v1','http://localhost/v1?key=secret','file:///tmp/model','http://localhost/{env:SECRET}']:
            with self.assertRaises(SystemExit): lab.main(['preview','--model','test','--base-url',url])

    def test_doctor_and_preview_do_not_start_processes(self):
        from unittest.mock import patch
        with patch.object(lab,'process',side_effect=AssertionError('external')):
            self.assertEqual(lab.main(['doctor']),0)
            self.assertEqual(lab.main(['preview','--model','id','--base-url','http://localhost:8000/v1']),0)

    def test_grader_rejects_candidate_public_test_forgery_and_symlink(self):
        with tempfile.TemporaryDirectory() as d:
            work = lab.prepare(Path(d)/'trial')
            (work/'public_test.py').write_text('print("all tests passed")')
            (work/'grade.json').write_text('{"passed":true,"total":999}')
            self.assertFalse(lab.grade(work)['passed'])
            (work/'solution.py').unlink()
            try:
                (work/'solution.py').symlink_to(work/'public_test.py')
            except OSError:
                self.skipTest('Windows symlink privilege unavailable')
            self.assertFalse(lab.grade(work)['passed'])

    def test_process_timeout_and_missing_executable(self):
        import os, sys
        self.assertEqual(lab.process([sys.executable, '-c', 'import time;time.sleep(10)'], '.', os.environ, .05)['status'], 'timeout')
        self.assertEqual(lab.process(['no-such-lab-executable'], '.', os.environ, 1)['status'], 'launch_error')

    def test_windows_npm_resolution_avoids_cmd_and_blocks_escape(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d).resolve()
            pkg = root / 'node_modules' / 'opencode-ai'
            (pkg / 'bin').mkdir(parents=True)
            (pkg / 'bin' / 'opencode').write_text('// node launcher')
            (pkg / 'package.json').write_text(json.dumps({'name':'opencode-ai', 'bin':{'opencode':'bin/opencode'}}))
            (root / 'node.exe').touch()
            shim = root / 'opencode.cmd'
            shim.write_text('@node "%dp0%node_modules/opencode-ai/bin/opencode" %*')
            cmd = lab.resolve_command(str(shim), windows=True)
            self.assertEqual(cmd, [str(root / 'node.exe'), str(pkg / 'bin' / 'opencode')])
            (pkg / 'package.json').write_text(json.dumps({'name':'opencode-ai','bin':'../../evil.js'}))
            with self.assertRaises(ValueError): lab.resolve_command(str(shim), windows=True)

    def test_default_run_never_launches_external_process(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as d, patch.object(lab, 'process', side_effect=AssertionError('external call')):
            self.assertEqual(lab.main(['run', '--output', str(Path(d)/'new')]), 0)
            self.assertFalse((Path(d)/'new').exists())

    def test_run_mocked_opencode_failure_is_reported_not_success(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as d:
            out = Path(d)/'result'
            with patch.object(lab, 'resolve_command', return_value=['opencode']), patch.object(lab, 'process', side_effect=[{'status':'ok','code':0,'stdout':lab.VERSION}, {'status':'ok','code':0,'stdout':''}]):
                rc = lab.main(['run','--execute','--output',str(out),'--model','test','--base-url','http://localhost:8000/v1','--runtime','mock-only'])
            self.assertEqual(rc, 1)
            result = json.loads((out/'results.json').read_text())
            self.assertEqual(result[0]['status'], 'protocol_error')
            self.assertIsNone(result[0]['tokens'])
            self.assertIn('protocol_error', (out/'results.csv').read_text())


if __name__ == '__main__':
    unittest.main()
