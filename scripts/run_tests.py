"""Run all offline stdlib tests; no OpenCode installation or model calls."""
import os
from pathlib import Path
import sys
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
raise SystemExit(0 if unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful() else 1)
