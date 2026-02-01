"""
Entry point for judges:

python team_solutions/The_Ducklings/run_demo.py
"""

import sys
import os
from random import random

# Add the *parent* directory so Python sees qec as a package
this_dir = os.path.dirname(__file__)
sys.path.insert(0, this_dir)

from qec.correction import run_full_QEC
from qec.states import plusState

if __name__ == "__main__":
    theta, phi = plusState()

    theta, phi = random() * 3.1415, random() * 6.2830

    print("\n=== The Ducklings: Steane QEC demo ===\n")

    run_full_QEC(theta, phi,
                 err_index=4,
                 err_basis=1)
