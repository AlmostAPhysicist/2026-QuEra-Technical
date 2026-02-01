#!/usr/bin/env python3
"""
Memory Benchmark: Physical vs Logical Error Rates

Measures operational fidelity: F = P(output matches ideal)
Logical error rate should scale as ~p^2 (distance-3 code)
Physical error rate should scale as ~p
"""

import numpy as np
import matplotlib.pyplot as plt
from bloqade.pyqrack import StackMemorySimulator
from bloqade import squin
from kirin.dialects.ilist import IList

from qec.encoding import prepareLogicalQubit, decode_713_block
from qec.syndrome import measure_clean_syndromes
from qec.error_mapping import color_parities, locate_flipped_qubit

emu = StackMemorySimulator()

# ============================================================================
# PHYSICAL MEMORY (BASELINE)
# ============================================================================

@squin.kernel
def physical_memory_with_noise(p: float):
    """Store |0⟩ in single qubit with depolarizing noise."""
    q = squin.qalloc(1)
    # q starts in |0⟩
    
    # Apply depolarizing noise (simulate storage time)
    if p > 0:
        squin.depolarize(p, q[0])
    
    return squin.measure(q[0])


def benchmark_physical_memory(p, shots=1000):
    """Measure physical qubit flip rate under noise."""
    results = emu.task(physical_memory_with_noise, args=(p,)).batch_run(shots=shots)
    
    # Count how many times we measured |1⟩ (error)
    errors = sum(1 for result in results if int(result) == 1)
    error_rate = errors / shots
    
    return error_rate


# ============================================================================
# LOGICAL MEMORY (WITH QEC)
# ============================================================================

@squin.kernel
def logical_memory_with_noise(p: float):
    """Store |0_L⟩ with noise, then decode."""
    block = prepareLogicalQubit(0.0, 0.0)  # |0_L⟩
    
    # Apply depolarizing noise on all 7 physical qubits
    if p > 0:
        squin.broadcast.depolarize(p, IList([block[0], block[1], block[2], block[3], block[4], block[5], block[6]]))
    
    # Measure syndromes for error detection
    probeX = prepareLogicalQubit(0.0, 3.1415926535 / 2)  # |+_L⟩
    for j in range(7):
        squin.cx(block[j], probeX[j])
    measX = squin.broadcast.measure(probeX)
    
    # Re-prepare for Z syndrome (simplified - just return syndrome)
    return measX


@squin.kernel  
def logical_memory_decode(p: float, corr_idx: int):
    """Apply correction and decode to measure logical qubit."""
    block = prepareLogicalQubit(0.0, 0.0)
    
    if p > 0:
        squin.broadcast.depolarize(p, IList([block[0], block[1], block[2], block[3], block[4], block[5], block[6]]))
    
    # Apply X correction if needed
    if 0 <= corr_idx < 7:
        squin.x(block[corr_idx])
    
    # Decode
    decode_713_block(block)
    
    # Measure final qubit
    return squin.measure(block[6])


def benchmark_logical_memory(p, shots=1000):
    """Measure logical qubit flip rate with QEC."""
    baseX, baseZ = list(emu.task(measure_clean_syndromes, args=(0.0, 0.0)).batch_run(shots=1))[0]
    synX0 = color_parities([int(b) for b in baseX])
    synZ0 = color_parities([int(b) for b in baseZ])
    
    errors = 0
    
    for _ in range(shots):
        # Measure syndrome
        measX = list(emu.task(logical_memory_with_noise, args=(p,)).batch_run(shots=1))[0]
        synX = color_parities([int(b) for b in measX])
        
        # Decode error location
        x_flip = locate_flipped_qubit(synX0, synX)
        
        # Apply correction and decode
        result = list(emu.task(logical_memory_decode, args=(p, x_flip)).batch_run(shots=1))[0]
        
        # Check if we got |1⟩ (error)
        if int(result) == 1:
            errors += 1
    
    error_rate = errors / shots
    return error_rate


# ============================================================================
# POST-SELECTION (BONUS)
# ============================================================================

def benchmark_postselection(p, target_shots=500):
    """Only accept shots with trivial syndrome."""
    baseX, baseZ = list(emu.task(measure_clean_syndromes, args=(0.0, 0.0)).batch_run(shots=1))[0]
    synX0 = color_parities([int(b) for b in baseX])
    
    accepted = 0
    errors = 0
    attempts = 0
    max_attempts = target_shots * 20
    
    while accepted < target_shots and attempts < max_attempts:
        attempts += 1
        
        measX = list(emu.task(logical_memory_with_noise, args=(p,)).batch_run(shots=1))[0]
        synX = color_parities([int(b) for b in measX])
        
        # Only accept trivial syndrome
        if synX == synX0:
            accepted += 1
            
            # Measure final state
            result = list(emu.task(logical_memory_decode, args=(p, -1)).batch_run(shots=1))[0]
            if int(result) == 1:
                errors += 1
    
    acceptance_rate = accepted / attempts if attempts > 0 else 0
    error_rate = errors / accepted if accepted > 0 else 1.0
    
    return error_rate, acceptance_rate


