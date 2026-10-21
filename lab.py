"""Offline-first local model lab. Only run --execute starts OpenCode."""
import argparse
import csv
import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from urllib.parse import urlsplit

def resolve_command(executable, windows=None):
    """Resolve official npm shim to Node entry; never interpolate CMD arguments."""
    found = shutil.which(executable) or executable
    shim = Path(found).resolve()
    windows = os.name == 'nt' if windows is None else windows
    if not windows or shim.suffix.lower() not in ('.cmd', '.bat'):
        return [str(found)]
    modules = shim.parent.parent if shim.parent.name == '.bin' else shim.parent / 'node_modules'
    package = (modules / 'opencode-ai').resolve()
    try:
        manifest = json.loads((package / 'package.json').read_text(encoding='utf-8'))
        entry = manifest['bin']
        entry = entry['opencode'] if isinstance(entry, dict) else entry
        if manifest['name'] != 'opencode-ai' or not isinstance(entry, str):
            raise ValueError('not official npm package')
        target = (package / entry).resolve()
        target.relative_to(package)
        text = shim.read_text(encoding='utf-8-sig').replace('\\', '/').lower()
        if entry.replace('\\', '/').lower() not in text or '%*' not in text or not target.is_file():
            raise ValueError('unrecognized npm shim')
    except (OSError, KeyError, TypeError, ValueError) as exc:
        raise ValueError('Use official opencode-ai npm installation or native executable') from exc
    if target.suffix.lower() == '.exe':
        return [str(target)]
    if target.suffix.lower() not in ('', '.js', '.cjs', '.mjs'):
        raise ValueError('Unsupported npm launcher type')
    node = shim.parent / 'node.exe'
    found_node = str(node) if node.is_file() else shutil.which('node.exe')
    if not found_node:
        raise ValueError('node.exe is required for npm launcher')
    return [found_node, str(target)]


def config(model, base_url, steps):
    selected = 'lab/' + model
    return {'$schema': 'https://opencode.ai/config.json', 'model': selected,
            'small_model': selected, 'default_agent': 'build', 'autoupdate': False,
            'share': 'disabled', 'plugin': [], 'mcp': {}, 'instructions': [],
            'lsp': False, 'formatter': False, 'permission': {'*': 'allow'},
            'agent': {'build': {'steps': steps}}, 'enabled_providers': ['lab'],
            'provider': {'lab': {'npm': '@ai-sdk/openai-compatible',
                'name': 'Explicit local endpoint', 'options': {'baseURL': base_url,
                'apiKey': '{env:LAB_KEY}', 'timeout': 60000},
                'models': {model: {'name': model}}}}}


def environment(root, key):
    # Allowlist: don't pass the user's provider keys, auth, plugins or proxy secrets.
    keep = {'PATH','SYSTEMROOT','WINDIR','COMSPEC','PATHEXT','PROCESSOR_ARCHITECTURE',
            'NUMBER_OF_PROCESSORS','OPENCODE_GIT_BASH_PATH'}
    env = {k: v for k, v in os.environ.items() if k.upper() in keep}
    for var, sub in {'HOME':'home','USERPROFILE':'home','OPENCODE_TEST_HOME':'home',
                     'XDG_CONFIG_HOME':'config','XDG_DATA_HOME':'data','XDG_CACHE_HOME':'cache',
                     'XDG_STATE_HOME':'state','APPDATA':'appdata','LOCALAPPDATA':'localappdata',
                     'OPENCODE_CONFIG_DIR':'opencode','TMP':'tmp','TEMP':'tmp','TMPDIR':'tmp'}.items():
        path = root / sub
        path.mkdir(parents=True, exist_ok=True)
        env[var] = str(path)
    for flag in ['DISABLE_AUTOUPDATE','DISABLE_DEFAULT_PLUGINS','DISABLE_LSP_DOWNLOAD',
                 'DISABLE_CLAUDE_CODE','DISABLE_EXTERNAL_SKILLS','DISABLE_MODELS_FETCH',
                 'DISABLE_PROJECT_CONFIG']:
        env['OPENCODE_' + flag] = 'true'
    env.update(LAB_KEY=key, OPENCODE_AUTO_SHARE='false', PYTHONIOENCODING='utf-8')
    # Managed enterprise settings also merge after inline config. Never use real managed dir.
    env['OPENCODE_TEST_MANAGED_CONFIG_DIR'] = str(root / 'managed-empty')
    return env


