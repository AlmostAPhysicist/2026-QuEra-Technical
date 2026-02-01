"""
QEC Package: Quantum Error Correction for [[7,1,3]] Color Code

A complete implementation of Steane's quantum error correction using QuEra's
magic state distillation (MSD) injection circuit for the [[7,1,3]] color code.

CORE CONCEPT
============
Encode 1 logical qubit into 7 physical qubits to detect and correct single-qubit errors.

PIPELINE
========
1. prepareLogicalQubit(theta, phi) → |ψ_L⟩
   Encode physical state into logical block via MSD circuit

2. measure_clean_syndromes(theta, phi) → baseline syndromes
   Measure syndrome reference (no error)

3. measure_error_syndromes(theta, phi, err_idx, err_basis) → syndromes with error
   Inject error, measure syndromes

4. Classical decode: compare syndromes, identify error location + type

5. Apply correction Pauli to flip error back

6. verify_correction() → remeasure syndromes
   Confirm error was cancelled

7. decode_713_block(reg) → |ψ⟩
   Recover original state from logical block

EXAMPLE
=======
from qec import *

theta, phi = zeroState()
run_full_QEC(theta, phi, err_index=4, err_basis=1)  # Y error on qubit 4

Expected: Detection → Correction → Verification → SUCCESS

See slides_notes.txt for detailed explanation.
"""

# qec package initializer - exposes a clean surface for run_demo.py
from .states import zeroState, oneState, plusState, minusState
from .encoding import setPhysicalQubit, encode_713_block, decode_713_block, prepareLogicalQubit
from .logical_ops import logical_X_roundtrip
from .errors import inject_pauli
from .syndrome import measure_clean_syndromes, measure_error_syndromes, verify_correction, measure_X_syndrome, measure_Z_syndrome
from .error_mapping import color_parities, locate_flipped_qubit
from .correction import run_full_QEC
from .experiments import run_noiseless, run_with_noise, postselected_memory_experiment, sweep_logical_error_vs_p
