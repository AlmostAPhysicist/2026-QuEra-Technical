#!/usr/bin/env python3
"""
Realistic Logical Memory Decay Simulation
========================================

Simulates a logical qubit stored for time T using repeated QEC cycles.

Each cycle:
  1. Apply memory noise (idle Pauli errors)
  2. Extract syndrome (Steane style)
  3. Either:
        - Postselect (discard nontrivial syndrome)
        - Correct (apply Pauli correction)
  4. Repeat

Finally:
  Decode logical qubit → physical
  Measure fidelity

Noise is applied INSIDE the circuit (real gate fidelity).
"""

from random import random, randint
from collections import Counter

from bloqade import squin
from bloqade.pyqrack import StackMemorySimulator

from qec.encoding import encode_713_block, decode_713_block, setPhysicalQubit
from qec.errors import inject_pauli
from qec.error_mapping import color_parities, locate_flipped_qubit

emu = StackMemorySimulator()


# ============================================================
# Noise parameters (realistic)
# ============================================================

P_IDLE = 0.01     # memory error per qubit per round
P_GATE = 0.01     # 2-qubit gate depolarizing error


# ============================================================
# Kernel: Apply idle memory noise
# ============================================================

@squin.kernel
def apply_idle_noise(block):
    """
    Apply single-qubit depolarizing noise to all 7 qubits.
    Models decoherence during storage.
    """
    squin.broadcast.depolarize(P_IDLE, block)


# ============================================================
# Kernel: Syndrome extraction with gate noise
# ============================================================

@squin.kernel
def measure_syndrome(block, probeX, probeZ):
    """Measure syndrome using provided probes (pre-allocated outside kernel)."""

    # Reset probes to |0⟩ state
    for j in range(7):
        squin.reset(probeX[j])
        squin.reset(probeZ[j])

    # Prepare X probe in |+⟩ state
    for j in range(7):
        squin.h(probeX[j])

    # Prepare Z probe in |0⟩ state (already done by reset)

    # --- X syndrome measurement ---
    for j in range(7):
        squin.cx(block[j], probeX[j])
        squin.depolarize2(P_GATE, block[j], probeX[j])

    measX = squin.broadcast.measure(probeX)

    # --- Z syndrome measurement ---
    for j in range(7):
        squin.cx(probeZ[j], block[j])
        squin.depolarize2(P_GATE, probeZ[j], block[j])

    for j in range(7):
        squin.h(probeZ[j])

    measZ = squin.broadcast.measure(probeZ)

    return measX, measZ


# ============================================================
# Kernel: Apply correction
# ============================================================

@squin.kernel
def apply_correction(block, idx: int, basis: int):
    if idx >= 0:
        inject_pauli(block, idx, basis)


# ============================================================
# Kernel: One full QEC cycle
# ============================================================

@squin.kernel
def qec_cycle(block, probeX, probeZ):
    """Apply idle noise and measure syndrome using provided probes."""
    
    # Apply idle noise
    squin.broadcast.depolarize(P_IDLE, block)
    
    # Reset probes to |0⟩ state
    for j in range(7):
        squin.reset(probeX[j])
        squin.reset(probeZ[j])

    # Prepare X probe in |+⟩ state
    for j in range(7):
        squin.h(probeX[j])

    # --- X syndrome measurement ---
    for j in range(7):
        squin.cx(block[j], probeX[j])
        squin.depolarize2(P_GATE, block[j], probeX[j])

    measX = squin.broadcast.measure(probeX)

    # --- Z syndrome measurement ---
    for j in range(7):
        squin.cx(probeZ[j], block[j])
        squin.depolarize2(P_GATE, probeZ[j], block[j])

    for j in range(7):
        squin.h(probeZ[j])

    measZ = squin.broadcast.measure(probeZ)

    return measX, measZ


# ============================================================
# Kernel: Prepare all qubits at once (non-kernel wrapper)
# ============================================================

@squin.kernel
def initialize_data_and_probes(theta: float, phi: float, block, probeX, probeZ):
    """Initialize data block and probe qubits."""
    # Initialize data block
    setPhysicalQubit(theta, phi, block[6])
    encode_713_block(block)
    
    # Initialize probes to |0⟩
    for j in range(7):
        squin.reset(probeX[j])
        squin.reset(probeZ[j])


