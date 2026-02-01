#!/usr/bin/env python3
"""
Logical Memory Benchmark v5

Fidelity measured as state overlap:
- Measure Z basis multiple times to get probability distribution
- Compare measured p(|0>) to ideal p(|0>)
- Fidelity = 1 - 2*|p_measured - p_ideal|
"""

import matplotlib
matplotlib.use("Agg")

import math
from random import randint, random, choice
from collections import Counter

from bloqade import squin
from bloqade.pyqrack import StackMemorySimulator

from qec.encoding import prepareLogicalQubit, decode_713_block
from qec.errors import inject_pauli
from qec.error_mapping import color_parities, locate_flipped_qubit

emu = StackMemorySimulator()

pi = math.pi

# ============================================================
# All 24 Clifford states with ideal p(|0>) in Z basis
# ============================================================

CLIFFORD_STATES = {
    # Z basis eigenstates
    "|0>": 1.0,      # Always measure 0
    "|1>": 0.0,      # Always measure 1
    
    # X basis eigenstates (50-50 in Z basis)
    "|+>": 0.5,
    "|->": 0.5,
    
    # Y basis eigenstates (50-50 in Z basis)
    "|+i>": 0.5,
    "|-i>": 0.5,
}


# ============================================================
# Multi-error sampler
# ============================================================

