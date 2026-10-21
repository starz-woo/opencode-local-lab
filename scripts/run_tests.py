"""Run all offline stdlib tests; no OpenCode installation or model calls."""
import os
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
os.chdir(root)
# Honor caller's scratch location when supplied.
if os.environ.get('TMPDIR'):
    tempfile.tempdir = os.environ['TMPDIR']
suite = unittest.defaultTestLoader.discover(str(root / 'tests'))
if suite.countTestCases() == 0:
    raise SystemExit('Refusing empty test suite')
python_ok = unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful()
node = subprocess.run(['node', '--test', str(root / 'tests/compact.test.mjs')], check=False)
raise SystemExit(0 if python_ok and node.returncode == 0 else 1)
