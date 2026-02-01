#!/usr/bin/env python3
"""
Logical Memory Benchmark: Baseline vs Error Correction

We compare:

(1) Baseline logical memory fidelity (no correction)
(2) Logical memory fidelity with 1-round Steane QEC correction

Fidelity = P(final decoded qubit == 0)
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from random import randint, random
from bloqade import squin
from bloqade.pyqrack import StackMemorySimulator

from qec.encoding import prepareLogicalQubit, decode_713_block
from qec.errors import inject_pauli
from qec.syndrome import measure_clean_syndromes
from qec.error_mapping import color_parities, locate_flipped_qubit

emu = StackMemorySimulator()


# ============================================================
# Kernel: Baseline (Encode → Inject → Decode → Measure)
# ============================================================

@squin.kernel
def logical_memory_trial(err_index: int, err_basis: int):
    block = prepareLogicalQubit(0.0, 0.0)

    inject_pauli(block, err_index, err_basis)

    decode_713_block(block)
    return squin.measure(block[6])


@squin.kernel
def logical_memory_clean():
    block = prepareLogicalQubit(0.0, 0.0)
    decode_713_block(block)
    return squin.measure(block[6])


# ============================================================
# Kernel: Syndrome extraction (Steane probes)
# ============================================================

@squin.kernel
def logical_memory_with_syndrome(err_index: int, err_basis: int):
    """
    Encode |0_L>, inject error, measure X and Z syndromes.
    Returns (measX, measZ).
    """

    data = prepareLogicalQubit(0.0, 0.0)

    inject_pauli(data, err_index, err_basis)

    # ---- X syndrome probe (|+_L>) ----
    probeX = prepareLogicalQubit(0.0, 3.1415926535 / 2)
    for j in range(7):
        squin.cx(data[j], probeX[j])
    measX = squin.broadcast.measure(probeX)

    # ---- Z syndrome probe (|0_L>) ----
    probeZ = prepareLogicalQubit(0.0, 0.0)
    for j in range(7):
        squin.cx(probeZ[j], data[j])
    for j in range(7):
        squin.h(probeZ[j])
    measZ = squin.broadcast.measure(probeZ)

    return measX, measZ


# ============================================================
# Kernel: Apply correction then decode + measure
# ============================================================

@squin.kernel
def logical_memory_corrected(err_index: int, err_basis: int,
                            corr_index: int, corr_basis: int):
    """
    Inject error, apply correction, decode, measure.
    """

    block = prepareLogicalQubit(0.0, 0.0)

    inject_pauli(block, err_index, err_basis)

    # Apply correction if valid
    if corr_index >= 0:
        inject_pauli(block, corr_index, corr_basis)

    decode_713_block(block)
    return squin.measure(block[6])


# ============================================================
# Host: Baseline fidelity
# ============================================================

def baseline_fidelity(p_error, shots=500):

    failures = 0

    for _ in range(shots):

        if random() < p_error:
            i = randint(0, 6)
            b = randint(0, 2)

            meas = list(
                emu.task(logical_memory_trial,
                         args=(i, b)).batch_run(shots=1)
            )[0]
        else:
            meas = list(
                emu.task(logical_memory_clean,
                         args=()).batch_run(shots=1)
            )[0]

        if int(meas) == 1:
            failures += 1

    return 1.0 - failures / shots


# ============================================================
# Host: QEC corrected fidelity
# ============================================================

def qec_fidelity(p_error, shots=500):

    # Baseline syndrome reference
    baseX, baseZ = list(
        emu.task(measure_clean_syndromes,
                 args=(0.0, 0.0)).batch_run(shots=1)
    )[0]

    synX0 = color_parities([int(b) for b in baseX])
    synZ0 = color_parities([int(b) for b in baseZ])

    failures = 0

    for _ in range(shots):

        # Random error injection
        if random() < p_error:
            err_index = randint(0, 6)
            err_basis = randint(0, 2)
        else:
            err_index = 0
            err_basis = 0   # harmless, overwritten by no-syndrome

        # Measure syndromes
        measX, measZ = list(
            emu.task(logical_memory_with_syndrome,
                     args=(err_index, err_basis)).batch_run(shots=1)
        )[0]

        synX1 = color_parities([int(b) for b in measX])
        synZ1 = color_parities([int(b) for b in measZ])

        # Decode location
        x_loc = locate_flipped_qubit(synX0, synX1)
        z_loc = locate_flipped_qubit(synZ0, synZ1)

        # Determine correction type
        if x_loc != -1 and z_loc != -1:
            corr_basis = 1  # Y
            corr_index = x_loc
        elif x_loc != -1:
            corr_basis = 0  # X
            corr_index = x_loc
        elif z_loc != -1:
            corr_basis = 2  # Z
            corr_index = z_loc
        else:
            corr_basis = 0
            corr_index = -1

        # Apply correction + decode + measure
        meas = list(
            emu.task(logical_memory_corrected,
                     args=(err_index, err_basis,
                           corr_index, corr_basis)).batch_run(shots=1)
        )[0]

        if int(meas) == 1:
            failures += 1

    return 1.0 - failures / shots


# ============================================================
# Sweep benchmark
# ============================================================

def run_benchmark():

    p_list = [0.0, 0.01, 0.05, 0.10, 0.20]

    base_vals = []
    qec_vals = []

    print("\n" + "="*70)
    print("LOGICAL MEMORY: BASELINE vs QEC CORRECTION")
    print("="*70)

    for p in p_list:
        base = baseline_fidelity(p, shots=1000)
        qec = qec_fidelity(p, shots=1000)

        base_vals.append(base)
        qec_vals.append(qec)

        print(f"p={p:.3f} | baseline={base:.4f} | QEC={qec:.4f}")

    # Plot
    plt.figure(figsize=(8,6))
    plt.plot(p_list, base_vals, "o-", label="No correction", linewidth=3)
    plt.plot(p_list, qec_vals, "o-", label="With Steane QEC", linewidth=3)

    plt.xlabel("Physical error probability p")
    plt.ylabel("Logical fidelity")
    plt.title("Baseline vs Error-Corrected Logical Memory")

    plt.grid(True)
    plt.ylim([0, 1.05])
    plt.legend()

    plt.savefig("qec_vs_baseline.png", dpi=300)
    print("\n✓ Saved qec_vs_baseline.png")


if __name__ == "__main__":
    run_benchmark()
