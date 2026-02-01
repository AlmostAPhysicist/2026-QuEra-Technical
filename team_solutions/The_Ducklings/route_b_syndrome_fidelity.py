#!/usr/bin/env python3
"""
ROUTE B: Syndrome Restoration Fidelity
=======================================

This approach directly uses the QEC machinery.

Fidelity = success rate of syndrome RESTORATION

Logic:
1. Prepare logical |ψ>, measure clean syndrome (baseline)
2. Inject errors
3. Extract syndrome (changed by error)
4. Apply correction based on syndrome diff
5. Extract syndrome again
6. Fidelity = rate at which syndrome RETURNS to baseline

This tells us: "How well did error correction work?"
Not about final measurement outcome, but about syndrome agreement.
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
    "|0>": (0.0, 0.0),
    "|1>": (pi, 0.0),
    "|+>": (pi/2, 0.0),
    "|->": (pi/2, pi),
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
def extract_syndrome_after_error(theta, phi, e1_i, e1_b, e2_i, e2_b):
    """Extract syndrome after error injection."""
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


@squin.kernel
def verify_syndrome_after_correction(theta, phi, 
                                     e1_i, e1_b, e2_i, e2_b,
                                     corr_i, corr_b):
    """Extract syndrome after error AND correction."""
    data = prepareLogicalQubit(theta, phi)
    inject_multiple(data, e1_i, e1_b, e2_i, e2_b)
    
    if corr_i >= 0:
        inject_pauli(data, corr_i, corr_b)
    
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


def run_route_b(p1: float, shots: int = 100):
    """
    ROUTE B: Syndrome Restoration Fidelity
    
    Metrics:
    - syndrome_restoration_rate: % of trials where syndrome returns to baseline
    - error_detection_rate: % of errors that cause syndrome change
    """
    
    # Get baseline syndrome
    baseX, baseZ = list(
        emu.task(measure_clean_syndromes,
                 args=(0.0, 0.0)).batch_run(shots=1)
    )[0]
    
    synX0 = color_parities([int(b) for b in baseX])
    synZ0 = color_parities([int(b) for b in baseZ])
    
    syndrome_restored = 0
    error_detected = 0
    total_with_errors = 0
    flip_hist = Counter()
    
    for _ in range(shots):
        label = choice(list(CLIFFORD_STATES.keys()))
        theta, phi = CLIFFORD_STATES[label]
        
        # Sample errors
        errors = sample_error_events(p1)
        flip_hist[len(errors)] += 1
        
        while len(errors) < 2:
            errors.append((-1, 0))
        
        (e1_i, e1_b), (e2_i, e2_b) = errors
        
        # Count errors injected
        num_errors = sum(1 for e_i, _ in errors if e_i >= 0)
        
        if num_errors > 0:
            total_with_errors += 1
        
        # ===== SYNDROME AFTER ERROR =====
        measX, measZ = list(
            emu.task(extract_syndrome_after_error,
                     args=(theta, phi, e1_i, e1_b, e2_i, e2_b)).batch_run(shots=1)
        )[0]
        
        synX1 = color_parities([int(b) for b in measX])
        synZ1 = color_parities([int(b) for b in measZ])
        
        # Did error change syndrome?
        syndrome_changed = (synX1 != synX0) or (synZ1 != synZ0)
        if syndrome_changed:
            error_detected += 1
        
        # ===== CORRECTION =====
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
        
        # ===== SYNDROME AFTER CORRECTION =====
        measX2, measZ2 = list(
            emu.task(verify_syndrome_after_correction,
                     args=(theta, phi, e1_i, e1_b, e2_i, e2_b,
                           corr_i, corr_b)).batch_run(shots=1)
        )[0]
        
        synX2 = color_parities([int(b) for b in measX2])
        synZ2 = color_parities([int(b) for b in measZ2])
        
        # Did syndrome return to baseline?
        if synX2 == synX0 and synZ2 == synZ0:
            syndrome_restored += 1
    
    syndrome_restoration_rate = syndrome_restored / shots
    error_detection_rate = error_detected / total_with_errors if total_with_errors > 0 else 0.0
    
    return syndrome_restoration_rate, error_detection_rate, flip_hist


if __name__ == "__main__":
    print("\n" + "="*70)
    print("ROUTE B: Syndrome Restoration Fidelity")
    print("="*70)
    
    configs = [
        ("No noise", 0.0, 50),
        ("Low noise", 0.05, 100),
        ("Medium noise", 0.15, 100),
    ]
    
    for name, p1, shots in configs:
        print(f"\n{name} (p1={p1})")
        print("-" * 50)
        
        restore_rate, detect_rate, hist = run_route_b(p1, shots)
        
        print(f"Syndrome restoration rate = {restore_rate:.4f}")
        print(f"Error detection rate      = {detect_rate:.4f}")
        
        print("\nError distribution:")
        total = sum(hist.values())
        for k in sorted(hist.keys()):
            frac = hist[k] / total
            print(f"  {k} errors: {frac:.3f}")