# ============================================================================
# MAIN BENCHMARK
# ============================================================================

def run_benchmark():
    """Run full benchmark: physical vs logical vs post-selection."""
    print("\n" + "="*70)
    print("MEMORY FIDELITY BENCHMARK")
    print("Storing |0⟩ under depolarizing noise")
    print("="*70)
    
    # Sweep physical error rates
    p_values = [0.001, 0.003, 0.01, 0.02, 0.04, 0.06]
    
    physical_errors = []
    logical_errors = []
    postselect_errors = []
    acceptance_rates = []
    
    for p in p_values:
        print(f"\nPhysical error rate p = {p:.3f}")
        
        # Physical baseline
        p_err = benchmark_physical_memory(p, shots=1000)
        physical_errors.append(p_err)
        print(f"  Physical memory:  {p_err:.4f}")
        
        # Logical with QEC
        l_err = benchmark_logical_memory(p, shots=500)
        logical_errors.append(l_err)
        print(f"  Logical QEC:      {l_err:.4f}")
        
        # Post-selection
        ps_err, acc = benchmark_postselection(p, target_shots=200)
        postselect_errors.append(ps_err)
        acceptance_rates.append(acc)
        print(f"  Post-selection:   {ps_err:.4f} (acceptance={acc:.1%})")
    
    # ========================================================================
    # PLOT
    # ========================================================================
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
    
    # Log-log plot of error rates
    ax1.loglog(p_values, physical_errors, 'o-', label='Physical (1 qubit)', 
               linewidth=2.5, markersize=10, color='red')
    ax1.loglog(p_values, logical_errors, 's-', label='Logical [[7,1,3]] + QEC', 
               linewidth=2.5, markersize=10, color='blue')
    ax1.loglog(p_values, postselect_errors, '^-', label='Post-Selection', 
               linewidth=2.5, markersize=10, color='green')
    
    # Reference lines
    ax1.loglog(p_values, p_values, '--', alpha=0.4, color='gray', label='~p (physical)')
    ax1.loglog(p_values, [p**2 for p in p_values], '--', alpha=0.4, color='purple', label='~p² (d=3)')
    
    ax1.set_xlabel('Physical Error Rate (p)', fontweight='bold', fontsize=13)
    ax1.set_ylabel('Logical Error Rate', fontweight='bold', fontsize=13)
    ax1.set_title('Quantum Memory Performance\n[[7,1,3]] Color Code', fontweight='bold', fontsize=14)
    ax1.legend(loc='best', fontsize=10)
    ax1.grid(True, alpha=0.3, which='both')
    
    # Acceptance rate
    ax2.semilogx(p_values, acceptance_rates, 'o-', linewidth=2.5, markersize=10, color='orange')
    ax2.set_xlabel('Physical Error Rate (p)', fontweight='bold', fontsize=13)
    ax2.set_ylabel('Post-Selection Acceptance', fontweight='bold', fontsize=13)
    ax2.set_title('Post-Selection Overhead', fontweight='bold', fontsize=14)
    ax2.grid(True, alpha=0.3)
    ax2.set_ylim([0, 1.05])
    
    plt.tight_layout()
    plt.savefig('memory_fidelity_benchmark.png', dpi=300, bbox_inches='tight')
    print("\n" + "="*70)
    print("✓ Saved: memory_fidelity_benchmark.png")
    print("="*70)
    
    # Print summary table
    print("\n" + "="*70)
    print("SUMMARY TABLE")
    print("="*70)
    print(f"{'p':<8} {'Physical':<12} {'Logical':<12} {'Post-Sel':<12} {'Accept%':<10}")
    print("-"*70)
    for i, p in enumerate(p_values):
        print(f"{p:<8.3f} {physical_errors[i]:<12.4f} {logical_errors[i]:<12.4f} "
              f"{postselect_errors[i]:<12.4f} {acceptance_rates[i]*100:<10.1f}")
    print("="*70)
    
    # Key result
    improvement = physical_errors[-1] / logical_errors[-1] if logical_errors[-1] > 0 else float('inf')
    print(f"\n🎯 At p={p_values[-1]:.3f}:")
    print(f"   QEC improves memory by {improvement:.1f}× over physical qubit")
    print("="*70)


if __name__ == "__main__":
    run_benchmark()
