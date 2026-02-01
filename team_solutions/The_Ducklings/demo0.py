"""
============================================================
The Ducklings: Steane [[7,1,3]] QEC Demo
============================================================

WHAT THIS DEMONSTRATES:
-----------------------
This demo showcases a complete quantum error correction (QEC) cycle
using the Steane [[7,1,3]] color code implemented on Bloqade:

1. Encode a logical qubit using 7 physical qubits
2. Inject a single-qubit Pauli error (X, Y, or Z) at a chosen location
3. Measure syndrome information to detect the error
4. Classically decode the syndrome to identify error type and location
5. Apply a correction operator to restore the original state
6. Verify correction by re-measuring syndromes

HOW TO RUN:
-----------
    python team_solutions/The_Ducklings/demo0.py

WHAT YOU'LL SEE:
----------------
- Baseline syndromes before error injection
- Syndromes after injecting the error (showing detection)
- Decoded error type and qubit location
- Syndromes after correction (should match baseline)
- Success/failure message

CUSTOMIZATION:
--------------
Edit the "PARAMETERS TO CHOOSE" section below to:
- Change the qubit index (0-6) where error is injected
- Change the error type ('X', 'Y', or 'Z')
- Use a random initial state instead of |0>

============================================================
"""

import sys
import os
from random import random

# Add the *parent* directory so Python sees qec as a package
this_dir = os.path.dirname(__file__)
sys.path.insert(0, this_dir)

from qec.correction import run_full_QEC
from qec.states import zeroState, plusState

if __name__ == "__main__":

    # ============================================================
    # PARAMETERS TO CHOOSE
    # ============================================================
    
    # Logical qubit initial state (arbitrary Bloch sphere angles)
    theta, phi = zeroState()  # |0> state

    # Or use |+> state or random state:
    # theta, phi = plusState()  # |+> state
    # theta, phi = random() * 3.1415926535, random() * 2 * 3.1415926535  # Random state
    
    # Qubit index where we'll inject an error (0-6 for the 7-qubit code)
    # The QEC circuit will detect and correct this error
    qubit_index = 4
    
    # Error type to inject: 'X', 'Y', or 'Z'
    error_type = 'Y'
    
    # ============================================================
    
    # Map error type to basis index
    ERROR_BASIS = {'X': 0, 'Y': 1, 'Z': 2}
    
    print("\n=== The Ducklings: Steane QEC demo ===\n")

    # Run full QEC cycle: inject error at qubit_index,
    # measure syndromes, decode error location, and apply correction
    run_full_QEC(theta, phi,
                 err_index=qubit_index,
                 err_basis=ERROR_BASIS[error_type])
