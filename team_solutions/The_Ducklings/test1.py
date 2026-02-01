#!/usr/bin/env python3
"""
Advanced Logical Memory Benchmark

We compare:

1. Baseline (no QEC)
2. Post-selection QEC (discard non-trivial syndromes)
3. Active correction QEC (apply correction)

We also allow MULTI-error injection:

Probability of k errors:
    P(1) = p1
    P(2) = p1*r
    P(3) = p1*r^2
    ...

Outputs:
- Fidelity
- Waste fraction (post-selection)
- Correction usage fraction
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
# Multi-error sampler
# ============================================================

def sample_error_events(p1: float, r: float = 0.2, max_errors: int = 3):
    """
    Sample 0,1,2,... Pauli errors with exponentially decreasing probability.

    Returns list of (err_index, err_basis)
    """

    errors = []

    # Decide how many errors happen
    k = 0
    prob = p1
    while k < max_errors and random() < prob:
        k += 1
        prob *= r  # exponential suppression

    # Sample k random Pauli flips
    for _ in range(k):
        idx = randint(0, 6)
        basis = randint(0, 2)  # X,Y,Z
        errors.append((idx, basis))

    return errors


# ============================================================
# Kernel: Apply list of Pauli errors
# ============================================================

@squin.kernel
def inject_multiple(block, e1_i: int, e1_b: int,
                    e2_i: int, e2_b: int,
                    e3_i: int, e3_b: int):
    """
    Inject up to 3 Pauli errors (unused ones set to -1).
    """

    if e1_i >= 0:
        inject_pauli(block, e1_i, e1_b)
    if e2_i >= 0:
        inject_pauli(block, e2_i, e2_b)
    if e3_i >= 0:
        inject_pauli(block, e3_i, e3_b)


# ============================================================
# Baseline trial (no correction)
# ============================================================

@squin.kernel
def baseline_trial(e1_i, e1_b, e2_i, e2_b, e3_i, e3_b):

    block = prepareLogicalQubit(0.0, 0.0)

    inject_multiple(block,
                    e1_i, e1_b,
                    e2_i, e2_b,
                    e3_i, e3_b)

    decode_713_block(block)
    return squin.measure(block[6])


# ============================================================
# Syndrome extraction kernel
# ============================================================

@squin.kernel
def syndrome_trial(e1_i, e1_b, e2_i, e2_b, e3_i, e3_b):

    data = prepareLogicalQubit(0.0, 0.0)

    inject_multiple(data,
                    e1_i, e1_b,
                    e2_i, e2_b,
                    e3_i, e3_b)

    # ---- X syndrome probe ----
    probeX = prepareLogicalQubit(0.0, 3.1415926535 / 2)
    for j in range(7):
        squin.cx(data[j], probeX[j])
    measX = squin.broadcast.measure(probeX)

    # ---- Z syndrome probe ----
    probeZ = prepareLogicalQubit(0.0, 0.0)
    for j in range(7):
        squin.cx(probeZ[j], data[j])
    for j in range(7):
        squin.h(probeZ[j])
    measZ = squin.broadcast.measure(probeZ)

    return measX, measZ


# ============================================================
# Correction trial kernel
# ============================================================

@squin.kernel
def corrected_trial(e1_i, e1_b, e2_i, e2_b, e3_i, e3_b,
                    corr_index: int, corr_basis: int):

    block = prepareLogicalQubit(0.0, 0.0)

    inject_multiple(block,
                    e1_i, e1_b,
                    e2_i, e2_b,
                    e3_i, e3_b)

    if corr_index >= 0:
        inject_pauli(block, corr_index, corr_basis)

    decode_713_block(block)
    return squin.measure(block[6])


# ============================================================
# Host: Run benchmark modes
# ============================================================

def run_modes(p1, shots=500):

    # Baseline syndromes
    baseX, baseZ = list(
        emu.task(measure_clean_syndromes,
                 args=(0.0, 0.0)).batch_run(shots=1)
    )[0]

    synX0 = color_parities([int(b) for b in baseX])
    synZ0 = color_parities([int(b) for b in baseZ])

    # Stats
    baseline_fail = 0

    post_fail = 0
    post_accept = 0
    post_total = 0

    corr_fail = 0
    corr_used = 0

    for _ in range(shots):

        # Sample multi-error event
        errors = sample_error_events(p1)

        # Pad to 3 errors max
        while len(errors) < 3:
            errors.append((-1, 0))

        (e1_i, e1_b), (e2_i, e2_b), (e3_i, e3_b) = errors

        # -------------------------------
        # Baseline
        # -------------------------------
        meas = list(
            emu.task(baseline_trial,
                     args=(e1_i, e1_b,
                           e2_i, e2_b,
                           e3_i, e3_b)).batch_run(shots=1)
        )[0]

        if int(meas) == 1:
            baseline_fail += 1

        # -------------------------------
        # Syndrome measurement
        # -------------------------------
        measX, measZ = list(
            emu.task(syndrome_trial,
                     args=(e1_i, e1_b,
                           e2_i, e2_b,
                           e3_i, e3_b)).batch_run(shots=1)
        )[0]

        synX1 = color_parities([int(b) for b in measX])
        synZ1 = color_parities([int(b) for b in measZ])

        # -------------------------------
        # Mode A: Post-selection
        # -------------------------------
        post_total += 1

        if synX1 == synX0 and synZ1 == synZ0:
            post_accept += 1

            meas_post = list(
                emu.task(baseline_trial,
                         args=(e1_i, e1_b,
                               e2_i, e2_b,
                               e3_i, e3_b)).batch_run(shots=1)
            )[0]

            if int(meas_post) == 1:
                post_fail += 1

        # -------------------------------
        # Mode B: Correction
        # -------------------------------
        x_loc = locate_flipped_qubit(synX0, synX1)
        z_loc = locate_flipped_qubit(synZ0, synZ1)

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

        if corr_index >= 0:
            corr_used += 1

        meas_corr = list(
            emu.task(corrected_trial,
                     args=(e1_i, e1_b,
                           e2_i, e2_b,
                           e3_i, e3_b,
                           corr_index, corr_basis)).batch_run(shots=1)
        )[0]

        if int(meas_corr) == 1:
            corr_fail += 1

    # Compute results
    baseline_fid = 1 - baseline_fail / shots

    post_fid = 1 - post_fail / post_accept if post_accept > 0 else 0
    post_waste = 1 - post_accept / post_total

    corr_fid = 1 - corr_fail / shots
    corr_usage = corr_used / shots

    return baseline_fid, post_fid, post_waste, corr_fid, corr_usage


# ============================================================
# Main sweep
# ============================================================

def main():

    configs = [
        ("Low noise", 0.0, 10),
        ("Medium noise", 0.10, 500),
        ("High noise", 0.50, 500),
    ]

    for name, p1, shots in configs:

        print("\n" + "="*70)
        print(name)
        print("="*70)

        base, post, waste, corr, usage = run_modes(p1, shots=shots)

        print(f"Physical error scale p1 = {p1}")
        print(f"Baseline fidelity        = {base:.4f}")
        print(f"Postselected fidelity    = {post:.4f}")
        print(f"Postselection waste frac = {waste:.4f}")
        print(f"Corrected fidelity       = {corr:.4f}")
        print(f"Correction used fraction = {usage:.4f}")


if __name__ == "__main__":
    main()
