# The Ducklings QEC Implementation - Complete Guide

## ✅ Status

All code is **working and complete**. The demo runs successfully:

```
(iquhack) PS ...> python run_demo.py

=== The Ducklings: Steane QEC demo ===

======================================
Injected error: Y on qubit 4
======================================
Baseline X syndrome: (1, 1, 1)
Baseline Z syndrome: (1, 1, -1)

After error injection:
X syndrome: (-1, -1, 1)
Z syndrome: (-1, -1, -1)

Detected error: Y on qubit 4

After correction:
X syndrome: (1, 1, 1)
Z syndrome: (1, 1, -1)

[SUCCESS] Correction successful.
```

---

## 📁 File Structure

```
The_Ducklings/
├── qec/                          # Main QEC package
│   ├── __init__.py               # Package interface + docstring
│   ├── states.py                 # Bloch angle helpers
│   ├── encoding.py               # MSD injection circuit
│   ├── errors.py                 # Pauli error injection
│   ├── error_mapping.py          # Stabilizer definitions + classical decoder
│   ├── syndrome.py               # Quantum syndrome measurement kernels
│   ├── logical_ops.py            # Logical gate experiments
│   ├── correction.py             # Full QEC pipeline orchestration
│   └── experiments.py            # Experiment runners
│
├── run_demo.py                   # Main demonstration script
├── qec_quickstart.py             # Quick start guide with 6 examples
├── slides_notes.txt              # Comprehensive technical documentation
├── IMPLEMENTATION_SUMMARY.md     # Summary of changes and additions
└── README.md                     # Original project README
```

---

## 🔑 Key Components

### 1. **Quantum Kernels** (squin decorators)

| Function | Purpose | Input | Output |
|----------|---------|-------|--------|
| `prepareLogicalQubit(θ, φ)` | Create 7-qubit encoded state | Bloch angles | 7-qubit register |
| `encode_713_block(reg)` | Apply 8-layer MSD circuit | 7-qubit register | Encoded state |
| `decode_713_block(reg)` | Reverse encoding | 7-qubit register | Original state |
| `measure_clean_syndromes(θ, φ)` | Baseline syndrome measurement | Bloch angles | (X_syndrome, Z_syndrome) |
| `measure_error_syndromes(θ, φ, idx, basis)` | Syndrome with injected error | Parameters + error spec | (X_syndrome, Z_syndrome) |
| `verify_correction(θ, φ, e_idx, e_basis, c_idx, c_basis)` | Inject, correct, remeasure | Parameters + error + correction | (X_syndrome, Z_syndrome) |

### 2. **Classical Functions** (Python)

| Function | Purpose | Input | Output |
|----------|---------|-------|--------|
| `zeroState()`, `oneState()`, etc. | Bloch angles for standard states | None | (θ, φ) tuple |
| `color_parities(bits)` | Extract stabilizer parities | Measurement bitstring | (R, G, B) tuple |
| `locate_flipped_qubit(old, new)` | Identify error from syndrome change | Two syndrome tuples | Qubit index |
| `run_full_QEC(θ, φ, idx, basis)` | Complete 7-step pipeline | Parameters + error spec | Prints results |

### 3. **Data Structures**

```python
# Stabilizer Supports (which qubits each stabilizer checks)
RED   = [2, 3, 4, 6]
GREEN = [1, 2, 4, 5]
BLUE  = [0, 1, 2, 3]

# Syndrome Decoding Table (syndrome flip pattern → error location)
SYNDROME_TABLE = {
    (0, 0, 0): -1,  # no error
    (0, 0, 1): 0,
    (0, 1, 1): 1,
    (1, 1, 1): 2,
    (1, 0, 1): 3,
    (1, 1, 0): 4,
    (0, 1, 0): 5,
    (1, 0, 0): 6,
}
```

---

## 🎓 Understanding the Pipeline

### The 7-Step QEC Workflow

```
Step 1: ENCODING
   |ψ⟩ ──[encode_713_block]──> |ψ_L⟩

Step 2: BASELINE SYNDROME
   |ψ_L⟩ ──[measure_clean_syndromes]──> (synX₀, synZ₀)

Step 3: ERROR INJECTION
   |ψ_L⟩ ──[inject_pauli]──> |ψ_L, error⟩

Step 4: ERROR SYNDROME
   |ψ_L, error⟩ ──[measure_error_syndromes]──> (synX₁, synZ₁)

Step 5: CLASSICAL DECODE
   Syndrome flip = synX₁ XOR synX₀ → identify qubit & error type

Step 6: CORRECTION
   |ψ_L, error⟩ ──[apply correction Pauli]──> |ψ_L⟩

Step 7: VERIFICATION
   Corrected state ──[measure syndromes]──> (synX₂, synZ₂)
   Check: (synX₂, synZ₂) == (synX₀, synZ₀) ?
```

### Why It Works

- **Non-locality**: Each physical qubit error affects multiple stabilizer parities
- **Unique signatures**: Each error produces a unique syndrome flip pattern
- **Non-demolition**: Probes extract error info without measuring data qubits
- **Classical detection**: Lookup table instantly identifies error
- **Reversibility**: Applying opposite Pauli cancels the error

---

## 📚 Documentation

### Main Resources

1. **`slides_notes.txt`** (comprehensive)
   - Why QEC is needed (no-cloning + decoherence)
   - [[7,1,3]] color code geometry
   - Steane syndrome extraction details
   - MSD circuit structure
   - Module-by-module explanation
   - Quick reference tables

2. **`qec_quickstart.py`** (hands-on)
   - 6 runnable examples
   - Demonstrates each concept
   - Can run individually or all together

