#!/usr/bin/env python3
"""
Minimal Quantum Memory Benchmark

Fidelity = P(logical measurement gives correct value)
Error rate = 1 - Fidelity

Baseline: Encode |0_L>, inject random Pauli error, measure Z parity
QEC: Same + syndrome measurement + correction
"""

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from random import randint, random
from bloqade.pyqrack import StackMemorySimulator
from bloqade import squin
from kirin.dialects.ilist import IList

from qec.encoding import prepareLogicalQubit
from qec.errors import inject_pauli
from qec.syndrome import measure_clean_syndromes
from qec.error_mapping import color_parities, locate_flipped_qubit

emu = StackMemorySimulator()


# ============================================================================
# Kernel: Encode + Inject Error + Measure
# ============================================================================

@squin.kernel
def logical_memory_trial(err_index: int, err_basis: int):
    """Encode |0_L>, inject Pauli error, measure all 7 qubits in Z."""
    block = prepareLogicalQubit(0.0, 0.0)
    inject_pauli(block, err_index, err_basis)
    return squin.broadcast.measure(block)


@squin.kernel
def logical_memory_with_syndrome(err_index: int, err_basis: int):
    """Encode |0_L>, inject error, measure syndromes."""
    data = prepareLogicalQubit(0.0, 0.0)
    inject_pauli(data, err_index, err_basis)
    
    # Measure X syndrome
    probeX = prepareLogicalQubit(0.0, 3.1415926535 / 2)
    for j in range(7):
        squin.cx(data[j], probeX[j])
    measX = squin.broadcast.measure(probeX)
    
    # Measure Z syndrome (fresh data + fresh probe)
    probeZ = prepareLogicalQubit(0.0, 0.0)
    for j in range(7):
        squin.cx(probeZ[j], data[j])
    for j in range(7):
        squin.h(probeZ[j])
    measZ = squin.broadcast.measure(probeZ)
    
    # Measure data qubits
    data_meas = squin.broadcast.measure(data)
    
    return data_meas, measX, measZ


@squin.kernel
def logical_memory_with_correction(err_index: int, err_basis: int, corr_idx: int):
    """Apply correction to data qubit, then measure."""
    block = prepareLogicalQubit(0.0, 0.0)
    inject_pauli(block, err_index, err_basis)
    
    # Apply correction
    if 0 <= corr_idx < 7:
        squin.x(block[corr_idx])
    
    # Measure Z parity
    return squin.broadcast.measure(block)


# ============================================================================
# Fidelity estimators
# ============================================================================

def logical_Z_parity(bits):
    """Compute logical Z value = parity of all 7 measurements."""
    return sum(int(b) for b in bits) % 2


def baseline_logical_fidelity(p_error, shots=200):
    """
    BASELINE: No QEC. Just noise + measure.
    
    With probability p_error, inject random single-qubit Pauli.
    Measure Z parity of all 7 qubits.
    Fidelity = P(parity = 0)
    """
    failures = 0
    
    for _ in range(shots):
        if random() < p_error:
            err_idx = randint(0, 6)
            err_basis = randint(0, 2)
        else:
            err_idx = -1
            err_basis = 0
        
        meas = list(emu.task(logical_memory_trial, args=(err_idx, err_basis)).batch_run(shots=1))[0]
        bits = [int(b) for b in meas]
        
        if logical_Z_parity(bits) == 1:  # 1 = error (odd parity)
            failures += 1
    
    return 1.0 - failures / shots


def postselection_fidelity(p_error, shots=200):
    """
    POST-SELECTION: Discard shots where error is detected.
    
    1. Measure syndrome
    2. If syndrome != trivial: discard (don't measure logical state)
    3. If syndrome == trivial: measure logical Z parity
    
    Returns: (fidelity, acceptance_rate)
    """
    # Baseline syndromes (no error)
    baseX, baseZ = list(emu.task(measure_clean_syndromes, args=(0.0, 0.0)).batch_run(shots=1))[0]
    synX0 = color_parities([int(b) for b in baseX])
    synZ0 = color_parities([int(b) for b in baseZ])
    
    accepted = 0
    failures = 0
    attempts = 0
    max_attempts = shots * 20  # Allow rejection
    
    while accepted < shots and attempts < max_attempts:
        attempts += 1
        
        if random() < p_error:
            err_idx = randint(0, 6)
            err_basis = randint(0, 2)
        else:
            err_idx = -1
            err_basis = 0
        
        # Measure syndrome
        data_bits, measX, measZ = list(emu.task(logical_memory_with_syndrome, args=(err_idx, err_basis)).batch_run(shots=1))[0]
        
        synX = color_parities([int(b) for b in measX])
        synZ = color_parities([int(b) for b in measZ])
        
        # POST-SELECT: only accept trivial syndromes
        if synX != synX0 or synZ != synZ0:
            continue  # Discard this shot
        
        # Accepted: measure logical state
        accepted += 1
        bits = [int(b) for b in data_bits]
        
        if logical_Z_parity(bits) == 1:
            failures += 1
    
    acceptance_rate = accepted / attempts if attempts > 0 else 0
    fidelity = 1.0 - failures / accepted if accepted > 0 else 0
    
    return fidelity, acceptance_rate


