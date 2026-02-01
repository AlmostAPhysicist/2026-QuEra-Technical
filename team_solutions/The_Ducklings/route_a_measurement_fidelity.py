#!/usr/bin/env python3
"""
ROUTE A: Measurement Outcome Fidelity
======================================

This approach is closest to test2.py.

Fidelity = success rate of final measurement outcome

Logic:
1. Prepare logical |ψ>
2. Inject errors
3. Extract syndrome & correct
4. Decode to physical qubit
5. Measure in Z basis
6. Compare to expected outcome for that state

For |0⟩/|+⟩: expect 0
For |1⟩/|-⟩: expect 1

Fidelity = (# correct measurements) / total shots
"""

from random import choice, randint, random
from collections import Counter

from bloqade import squin
from bloqade.pyqrack import StackMemorySimulator

from qec.encoding import prepareLogicalQubit, decode_713_block
from qec.errors import inject_pauli
from qec.syndrome import measure_clean_syndromes
from qec.error_mapping import color_parities, locate_flipped_qubit

emu = StackMemorySimulator()

import math
pi = math.pi

CLIFFORD_STATES = {
    "|0>": (0.0, 0.0, 0),           # expect 0
    "|1>": (pi, 0.0, 1),             # expect 1
    "|+>": (pi/2, 0.0, 0),           # expect 0
    "|->": (pi/2, pi, 1),            # expect 1
}


def sample_error_events(p1: float, r: float = 0.25, max_errors: int = 2):
    """Sample up to 2 errors for speed."""
    errors = []
    prob = p1
    k = 0

    while k < max_errors and random() < prob:
        k += 1
        prob *= r

    for _ in range(k):
        idx = randint(0, 6)
        basis = randint(0, 2)
        errors.append((idx, basis))

    return errors


@squin.kernel
def inject_multiple(block, e1_i, e1_b, e2_i, e2_b):
    if e1_i >= 0: inject_pauli(block, e1_i, e1_b)
    if e2_i >= 0: inject_pauli(block, e2_i, e2_b)


@squin.kernel
def baseline_measure(theta, phi, e1_i, e1_b, e2_i, e2_b):
    """No correction, just measure."""
    block = prepareLogicalQubit(theta, phi)
    inject_multiple(block, e1_i, e1_b, e2_i, e2_b)
    decode_713_block(block)
    return squin.measure(block[6])


@squin.kernel
def measure_with_correction(theta, phi, 
                           e1_i, e1_b, e2_i, e2_b,
                           corr_i, corr_b):
    """Measure with error injection and correction."""
    block = prepareLogicalQubit(theta, phi)
    inject_multiple(block, e1_i, e1_b, e2_i, e2_b)
    
    if corr_i >= 0:
        inject_pauli(block, corr_i, corr_b)
    
    decode_713_block(block)
    return squin.measure(block[6])


@squin.kernel
def extract_syndrome(theta, phi, e1_i, e1_b, e2_i, e2_b):
    """Extract X and Z syndromes."""
    data = prepareLogicalQubit(theta, phi)
    inject_multiple(data, e1_i, e1_b, e2_i, e2_b)
    
    # X syndrome
    probeX = prepareLogicalQubit(0.0, pi/2)
    for j in range(7):
        squin.cx(data[j], probeX[j])
    measX = squin.broadcast.measure(probeX)
    
    # Z syndrome
    probeZ = prepareLogicalQubit(0.0, 0.0)
    for j in range(7):
        squin.cx(probeZ[j], data[j])
    for j in range(7):
        squin.h(probeZ[j])
    measZ = squin.broadcast.measure(probeZ)
    
    return measX, measZ


def run_route_a(p1: float, shots: int = 100):
    """
    ROUTE A: Measurement Outcome Fidelity
    
    Metrics:
    - baseline_fid: % correct measurements WITHOUT correction
    - corrected_fid: % correct measurements WITH correction
    """
    
    # Get baseline syndrome
    baseX, baseZ = list(
        emu.task(measure_clean_syndromes,
                 args=(0.0, 0.0)).batch_run(shots=1)
    )[0]
    
    synX0 = color_parities([int(b) for b in baseX])
    synZ0 = color_parities([int(b) for b in baseZ])
    
    baseline_correct = 0
    corrected_correct = 0
    flip_hist = Counter()
    
    for _ in range(shots):
        label = choice(list(CLIFFORD_STATES.keys()))
        theta, phi, expected = CLIFFORD_STATES[label]
        
        # Sample errors
        errors = sample_error_events(p1)
        flip_hist[len(errors)] += 1
        
        while len(errors) < 2:
            errors.append((-1, 0))
        
        (e1_i, e1_b), (e2_i, e2_b) = errors
        
        # ===== BASELINE (no correction) =====
        meas_base = int(list(
            emu.task(baseline_measure,
                     args=(theta, phi, e1_i, e1_b, e2_i, e2_b)).batch_run(shots=1)
        )[0])
        
        if meas_base == expected:
            baseline_correct += 1
        
        # ===== CORRECTION =====
        # Extract syndrome
        measX, measZ = list(
            emu.task(extract_syndrome,
                     args=(theta, phi, e1_i, e1_b, e2_i, e2_b)).batch_run(shots=1)
        )[0]
        
        synX1 = color_parities([int(b) for b in measX])
        synZ1 = color_parities([int(b) for b in measZ])
        
        # Locate error
        x_loc = locate_flipped_qubit(synX0, synX1)
        z_loc = locate_flipped_qubit(synZ0, synZ1)
        
        if x_loc != -1 and z_loc != -1:
            corr_b, corr_i = 1, x_loc  # Y
        elif x_loc != -1:
            corr_b, corr_i = 0, x_loc  # X
        elif z_loc != -1:
            corr_b, corr_i = 2, z_loc  # Z
        else:
            corr_b, corr_i = 0, -1
        
        # Measure with correction
        meas_corr = int(list(
            emu.task(measure_with_correction,
                     args=(theta, phi, e1_i, e1_b, e2_i, e2_b,
                           corr_i, corr_b)).batch_run(shots=1)
        )[0])
        
        if meas_corr == expected:
            corrected_correct += 1
    
    baseline_fid = baseline_correct / shots
    corrected_fid = corrected_correct / shots
    
    return baseline_fid, corrected_fid, flip_hist


if __name__ == "__main__":
    print("\n" + "="*70)
    print("ROUTE A: Measurement Outcome Fidelity")
    print("="*70)
    
    configs = [
        ("No noise", 0.0, 50),
        ("Low noise", 0.05, 100),
        ("Medium noise", 0.15, 100),
    ]
    
    for name, p1, shots in configs:
        print(f"\n{name} (p1={p1})")
        print("-" * 50)
        
        base_fid, corr_fid, hist = run_route_a(p1, shots)
        
        print(f"Baseline fidelity (no QEC)  = {base_fid:.4f}")
        print(f"Corrected fidelity (w/ QEC) = {corr_fid:.4f}")
        print(f"QEC improvement             = {corr_fid - base_fid:+.4f}")
        
        print("\nError distribution:")
        total = sum(hist.values())
        for k in sorted(hist.keys()):
            frac = hist[k] / total
            print(f"  {k} errors: {frac:.3f}")
