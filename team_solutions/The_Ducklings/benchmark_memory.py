#!/usr/bin/env python3
"""
Quantum Memory Benchmark - Measurement Outcome Fidelity

This benchmark tests how well the [[7,1,3]] Steane color code preserves
quantum states under Pauli errors.

FIDELITY METRIC (Route A):
    Fidelity = (# correct Z-basis measurements) / total shots
    
WORKFLOW:
    1. Prepare logical |ψ⟩_L
    2. Measure baseline syndrome (before errors)
    3. Inject Pauli errors
    4. Measure syndrome after error
    5. Locate error using syndrome diff
    6. Apply correction
    7. Measure syndrome after correction
    8. Decode and measure in Z basis
    9. Compare to expected outcome
    
THREE MODES TESTED:
    - Baseline: No error correction (just measure broken state)
    - Postselection: Only keep trials with clean syndrome
    - Correction: Apply QEC based on syndrome diagnosis
"""

from random import choice, randint, random
from collections import Counter

from bloqade import squin
from bloqade.pyqrack import StackMemorySimulator

from qec.encoding import prepareLogicalQubit, decode_713_block, zeroState, oneState, plusState, minusState
from qec.errors import inject_pauli
from qec.syndrome import measure_clean_syndromes, measure_error_syndromes, verify_correction_syndromes
from qec.error_mapping import color_parities, locate_flipped_qubit

import math
pi = math.pi

emu = StackMemorySimulator()


# ============================================================
# Clifford States with Expected Z-basis Outcomes
# ============================================================

CLIFFORD_STATES = {
    "|0⟩": (0.0, 0.0, 0),         # Z-basis: always measure 0
    "|1⟩": (pi, 0.0, 1),           # Z-basis: always measure 1
    "|+⟩": (pi/2, 0.0, 0),         # X-basis eigenstate: expect 0 in Z
    "|−⟩": (pi/2, pi, 1),          # X-basis eigenstate: expect 1 in Z
}


# ============================================================
# Error Sampling
# ============================================================

def sample_error_events(p1: float, r: float = 0.25, max_errors: int = 2):
    """
    Sample errors with exponentially decreasing probability.
    
    P(1 error) = p1
    P(2 errors) = p1 * r
    P(3 errors) = p1 * r^2
    ...
    
    For each error, randomly choose:
        - qubit index (0-6)
        - Pauli basis (0=X, 1=Y, 2=Z)
    """
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


# ============================================================
# Kernel: Baseline (no correction)
# ============================================================

@squin.kernel
def inject_multiple(block, e1_i, e1_b, e2_i, e2_b):
    """Helper to inject up to 2 errors."""
    if e1_i >= 0:inject_pauli(block, e1_i, e1_b)
    if e2_i >= 0: inject_pauli(block, e2_i, e2_b)


@squin.kernel
def baseline_measure(theta, phi, e1_i, e1_b, e2_i, e2_b):
    """Measure state WITHOUT error correction."""
    block = prepareLogicalQubit(theta, phi)
    inject_multiple(block, e1_i, e1_b, e2_i, e2_b)
    decode_713_block(block)
    return squin.measure(block[6])


# ============================================================
# Kernel: Corrected Measurement
# ============================================================

@squin.kernel
def corrected_measure(theta, phi,
                      e1_i, e1_b, e2_i, e2_b,
                      corr_i, corr_b):
    """Measure state WITH error correction."""
    block = prepareLogicalQubit(theta, phi)
    inject_multiple(block, e1_i, e1_b, e2_i, e2_b)
    
    if corr_i >= 0:
        inject_pauli(block, corr_i, corr_b)
    
    decode_713_block(block)
    return squin.measure(block[6])


# ============================================================
# Main Benchmark
# ============================================================