def events(output):
    completed, error, tokens, tools = False, False, [], 0
    for line in output.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if not isinstance(event, dict):
            continue
        error |= event.get('type') == 'error'
        tools += int(event.get('type') == 'tool_use')
        part = event.get('part', {})
        if event.get('type') == 'step_finish' and isinstance(part, dict):
            completed = part.get('reason') in ('stop', 'end-turn')
            usage = part.get('tokens', {})
            total = usage.get('total') if isinstance(usage, dict) else None
            tokens.append(total if isinstance(total, (int, float)) and not isinstance(total, bool) and math.isfinite(total) and total >= 0 else None)
    return {'completed': completed and not error,
            'tokens': sum(tokens) if tokens and all(x is not None for x in tokens) else None,
            'tool_events': tools}


VERSION = '1.2.27'
ROOT = Path(__file__).resolve().parent
TASK = '''Implement solution.py as a standalone Python CLI. Read one JSON array of
integers from stdin, remove duplicates, sort ascending, and output a JSON array
of maximal inclusive consecutive ranges [[start,end],...]. Empty input -> [].
Example: [3,1,2,2,7] -> [[1,3],[7,7]]. Negatives are valid.
Use only Python standard library. Do not modify TASK.md. No network needed.
Run public_test.py to check the public example. Hidden evaluation is external.
'''
STARTER = 'import json, sys\nvalues = json.load(sys.stdin)\nprint(json.dumps([]))\n'


def prepare(root):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=False)
    work = root / 'workspace'
    work.mkdir()
    (work / 'TASK.md').write_text(TASK, encoding='utf-8')
    (work / 'solution.py').write_text(STARTER, encoding='utf-8')
    (work / 'public_test.py').write_text(
        'import json, subprocess, sys\n'
        'p = subprocess.run([sys.executable, "solution.py"], input="[3,1,2,2,7]", text=True, capture_output=True)\n'
        'assert p.returncode == 0 and json.loads(p.stdout) == [[1,3],[7,7]]\n', encoding='utf-8')
    return work


