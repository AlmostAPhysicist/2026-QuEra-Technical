# The Ducklings — QuEra iQuHACK 2026 Submission

This submission demonstrates an MSD injection encoder and a Steane-style syndrome extraction + classical decoding for the [[7,1,3]] color code.

## Structure
team_solutions/The_Ducklings/
├── run_demo.py # entry point (judges call this)
├── README.md
├── slides_notes.txt
└── qec/
├── init.py
├── states.py
├── encoding.py
├── logical_ops.py
├── errors.py
├── syndrome.py
├── error_mapping.py
├── correction.py
└── experiments.py


## How to run (judges)
1. Create and activate environment per repo instructions (uv sync).
2. From repo root:
```bash
python team_solutions/The_Ducklings/run_demo.py
You should see the QEC run with baseline syndromes, injected error, detected/corrected error, and verification.

Notes
The simulation uses bloqade.pyqrack.StackMemorySimulator for noiseless execution and the bloqade.cirq_utils + bloqade.stim pipeline for heuristic noisy circuits.

For large Clifford-only workloads, use Stim or Tsim via the Cirq export pipeline.

We do post-selection, noise sweeps and plotting in qec/experiments.py (toy demo + guidance).


---

### 12) `team_solutions/The_Ducklings/documentation.md` — explanation & background
```markdown
# Documentation — The Ducklings

## Overview (short)
This project implements a working logical-qubit pipeline for the [[7,1,3]] color code (MSD injection encoding + Steane-style syndrome extraction and classical decoding). It is written using the :contentReference[oaicite:7]{index=7} SDK and can be simulated noiselessly using the `pyqrack` backend and, for noisy experiments, via an export-to-Cirq -> heuristic-noise -> Stim/Tsim sampling pipeline.

## Quick conceptual primer

### Qubits and noise
Physical qubits are fragile: they suffer from *coherence loss* (dephasing), *spontaneous decay* (amplitude damping), and gate errors (imperfect rotations, two-qubit entangling errors). Practically these errors manifest as stochastic Pauli faults (X, Y, Z) after a quantum circuit or as continuous channels.

### Classical redundancy vs quantum no-cloning
Classically, to protect a bit you can copy it many times (e.g., triple-modular redundancy). In quantum mechanics **you cannot clone an unknown quantum state** (no-cloning theorem). So quantum error correction (QEC) must **spread logical information non-trivially across multiple physical qubits** so that measuring certain observables gives error information without collapsing the logical state.

### Stabilizer codes and the [[7,1,3]] color code
Stabilizer QEC uses commuting Pauli operators (stabilizers) which all have +1 eigenvalue on the codespace. Measuring stabilizers gives a syndrome that tells you where a small number of local errors occurred, without fully measuring (collapsing) the logical information.

The [[7,1,3]] color code:
- Encodes 1 logical qubit into 7 physical qubits.
- Distance 3 means it can correct any single-qubit Pauli error.
- Its stabilizers are color-based (red/green/blue faces). In our code:
  - RED support: qubits [2,3,4,6]
  - GREEN support: qubits [1,2,4,5]
  - BLUE support: qubits [0,1,2,3]

### Steane-style syndrome extraction (high level)
Steane-style QEC extracts X- and Z-syndromes by preparing *logical probe states* and coupling them transversally to the data block:
- X-syndrome: prepare probe in |+_L>, apply CNOTs data → probe, measure probe in Z.
- Z-syndrome: prepare probe in |0_L>, apply CNOTs probe → data, measure probe in X.
Because operations are transversal at the logical level, this preserves locality and is fault-tolerant in a natural way.

### This project's pipeline
1. **Prepare** a physical Bloch-state on a target qubit (Rz, Rx).
2. **Encode** with the MSD injection circuit (`encode_713_block`).
3. **Extract syndromes** with logical probes (Steane procedure).
4. **Decode** classically: compute parity changes and map them using the syndrome table to a qubit index.
5. **Apply correction** (Pauli) and verify via re-measurement.

## Files & responsibilities
- `encoding.py` — MSD encoder + decoder + logical preparation kernel.
- `syndrome.py` — probe preparation kernels and syndrome extraction kernels.
- `error_mapping.py` — stabilizer definitions, parity, classical decoder mapping.
- `correction.py` — host-side pipeline `run_full_QEC` (simulate, decode, correct).
- `experiments.py` — sampling helpers, toy sweeps and plotting hooks.
- `run_demo.py` — judges entrypoint.

## How to extend
- Replace the toy noise in `experiments.sweep_logical_error_vs_p` with the Cirq -> Gemini noise model pipeline (used in `experiments.run_with_noise`).
- Add multi-round syndrome extraction by repeating the probe kernels and using majority / MWPM or a custom decoder.
- Implement a flagged encoding or an alternate injection that reduces logical faults during encoding.

## References & tooling
- Use :contentReference[oaicite:8]{index=8} or :contentReference[oaicite:9]{index=9} for fast Clifford/stabilizer simulation.
- Primary SDK: :contentReference[oaicite:10]{index=10}
- Challenge: :contentReference[oaicite:11]{index=11}
- Company: :contentReference[oaicite:12]{index=12}