3. **`IMPLEMENTATION_SUMMARY.md`** (overview)
   - Files modified/added
   - Key fix (missing measure_error_syndromes)
   - Available functions
   - Verification results

4. **Module docstrings**
   - Each .py file has comprehensive docstring
   - `qec/__init__.py` has full package documentation
   - Functions have inline comments

---

## 🚀 Usage Examples

### Basic QEC Test
```python
from qec import zeroState, run_full_QEC

theta, phi = zeroState()
run_full_QEC(theta, phi, err_index=4, err_basis=1)  # Y error on qubit 4
```

### Test All Errors
```python
from qec import zeroState, run_full_QEC

theta, phi = zeroState()

for qubit in range(7):
    for error_type in range(3):  # X, Y, Z
        run_full_QEC(theta, phi, err_index=qubit, err_basis=error_type)
```

### Logical Operation
```python
from qec import plusState, logical_X_roundtrip
from bloqade.pyqrack import StackMemorySimulator

theta, phi = plusState()

emu = StackMemorySimulator()
task = emu.task(logical_X_roundtrip, args=(theta, phi))
results = task.batch_run(shots=100)
print(results)
```

### Manual Syndrome Inspection
```python
from qec import zeroState, measure_clean_syndromes, color_parities
from bloqade.pyqrack import StackMemorySimulator

theta, phi = zeroState()
emu = StackMemorySimulator()

measX, measZ = list(
    emu.task(measure_clean_syndromes, args=(theta, phi)).batch_run(shots=1)
)[0]

synX = color_parities([int(b) for b in measX])
synZ = color_parities([int(b) for b in measZ])

print(f"X syndrome: {synX}")
print(f"Z syndrome: {synZ}")
```

---

## 🔧 Key Fix

### Problem
`ImportError: cannot import name 'measure_error_syndromes' from 'qec.syndrome'`

The function was called in `qec/correction.py` and imported in `qec/__init__.py` but was missing from `qec/syndrome.py`.

### Solution
Added the complete function:
```python
@squin.kernel
def measure_error_syndromes(theta: float, phi: float,
                            err_index: int, err_basis: int):
    data = prepareLogicalQubit(theta, phi)
    inject_pauli(data, err_index, err_basis)
    
    # Measure X and Z syndromes
    probeX = prepareLogicalQubit(0.0, 3.1415926535 / 2)
    for j in range(7):
        squin.cx(data[j], probeX[j])
    measX = squin.broadcast.measure(probeX)
    
    probeZ = prepareLogicalQubit(0.0, 0.0)
    for j in range(7):
        squin.cx(probeZ[j], data[j])
    for j in range(7):
        squin.h(probeZ[j])
    measZ = squin.broadcast.measure(probeZ)
    
    return measX, measZ
```

---

## 📊 Code Quality

✅ **Modular**: Each file has single responsibility
✅ **Documented**: Comprehensive docstrings and comments
✅ **Tested**: Demo runs without errors
✅ **Extensible**: Clear patterns for new experiments
✅ **Pedagogical**: Code mirrors theory presentation
✅ **Working**: All imports and functions operational

---

## 🎯 Next Steps

### Short Term
- ✅ Run all 7 qubit × 3 error tests
- ✅ Test different initial states
- ✅ Verify syndrome table correctness

### Medium Term
- [ ] Multiple rounds of syndrome extraction
- [ ] Post-selection based on syndrome outcomes
- [ ] Characterize logical error vs physical error
- [ ] Integrate Gemini noise model

### Long Term
- [ ] Distance 5 [[25,1,5]] code
- [ ] Distance 7 [[49,1,7]] code
- [ ] Feedforward corrections
- [ ] T-state memory via Tsim
- [ ] Real hardware deployment

---

## 💡 Theory Summary

### The [[7,1,3]] Color Code

**Encodes**: 1 logical qubit into 7 physical qubits
**Corrects**: All single-qubit Pauli errors (X, Y, Z)
**Uses**: 3 stabilizers (RED, GREEN, BLUE) based on 2D checkerboard geometry

### Steane Syndrome Extraction

**Principle**: Use auxiliary qubits to measure error syndromes without disturbing data

**X-syndrome probe**: |+_L⟩ eigenstate → CNOT(data→probe) → measure probe
**Z-syndrome probe**: |0_L⟩ eigenstate → CNOT(probe→data) → measure probe

**Advantage**: Non-demolition measurement. Data qubits undisturbed, reusable.

### Classical Decoding

Each single-qubit error produces unique syndrome flip pattern:
- X error: only X syndrome flips
- Z error: only Z syndrome flips  
- Y error: both X and Z syndromes flip
- No error: neither syndrome flips

Lookup table maps (flip₁, flip₂, flip₃) → qubit index (0-6) or -1 (no error)

### Error Correction

Apply opposite Pauli to cancel error:
- If detected X on qubit i: apply X(qubit i)
- If detected Y on qubit i: apply Y(qubit i)
- If detected Z on qubit i: apply Z(qubit i)

---

## 📞 Contact & Attribution

**Team**: The Ducklings
**Event**: QuEra iQuHACK 2026
**Code Base**: Bloqade quantum programming framework
**Hardware**: QuEra Neutral-Atom quantum platform

---

## ✨ Success Metrics

- ✅ Code imports without errors
- ✅ Demo runs successfully
- ✅ All single-error corrections verified
- ✅ Comprehensive documentation provided
- ✅ Modular and extensible design
- ✅ Clear pedagogical path

**Status**: COMPLETE AND READY FOR USE 🎉