def process(command, cwd, env, timeout, data=None):
    """No shell. Kill the process group / Windows tree on timeout or interruption."""
    options = {'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == 'nt' else {'start_new_session': True}
    try:
        p = subprocess.Popen(command, cwd=cwd, env=env, stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, **options)
    except OSError:
        return {'status': 'launch_error', 'code': None, 'stdout': ''}
    def kill():
        if os.name == 'nt':
            subprocess.run(['taskkill.exe', '/PID', str(p.pid), '/T', '/F'],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
        else:
            try:
                os.killpg(p.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
    try:
        out, _ = p.communicate(None if data is None else data.encode('utf-8'), timeout=timeout)
    except subprocess.TimeoutExpired:
        kill()
        p.communicate(timeout=10)
        return {'status': 'timeout', 'code': p.returncode, 'stdout': ''}
    except BaseException:
        kill()
        p.wait(timeout=10)
        raise
    return {'status': 'ok' if p.returncode == 0 else 'process_error',
            'code': p.returncode, 'stdout': out.decode('utf-8', errors='replace')}


def grade(work):
    """Trusted parent compares actual CLI output; no candidate-written test report."""
    cases = [([], []), ([8], [[8, 8]]), ([3,1,2,2,7], [[1,3],[7,7]]),
             ([-4,-2,-3,0,1], [[-4,-2],[0,1]]),
             ([1000000,-1000000,1000000], [[-1000000,-1000000],[1000000,1000000]]),
             (list(range(40, -41, -1)), [[-40,40]])]
    intact = (work / 'TASK.md').is_file() and (work / 'TASK.md').read_text(encoding='utf-8') == TASK
    solution = work / 'solution.py'
    if not solution.is_file() or solution.is_symlink():
        return {'passed': False, 'total': len(cases), 'correct': 0, 'integrity': intact}
    correct = 0
    # Execute a snapshot in a fresh grader cwd OUTSIDE the agent workspace.
    with tempfile.TemporaryDirectory(prefix='lab-grader-') as d:
        dst = Path(d) / 'candidate.py'
        shutil.copyfile(solution, dst)
        for value, expected in cases:
            result = process([sys.executable, '-I', str(dst)], d,
                             {'PATH': os.environ.get('PATH', ''), 'SYSTEMROOT': os.environ.get('SYSTEMROOT', '')},
                             3, json.dumps(value))
            try:
                answer = json.loads(result['stdout'])
                # Exact JSON structure/types, not boolean==integer equality.
                equal = json.dumps(answer) == json.dumps(expected)
                correct += int(result['status'] == 'ok' and equal)
            except (ValueError, TypeError):
                pass
    return {'passed': intact and correct == len(cases), 'total': len(cases),
            'correct': correct, 'integrity': intact}


def report(root, rows):
    (root / 'results.json').write_text(json.dumps(rows, indent=2), encoding='utf-8')
    with (root / 'results.csv').open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        for row in rows:
            writer.writerow({k: 'unknown' if v is None else v for k, v in row.items()})
    passed = sum(row['status'] == 'passed' for row in rows)
    text = f'# Baseline report\n\n{passed}/{len(rows)} passed (failures included).\n\n'
    text += 'Unknown token usage is not zero. No optimized comparison exists.\n'
    text += '\n| Trial | Status | Seconds | Tokens | Tests |\n|---|---|---|---|---|\n'
    for row in rows:
        text += f"| {row['trial']} | {row['status']} | {row['seconds']} | {row['tokens'] if row['tokens'] is not None else 'unknown'} | {row['correct']}/{row['total']} |\n"
    (root / 'REPORT.md').write_text(text, encoding='utf-8')


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=['doctor','prepare','preview','run','report'])
    p.add_argument('--execute', action='store_true', help='authorize model calls and auto-approved tools; NOT a sandbox')
    p.add_argument('--model', help='exact API model ID, without lab/ prefix')
    p.add_argument('--base-url', help='OpenAI-compatible endpoint including /v1 if needed')
    p.add_argument('--runtime', help='user-recorded engine/version/quantization/hardware description')
    p.add_argument('--key-env', default='LOCAL_MODEL_API_KEY', help='environment variable NAME, never key value')
    p.add_argument('--opencode', default='opencode', help='official executable or npm .cmd shim')
    p.add_argument('--output', default='results/baseline-01', help='new directory (report reads existing)')
    p.add_argument('--repeats', type=int, default=1)
    p.add_argument('--timeout', type=float, default=180)
    p.add_argument('--max-steps', type=int, default=10)
    return p


def main(argv=None):
    p = parser()
    a = p.parse_args(argv)
    root = Path(a.output).resolve()
    if a.repeats < 1 or a.max_steps < 1 or not math.isfinite(a.timeout) or a.timeout <= 0:
        p.error('repeats, max-steps and finite timeout must be positive')
    if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', a.key_env):
        p.error('key-env must be an environment variable name')
    if a.command == 'doctor':
        # Deliberately no --version execution or network. Missing tool != inference.
        print(json.dumps({'python': sys.version.split()[0], 'platform': sys.platform,
            'opencode_path': shutil.which(a.opencode), 'node_path': shutil.which('node'),
            'git_path': shutil.which('git'), 'bash_path': shutil.which('bash'),
            'required_opencode': VERSION, 'version_verified': False,
            'inference': False, 'note': 'Windows bash tools need Git for Windows; see README'}, indent=2))
        return 0
    if a.command == 'prepare':
        prepare(root)
        print('Prepared fresh public task; no process started.')
        return 0
    if a.command == 'report':
        rows = json.loads((root / 'results.json').read_text(encoding='utf-8'))
        if not rows:
            p.error('no results to report')
        report(root, rows)
        print(f'Regenerated report from {len(rows)} recorded trials.')
        return 0
    if a.command == 'run' and not a.execute:
        print('DRY RUN: no processes, model calls, or files. Use --execute in a disposable VM.\n'
              'Plan: exact version check -> fresh state/workspace per trial -> real OpenCode -> external grader -> JSON/CSV/report.\n'
              f'Budget: {a.timeout}s, {a.max_steps} steps, {a.repeats} trials; tokens unknown until measured.')
        return 0
    if not a.model or not a.base_url or (a.command == 'run' and not a.runtime):
        p.error('model, base-url, and (for execution) runtime are required')
    url = urlsplit(a.base_url)
    if url.scheme not in ('http','https') or not url.hostname or url.username or url.password or url.query or url.fragment:
        p.error('base-url must be HTTP(S), without credentials/query/fragment')
    if any(c in a.model + a.base_url for c in '{}\r\n'):
        p.error('config substitutions/control characters are not allowed')
    cfg = config(a.model, a.base_url, a.max_steps)
    if a.command == 'preview':
        print(json.dumps(cfg, indent=2))
        return 0
    root.mkdir(parents=True, exist_ok=False)
    # Metadata is explicit and contains no key or raw agent text.
    metadata = {'model':a.model, 'base_url':a.base_url, 'runtime':a.runtime,
                'opencode_version':VERSION, 'timeout':a.timeout, 'max_steps':a.max_steps,
                'repeats':a.repeats, 'cache':'fresh OpenCode state; server cache uncontrolled',
                'task':'ranges-v1', 'python':sys.version.split()[0], 'platform':sys.platform}
    (root / 'manifest.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')
    rows = []
    for index in range(a.repeats):
        start = time.monotonic()
        row = {'trial':index+1, 'status':'launch_error', 'seconds':0,
               'tokens':None, 'tool_events':0, 'correct':0, 'total':6, 'exit_code':None}
        try:
            with tempfile.TemporaryDirectory(prefix='opencode-lab-') as d:
                trial = Path(d)
                work = prepare(trial / 'task')
                env = environment(trial / 'isolated', os.environ.get(a.key_env, ''))
                env['OPENCODE_CONFIG_CONTENT'] = json.dumps(cfg)
                command = resolve_command(a.opencode)
                version = process(command + ['--version'], work, env, min(a.timeout, 30))
                if version['status'] != 'ok' or version['stdout'].strip() != VERSION:
                    row['status'] = 'version_mismatch' if version['status'] == 'ok' else version['status']
                else:
                    result = process(command + ['run', '--format', 'json', '--agent', 'build',
                        '--model', 'lab/' + a.model, 'Read TASK.md and implement solution.py. Check public_test.py.'], work, env, a.timeout)
                    summary = events(result['stdout'])
                    row.update(tokens=summary['tokens'], tool_events=summary['tool_events'], exit_code=result['code'])
                    row['status'] = result['status']
                    if row['status'] == 'ok':
                        row['status'] = 'protocol_error'
                        if summary['completed']:
                            grading = grade(work)
                            row.update(correct=grading['correct'], total=grading['total'])
                            row['status'] = 'passed' if grading['passed'] else 'grade_failed'
        except (OSError, ValueError, subprocess.SubprocessError):
            row['status'] = 'runner_error'
        row['seconds'] = round(time.monotonic() - start, 3)
        rows.append(row)
        report(root, rows)
    print(f'Recorded {len(rows)} trials; see REPORT.md, results.csv, results.json (raw text not retained).')
    return 0 if all(r['status'] == 'passed' for r in rows) else 1


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError):
        print('Operation failed: check paths and input; existing output is never overwritten.', file=sys.stderr)
        raise SystemExit(2)
