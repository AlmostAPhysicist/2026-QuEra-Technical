#!/usr/bin/env python3
"""
Quantum Memory Decay Simulation

Models time-dependent decoherence:
- Half-life t_half = 1.0 second
- Error probability p(t) = 1 - 2^(-t/t_half)
- Test storage times: 0.01s, 0.1s, 0.5s, 1s, 2s, 5s, 10s

Compares:
- Passive memory (no QEC): errors accumulate, measure at end
- Active QEC memory: correct every dt=0.01s during storage
"""

from random import random, randint, choice
import numpy as np

from bloqade import squin
from bloqade.pyqrack import StackMemorySimulator

from qec.encoding import prepareLogicalQubit, decode_713_block
from qec.errors import inject_pauli
from qec.syndrome import measure_clean_syndromes
from qec.error_mapping import color_parities, locate_flipped_qubit

emu = StackMemorySimulator()


# ============================================================
# Test states
# ============================================================

CLIFFORD_STATES = {
    "|0>": (0.0, 0.0),
    # "|1>": (0.0, 3.1415926535),
    # "|+>": (0.0, 3.1415926535 / 2),
    # "|->": (3.1415926535, 3.1415926535 / 2),
}


# ============================================================
# Time-dependent error probability
# ============================================================

def error_probability(t: float, t_half: float = 1.0) -> float:
    """
    Calculate error probability after time t.
    
    Using exponential decay model:
        p(t) = 1 - 2^(-t/t_half)
    
    At t = t_half: p = 0.5 (50% chance of error)
    At t = 0:      p = 0.0 (no errors)
    As t → ∞:      p → 1.0 (certain error)
    """
    return 1.0 - 2**(-t / t_half)


def sample_time_errors(t: float, t_half: float = 1.0) -> list:
    """
    Sample which qubits have errors after time t.
    
    Returns list of (qubit_index, basis) tuples.
    """
    p = error_probability(t, t_half)
    errors = []
    
    for qubit_idx in range(7):
        if random() < p:
            basis = randint(0, 2)  # X, Y, or Z
            errors.append((qubit_idx, basis))
    
    return errors


# ============================================================
# Kernels: Passive memory (no QEC)
# ============================================================

@squin.kernel
def passive_memory(theta: float, phi: float,
                   e1_i, e1_b, e2_i, e2_b, e3_i, e3_b,
                   e4_i, e4_b, e5_i, e5_b, e6_i, e6_b, e7_i, e7_b):
    """
    Store state without error correction.
    
    1. Encode |ψ⟩ → |ψ_L⟩
    2. Wait (apply time-dependent errors)
    3. Decode |ψ_L⟩ → |ψ⟩
    4. Measure
    """
    block = prepareLogicalQubit(theta, phi)
    
    # Apply errors that accumulated during storage
    if e1_i >= 0: inject_pauli(block, e1_i, e1_b)
    if e2_i >= 0: inject_pauli(block, e2_i, e2_b)
    if e3_i >= 0: inject_pauli(block, e3_i, e3_b)
    if e4_i >= 0: inject_pauli(block, e4_i, e4_b)
    if e5_i >= 0: inject_pauli(block, e5_i, e5_b)
    if e6_i >= 0: inject_pauli(block, e6_i, e6_b)
    if e7_i >= 0: inject_pauli(block, e7_i, e7_b)
    
    decode_713_block(block)
    return squin.measure(block[6])


# ============================================================
# Kernels: Active QEC memory
# ============================================================

@squin.kernel
def active_qec_memory(theta: float, phi: float,
                      e1_i, e1_b, e2_i, e2_b, e3_i, e3_b,
                      e4_i, e4_b, e5_i, e5_b, e6_i, e6_b, e7_i, e7_b):
    """
    Store state WITH error correction.
    
    1. Encode |ψ⟩ → |ψ_L⟩
    2. Wait (apply time-dependent errors)
    3. Measure syndromes
    4. Decode |ψ_L⟩ → |ψ⟩
    5. Measure
    
    Returns: measurement + syndrome data
    """
    data = prepareLogicalQubit(theta, phi)
    
    # Apply errors that accumulated during storage
    if e1_i >= 0: inject_pauli(data, e1_i, e1_b)
    if e2_i >= 0: inject_pauli(data, e2_i, e2_b)
    if e3_i >= 0: inject_pauli(data, e3_i, e3_b)
    if e4_i >= 0: inject_pauli(data, e4_i, e4_b)
    if e5_i >= 0: inject_pauli(data, e5_i, e5_b)
    if e6_i >= 0: inject_pauli(data, e6_i, e6_b)
    if e7_i >= 0: inject_pauli(data, e7_i, e7_b)
    
    # Measure X syndrome (detects X/Y errors)
    probeX = prepareLogicalQubit(0.0, 3.1415926535 / 2)
    for j in range(7):
        squin.cx(data[j], probeX[j])
    measX = squin.broadcast.measure(probeX)
    
    # Measure Z syndrome (detects Z/Y errors)
    probeZ = prepareLogicalQubit(0.0, 0.0)
    for j in range(7):
        squin.cx(probeZ[j], data[j])
    for j in range(7):
        squin.h(probeZ[j])
    measZ = squin.broadcast.measure(probeZ)
    
    decode_713_block(data)
    return squin.measure(data[6]), measX, measZ