def correction_fidelity(p_error, shots=200):
    """
    CORRECTION: Detect error from syndrome and apply correction.
    
    1. Measure syndrome
    2. Locate error from syndrome difference
    3. Apply X correction on detected qubit
    4. Measure logical Z parity
    
    Returns: (fidelity, correction_success_rate)
    """
    # Baseline syndromes (no error)
    baseX, baseZ = list(emu.task(measure_clean_syndromes, args=(0.0, 0.0)).batch_run(shots=1))[0]
    synX0 = color_parities([int(b) for b in baseX])
    synZ0 = color_parities([int(b) for b in baseZ])
    
    failures = 0
    corrections_applied = 0
    
    for _ in range(shots):
        if random() < p_error:
            err_idx = randint(0, 6)
            err_basis = randint(0, 2)
        else:
            err_idx = -1
            err_basis = 0
        
        # Measure syndrome
        data_bits, measX, measZ = list(emu.task(logical_memory_with_syndrome, args=(err_idx, err_basis)).batch_run(shots=1))[0]
        
        synX = color_parities([int(b) for b in measX])
        synZ = color_parities([int(b) for b in measZ])
        
        # Locate error
        x_flip = locate_flipped_qubit(synX0, synX)
        
        # Apply correction
        if x_flip != -1:
            corrections_applied += 1
            corr_data = list(emu.task(logical_memory_with_correction, args=(err_idx, err_basis, x_flip)).batch_run(shots=1))[0]
            corr_bits = [int(b) for b in corr_data]
            
            if logical_Z_parity(corr_bits) == 1:
                failures += 1
        else:
            # No error detected, just measure
            bits = [int(b) for b in data_bits]
            if logical_Z_parity(bits) == 1:
                failures += 1
    
    correction_rate = corrections_applied / shots if shots > 0 else 0
    fidelity = 1.0 - failures / shots
    
    return fidelity, correction_rate


def qec_logical_fidelity(p_error, shots=200):
    """
    QEC fidelity WITH syndrome + correction.
    """
    # Baseline syndromes (no error)
    baseX, baseZ = list(emu.task(measure_clean_syndromes, args=(0.0, 0.0)).batch_run(shots=1))[0]
    synX0 = color_parities([int(b) for b in baseX])
    synZ0 = color_parities([int(b) for b in baseZ])
    
    failures = 0
    
    for _ in range(shots):
        if random() < p_error:
            err_idx = randint(0, 6)
            err_basis = randint(0, 2)
        else:
            err_idx = -1
            err_basis = 0
        
        # Get syndromes
        data_bits, measX, measZ = list(emu.task(logical_memory_with_syndrome, args=(err_idx, err_basis)).batch_run(shots=1))[0]
        
        synX = color_parities([int(b) for b in measX])
        synZ = color_parities([int(b) for b in measZ])
        
        # Decode error location
        x_flip = locate_flipped_qubit(synX0, synX)
        
        # Apply correction
        corr_data = list(emu.task(logical_memory_with_correction, args=(err_idx, err_basis, x_flip)).batch_run(shots=1))[0]
        corr_bits = [int(b) for b in corr_data]
        
        if logical_Z_parity(corr_bits) == 1:
            failures += 1
    
    return 1.0 - failures / shots


def postselection_fidelity(p_error, shots=200):
    """
    Post-selection: only accept trivial syndromes.
    """
    baseX, baseZ = list(emu.task(measure_clean_syndromes, args=(0.0, 0.0)).batch_run(shots=1))[0]
    synX0 = color_parities([int(b) for b in baseX])
    synZ0 = color_parities([int(b) for b in baseZ])
    
    accepted = 0
    failures = 0
    max_attempts = shots * 10
    
    for _ in range(max_attempts):
        if random() < p_error:
            err_idx = randint(0, 6)
            err_basis = randint(0, 2)
        else:
            err_idx = -1
            err_basis = 0
        
        # Get syndromes
        data_bits, measX, measZ = list(emu.task(logical_memory_with_syndrome, args=(err_idx, err_basis)).batch_run(shots=1))[0]
        
        synX = color_parities([int(b) for b in measX])
        synZ = color_parities([int(b) for b in measZ])
        
        # Only accept trivial syndromes
        if synX != synX0 or synZ != synZ0:
            continue
        
        accepted += 1
        
        # Check logical state
        bits = [int(b) for b in data_bits]
        if logical_Z_parity(bits) == 1:
            failures += 1
        
        if accepted >= shots:
            break
    
    if accepted == 0:
        return 0.0
    
    return 1.0 - failures / accepted


# ============================================================================
# Main benchmark
# ============================================================================

def run_benchmark():
    """Baseline fidelity only - no QEC."""
    print("\n" + "="*70)
    print("BASELINE LOGICAL FIDELITY - No QEC")
    print("="*70)
    
    p_list = [0.0, 0.01, 0.05, 0.10, 0.20]
    
    baseline_fids = []
    
    for p in p_list:
        print(f"\nError probability p = {p:.3f}")
        
        base_fid = baseline_logical_fidelity(p, shots=1000)
        baseline_fids.append(base_fid)
        print(f"  Fidelity: {base_fid:.4f}  (Error rate: {1-base_fid:.4f})")
    
    # Plot
    fig, ax = plt.subplots(figsize=(10, 7))
    
    ax.plot(p_list, baseline_fids, 'o-', linewidth=3, markersize=12, color='red', label='[[7,1,3]] Code')
    ax.plot(p_list, p_list, '--', linewidth=2, alpha=0.5, color='gray', label='Single qubit (~p)')
    
    ax.set_xlabel('Error Injection Probability (p)', fontweight='bold', fontsize=13)
    ax.set_ylabel('Logical Fidelity', fontweight='bold', fontsize=13)
    ax.set_title('Baseline Logical Fidelity (No Correction)\n|0_L⟩ + Pauli Noise', fontweight='bold', fontsize=14)
    ax.legend(fontsize=12)
    ax.grid(True, alpha=0.3)
    ax.set_ylim([0, 1.05])
    
    plt.tight_layout()
    plt.savefig('baseline_fidelity.png', dpi=300, bbox_inches='tight')
    print("\n✓ Saved: baseline_fidelity.png")
    print("="*70)


if __name__ == "__main__":
    run_benchmark()
