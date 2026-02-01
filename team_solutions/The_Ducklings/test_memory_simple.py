#!/usr/bin/env python3
"""
Simplified Quantum Memory Benchmark

Models time-dependent decoherence: p(t) = 1 - 2^(-t/1s)

Compares 3 modes:
1. Passive: no QEC  
2. Active (perfect gates): QEC with ideal gates
3. Active (99% gates): QEC with gate error modeling
"""

from random import random, randint, choice

from bloqade import squin
from bloqade.pyqrack import StackMemorySimulator

from qec.encoding import prepareLogicalQubit, decode_713_block
from qec.errors import inject_pauli
from qec.syndrome import measure_clean_syndromes
from qec.error_mapping import color_parities, locate_flipped_qubit

emu = StackMemorySimulator()

CLIFFORD_STATES = {
    "|0>": (0.0, 0.0),
    "|1>": (0.0, 3.1415926535),
    "|+>": (0.0, 3.1415926535 / 2),
    "|->": (3.1415926535, 3.1415926535 / 2),
}


def error_probability(t: float, t_half: float = 1.0) -> float:
    """p(t) = 1 - 2^(-t/t_half)"""
    return 1.0 - 2**(-t / t_half)


def sample_time_errors(t: float, t_half: float = 1.0) -> list:
    """Sample which qubits have errors after time t."""
    p = error_probability(t, t_half)
    errors = []
    
    for qubit_idx in range(7):
        if random() < p:
            basis = randint(0, 2)
            errors.append((qubit_idx, basis))
    
    return errors


def apply_cumulative_gate_errors(num_gates: int, gate_error_rate: float = 0.01):
    """Apply cumulative gate errors."""
    errors = []
    total_error_prob = num_gates * gate_error_rate
    
    for qubit_idx in range(7):
        if random() < total_error_prob / 7:
            basis = randint(0, 2)
            errors.append((qubit_idx, basis))
    
    return errors


# ============================================================
# Kernels
# ============================================================

@squin.kernel
def passive_memory(theta: float, phi: float,
                   e1_i, e1_b, e2_i, e2_b, e3_i, e3_b,
                   e4_i, e4_b, e5_i, e5_b, e6_i, e6_b, e7_i, e7_b):
    """Passive: encode → errors → decode → measure"""
    block = prepareLogicalQubit(theta, phi)
    
    if e1_i >= 0: inject_pauli(block, e1_i, e1_b)
    if e2_i >= 0: inject_pauli(block, e2_i, e2_b)
    if e3_i >= 0: inject_pauli(block, e3_i, e3_b)
    if e4_i >= 0: inject_pauli(block, e4_i, e4_b)
    if e5_i >= 0: inject_pauli(block, e5_i, e5_b)
    if e6_i >= 0: inject_pauli(block, e6_i, e6_b)
    if e7_i >= 0: inject_pauli(block, e7_i, e7_b)
    
    decode_713_block(block)
    return squin.measure(block[6])


@squin.kernel
def get_syndromes_only(theta: float, phi: float,
                       e1_i, e1_b, e2_i, e2_b, e3_i, e3_b,
                       e4_i, e4_b, e5_i, e5_b, e6_i, e6_b, e7_i, e7_b):
    """Get syndromes only (for correction decision)"""
    data = prepareLogicalQubit(theta, phi)
    
    if e1_i >= 0: inject_pauli(data, e1_i, e1_b)
    if e2_i >= 0: inject_pauli(data, e2_i, e2_b)
    if e3_i >= 0: inject_pauli(data, e3_i, e3_b)
    if e4_i >= 0: inject_pauli(data, e4_i, e4_b)
    if e5_i >= 0: inject_pauli(data, e5_i, e5_b)
    if e6_i >= 0: inject_pauli(data, e6_i, e6_b)
    if e7_i >= 0: inject_pauli(data, e7_i, e7_b)
    
    # Measure X syndrome
    probeX = prepareLogicalQubit(0.0, 3.1415926535 / 2)
    for j in range(7):
        squin.cx(data[j], probeX[j])
    measX = squin.broadcast.measure(probeX)
    
    # Measure Z syndrome
    probeZ = prepareLogicalQubit(0.0, 0.0)
    for j in range(7):
        squin.cx(probeZ[j], data[j])
    for j in range(7):
        squin.h(probeZ[j])
    measZ = squin.broadcast.measure(probeZ)
    
    return measX, measZ


