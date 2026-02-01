#!/usr/bin/env python3
import subprocess
import sys

result = subprocess.run([
    sys.executable, '-m', 'qec.main'
], cwd='team_solutions/The_Ducklings')

sys.exit(result.returncode)