# ============================================================
# Full memory experiment (host-controlled loop)
# ============================================================

def run_memory_experiment(T=1.0, dt=0.1, shots=200):

    rounds = int(T / dt)

    print("\n===================================================")
    print(f"Logical memory simulation: T={T}s, rounds={rounds}")
    print(f"P_IDLE={P_IDLE}, P_GATE={P_GATE}")
    print("===================================================")

    post_accept = 0
    post_total = 0

    corr_success = 0
    corr_total = 0

    flip_hist = Counter()

    for shot_idx in range(shots):

        # --- Random logical input (Bloch sphere) ---
        theta = random() * 3.1415926535
        phi   = random() * 2 * 3.1415926535

        # --- Allocate all qubits at the Python level (outside kernel) ---
        # We need to allocate them in a single kernel call to avoid issues
        @squin.kernel
        def allocate_all():
            block = squin.qalloc(7)
            probeX = squin.qalloc(7)
            probeZ = squin.qalloc(7)
            return block, probeX, probeZ
        
        block, probeX, probeZ = list(
            emu.task(allocate_all).batch_run(shots=1)
        )[0]

        # --- Initialize block and probes ---
        list(
            emu.task(initialize_data_and_probes,
                     args=(theta, phi, block, probeX, probeZ)).batch_run(shots=1)
        )

        # --- Measure initial syndrome baseline ---
        measX0, measZ0 = list(
            emu.task(measure_syndrome, args=(block, probeX, probeZ)).batch_run(shots=1)
        )[0]

        synX0 = color_parities([int(b) for b in measX0])
        synZ0 = color_parities([int(b) for b in measZ0])

        # --- Run repeated QEC cycles ---
        for r in range(rounds):

            measX, measZ = list(
                emu.task(qec_cycle, args=(block, probeX, probeZ)).batch_run(shots=1)
            )[0]

            synX = color_parities([int(b) for b in measX])
            synZ = color_parities([int(b) for b in measZ])

            post_total += 1

            # ========== POSTSELECTION ==========
            if synX == synX0 and synZ == synZ0:
                post_accept += 1

            # ========== CORRECTION ==========
            x_loc = locate_flipped_qubit(synX0, synX)
            z_loc = locate_flipped_qubit(synZ0, synZ)

            if x_loc != -1 and z_loc != -1:
                basis, idx = 1, x_loc   # Y
            elif x_loc != -1:
                basis, idx = 0, x_loc   # X
            elif z_loc != -1:
                basis, idx = 2, z_loc   # Z
            else:
                basis, idx = 0, -1

            if idx != -1:
                corr_total += 1

                # Apply correction physically
                list(
                    emu.task(apply_correction,
                             args=(block, idx, basis)).batch_run(shots=1)
                )

                # Re-measure syndrome to confirm restore
                measX2, measZ2 = list(
                    emu.task(measure_syndrome,
                             args=(block, probeX, probeZ)).batch_run(shots=1)
                )[0]

                synX2 = color_parities([int(b) for b in measX2])
                synZ2 = color_parities([int(b) for b in measZ2])

                if synX2 == synX0 and synZ2 == synZ0:
                    corr_success += 1

        # Histogram of how often corrections happened
        flip_hist[corr_total] += 1

    # ========================================================
    # Results
    # ========================================================

    waste = 1 - post_accept / post_total
    restore_rate = corr_success / corr_total if corr_total > 0 else 1.0

    print("\nRESULTS:")
    print(f"Postselection waste fraction      = {waste:.3f}")
    print(f"Correction syndrome restore rate  = {restore_rate:.3f}")

    print("\nCorrection events distribution:")
    total = sum(flip_hist.values())
    for k in sorted(flip_hist):
        print(f"  {k} corrections: {flip_hist[k]/total:.3f}")


# ============================================================
# Main
# ============================================================

if __name__ == "__main__":

    configs = [
        ("Short time", 0.2),
        ("Medium time", 1.0),
        ("Long time", 3.0),
    ]

    for name, T in configs:
        print("\n" + "="*70)
        print(name)
        print("="*70)

        run_memory_experiment(T=T, dt=0.2, shots=200)