@squin.kernel
def active_with_correction(theta: float, phi: float,
                           e1_i, e1_b, e2_i, e2_b, e3_i, e3_b,
                           e4_i, e4_b, e5_i, e5_b, e6_i, e6_b, e7_i, e7_b,
                           corr_i, corr_b,
                           g1_i, g1_b, g2_i, g2_b, g3_i, g3_b, g4_i, g4_b, g5_i, g5_b):
    """Active: encode → errors → correction → gate errors → decode → measure"""
    block = prepareLogicalQubit(theta, phi)
    
    # Storage errors
    if e1_i >= 0: inject_pauli(block, e1_i, e1_b)
    if e2_i >= 0: inject_pauli(block, e2_i, e2_b)
    if e3_i >= 0: inject_pauli(block, e3_i, e3_b)
    if e4_i >= 0: inject_pauli(block, e4_i, e4_b)
    if e5_i >= 0: inject_pauli(block, e5_i, e5_b)
    if e6_i >= 0: inject_pauli(block, e6_i, e6_b)
    if e7_i >= 0: inject_pauli(block, e7_i, e7_b)
    
    # QEC correction
    if corr_i >= 0: inject_pauli(block, corr_i, corr_b)
    
    # Gate errors (cumulative)
    if g1_i >= 0: inject_pauli(block, g1_i, g1_b)
    if g2_i >= 0: inject_pauli(block, g2_i, g2_b)
    if g3_i >= 0: inject_pauli(block, g3_i, g3_b)
    if g4_i >= 0: inject_pauli(block, g4_i, g4_b)
    if g5_i >= 0: inject_pauli(block, g5_i, g5_b)
    
    decode_713_block(block)
    return squin.measure(block[6])


# ============================================================
# Benchmark
# ============================================================

