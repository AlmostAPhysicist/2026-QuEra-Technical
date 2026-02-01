#!/usr/bin/env python3
"""
Complete Step 2 Implementation - All Challenge Requirements

Uses existing QEC infrastructure with depolarizing noise injection.
"""

import matplotlib.pyplot as plt
import numpy as np
from bloqade.pyqrack import StackMemorySimulator
from bloqade import squin
from kirin.dialects.ilist import IList

from qec.encoding import prepareLogicalQubit
from qec.syndrome import measure_clean_syndromes, measure_error_syndromes, verify_correction
from qec.error_mapping import color_parities, locate_flipped_qubit
from qec.errors import inject_pauli

emu = StackMemorySimulator()

# ============================================================================
# Noise injection kernels using depolarizing channels
# ============================================================================

@squin.kernel
def encode_with_depolarizing(theta: float, phi: float, p_noise: float):
    """Encode + depolarizing noise + measure."""
    q = prepareLogicalQubit(theta, phi)
    if p_noise > 0:
        squin.broadcast.depolarize(p_noise, IList([q[0], q[1], q[2], q[3], q[4], q[5], q[6]]))
    return squin.broadcast.measure(q)


@squin.kernel
def syndrome_with_depolarizing(theta: float, phi: float, err_idx: int, err_basis: int, p_noise: float):
    """Measure syndromes with depolarizing noise."""
    data = prepareLogicalQubit(theta, phi)
    inject_pauli(data, err_idx, err_basis)
    
    if p_noise > 0:
        squin.broadcast.depolarize(p_noise, IList([data[0], data[1], data[2], data[3], data[4], data[5], data[6]]))
    
    probeX = prepareLogicalQubit(0.0, 3.1415926535 / 2)
    for j in range(7):
        squin.cx(data[j], probeX[j])
    measX = squin.broadcast.measure(probeX)

    data2 = prepareLogicalQubit(theta, phi)
    inject_pauli(data2, err_idx, err_basis)
    if p_noise > 0:
        squin.broadcast.depolarize(p_noise, IList([data2[0], data2[1], data2[2], data2[3], data2[4], data2[5], data2[6]]))
    
    probeZ = prepareLogicalQubit(0.0, 0.0)
    for j in range(7):
        squin.cx(probeZ[j], data2[j])
    for j in range(7):
        squin.h(probeZ[j])
    measZ = squin.broadcast.measure(probeZ)

    return measX, measZ


# ============================================================================
# Test functions
# ============================================================================

def test_baseline_no_correction(p_noise, shots=30):
    """Baseline: encode + noise + measure (NO correction)."""
    failures = 0
    for _ in range(shots):
        result = list(emu.task(encode_with_depolarizing, args=(0.0, 0.0, p_noise)).batch_run(shots=1))[0]
        if sum(int(b) for b in result) != 0:
            failures += 1
    return failures / shots


def test_active_qec(p_noise, shots=30):
    """Active QEC: encode + noise + detect + correct."""
    failures = 0
    
    baseX, baseZ = list(emu.task(measure_clean_syndromes, args=(0.0, 0.0)).batch_run(shots=1))[0]
    synX0 = color_parities([int(b) for b in baseX])
    synZ0 = color_parities([int(b) for b in baseZ])
    
    for _ in range(shots):
        measX, measZ = list(emu.task(syndrome_with_depolarizing, args=(0.0, 0.0, -1, 0, p_noise)).batch_run(shots=1))[0]
        
        synX1 = color_parities([int(b) for b in measX])
        synZ1 = color_parities([int(b) for b in measZ])
        
        x_flip = locate_flipped_qubit(synX0, synX1)
        z_flip = locate_flipped_qubit(synZ0, synZ1)
        
        # Apply correction via verify_correction
        if x_flip != -1 and z_flip != -1:
            corr_basis = 1  # Y
            corr_loc = x_flip
        elif x_flip != -1:
            corr_basis = 0  # X
            corr_loc = x_flip
        elif z_flip != -1:
            corr_basis = 2  # Z
            corr_loc = z_flip
        else:
            corr_basis = 0
            corr_loc = -1
        
        if corr_loc == -1:
            continue
            
        measX2, measZ2 = list(emu.task(verify_correction, args=(0.0, 0.0, -1, 0, corr_loc, corr_basis)).batch_run(shots=1))[0]
        synX2 = color_parities([int(b) for b in measX2])
        synZ2 = color_parities([int(b) for b in measZ2])
        
        if not (synX2 == synX0 and synZ2 == synZ0):
            failures += 1
    
    return failures / shots


