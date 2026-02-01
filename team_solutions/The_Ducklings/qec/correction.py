from bloqade.pyqrack import StackMemorySimulator
from bloqade.cirq_utils import emit_circuit
from .syndrome import measure_clean_syndromes, measure_error_syndromes, verify_correction, apply_cirq_noise_to_kernel
from .error_mapping import color_parities, locate_flipped_qubit

emu = StackMemorySimulator()

def run_full_QEC(theta: float, phi: float,
                 err_index: int, err_basis: int,
                 noise_scaling: float = 0.0,
                 verbose: bool = True):
    """
    Host-side pipeline:
      1) baseline syndromes
      2) inject error and measure syndromes
      3) classical decode to get location+type
      4) apply correction and verify
    
    Returns:
        (success, circuit): success is bool, circuit is the Cirq circuit used for error syndrome measurement
      
    Args:
        noise_scaling: GeminiOneZoneNoiseModel scaling factor (0 = noiseless)
        verbose: Print detailed syndrome info (default True)
    """
    
    print("\n======================================")
    print("Injected error:", ["X", "Y", "Z"][err_basis], "on qubit", err_index)
    print("======================================")
    
    # Emit the circuit for visualization
    circuit = emit_circuit(measure_error_syndromes,
                          args=(theta, phi, err_index, err_basis),
                          ignore_returns=True)
    
    # --------------------------------------------------------
    # Step 1: Baseline syndrome measurement
    # --------------------------------------------------------
    
    baseX, baseZ = list(emu.task(measure_clean_syndromes,
                                 args=(theta, phi)).batch_run(shots=1))[0]

    synX0 = color_parities([int(b) for b in baseX])
    synZ0 = color_parities([int(b) for b in baseZ])

    print("Baseline X syndrome:", synX0)
    print("Baseline Z syndrome:", synZ0)

    # --------------------------------------------------------
    # Step 2: Syndrome after injected error
    # --------------------------------------------------------

    # Use noisy or noiseless syndrome measurement
    if noise_scaling > 0:
        noisy_measure = apply_cirq_noise_to_kernel(measure_error_syndromes, noise_scaling)
        measX, measZ = list(emu.task(noisy_measure,
                                     args=(theta, phi, err_index, err_basis)).batch_run(shots=1))[0]
    else:
        measX, measZ = list(emu.task(measure_error_syndromes,
                                     args=(theta, phi, err_index, err_basis)).batch_run(shots=1))[0]

    synX1 = color_parities([int(b) for b in measX])
    synZ1 = color_parities([int(b) for b in measZ])

    x_guess = locate_flipped_qubit(synX0, synX1)
    z_guess = locate_flipped_qubit(synZ0, synZ1)

    print("\nAfter error injection:")
    print("X syndrome:", synX1)
    print("Z syndrome:", synZ1)

    # --------------------------------------------------------
    # Step 3: Classify Pauli type
    # --------------------------------------------------------

    # classify Pauli
    if x_guess != -1 and z_guess != -1:
        etype, qloc = "Y", x_guess
    elif x_guess != -1:
        etype, qloc = "X", x_guess
    elif z_guess != -1:
        etype, qloc = "Z", z_guess
    else:
        etype, qloc = "None", -1

    print("\nDetected error:", etype, "on qubit", qloc)

    if etype == "None":
        print("No correction needed.")
        return True

    corr_basis = {"X": 0, "Y": 1, "Z": 2}[etype]

    # --------------------------------------------------------
    # Step 4: Verify correction restores baseline
    # --------------------------------------------------------

    # Use noisy or noiseless verification
    if noise_scaling > 0:
        noisy_verify = apply_cirq_noise_to_kernel(verify_correction, noise_scaling)
        measX2, measZ2 = list(emu.task(
            noisy_verify,
            args=(theta, phi,
                  err_index, err_basis,
                  qloc, corr_basis)
        ).batch_run(shots=1))[0]
    else:
        measX2, measZ2 = list(emu.task(
            verify_correction,
            args=(theta, phi,
                  err_index, err_basis,
                  qloc, corr_basis)
        ).batch_run(shots=1))[0]

    synX2 = color_parities([int(b) for b in measX2])
    synZ2 = color_parities([int(b) for b in measZ2])

    print("\nAfter correction:")
    print("X syndrome:", synX2)
    print("Z syndrome:", synZ2)

    success = (synX2 == synX0 and synZ2 == synZ0)
    
    if success:
        print("\n✅ Correction successful.")
    else:
        print("\n❌ Correction failed.")
    
    return success, circuit 