def benchmark(t, shots=100):
    """Run benchmark at time t."""
    
    # Baseline syndromes
    baseX, baseZ = list(emu.task(measure_clean_syndromes, args=(0.0, 0.0)).batch_run(shots=1))[0]
    synX0 = color_parities([int(b) for b in baseX])
    synZ0 = color_parities([int(b) for b in baseZ])
    
    passive_fail = 0
    active_perfect_fail = 0
    active_99_fail = 0
    
    # Gate count: ~50 gates per syndrome × 2 = 100 gates
    num_qec_gates = 100
    
    for _ in range(shots):
        label = choice(list(CLIFFORD_STATES.keys()))
        theta, phi = CLIFFORD_STATES[label]
        expected = 0 if label in ["|0>", "|+>"] else 1
        
        # Sample storage errors
        errors = sample_time_errors(t)
        while len(errors) < 7:
            errors.append((-1, 0))
        
        (e1_i, e1_b), (e2_i, e2_b), (e3_i, e3_b), (e4_i, e4_b), \
        (e5_i, e5_b), (e6_i, e6_b), (e7_i, e7_b) = errors
        
        # PASSIVE: no QEC
        meas = list(emu.task(passive_memory, args=(theta, phi, e1_i, e1_b, e2_i, e2_b, e3_i, e3_b,
                                                     e4_i, e4_b, e5_i, e5_b, e6_i, e6_b, e7_i, e7_b)
                             ).batch_run(shots=1))[0]
        if int(meas) != expected:
            passive_fail += 1
        
        # Get syndromes (to determine correction)
        measX, measZ = list(emu.task(get_syndromes_only, 
                                     args=(theta, phi, e1_i, e1_b, e2_i, e2_b, e3_i, e3_b,
                                           e4_i, e4_b, e5_i, e5_b, e6_i, e6_b, e7_i, e7_b)
                                     ).batch_run(shots=1))[0]
        
        synX1 = color_parities([int(b) for b in measX])
        synZ1 = color_parities([int(b) for b in measZ])
        
        # Determine correction
        x_loc = locate_flipped_qubit(synX0, synX1)
        z_loc = locate_flipped_qubit(synZ0, synZ1)
        
        if x_loc != -1 and z_loc != -1:
            corr_i, corr_b = x_loc, 1  # Y
        elif x_loc != -1:
            corr_i, corr_b = x_loc, 0  # X
        elif z_loc != -1:
            corr_i, corr_b = z_loc, 2  # Z
        else:
            corr_i, corr_b = -1, 0
        
        # ACTIVE PERFECT: QEC with perfect gates
        meas_perf = list(emu.task(active_with_correction,
                                  args=(theta, phi, e1_i, e1_b, e2_i, e2_b, e3_i, e3_b,
                                        e4_i, e4_b, e5_i, e5_b, e6_i, e6_b, e7_i, e7_b,
                                        corr_i, corr_b,
                                        -1, 0, -1, 0, -1, 0, -1, 0, -1, 0)  # No gate errors
                                  ).batch_run(shots=1))[0]
        if int(meas_perf) != expected:
            active_perfect_fail += 1
        
        # ACTIVE 99%: QEC with gate errors  
        gate_errs = apply_cumulative_gate_errors(num_qec_gates, 0.01)
        while len(gate_errs) < 5:
            gate_errs.append((-1, 0))
        (g1_i, g1_b), (g2_i, g2_b), (g3_i, g3_b), (g4_i, g4_b), (g5_i, g5_b) = gate_errs
        
        meas_99 = list(emu.task(active_with_correction,
                                args=(theta, phi, e1_i, e1_b, e2_i, e2_b, e3_i, e3_b,
                                      e4_i, e4_b, e5_i, e5_b, e6_i, e6_b, e7_i, e7_b,
                                      corr_i, corr_b,
                                      g1_i, g1_b, g2_i, g2_b, g3_i, g3_b, g4_i, g4_b, g5_i, g5_b)
                                ).batch_run(shots=1))[0]
        if int(meas_99) != expected:
            active_99_fail += 1
    
    return (1 - passive_fail/shots, 
            1 - active_perfect_fail/shots,
            1 - active_99_fail/shots)


def main():
    print("\n" + "="*70)
    print("QUANTUM MEMORY WITH TIME-DEPENDENT DECOHERENCE")
    print("="*70)
    print("Decoherence: p(t) = 1 - 2^(-t/1s)")
    print("QEC gates: ~100 gates, 99% fidelity = 1% error rate per gate")
    print("="*70)
    
    times = [0.01, 0.05, 0.1, 0.5, 1.0]
    shots = 100
    
    print(f"\nRunning {shots} shots per time point...\n")
    
    results = []
    for t in times:
        p = error_probability(t)
        print(f"t={t:.2f}s (p={p:.3f})...", end=" ", flush=True)
        
        passive, active_perf, active_99 = benchmark(t, shots)
        
        results.append((t, p, passive, active_perf, active_99))
        print(f"Passive: {passive:.3f} | Perfect: {active_perf:.3f} | 99%: {active_99:.3f}")
    
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    print(f"{'Time':>6} {'p(t)':>6} {'Passive':>8} {'Perfect':>8} {'99% Gates':>10} {'Benefit':>8}")
    print("-"*70)
    
    for t, p, passive, perf, g99 in results:
        benefit = g99 - passive
        print(f"{t:6.2f} {p:6.3f} {passive:8.3f} {perf:8.3f} {g99:10.3f} {benefit:+8.3f}")
    
    print("="*70)


if __name__ == "__main__":
    main()