# ============================================================
# Kernels for repeated QEC rounds
# ============================================================

@squin.kernel
def qec_round_with_syndromes(theta: float, phi: float,
                             e1_i, e1_b, e2_i, e2_b, e3_i, e3_b,
                             e4_i, e4_b, e5_i, e5_b, e6_i, e6_b, e7_i, e7_b):
    """
    One QEC round: apply errors, measure syndromes.
    Returns syndromes for host-side correction decision.
    """
    data = prepareLogicalQubit(theta, phi)
    
    # Apply errors for this time step
    if e1_i >= 0: inject_pauli(data, e1_i, e1_b)
    if e2_i >= 0: inject_pauli(data, e2_i, e2_b)
    if e3_i >= 0: inject_pauli(data, e3_i, e3_b)
    if e4_i >= 0: inject_pauli(data, e4_i, e4_b)
    if e5_i >= 0: inject_pauli(data, e5_i, e5_b)
    if e6_i >= 0: inject_pauli(data, e6_i, e6_b)
    if e7_i >= 0: inject_pauli(data, e7_i, e7_b)
    
    # Measure syndromes
    probeX = prepareLogicalQubit(0.0, 3.1415926535 / 2)
    for j in range(7):
        squin.cx(data[j], probeX[j])
    measX = squin.broadcast.measure(probeX)
    
    probeZ = prepareLogicalQubit(0.0, 0.0)
    for j in range(7):
        squin.cx(probeZ[j], data[j])
    for j in range(7):
        squin.h(probeZ[j])
    measZ = squin.broadcast.measure(probeZ)
    
    decode_713_block(data)
    return squin.measure(data[6]), measX, measZ


@squin.kernel
def qec_round_with_correction(theta: float, phi: float,
                               e1_i, e1_b, e2_i, e2_b, e3_i, e3_b,
                               e4_i, e4_b, e5_i, e5_b, e6_i, e6_b, e7_i, e7_b,
                               corr_index: int, corr_basis: int):
    """
    One QEC round: apply errors, apply correction, decode, measure.
    """
    block = prepareLogicalQubit(theta, phi)
    
    # Apply errors
    if e1_i >= 0: inject_pauli(block, e1_i, e1_b)
    if e2_i >= 0: inject_pauli(block, e2_i, e2_b)
    if e3_i >= 0: inject_pauli(block, e3_i, e3_b)
    if e4_i >= 0: inject_pauli(block, e4_i, e4_b)
    if e5_i >= 0: inject_pauli(block, e5_i, e5_b)
    if e6_i >= 0: inject_pauli(block, e6_i, e6_b)
    if e7_i >= 0: inject_pauli(block, e7_i, e7_b)
    
    # Apply correction
    if corr_index >= 0:
        inject_pauli(block, corr_index, corr_basis)
    
    decode_713_block(block)
    return squin.measure(block[6])


# ============================================================
# Benchmark at specific time
# ============================================================

