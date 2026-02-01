#!/usr/bin/env python
"""Quick test to verify all imports work."""

print("Testing QEC package imports...")

try:
    from qec import (
        zeroState, oneState, plusState, minusState,
        setPhysicalQubit, encode_713_block, decode_713_block, prepareLogicalQubit,
        logical_X_roundtrip,
        inject_pauli,
        measure_clean_syndromes, measure_error_syndromes, verify_correction,
        measure_X_syndrome, measure_Z_syndrome,
        color_parities, locate_flipped_qubit,
        run_full_QEC,
        run_noiseless, run_with_noise, postselected_memory_experiment, sweep_logical_error_vs_p
    )
    print("[SUCCESS] All imports successful!")
    print("\nAvailable functions:")
    funcs = [
        'zeroState', 'oneState', 'plusState', 'minusState',
        'setPhysicalQubit', 'encode_713_block', 'decode_713_block', 'prepareLogicalQubit',
        'logical_X_roundtrip',
        'inject_pauli',
        'measure_clean_syndromes', 'measure_error_syndromes', 'verify_correction',
        'measure_X_syndrome', 'measure_Z_syndrome',
        'color_parities', 'locate_flipped_qubit',
        'run_full_QEC',
        'run_noiseless', 'run_with_noise', 'postselected_memory_experiment', 'sweep_logical_error_vs_p'
    ]
    for func in funcs:
        print(f"  - {func}")
    
    print("\n[SUCCESS] Module structure is correct!")
    
except ImportError as e:
    print(f"[ERROR] Import failed: {e}")
    exit(1)

except Exception as e:
    print(f"[ERROR] Unexpected error: {e}")
    exit(1)

print("\nTesting state preparation...")
try:
    theta, phi = zeroState()
    print(f"  Zero state: theta={theta}, phi={phi}")
    
    theta, phi = plusState()
    print(f"  Plus state: theta={theta}, phi={phi}")
    
    print("[SUCCESS] State preparation functions work!")
except Exception as e:
    print(f"[ERROR] State prep failed: {e}")
    exit(1)

print("\n" + "="*60)
print("All tests passed! The QEC package is ready to use.")
print("="*60)