def run_memory_benchmark(p1: float, shots: int = 100, verbose: bool = False):
    """
    Run quantum memory benchmark at error rate p1.
    
    Returns:
        (baseline_fid, postselection_fid, waste_frac, corrected_fid, stats)
    """
    
    # Get baseline syndrome (for reference)
    baseX, baseZ = list(
        emu.task(measure_clean_syndromes,
                 args=(0.0, 0.0)).batch_run(shots=1)
    )[0]
    
    synX0_ref = color_parities([int(b) for b in baseX])
    synZ0_ref = color_parities([int(b) for b in baseZ])
    
    # Counters
    baseline_correct = 0
    postsel_correct = 0
    corr_correct = 0
    
    postsel_accepted = 0
    syndrome_restored = 0
    
    flip_hist = Counter()
    
    if verbose:
        print(f"\n{'='*70}")
        print(f"BENCHMARK: p1={p1}, shots={shots}")
        print(f"Reference baseline syndrome: X={synX0_ref}, Z={synZ0_ref}")
        print(f"{'='*70}\n")
    
    for trial in range(shots):
        # Random Clifford state
        label = choice(list(CLIFFORD_STATES.keys()))
        theta, phi, expected = CLIFFORD_STATES[label]
        
        # Sample errors
        errors = sample_error_events(p1)
        flip_hist[len(errors)] += 1
        
        while len(errors) < 2:
            errors.append((-1, 0))
        
        (e1_i, e1_b), (e2_i, e2_b) = errors
        
        if verbose and trial < 3:  # Show first 3 trials
            print(f"\nTrial {trial+1}: State {label}")
            print(f"  Errors: {[(i, ['X','Y','Z'][b]) for i,b in errors if i >= 0]}")
        
        # ===== BASELINE (no QEC) =====
        meas_base = int(list(
            emu.task(baseline_measure,
                     args=(theta, phi, e1_i, e1_b, e2_i, e2_b)).batch_run(shots=1)
        )[0])
        
        if meas_base == expected:
            baseline_correct += 1
        
        if verbose and trial < 3:
            print(f"  Baseline: measured {meas_base}, expected {expected} → {'✓' if meas_base==expected else '✗'}")
        
        # ===== SYNDROME EXTRACTION =====
        measX, measZ = list(
            emu.task(measure_error_syndromes,
                     args=(theta, phi, e1_i, e1_b, e2_i, e2_b)).batch_run(shots=1)
        )[0]
        
        synX1 = color_parities([int(b) for b in measX])
        synZ1 = color_parities([int(b) for b in measZ])
        
        if verbose and trial < 3:
            print(f"  Syndrome after error: X={synX1}, Z={synZ1}")
        
        # ===== POSTSELECTION =====
        if synX1 == synX0_ref and synZ1 == synZ0_ref:
            postsel_accepted += 1
            if meas_base == expected:
                postsel_correct += 1
        
        # ===== ERROR CORRECTION =====
        x_loc = locate_flipped_qubit(synX0_ref, synX1)
        z_loc = locate_flipped_qubit(synZ0_ref, synZ1)
        
        if x_loc != -1 and z_loc != -1:
            corr_b, corr_i = 1, x_loc  # Y error
        elif x_loc != -1:
            corr_b, corr_i = 0, x_loc  # X error
        elif z_loc != -1:
            corr_b, corr_i = 2, z_loc  # Z error
        else:
            corr_b, corr_i = 0, -1     # No error detected
        
        if verbose and trial < 3:
            if corr_i >= 0:
                print(f"  Correction: {['X','Y','Z'][corr_b]} on qubit {corr_i}")
            else:
                print(f"  Correction: None needed")
        
        # Verify syndrome restoration
        if corr_i >= 0:
            measX2, measZ2 = list(
                emu.task(verify_correction_syndromes,
                         args=(theta, phi, e1_i, e1_b, e2_i, e2_b,
                               corr_i, corr_b)).batch_run(shots=1)
            )[0]
            
            synX2 = color_parities([int(b) for b in measX2])
            synZ2 = color_parities([int(b) for b in measZ2])
            
            if synX2 == synX0_ref and synZ2 == synZ0_ref:
                syndrome_restored += 1
                
            if verbose and trial < 3:
                print(f"  Syndrome after correction: X={synX2}, Z={synZ2} → {'✓ restored' if (synX2==synX0_ref and synZ2==synZ0_ref) else '✗ not restored'}")
        
        # Measure with correction
        meas_corr = int(list(
            emu.task(corrected_measure,
                     args=(theta, phi, e1_i, e1_b, e2_i, e2_b,
                           corr_i, corr_b)).batch_run(shots=1)
        )[0])
        
        if meas_corr == expected:
            corr_correct += 1
        
        if verbose and trial < 3:
            print(f"  Corrected: measured {meas_corr}, expected {expected} → {'✓' if meas_corr==expected else '✗'}")
    
    # Compute metrics
    baseline_fid = baseline_correct / shots
    corr_fid = corr_correct / shots
    postsel_fid = postsel_correct / postsel_accepted if postsel_accepted > 0 else 0.0
    waste_frac = 1 - postsel_accepted / shots
    restore_rate = syndrome_restored / sum(1 for e1_i, _ in errors if e1_i >= 0) if any(e1_i >= 0 for e1_i, _ in errors) else 0.0
    
    stats = {
        'flip_histogram': flip_hist,
        'syndrome_restored': syndrome_restored,
        'postsel_accepted': postsel_accepted,
    }
    
    return baseline_fid, postsel_fid, waste_frac, corr_fid, stats


# ============================================================
# Pretty Output
# ============================================================

def print_results(name, p1, shots, results):
    """Print formatted benchmark results."""
    baseline_fid, postsel_fid, waste_frac, corr_fid, stats = results
    
    print(f"\n{'='*70}")
    print(f"{name}")
    print(f"{'='*70}")
    print(f"Physical error rate p1 = {p1}")
    print(f"Baseline fidelity        = {baseline_fid:.4f}")
    print(f"Postselected fidelity    = {postsel_fid:.4f}")
    print(f"Postselection waste frac = {waste_frac:.4f}")
    print(f"Corrected fidelity       = {corr_fid:.4f}")
    print(f"Syndromes restored       = {stats['syndrome_restored']} / {stats['postsel_accepted']}")
    
    print(f"\nError distribution:")
    hist = stats['flip_histogram']
    total = sum(hist.values())
    for k in sorted(hist.keys()):
        frac = hist[k] / total
        print(f"  {k} errors: {frac:.3f}")


# ============================================================
# Main
# ============================================================

if __name__ == "__main__":
    
    configs = [
        ("No noise", 0.0, 50),
        ("Low noise", 0.05, 100),
        ("Medium noise", 0.15, 100),
    ]
    
    for name, p1, shots in configs:
        results = run_memory_benchmark(p1, shots, verbose=(p1 == 0.0))
        print_results(name, p1, shots, results)
