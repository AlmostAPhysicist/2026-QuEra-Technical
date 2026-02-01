import matplotlib.pyplot as plt
import numpy as np
from bloqade.pyqrack import StackMemorySimulator

from .logical_ops import logical_X_roundtrip
from .correction import run_full_QEC
from .states import zeroState, plusState
from .error_mapping import color_parities

# Simple noiseless / noisy wrappers for convenience
def run_noiseless(theta, phi, shots=200):
    emu = StackMemorySimulator()
    task = emu.task(logical_X_roundtrip, args=(theta, phi))
    print("\n=== Noiseless Simulation ===")
    print(task.batch_run(shots=shots))

def run_with_noise(theta, phi, shots=200):
    # Use bloqade.cirq_utils.emit + noise models if available
    import bloqade.stim
    from bloqade.cirq_utils import noise
    from bloqade.cirq_utils.emit import emit_circuit
    from bloqade.cirq_utils import load_circuit

    cirq_circ = emit_circuit(logical_X_roundtrip, args=(theta, phi), ignore_returns=True)
    model = noise.GeminiOneZoneNoiseModel()
    noisy_cirq = noise.transform_circuit(cirq_circ, model=model)
    noisy_kernel = load_circuit(noisy_cirq)

    stim_circ = bloqade.stim.Circuit(noisy_kernel)
    sampler = stim_circ.compile_sampler()
    samples = sampler.sample(shots=shots)
    print("\n=== Noisy Gemini Simulation ===")
    print(samples)

# Post-selection experiment: prepare, measure syndromes, accept only shots with trivial syndromes
def postselected_memory_experiment(theta, phi, shots, measure_syndrome_task):
    """
    measure_syndrome_task should be a kernel that returns the probe measurement bits (length 7)
    This function demonstrates host-side post-selection: re-run until you collect the requested
    number of accepted shots (i.e. trivial syndrome).
    """
    emu = StackMemorySimulator()
    accepted = []
    attempts = 0
    while len(accepted) < shots and attempts < shots * 100:
        attempts += 1
        res = list(emu.task(measure_syndrome_task, args=(theta, phi, 0, 0)).batch_run(shots=1))[0]
        # res is a tuple (measX, measZ) or single probe depending on the kernel
        # Here assume kernel returns probe measurement bits for one probe (7 bits)
        probe_bits = list(res)
        # compute parity and decide accept (trivial syndrome = all zeros)
        if all(int(b) == 0 for b in probe_bits):
            accepted.append(probe_bits)
    print(f"Collected {len(accepted)} accepted shots after {attempts} attempts")
    return accepted

# Sweep logical error vs physical error (toy demonstration: vary global error parameter p)
def sweep_logical_error_vs_p(p_list, shots_per_point=200, state=(0.0, 0.0)):
    """
    This is a high-level host driver:
    - for each p (global physical error strength) apply a simple stochastic Pauli
      injection strategy across the encoding circuit and measure logical failure.
    NOTE: This function is a simple demo and uses a toy noise model (random Pauli insertion).
    For rigorous results use the Cirq/Gemini noise pipeline already available.
    """
    emu = StackMemorySimulator()

    def sample_logical_failure(p):
        failures = 0
        for _ in range(shots_per_point):
            # For speed, reuse the logical_X_roundtrip kernel (noisy behavior must be inserted
            # via a proper noise model; here we illustrate a very small-scale toy approach)
            # We simply call the noiseless kernel and then randomly flip the decoded bit with
            # probability ~ p to mimic physical errors — **toy only**.
            res = list(emu.task(logical_X_roundtrip, args=state).batch_run(shots=1))[0]
            # res is measured bits — coarse heuristic to determine logical flip
            # If decoded physical qubit (index 6) is 1 -> treat as logical flip
            # For the toy model, flip it randomly with probability p
            import random
            if random.random() < p:
                failures += 1
        return failures / shots_per_point

    results = []
    for p in p_list:
        print(f"Sampling p={p}")
        rate = sample_logical_failure(p)
        results.append(rate)

    plt.figure()
    plt.loglog(p_list, results, marker='o')
    plt.xlabel("physical error rate p")
    plt.ylabel("logical error rate")
    plt.title("Toy sweep: logical error vs physical error")
    plt.grid(True)
    plt.show()
    return p_list, results
