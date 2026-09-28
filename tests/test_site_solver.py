"""
Sitenin tarayıcı çözücüsü (site/solver.js) için tutarlılık kontrolü:
mesafe simetrik ve üçgen eşitsizliğini sağlıyor, çizilen yol uzunluğu mesafeye
eşit, üç algoritma dört kapı yeri ve 1/2/3 blokla çalışıyor.
Node.js kurulu değilse atlanır.
"""
import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.skipif(shutil.which('node') is None, reason="Node.js kurulu değil")
def test_browser_solver_consistent():
    script = Path(__file__).parent / 'js' / 'solver_check.js'
    r = subprocess.run(['node', str(script)], capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stdout + r.stderr
