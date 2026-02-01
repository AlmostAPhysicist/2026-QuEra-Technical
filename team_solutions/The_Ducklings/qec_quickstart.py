#!/usr/bin/env python3
"""
Quick Start Guide for QEC Package
==================================

This file demonstrates the main ways to use the QEC package.
Run any of these examples to explore quantum error correction.
"""

# ==============================================================================
# EXAMPLE 1: Basic Error Correction Test
# ==============================================================================
# Shows the complete QEC workflow for a single injected error

def example_basic_qec():
    """Run full QEC pipeline: encode → inject error → measure → correct → verify"""
    from qec import zeroState, run_full_QEC
    
    # Prepare logical |0⟩
    theta, phi = zeroState()
    
    # Inject Y error on qubit 4 and demonstrate correction
    run_full_QEC(theta, phi, err_index=4, err_basis=1)
    
    # Expected output:
    # - Baseline syndromes (reference)
    # - Syndromes with error (changed)
    # - Detected error: Y on qubit 4
    # - Syndromes after correction (back to baseline)
    # - [SUCCESS] Correction successful


# ==============================================================================
# EXAMPLE 2: Test All Single-Qubit Errors
# ==============================================================================
# Systematically test error detection and correction

def example_sweep_all_errors():
    """Test correction on all 7 qubits and all 3 error types"""
    from qec import zeroState, run_full_QEC
    
    theta, phi = zeroState()
    
    error_names = ['X', 'Y', 'Z']
    
    print("\n" + "="*60)
    print("Testing all single-qubit errors on [[7,1,3]] code")
    print("="*60)
    
    for qubit in range(7):
        for error_basis in range(3):
            print(f"\nTesting {error_names[error_basis]} error on qubit {qubit}:")
            run_full_QEC(theta, phi, err_index=qubit, err_basis=error_basis)


# ==============================================================================
# EXAMPLE 3: Test Different Initial States
# ==============================================================================
# Verify QEC works for different logical states

def example_different_states():
    """Test QEC with different initial quantum states"""
    from qec import zeroState, oneState, plusState, minusState
    from qec import run_full_QEC
    
    states = [
        ("Zero", zeroState()),
        ("One", oneState()),
        ("Plus", plusState()),
        ("Minus", minusState()),
    ]
    
    print("\n" + "="*60)
    print("Testing QEC with different initial states")
    print("="*60)
    
    for name, (theta, phi) in states:
        print(f"\n--- Initial state: |{name}⟩ ---")
        run_full_QEC(theta, phi, err_index=2, err_basis=2)  # Z error on qubit 2


# ==============================================================================
# EXAMPLE 4: Logical X Gate Demonstration
# ==============================================================================
# Show that encoding preserves quantum information through a logical gate

def example_logical_operation():
    """Encode → apply logical X → decode → measure"""
    from qec import plusState, logical_X_roundtrip
    from bloqade.pyqrack import StackMemorySimulator
    
    print("\n" + "="*60)
    print("Logical X gate roundtrip: |+⟩ → X|+⟩ = |-⟩")
    print("="*60)
    
    theta, phi = plusState()
    
    emu = StackMemorySimulator()
    task = emu.task(logical_X_roundtrip, args=(theta, phi))
    results = task.batch_run(shots=10)
    
    print("\nMeasurement results after logical X:")
    print(results)
    print("\nNote: Due to X gate, most qubits should measure |1⟩ (flipped from |+⟩)")


# ==============================================================================
# EXAMPLE 5: Understanding Syndrome Changes
# ==============================================================================
# Detailed breakdown of how syndromes reveal error location

