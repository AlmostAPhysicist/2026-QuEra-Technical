#!/usr/bin/env python3
"""
Advanced Logical Memory Benchmark v3 (Correct)

Upgrades:

✅ Arbitrary logical input state (random θ,φ)
✅ Baseline stabilizers measured BEFORE noise per-shot
✅ Multi-error injection (0–5 flips)
✅ Baseline vs Postselection vs Correction comparison
✅ Fidelity defined relative to baseline decoded measurement
"""

import matplotlib
matplotlib.use("Agg")

from random import randint, random
from collections import Counter

import numpy as np

from bloqade import squin
from bloqade.pyqrack import StackMemorySimulator

from qec.encoding import prepareLogicalQubit, decode_713_block
from qec.errors import inject_pauli
from qec.error_mapping import color_parities, locate_flipped_qubit

emu = StackMemorySimulator()


# ============================================================
# Multi-error sampler
# ============================================================

def sample_error_events(p1: float, r: float = 0.25, max_errors: int = 5):
    """
    Sample k errors with exponentially decreasing probability.

    P(1)=p1
    P(2)=p1*r
    P(3)=p1*r^2
    ...

    Returns list of (index, basis).
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
# Kernel: Inject up to 5 Pauli flips
# ============================================================

@squin.kernel
def inject_multiple(block,
                    e1_i, e1_b,
                    e2_i, e2_b,
                    e3_i, e3_b,
                    e4_i, e4_b,
                    e5_i, e5_b):

    if e1_i >= 0: inject_pauli(block, e1_i, e1_b)
    if e2_i >= 0: inject_pauli(block, e2_i, e2_b)
    if e3_i >= 0: inject_pauli(block, e3_i, e3_b)
    if e4_i >= 0: inject_pauli(block, e4_i, e4_b)
    if e5_i >= 0: inject_pauli(block, e5_i, e5_b)


# ============================================================
# Kernel: Decode + measure logical output qubit
# ============================================================

@squin.kernel
def measure_logical(theta: float, phi: float,
                    e1_i, e1_b,
                    e2_i, e2_b,
                    e3_i, e3_b,
                    e4_i, e4_b,
                    e5_i, e5_b):

    block = prepareLogicalQubit(theta, phi)

    inject_multiple(block,
                    e1_i, e1_b,
                    e2_i, e2_b,
                    e3_i, e3_b,
                    e4_i, e4_b,
                    e5_i, e5_b)

    decode_713_block(block)

    return squin.measure(block[6])


# ============================================================
# Kernel: Syndrome extraction
# ============================================================

@squin.kernel
def syndrome_trial(theta: float, phi: float,
                   e1_i, e1_b,
                   e2_i, e2_b,
                   e3_i, e3_b,
                   e4_i, e4_b,
                   e5_i, e5_b):

    data = prepareLogicalQubit(theta, phi)

    inject_multiple(data,
                    e1_i, e1_b,
                    e2_i, e2_b,
                    e3_i, e3_b,
                    e4_i, e4_b,
                    e5_i, e5_b)

    # ---- X probe ----
    probeX = prepareLogicalQubit(0.0, np.pi / 2)
    for j in range(7):
        squin.cx(data[j], probeX[j])
    measX = squin.broadcast.measure(probeX)

    # ---- Z probe ----
    probeZ = prepareLogicalQubit(0.0, 0.0)
    for j in range(7):
        squin.cx(probeZ[j], data[j])
    for j in range(7):
        squin.h(probeZ[j])
    measZ = squin.broadcast.measure(probeZ)

    return measX, measZ


# ============================================================
# Kernel: Correction trial
# ============================================================

@squin.kernel
def corrected_trial(theta: float, phi: float,
                    e1_i, e1_b,
                    e2_i, e2_b,
                    e3_i, e3_b,
                    e4_i, e4_b,
                    e5_i, e5_b,
                    corr_index: int,
                    corr_basis: int):

    block = prepareLogicalQubit(theta, phi)

    inject_multiple(block,
                    e1_i, e1_b,
                    e2_i, e2_b,
                    e3_i, e3_b,
                    e4_i, e4_b,
                    e5_i, e5_b)

    if corr_index >= 0:
        inject_pauli(block, corr_index, corr_basis)

    decode_713_block(block)
    return squin.measure(block[6])


# ============================================================
# Benchmark runner
# ============================================================

def run_modes(p1: float, shots: int = 500):

    baseline_fail = 0
    corr_fail = 0
    post_fail = 0

    post_accept = 0
    post_total = 0

    flip_hist = Counter()

    for _ in range(shots):

        # Random arbitrary input state
        theta = random() * 2*np.pi
        phi   = random() * np.pi

        # ----------------------------------------------------
        # Baseline decoded measurement (no noise)
        # ----------------------------------------------------
        meas0 = list(
            emu.task(measure_logical,
                     args=(theta, phi,
                           -1,0,-1,0,-1,0,-1,0,-1,0)).batch_run(shots=1)
        )[0]

        expected = int(meas0)

        # ----------------------------------------------------
        # Baseline stabilizers BEFORE noise
        # ----------------------------------------------------
        measX0, measZ0 = list(
            emu.task(syndrome_trial,
                     args=(theta, phi,
                           -1,0,-1,0,-1,0,-1,0,-1,0)).batch_run(shots=1)
        )[0]

        synX0 = color_parities([int(b) for b in measX0])
        synZ0 = color_parities([int(b) for b in measZ0])

        # ----------------------------------------------------
        # Sample errors
        # ----------------------------------------------------
        errors = sample_error_events(p1)
        flip_hist[len(errors)] += 1

        while len(errors) < 5:
            errors.append((-1, 0))

        (e1_i, e1_b), (e2_i, e2_b), (e3_i, e3_b), (e4_i, e4_b), (e5_i, e5_b) = errors

        # ---------------- Baseline noisy ----------------
        meas = list(
            emu.task(measure_logical,
                     args=(theta, phi,
                           e1_i,e1_b,
                           e2_i,e2_b,
                           e3_i,e3_b,
                           e4_i,e4_b,
                           e5_i,e5_b)).batch_run(shots=1)
        )[0]

        if int(meas) != expected:
            baseline_fail += 1

        # ---------------- Syndrome after noise ----------------
        measX, measZ = list(
            emu.task(syndrome_trial,
                     args=(theta, phi,
                           e1_i,e1_b,
                           e2_i,e2_b,
                           e3_i,e3_b,
                           e4_i,e4_b,
                           e5_i,e5_b)).batch_run(shots=1)
        )[0]

        synX1 = color_parities([int(b) for b in measX])
        synZ1 = color_parities([int(b) for b in measZ])

        # ---------------- Postselection ----------------
        post_total += 1

        if synX1 == synX0 and synZ1 == synZ0:
            post_accept += 1

            if int(meas) != expected:
                post_fail += 1

        # ---------------- Correction ----------------
        x_loc = locate_flipped_qubit(synX0, synX1)
        z_loc = locate_flipped_qubit(synZ0, synZ1)

        if x_loc != -1 and z_loc != -1:
            corr_basis, corr_index = 1, x_loc
        elif x_loc != -1:
            corr_basis, corr_index = 0, x_loc
        elif z_loc != -1:
            corr_basis, corr_index = 2, z_loc
        else:
            corr_basis, corr_index = 0, -1

        meas_corr = list(
            emu.task(corrected_trial,
                     args=(theta, phi,
                           e1_i,e1_b,
                           e2_i,e2_b,
                           e3_i,e3_b,
                           e4_i,e4_b,
                           e5_i,e5_b,
                           corr_index, corr_basis)).batch_run(shots=1)
        )[0]

        if int(meas_corr) != expected:
            corr_fail += 1

    # Results
    baseline_fid = 1 - baseline_fail / shots
    corr_fid = 1 - corr_fail / shots

    post_fid = 1 - post_fail / post_accept if post_accept > 0 else 0
    waste = 1 - post_accept / post_total

    return baseline_fid, post_fid, waste, corr_fid, flip_hist


# ============================================================
# Main
# ============================================================

def main():

    configs = [
        ("Low noise", 0.0, 50),
        ("Medium noise", 0.10, 500),
        ("High noise", 0.50, 500),
    ]

    for name, p1, shots in configs:

        print("\n" + "="*70)
        print(name)
        print("="*70)

        base, post, waste, corr, hist = run_modes(p1, shots)

        print(f"Physical error scale p1 = {p1}")
        print(f"Baseline fidelity        = {base:.4f}")
        print(f"Postselected fidelity    = {post:.4f}")
        print(f"Postselection waste frac = {waste:.4f}")
        print(f"Corrected fidelity       = {corr:.4f}")

        print("\nAverage injected flips per shot:")
        total = sum(hist.values())
        for k in sorted(hist.keys()):
            frac = hist[k] / total
            print(f"  {k} flips: {frac:.3f}")


if __name__ == "__main__":
    main()