def sample_error_events(p1: float, r: float = 0.25, max_errors: int = 5):
    """
    Sample k errors with exponentially decreasing probability.
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
# Kernel: Measure state in Z basis (no errors)
# ============================================================

@squin.kernel
def measure_state_z(theta: float, phi: float):
    block = prepareLogicalQubit(theta, phi)
    decode_713_block(block)
    return squin.measure(block[6])


# ============================================================
# Kernel: Measure state in Z basis with errors
# ============================================================

@squin.kernel
def measure_state_z_with_errors(theta: float, phi: float,
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
# Kernel: Syndrome measurement
# ============================================================

@squin.kernel
def measure_syndrome(theta: float, phi: float):
    data = prepareLogicalQubit(theta, phi)

    # ---- X probe ----
    probeX = prepareLogicalQubit(0.0, pi / 2)
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
# Kernel: Syndrome extraction after errors
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
    probeX = prepareLogicalQubit(0.0, pi / 2)
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

def run_modes(p1: float, shots: int = 500, meas_shots: int = 10):
    """
    meas_shots: number of measurements per trial to estimate p(|0>)
    """

    baseline_fid = 0.0
    corr_fid = 0.0
    post_fid = 0.0

    post_accept = 0
    post_total = 0

    syndrome_restored = 0
    correction_attempted = 0

    flip_hist = Counter()

    for _ in range(shots):

        # Random Clifford input state
        label = choice(list(CLIFFORD_STATES.keys()))
        p_ideal = CLIFFORD_STATES[label]
        
        # Get theta, phi from simple mapping
        if label == "|0>":
            theta, phi = 0.0, 0.0
        elif label == "|1>":
            theta, phi = pi, 0.0
        elif label == "|+>":
            theta, phi = pi/2, 0.0
        elif label == "|->":
            theta, phi = pi/2, pi
        elif label == "|+i>":
            theta, phi = pi/2, pi/2
        elif label == "|-i>":
            theta, phi = pi/2, 3*pi/2

        # Measure baseline syndrome BEFORE errors
        baseX, baseZ = list(
            emu.task(measure_syndrome,
                     args=(theta, phi)).batch_run(shots=1)
        )[0]

        synX0 = color_parities([int(b) for b in baseX])
        synZ0 = color_parities([int(b) for b in baseZ])

        # Sample errors
        errors = sample_error_events(p1)
        flip_hist[len(errors)] += 1

        while len(errors) < 5:
            errors.append((-1, 0))

        (e1_i, e1_b), (e2_i, e2_b), (e3_i, e3_b), (e4_i, e4_b), (e5_i, e5_b) = errors

        # =============== BASELINE: Measure with errors, no correction ===============
        zeros_baseline = 0
        for _ in range(meas_shots):
            meas = list(
                emu.task(measure_state_z_with_errors,
                         args=(theta, phi,
                               e1_i, e1_b,
                               e2_i, e2_b,
                               e3_i, e3_b,
                               e4_i, e4_b,
                               e5_i, e5_b)).batch_run(shots=1)
            )[0]
            if int(meas) == 0:
                zeros_baseline += 1

        p_measured_baseline = zeros_baseline / meas_shots
        fid_baseline = 1.0 - 2.0 * abs(p_measured_baseline - p_ideal)
        baseline_fid += fid_baseline

        # =============== SYNDROME: Get syndrome after errors ===============
        measX, measZ = list(
            emu.task(syndrome_trial,
                     args=(theta, phi,
                           e1_i, e1_b,
                           e2_i, e2_b,
                           e3_i, e3_b,
                           e4_i, e4_b,
                           e5_i, e5_b)).batch_run(shots=1)
        )[0]

        synX1 = color_parities([int(b) for b in measX])
        synZ1 = color_parities([int(b) for b in measZ])

        # =============== POSTSELECTION ===============
        post_total += 1

        if synX1 == synX0 and synZ1 == synZ0:
            post_accept += 1

            # Postselection: only measure if syndrome is clean
            zeros_post = 0
            for _ in range(meas_shots):
                meas = list(
                    emu.task(measure_state_z_with_errors,
                             args=(theta, phi,
                                   e1_i, e1_b,
                                   e2_i, e2_b,
                                   e3_i, e3_b,
                                   e4_i, e4_b,
                                   e5_i, e5_b)).batch_run(shots=1)
                )[0]
                if int(meas) == 0:
                    zeros_post += 1

            p_measured_post = zeros_post / meas_shots
            fid_post = 1.0 - 2.0 * abs(p_measured_post - p_ideal)
            post_fid += fid_post

        # =============== CORRECTION ===============
        x_loc = locate_flipped_qubit(synX0, synX1)
        z_loc = locate_flipped_qubit(synZ0, synZ1)

        if x_loc != -1 and z_loc != -1:
            corr_basis, corr_index = 1, x_loc  # Y
        elif x_loc != -1:
            corr_basis, corr_index = 0, x_loc  # X
        elif z_loc != -1:
            corr_basis, corr_index = 2, z_loc  # Z
        else:
            corr_basis, corr_index = 0, -1

        if corr_index >= 0:
            correction_attempted += 1

        zeros_corr = 0
        for _ in range(meas_shots):
            meas_corr = list(
                emu.task(corrected_trial,
                         args=(theta, phi,
                               e1_i, e1_b,
                               e2_i, e2_b,
                               e3_i, e3_b,
                               e4_i, e4_b,
                               e5_i, e5_b,
                               corr_index, corr_basis)).batch_run(shots=1)
            )[0]
            if int(meas_corr) == 0:
                zeros_corr += 1

        p_measured_corr = zeros_corr / meas_shots
        fid_corr = 1.0 - 2.0 * abs(p_measured_corr - p_ideal)
        corr_fid += fid_corr

        if corr_index >= 0 and fid_corr > fid_baseline:
            syndrome_restored += 1

    # Results (average fidelities)
    baseline_fid /= shots
    corr_fid /= shots
    post_fid /= post_accept if post_accept > 0 else 1
    waste = 1 - post_accept / post_total

    restore_rate = syndrome_restored / correction_attempted if correction_attempted > 0 else 0

    return baseline_fid, post_fid, waste, corr_fid, restore_rate, flip_hist


# ============================================================
# Main
# ============================================================

def main():

    configs = [
        ("Low noise", 0.0, 20),
        ("Medium noise", 0.10, 100),
        ("High noise", 0.50, 100),
    ]

    for name, p1, shots in configs:

        print("\n" + "="*70)
        print(name)
        print("="*70)

        base, post, waste, corr, restore, hist = run_modes(p1, shots, meas_shots=10)

        print(f"Physical error scale p1 = {p1}")
        print(f"Baseline fidelity        = {base:.4f}")
        print(f"Postselected fidelity    = {post:.4f}")
        print(f"Postselection waste frac = {waste:.4f}")
        print(f"Corrected fidelity       = {corr:.4f}")
        print(f"Correction syndrome restore rate = {restore:.4f}")

        print("\nInjected flip count distribution:")
        total = sum(hist.values())
        for k in sorted(hist.keys()):
            frac = hist[k] / total
            print(f"  {k} flips: {frac:.3f}")


if __name__ == "__main__":
    main()