def example_understand_syndromes():
    """Manually step through syndrome measurement and interpretation"""
    from qec import zeroState, measure_clean_syndromes, measure_error_syndromes
    from qec import color_parities, locate_flipped_qubit
    from bloqade.pyqrack import StackMemorySimulator
    
    print("\n" + "="*60)
    print("Understanding Syndrome Extraction")
    print("="*60)
    
    theta, phi = zeroState()
    emu = StackMemorySimulator()
    
    # Step 1: Baseline
    print("\nStep 1: BASELINE (no error injected)")
    measX_base, measZ_base = list(
        emu.task(measure_clean_syndromes, args=(theta, phi)).batch_run(shots=1)
    )[0]
    
    synX_base = color_parities([int(b) for b in measX_base])
    synZ_base = color_parities([int(b) for b in measZ_base])
    
    print(f"  X probe measurement: {measX_base}")
    print(f"  Z probe measurement: {measZ_base}")
    print(f"  X syndrome (R,G,B): {synX_base}")
    print(f"  Z syndrome (R,G,B): {synZ_base}")
    
    # Step 2: With error
    print("\nStep 2: WITH ERROR (X error on qubit 3)")
    measX_err, measZ_err = list(
        emu.task(measure_error_syndromes, args=(theta, phi, 3, 0)).batch_run(shots=1)
    )[0]
    
    synX_err = color_parities([int(b) for b in measX_err])
    synZ_err = color_parities([int(b) for b in measZ_err])
    
    print(f"  X probe measurement: {measX_err}")
    print(f"  Z probe measurement: {measZ_err}")
    print(f"  X syndrome (R,G,B): {synX_err}")
    print(f"  Z syndrome (R,G,B): {synZ_err}")
    
    # Step 3: Classical decoding
    print("\nStep 3: CLASSICAL DECODING")
    x_qubit = locate_flipped_qubit(synX_base, synX_err)
    z_qubit = locate_flipped_qubit(synZ_base, synZ_err)
    
    print(f"  X syndrome changed → qubit {x_qubit}")
    print(f"  Z syndrome changed → qubit {z_qubit}")
    
    if x_qubit == 3 and z_qubit == -1:
        print("  Diagnosis: X error on qubit 3 ✓ CORRECT")
    else:
        print("  Diagnosis: Unexpected error pattern")


# ==============================================================================
# EXAMPLE 6: Module Overview
# ==============================================================================
# Show what's available in the package

def example_module_overview():
    """List and describe all available functions"""
    import qec
    
    print("\n" + "="*60)
    print("QEC Package Overview")
    print("="*60)
    
    print("\nState Preparation (returns Bloch angles):")
    print("  zeroState() → |0⟩")
    print("  oneState() → |1⟩")
    print("  plusState() → |+⟩")
    print("  minusState() → |-⟩")
    
    print("\nEncoding (distribute info across 7 qubits):")
    print("  prepareLogicalQubit(theta, phi) → |ψ_L⟩")
    print("  encode_713_block(reg) → apply MSD circuit")
    print("  decode_713_block(reg) → recover original")
    
    print("\nSyndrome Measurement (extract error info without collapse):")
    print("  measure_clean_syndromes(theta, phi) → baseline syndromes")
    print("  measure_error_syndromes(theta, phi, idx, basis) → with error")
    print("  measure_X_syndrome(...) → X-stabilizer only")
    print("  measure_Z_syndrome(...) → Z-stabilizer only")
    
    print("\nClassical Decoding (identify error):")
    print("  color_parities(bits) → extract stabilizer parities")
    print("  locate_flipped_qubit(old_syn, new_syn) → error location")
    
    print("\nFull QEC Pipeline:")
    print("  run_full_QEC(theta, phi, err_idx, err_basis)")
    print("    1. Measure baseline syndromes")
    print("    2. Inject error")
    print("    3. Measure error syndromes")
    print("    4. Decode: infer error location + type")
    print("    5. Apply correction")
    print("    6. Verify by remeasuring")
    
    print("\nExperiments:")
    print("  run_noiseless(theta, phi, shots=200)")
    print("  run_with_noise(theta, phi, shots=200)")
    print("  postselected_memory_experiment(...)")
    print("  sweep_logical_error_vs_p(...)")


# ==============================================================================
# MAIN: Run Examples
# ==============================================================================

if __name__ == "__main__":
    import sys
    
    examples = {
        '1': ('Basic QEC Test', example_basic_qec),
        '2': ('Sweep All Errors', example_sweep_all_errors),
        '3': ('Different States', example_different_states),
        '4': ('Logical Operation', example_logical_operation),
        '5': ('Understand Syndromes', example_understand_syndromes),
        '6': ('Module Overview', example_module_overview),
    }
    
    print("\n" + "="*60)
    print("QEC Package - Quick Start Guide")
    print("="*60)
    print("\nAvailable examples:")
    for key, (name, _) in examples.items():
        print(f"  {key}: {name}")
    print("\nUsage: python qec_quickstart.py [1-6]")
    print("Or import and call examples directly:")
    print("  from qec_quickstart import example_basic_qec")
    print("  example_basic_qec()")
    print("="*60 + "\n")
    
    if len(sys.argv) > 1:
        choice = sys.argv[1]
        if choice in examples:
            name, func = examples[choice]
            print(f"Running: {name}\n")
            func()
        else:
            print(f"Invalid choice. Please use 1-6.")
    else:
        # Run example 1 by default
        print("Running Example 1 (Basic QEC Test)\n")
        example_basic_qec()