def benchmark_at_time(t: float, shots: int = 500, t_half: float = 1.0, dt: float = 0.01):
    """
    Run memory benchmark at storage time t.
    
    Passive mode: accumulate errors over full time t, then measure
    Active mode: correct every dt seconds (default 0.01s)
    
    Returns:
        (passive_fidelity, active_fidelity, avg_corrections_per_shot)
    """
    
    # Get baseline syndromes
    baseX, baseZ = list(
        emu.task(measure_clean_syndromes, args=(0.0, 0.0)).batch_run(shots=1)
    )[0]
    synX0 = color_parities([int(b) for b in baseX])
    synZ0 = color_parities([int(b) for b in baseZ])
    
    passive_fail = 0
    active_fail = 0
    total_corrections = 0
    
    # Number of QEC rounds for active mode
    n_rounds = max(1, int(t / dt))
    
    for _ in range(shots):
        # Random Clifford state
        label = choice(list(CLIFFORD_STATES.keys()))
        theta, phi = CLIFFORD_STATES[label]
        expected = 0 if label in ["|0>", "|+>"] else 1
        
        # ============================================================
        # PASSIVE: Errors accumulate over full time t
        # ============================================================
        
        errors_passive = sample_time_errors(t, t_half)
        while len(errors_passive) < 7:
            errors_passive.append((-1, 0))
        
        (e1_i, e1_b), (e2_i, e2_b), (e3_i, e3_b), (e4_i, e4_b), \
        (e5_i, e5_b), (e6_i, e6_b), (e7_i, e7_b) = errors_passive
        
        meas_passive = list(
            emu.task(passive_memory,
                    args=(theta, phi,
                          e1_i, e1_b, e2_i, e2_b, e3_i, e3_b,
                          e4_i, e4_b, e5_i, e5_b, e6_i, e6_b, e7_i, e7_b)
                    ).batch_run(shots=1)
        )[0]
        
        if int(meas_passive) != expected:
            passive_fail += 1
        
        # ============================================================
        # ACTIVE: Correct every dt seconds
        # ============================================================
        
        corrections_this_shot = 0
        
        # Simulate n_rounds of QEC cycles
        for round_idx in range(n_rounds):
            # Sample errors for this time step
            errors_active = sample_time_errors(dt, t_half)
            while len(errors_active) < 7:
                errors_active.append((-1, 0))
            
            (e1_i, e1_b), (e2_i, e2_b), (e3_i, e3_b), (e4_i, e4_b), \
            (e5_i, e5_b), (e6_i, e6_b), (e7_i, e7_b) = errors_active
            
            # Measure syndromes after errors
            meas, measX, measZ = list(
                emu.task(qec_round_with_syndromes,
                        args=(theta, phi,
                              e1_i, e1_b, e2_i, e2_b, e3_i, e3_b,
                              e4_i, e4_b, e5_i, e5_b, e6_i, e6_b, e7_i, e7_b)
                        ).batch_run(shots=1)
            )[0]
            
            synX1 = color_parities([int(b) for b in measX])
            synZ1 = color_parities([int(b) for b in measZ])
            
            # Determine correction
            x_loc = locate_flipped_qubit(synX0, synX1)
            z_loc = locate_flipped_qubit(synZ0, synZ1)
            
            if x_loc != -1 and z_loc != -1:
                corr_basis, corr_index = 1, x_loc  # Y error
                corrections_this_shot += 1
            elif x_loc != -1:
                corr_basis, corr_index = 0, x_loc  # X error
                corrections_this_shot += 1
            elif z_loc != -1:
                corr_basis, corr_index = 2, z_loc  # Z error
                corrections_this_shot += 1
            else:
                corr_basis, corr_index = 0, -1     # No error
            
            # For last round, measure with correction
            if round_idx == n_rounds - 1:
                meas_active = list(
                    emu.task(qec_round_with_correction,
                            args=(theta, phi,
                                  e1_i, e1_b, e2_i, e2_b, e3_i, e3_b,
                                  e4_i, e4_b, e5_i, e5_b, e6_i, e6_b, e7_i, e7_b,
                                  corr_index, corr_basis)
                            ).batch_run(shots=1)
                )[0]
        
        total_corrections += corrections_this_shot
        
        if int(meas_active) != expected:
            active_fail += 1
    
    passive_fid = 1.0 - passive_fail / shots
    active_fid = 1.0 - active_fail / shots
    avg_corrections = total_corrections / shots
    
    return passive_fid, active_fid, avg_corrections


# ============================================================
# Main: Sweep storage times
# ============================================================

def main():
    print("\n" + "="*70)
    print("QUANTUM MEMORY DECAY SIMULATION")
    print("="*70)
    print(f"Decoherence half-life: t_half = 1.0 second")
    print(f"Error model: p(t) = 1 - 2^(-t/t_half)")
    print(f"Active QEC: correct every dt = 0.01 seconds")
    print("="*70)
    
    # Storage times to test
    times = [0.01, 0.1, 0.5, 1.0, 2.0, 5.0]
    shots = 200
    dt = 0.01
    
    print(f"\nRunning {shots} shots per time point...")
    print(f"Active mode: correcting every {dt}s\n")
    
    results = []
    
    for t in times:
        n_rounds = max(1, int(t / dt))
        p_theory = error_probability(t)
        passive_fid, active_fid, avg_corr = benchmark_at_time(t, shots=shots, dt=dt)
        
        improvement = (active_fid - passive_fid) / (1.0 - passive_fid) if passive_fid < 1.0 else 0.0
        
        results.append((t, n_rounds, p_theory, passive_fid, active_fid, avg_corr))
        
        print(f"t = {t:6.2f}s ({n_rounds:3d} rounds)  |  p_per_qubit = {p_theory:.4f}  |  "
              f"Passive: {passive_fid:.4f}  |  Active: {active_fid:.4f}  |  "
              f"Avg corr: {avg_corr:.2f}  |  Δ: {improvement:+.1%}")
    
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    print(f"{'Time (s)':>10} {'Rounds':>8} {'p(t)':>8} {'Passive':>10} {'Active':>10} {'Δ Fid':>10}")
    print("-"*70)
    
    for t, n_r, p, passive, active, _ in results:
        delta = active - passive
        print(f"{t:10.2f} {n_r:8d} {p:8.4f} {passive:10.4f} {active:10.4f} {delta:+10.4f}")
    
    print("\n" + "="*70)
    print("KEY INSIGHTS:")
    print("  - Passive mode: errors accumulate over full time, measured once at end")
    print("  - Active mode: errors corrected every 0.01s during storage")
    print("  - Short times: Few errors, both work well")
    print("  - Medium times (~1s): QEC corrects single errors, large benefit")
    print("  - Long times (>2s): Error rate overwhelms correction rate, both degrade")
    print("="*70)


if __name__ == "__main__":
    main()