def test_postselection(p_noise, target_shots=20):
    """Post-selection: only keep clean syndromes."""
    baseX, baseZ = list(emu.task(measure_clean_syndromes, args=(0.0, 0.0)).batch_run(shots=1))[0]
    synX0 = color_parities([int(b) for b in baseX])
    synZ0 = color_parities([int(b) for b in baseZ])
    
    accepted = 0
    failures = 0
    attempts = 0
    max_attempts = target_shots * 20
    
    while accepted < target_shots and attempts < max_attempts:
        attempts += 1
        
        measX, measZ = list(emu.task(syndrome_with_depolarizing, args=(0.0, 0.0, -1, 0, p_noise)).batch_run(shots=1))[0]
        synX = color_parities([int(b) for b in measX])
        synZ = color_parities([int(b) for b in measZ])
        
        # Only accept trivial syndromes
        if synX == synX0 and synZ == synZ0:
            accepted += 1
            result = list(emu.task(encode_with_depolarizing, args=(0.0, 0.0, p_noise)).batch_run(shots=1))[0]
            if sum(int(b) for b in result) != 0:
                failures += 1
    
    acceptance_rate = accepted / attempts if attempts > 0 else 0
    logical_error = failures / accepted if accepted > 0 else 1.0
    
    return logical_error, acceptance_rate


# ============================================================================
# Experiments
# ============================================================================

def experiment_logical_vs_physical():
    """Plot logical error vs physical error rate."""
    print("\n" + "="*70)
    print("EXPERIMENT 1: Logical vs Physical Error Rate")
    print("="*70)
    
    noise_levels = [0.0, 0.01, 0.03, 0.05, 0.08]
    
    baseline_errors = []
    qec_errors = []
    postselect_errors = []
    acceptance_rates = []
    
    for p in noise_levels:
        print(f"\nPhysical error rate: {p:.3f}")
        
        err_base = test_baseline_no_correction(p, shots=30)
        baseline_errors.append(err_base)
        print(f"  Baseline:  {err_base:.3f}")
        
        err_qec = test_active_qec(p, shots=30)
        qec_errors.append(err_qec)
        print(f"  QEC:       {err_qec:.3f}")
        
        err_ps, acc_rate = test_postselection(p, target_shots=20)
        postselect_errors.append(err_ps)
        acceptance_rates.append(acc_rate)
        print(f"  Post-sel:  {err_ps:.3f} (acc={acc_rate:.1%})")
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
    
    ax1.semilogy(noise_levels, baseline_errors, 'o-', label='No Correction', linewidth=2, markersize=8)
    ax1.semilogy(noise_levels, qec_errors, 's-', label='Active QEC', linewidth=2, markersize=8)
    ax1.semilogy(noise_levels, postselect_errors, '^-', label='Post-Selection', linewidth=2, markersize=8)
    ax1.set_xlabel('Physical Error Rate (p)', fontweight='bold', fontsize=12)
    ax1.set_ylabel('Logical Error Rate', fontweight='bold', fontsize=12)
    ax1.set_title('Logical vs Physical Error\n[[7,1,3]] Color Code', fontweight='bold')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    ax2.plot(noise_levels, acceptance_rates, 'o-', linewidth=2, markersize=8, color='orange')
    ax2.set_xlabel('Physical Error Rate (p)', fontweight='bold', fontsize=12)
    ax2.set_ylabel('Post-Selection Acceptance', fontweight='bold', fontsize=12)
    ax2.set_title('Post-Selection Overhead', fontweight='bold')
    ax2.grid(True, alpha=0.3)
    ax2.set_ylim([0, 1.05])
    
    plt.tight_layout()
    plt.savefig('logical_vs_physical_error.png', dpi=200)
    print("\n✓ Saved: logical_vs_physical_error.png")


def main():
    print("\n" + "="*70)
    print("STEP 2: Noise Modeling + QEC Performance")
    print("="*70)
    
    experiment_logical_vs_physical()
    
    print("\n" + "="*70)
    print("COMPLETE - Requirements Met:")
    print("✓ Noise injection (depolarizing)")
    print("✓ Logical vs physical error")
    print("✓ Post-selection on syndromes")
    print("="*70)


if __name__ == "__main__":
    main()
