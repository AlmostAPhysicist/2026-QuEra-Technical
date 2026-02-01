"""
Test QEC with fully random quantum states
Compares theoretical vs actual Z-basis measurement probabilities

For any state |ψ⟩ = cos(θ/2)|0⟩ + e^(iφ)sin(θ/2)|1⟩:
    P(measure 0) = cos²(θ/2)
    P(measure 1) = sin²(θ/2)
"""

from bloqade import squin
from bloqade.pyqrack import StackMemorySimulator
import numpy as np
from qec.encoding import prepareLogicalQubit, encode_713_block, decode_713_block
from qec.error_mapping import color_parities, locate_flipped_qubit


emu = StackMemorySimulator()


def theoretical_prob_zero(theta):
    """Calculate theoretical probability of measuring |0⟩"""
    return np.cos(theta/2)**2


# ============================================================
# Kernels
# ============================================================

@squin.kernel
def baseline_trial(theta: float, phi: float, 
                   err_index: int, err_basis: int):
    """Measure without QEC - encode, inject error, decode, measure"""
    data = prepareLogicalQubit(theta, phi)
    encode_713_block(data)
    
    # Inject error
    if err_basis >= 0:  # -1 means no error
        if err_basis == 0:
            squin.x(data[err_index])
        elif err_basis == 1:
            squin.y(data[err_index])
        elif err_basis == 2:
            squin.z(data[err_index])
    
    decode_713_block(data)
    return squin.broadcast.measure(data)


@squin.kernel
def corrected_trial(theta: float, phi: float,
                   err_index: int, err_basis: int):
    """Full QEC: measure syndromes, inject error, correct, decode, measure"""
    data = prepareLogicalQubit(theta, phi)
    encode_713_block(data)
    
    # ---- Measure clean X syndrome ----
    probeX_clean = prepareLogicalQubit(0.0, np.pi/2)
    for j in range(7):
        squin.cx(data[j], probeX_clean[j])
    measX_clean = squin.broadcast.measure(probeX_clean)
    
    # ---- Measure clean Z syndrome ----
    probeZ_clean = prepareLogicalQubit(0.0, 0.0)
    for j in range(7):
        squin.cx(probeZ_clean[j], data[j])
    for j in range(7):
        squin.h(probeZ_clean[j])
    measZ_clean = squin.broadcast.measure(probeZ_clean)
    
    # ---- Inject error ----
    if err_basis >= 0:
        if err_basis == 0:
            squin.x(data[err_index])
        elif err_basis == 1:
            squin.y(data[err_index])
        elif err_basis == 2:
            squin.z(data[err_index])
    
    # ---- Measure error X syndrome ----
    probeX_err = prepareLogicalQubit(0.0, np.pi/2)
    for j in range(7):
        squin.cx(data[j], probeX_err[j])
    measX_err = squin.broadcast.measure(probeX_err)
    
    # ---- Measure error Z syndrome ----
    probeZ_err = prepareLogicalQubit(0.0, 0.0)
    for j in range(7):
        squin.cx(probeZ_err[j], data[j])
    for j in range(7):
        squin.h(probeZ_err[j])
    measZ_err = squin.broadcast.measure(probeZ_err)
    
    decode_713_block(data)
    
    # Return: data measurement + clean syndromes + error syndromes
    return squin.broadcast.measure(data) + measX_clean + measZ_clean + measX_err + measZ_err


def run_benchmark(theta, phi, p1, shots=1000):
    """Run benchmark for a specific random state"""
    print(f"\n{'='*70}")
    print(f"Testing random state: θ={theta:.4f}, φ={phi:.4f}")
    print(f"Theoretical P(|0⟩) = {theoretical_prob_zero(theta):.4f}")
    print(f"Physical error rate p1 = {p1}")
    print(f"{'='*70}")
    
    # Sample error events for each shot
    error_samples = []
    for _ in range(shots):
        if np.random.random() < p1:
            err_idx = np.random.randint(0, 7)
            err_basis = np.random.randint(0, 3)
        else:
            err_idx = 0
            err_basis = -1  # No error
        error_samples.append((err_idx, err_basis))
    
    # ---- Baseline: no error correction ----
    print("\nRunning baseline (no QEC)...")
    baseline_zeros = 0
    for err_idx, err_basis in error_samples:
        results = list(emu.task(baseline_trial, args=(theta, phi, err_idx, err_basis)).batch_run(shots=1))[0]
        if int(results[0]) == 0:
            baseline_zeros += 1
    
    baseline_prob_zero = baseline_zeros / shots
    
    # ---- Corrected: full QEC ----
    print("Running corrected (with QEC)...")
    corrected_zeros = 0
    corrections_applied = 0
    
    for err_idx, err_basis in error_samples:
        results = list(emu.task(corrected_trial, args=(theta, phi, err_idx, err_basis)).batch_run(shots=1))[0]
        
        measurement = int(results[0])
        
        # Extract syndromes (7 data qubits per probe)
        measX_clean = [int(results[i]) for i in range(1, 8)]
        measZ_clean = [int(results[i]) for i in range(8, 15)]
        measX_err = [int(results[i]) for i in range(15, 22)]
        measZ_err = [int(results[i]) for i in range(22, 29)]
        
        synX_clean = color_parities(measX_clean)
        synZ_clean = color_parities(measZ_clean)
        synX_err = color_parities(measX_err)
        synZ_err = color_parities(measZ_err)
        
        # Determine correction needed
        x_flip = locate_flipped_qubit(synX_clean, synX_err)
        z_flip = locate_flipped_qubit(synZ_clean, synZ_err)
        
        # Apply correction to measurement outcome if logical qubit flipped
        if x_flip == 0 or z_flip == 0:
            corrections_applied += 1
            measurement ^= 1
        
        if measurement == 0:
            corrected_zeros += 1
    
    corrected_prob_zero = corrected_zeros / shots
    
    # Calculate fidelities
    theoretical = theoretical_prob_zero(theta)
    baseline_fidelity = 1.0 - abs(baseline_prob_zero - theoretical)
    corrected_fidelity = 1.0 - abs(corrected_prob_zero - theoretical)
    
    print(f"\nResults:")
    print(f"  Theoretical P(|0⟩)  = {theoretical:.4f}")
    print(f"  Baseline P(|0⟩)     = {baseline_prob_zero:.4f}  (fidelity: {baseline_fidelity:.4f})")
    print(f"  Corrected P(|0⟩)    = {corrected_prob_zero:.4f}  (fidelity: {corrected_fidelity:.4f})")
    print(f"  Corrections applied = {corrections_applied}/{shots}")
    
    return baseline_fidelity, corrected_fidelity


if __name__ == "__main__":
    # Test with multiple random states
    print("\n" + "="*70)
    print("RANDOM STATE QEC BENCHMARK")
    print("="*70)
    
    np.random.seed(42)  # For reproducibility
    
    # Test 1: Random state at low noise
    theta1 = np.random.uniform(0, np.pi)
    phi1 = np.random.uniform(0, 2*np.pi)
    run_benchmark(theta1, phi1, p1=0.0, shots=1000)
    
    # Test 2: Same state at medium noise
    run_benchmark(theta1, phi1, p1=0.1, shots=1000)
    
    # Test 3: Different random state
    theta2 = np.random.uniform(0, np.pi)
    phi2 = np.random.uniform(0, 2*np.pi)
    run_benchmark(theta2, phi2, p1=0.1, shots=1000)
    
    # Test 4: High noise
    run_benchmark(theta2, phi2, p1=0.3, shots=1000)
    
    print("\n" + "="*70)
    print("DONE")
    print("="*70)
