from bloqade.pyqrack import StackMemorySimulator
from .syndrome import measure_clean_syndromes, measure_error_syndromes, verify_correction
from .error_mapping import color_parities, locate_flipped_qubit

emu = StackMemorySimulator()

def run_full_QEC(theta: float, phi: float,
                 err_index: int, err_basis: int):
    """
    Host-side pipeline:
      1) baseline syndromes
      2) inject error and measure syndromes
      3) classical decode to get location+type
      4) apply correction and verify
    """
    print("\n======================================")
    print("Injected error:", ["X", "Y", "Z"][err_basis], "on qubit", err_index)
    print("======================================")

    baseX, baseZ = list(emu.task(measure_clean_syndromes,
                                 args=(theta, phi)).batch_run(shots=1))[0]

    synX0 = color_parities([int(b) for b in baseX])
    synZ0 = color_parities([int(b) for b in baseZ])

    print("Baseline X syndrome:", synX0)
    print("Baseline Z syndrome:", synZ0)

    measX, measZ = list(emu.task(measure_error_syndromes,
                                 args=(theta, phi, err_index, err_basis)).batch_run(shots=1))[0]

    synX1 = color_parities([int(b) for b in measX])
    synZ1 = color_parities([int(b) for b in measZ])

    x_guess = locate_flipped_qubit(synX0, synX1)
    z_guess = locate_flipped_qubit(synZ0, synZ1)

    print("\nAfter error injection:")
    print("X syndrome:", synX1)
    print("Z syndrome:", synZ1)

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
        return

    corr_basis = {"X": 0, "Y": 1, "Z": 2}[etype]

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

    if synX2 == synX0 and synZ2 == synZ0:
        print("\n✅ Correction successful.")
    else:
        print("\n❌ Correction failed.")
