#!/usr/bin/env python3
"""
Memory Benchmark Runner - Standalone
"""

import sys
import os

# Add qec to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'qec'))

import numpy as np
import matplotlib.pyplot as plt
from bloqade.pyqrack import StackMemorySimulator
from bloqade import squin
from kirin.dialects.ilist import IList

# Import with sys.path adjusted
import importlib.util

# Load modules
qec_path = os.path.join(os.path.dirname(__file__), 'qec')
spec_enc = importlib.util.spec_from_file_location("encoding", os.path.join(qec_path, 'encoding.py'))
encoding = importlib.util.module_from_spec(spec_enc)
sys.modules['encoding'] = encoding

spec_syn = importlib.util.spec_from_file_location("syndrome", os.path.join(qec_path, 'syndrome.py'))
syndrome = importlib.util.module_from_spec(spec_syn)
sys.modules['syndrome'] = syndrome

spec_err = importlib.util.spec_from_file_location("error_mapping", os.path.join(qec_path, 'error_mapping.py'))
error_mapping = importlib.util.module_from_spec(spec_err)
sys.modules['error_mapping'] = error_mapping

# Load in order
spec_enc.loader.exec_module(encoding)
spec_syn.loader.exec_module(syndrome)
spec_err.loader.exec_module(error_mapping)

from encoding import prepareLogicalQubit, decode_713_block
from syndrome import measure_clean_syndromes
from error_mapping import color_parities, locate_flipped_qubit

emu = StackMemorySimulator()


# ============================================================================
# Physical baseline kernel
# ============================================================================

@squin.kernel
def physical_memory_Z(p: float):
    """Store |0⟩ under depolarizing noise, measure in Z."""
    q = squin.qalloc(1)
    if p > 0:
        squin.depolarize(p, q[0])
    return squin.measure(q[0])


# ============================================================================
# Logical memory kernels
# ============================================================================

@squin.kernel
def logical_with_syndrome(p: float):
    """Encode |0_L⟩, apply noise, measure syndromes."""
    data = prepareLogicalQubit(0.0, 0.0)
    
    if p > 0:
        squin.broadcast.depolarize(p, IList([data[0], data[1], data[2], data[3], data[4], data[5], data[6]]))
    
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
    
    # Measure data
    data_meas = squin.broadcast.measure(data)
    
    return data_meas, measX, measZ


@squin.kernel
def logical_with_correction(p: float, corr_idx: int):
    """Apply correction on data qubit then decode."""
    data = prepareLogicalQubit(0.0, 0.0)
    
    if p > 0:
        squin.broadcast.depolarize(p, IList([data[0], data[1], data[2], data[3], data[4], data[5], data[6]]))
    
    # Apply correction
    if 0 <= corr_idx < 7:
        squin.x(data[corr_idx])
    
    # Decode and measure
    decode_713_block(data)
    return squin.measure(data[6])


# ============================================================================
# Benchmark functions
# ============================================================================

def benchmark_physical(p, shots=500):
    """Physical memory error rate."""
    results = emu.task(physical_memory_Z, args=(p,)).batch_run(shots=shots)
    errors = sum(1 for r in results if int(r) == 1)
    return errors / shots


def benchmark_logical(p, shots=500, postselect=False):
    """Logical memory error rate with optional post-selection."""
    # Get baseline syndromes
    baseX, baseZ = list(emu.task(measure_clean_syndromes, args=(0.0, 0.0)).batch_run(shots=1))[0]
    synX0 = color_parities([int(b) for b in baseX])
    synZ0 = color_parities([int(b) for b in baseZ])
    
    results = emu.task(logical_with_syndrome, args=(p,)).batch_run(shots=shots)
    
    failures = 0
    accepted = 0
    
    for data_bits, measX, measZ in results:
        synX = color_parities([int(b) for b in measX])
        synZ = color_parities([int(b) for b in measZ])
        
        # Post-selection: only accept trivial syndromes
        if postselect and (synX != synX0 or synZ != synZ0):
            continue
        
        accepted += 1
        
        # Locate error
        x_flip = locate_flipped_qubit(synX0, synX)
        
        # Apply correction
        corr_result = list(emu.task(logical_with_correction, args=(p, x_flip)).batch_run(shots=1))[0]
        if int(corr_result) == 1:
            failures += 1
    
    if accepted == 0:
        return 1.0
    
    return failures / accepted


# ============================================================================
# Main benchmark
# ============================================================================

def run_benchmark():
    """Run full benchmark sweep."""
    print("\n" + "="*70)
    print("QUANTUM MEMORY FIDELITY BENCHMARK")
    print("="*70)
    
    p_list = np.logspace(-3, -1, 6)  # [0.001, 0.002, 0.005, 0.010, 0.021, 0.046]
    
    phys_errs = []
    log_errs = []
    post_errs = []
    
    for p in p_list:
        print(f"\nPhysical error rate p = {p:.4f}")
        
        phys = benchmark_physical(p, shots=300)
        log = benchmark_logical(p, shots=200, postselect=False)
        post = benchmark_logical(p, shots=200, postselect=True)
        
        phys_errs.append(phys)
        log_errs.append(log)
        post_errs.append(post)
        
        print(f"  Physical:       {phys:.4f}")
        print(f"  Logical:        {log:.4f}")
        print(f"  Post-selected:  {post:.4f}")
    
    # Plot
    fig, ax = plt.subplots(figsize=(10, 7))
    
    ax.loglog(p_list, phys_errs, 'o-', linewidth=2.5, markersize=10, label='Physical (1 qubit)', color='red')
    ax.loglog(p_list, log_errs, 's-', linewidth=2.5, markersize=10, label='Logical [[7,1,3]] + QEC', color='blue')
    ax.loglog(p_list, post_errs, '^-', linewidth=2.5, markersize=10, label='Post-Selection', color='green')
    
    # Reference curves
    ax.loglog(p_list, p_list, '--', alpha=0.4, color='gray', linewidth=1.5, label='~p (linear)')
    ax.loglog(p_list, [p**2 for p in p_list], ':', alpha=0.4, color='purple', linewidth=1.5, label='~p² (quadratic)')
    
    ax.set_xlabel('Physical Error Rate (p)', fontweight='bold', fontsize=13)
    ax.set_ylabel('Logical Error Rate', fontweight='bold', fontsize=13)
    ax.set_title('Quantum Memory: Physical vs Logical Error\n[[7,1,3]] Color Code', fontweight='bold', fontsize=14)
    ax.legend(fontsize=11, loc='best')
    ax.grid(True, alpha=0.3, which='both')
    
    plt.tight_layout()
    plt.savefig('memory_fidelity_benchmark.png', dpi=300, bbox_inches='tight')
    print("\n✓ Saved: memory_fidelity_benchmark.png")
    print("="*70)


if __name__ == "__main__":
    run_benchmark()
