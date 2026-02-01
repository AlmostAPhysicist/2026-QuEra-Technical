# iQuHACK 2026 - Team Solutions

## The Ducklings: Steane [[7,1,3]] Quantum Error Correction

**Team:** The Ducklings  
**GitHub Repository:** [iQuHACK/2026-QuEra-Technical](https://github.com/iQuHACK/2026-QuEra-Technical)

**Problem:** Quantum error correction for neutral atom quantum computers

**Solution Folder:** [`team_solutions/The_Ducklings/`](team_solutions/The_Ducklings/)

### Documentation

Full documentation, methods, and results available in:
- **[README.md](team_solutions/The_Ducklings/README.md)** — Complete technical writeup with theory, implementation, results, and references

### How to Run

#### Interactive Demonstration (Recommended)
```bash
cd team_solutions/The_Ducklings
jupyter notebook qec_demo.ipynb
```

This notebook contains:
1. Single QEC cycle with circuit visualization
2. Four-noise-level benchmark (0%, 5%, 25%, 60%)
3. Power-law scaling analysis at moderate noise
4. Postselection overhead visualization

#### Full QEC Pipeline as Python Script

**Alternative: Run everything as a standalone Python script** (same as notebook, with interactive prompts):
```bash
cd team_solutions/The_Ducklings
python run_qec_alternative.py
```
This script replicates all notebook functionality with ENTER prompts between sections and displays all plots inline.

#### Command-Line Demos

**Single QEC cycle (customizable):**
```bash
python demo0.py
```
Edit parameters in `demo0.py` to test different states, qubit locations, and error types.

**Full benchmark (0%, 5%, 25%, 60% noise):**
```bash
python demo1.py
```

### Key Results

| Noise Level | Baseline Fidelity | Active Correction | Improvement |
|---|---|---|---|
| 5% | 98.6% | **100%** | +1.4% |
| 25% | 92.8% | **99.2%** | +6.4% |
| 60% | 80.4% | **97.2%** | +16.8% |

**Power-Law Scaling (p₁=0.5):**
- Active Correction: Error ∝ N⁻¹ (linear improvement with shots)
- Postselection: ~50% waste overhead
- Correction **5x better** than baseline at 100 shots

### Challenge Requirements Coverage

✅ **Step 1:** Bloqade kernels, PyQrack simulation, circuit execution

✅ **Step 2:** 
- MSD state encoding circuit implementation
- Steane QEC syndrome extraction pipeline
- Classical decoder for error location/type
- Multi-noise-level analysis
- Power-law scaling plots
- Postselection overhead quantification

⏳ **Bonus Tasks:** 
- Distance 5 code (not implemented)
- Recurrent syndrome extraction (foundation in place)
- Bespoke atom moving (framework ready)
- Tsim backend with T-states (PyQrack sufficient for current scope)

### Code Structure

```
team_solutions/The_Ducklings/
├── qec/                          # Core QEC package
│   ├── __init__.py
│   ├── states.py                 # Clifford basis states
│   ├── encoding.py               # prepareLogicalQubit (MSD circuit)
│   ├── syndrome.py               # Syndrome measurement kernels
│   ├── errors.py                 # Error injection
│   ├── error_mapping.py          # Classical decoder
│   ├── correction.py             # run_full_QEC + circuit emission
│   ├── logical_ops.py            # Logical operations
│   ├── experiments.py            # Analysis utilities
│   └── main.py                   # Standalone benchmark
├── demo0.py                      # Single QEC cycle (interactive)
├── demo1.py                      # Full benchmark
├── qec_demo.ipynb                # Interactive notebook
├── pyproject.toml                # Dependencies
└── README.md                     # Full documentation
```

### References

1. **Steane QEC:** [arxiv:2312.09745](https://arxiv.org/pdf/2312.09745)
2. **QuEra MSD Circuit:** [arxiv:2412.15165](https://arxiv.org/abs/2412.15165)
3. **Color Code Flagging:** [arxiv:2312.03982](https://arxiv.org/pdf/2312.03982)
4. **Bloqade SDK:** https://bloqade.quera.com/

---

**Status:** Complete (Core + Analysis ✅ | Bonuses ⏳)

**Last Updated:** February 1, 2026
