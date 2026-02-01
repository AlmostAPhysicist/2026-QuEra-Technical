#!/usr/bin/env python3
"""
Logical Memory Benchmark - Bloqade Implementation
=================================================

Compares passive vs active (QEC) memory using [[7,1,3]] encoding.
All syndrome decoding on host side (not in kernel).
"""

from bloqade import squin
from bloqade.pyqrack import StackMemorySimulator
from qec.error_mapping import color_parities

emu = StackMemorySimulator()

P_IDLE = 0.005
P_GATE = 0.01


# ============================================================
# Passive memory kernel - FULLY INLINED ENCODE/DECODE
# ============================================================

@squin.kernel
def passive_memory(R: int):
    """Encode → Noise^R → Decode → Measure"""

    block = squin.qalloc(7)
    
    # ENCODE (inlined)
    for i in range(6):
        squin.sqrt_y_adj(block[i])
    for i in (1, 3, 5):
        squin.cz(block[i], block[i + 1])
    squin.sqrt_y(block[6])
    for i in (0, 2):
        squin.cz(block[i], block[i + 3])
    squin.cz(block[4], block[6])
    for i in range(2, 7):
        squin.sqrt_y(block[i])
    for i in (0, 2, 4):
        squin.cz(block[i], block[i + 1])
    for i in (1, 2, 4):
        squin.sqrt_y(block[i])

    # Apply noise R times
    for _ in range(R):
        squin.broadcast.depolarize(P_IDLE, block)

    # DECODE (inlined - exact inverse)
    for i in (1, 2, 4):
        squin.sqrt_y_adj(block[i])
    for i in (0, 2, 4):
        squin.cz(block[i], block[i + 1])
    for i in range(2, 7):
        squin.sqrt_y_adj(block[i])
    squin.cz(block[4], block[6])
    for i in (0, 2):
        squin.cz(block[i], block[i + 3])
    squin.sqrt_y_adj(block[6])
    for i in (1, 3, 5):
        squin.cz(block[i], block[i + 1])
    for i in range(6):
        squin.sqrt_y(block[i])
    
    return squin.measure(block[6])


# ============================================================
# Active memory kernel - FULLY INLINED
# ============================================================

@squin.kernel
def active_memory_measure(R: int):
    """Encode → (Noise + Syndrome)^R → Decode → Measure"""

    data = squin.qalloc(7)
    
    # ENCODE data (inlined)
    for i in range(6):
        squin.sqrt_y_adj(data[i])
    for i in (1, 3, 5):
        squin.cz(data[i], data[i + 1])
    squin.sqrt_y(data[6])
    for i in (0, 2):
        squin.cz(data[i], data[i + 3])
    squin.cz(data[4], data[6])
    for i in range(2, 7):
        squin.sqrt_y(data[i])
    for i in (0, 2, 4):
        squin.cz(data[i], data[i + 1])
    for i in (1, 2, 4):
        squin.sqrt_y(data[i])

    # Pre-allocate baseline probes
    probeX_base = squin.qalloc(7)
    probeZ_base = squin.qalloc(7)
    
    # ENCODE probeX_base (inlined)
    for i in range(6):
        squin.sqrt_y_adj(probeX_base[i])
    for i in (1, 3, 5):
        squin.cz(probeX_base[i], probeX_base[i + 1])
    squin.sqrt_y(probeX_base[6])
    for i in (0, 2):
        squin.cz(probeX_base[i], probeX_base[i + 3])
    squin.cz(probeX_base[4], probeX_base[6])
    for i in range(2, 7):
        squin.sqrt_y(probeX_base[i])
    for i in (0, 2, 4):
        squin.cz(probeX_base[i], probeX_base[i + 1])
    for i in (1, 2, 4):
        squin.sqrt_y(probeX_base[i])

    # ENCODE probeZ_base (inlined)
    for i in range(6):
        squin.sqrt_y_adj(probeZ_base[i])
    for i in (1, 3, 5):
        squin.cz(probeZ_base[i], probeZ_base[i + 1])
    squin.sqrt_y(probeZ_base[6])
    for i in (0, 2):
        squin.cz(probeZ_base[i], probeZ_base[i + 3])
    squin.cz(probeZ_base[4], probeZ_base[6])
    for i in range(2, 7):
        squin.sqrt_y(probeZ_base[i])
    for i in (0, 2, 4):
        squin.cz(probeZ_base[i], probeZ_base[i + 1])
    for i in (1, 2, 4):
        squin.sqrt_y(probeZ_base[i])

    # Measure baseline X syndrome
    for j in range(7):
        squin.cx(data[j], probeX_base[j])
    baseX = squin.broadcast.measure(probeX_base)

    # Measure baseline Z syndrome
    for j in range(7):
        squin.cx(probeZ_base[j], data[j])
    for j in range(7):
        squin.h(probeZ_base[j])
    baseZ = squin.broadcast.measure(probeZ_base)

    # Measure syndrome for each round
    syndromes = []
    
    for r in range(R):
        squin.broadcast.depolarize(P_IDLE, data)
        
        # Fresh probes each round
        probeX = squin.qalloc(7)
        probeZ = squin.qalloc(7)
        
        # ENCODE probeX (inlined)
        for i in range(6):
            squin.sqrt_y_adj(probeX[i])
        for i in (1, 3, 5):
            squin.cz(probeX[i], probeX[i + 1])
        squin.sqrt_y(probeX[6])
        for i in (0, 2):
            squin.cz(probeX[i], probeX[i + 3])
        squin.cz(probeX[4], probeX[6])
        for i in range(2, 7):
            squin.sqrt_y(probeX[i])
        for i in (0, 2, 4):
            squin.cz(probeX[i], probeX[i + 1])
        for i in (1, 2, 4):
            squin.sqrt_y(probeX[i])

        # ENCODE probeZ (inlined)
        for i in range(6):
            squin.sqrt_y_adj(probeZ[i])
        for i in (1, 3, 5):
            squin.cz(probeZ[i], probeZ[i + 1])
        squin.sqrt_y(probeZ[6])
        for i in (0, 2):
            squin.cz(probeZ[i], probeZ[i + 3])
        squin.cz(probeZ[4], probeZ[6])
        for i in range(2, 7):
            squin.sqrt_y(probeZ[i])
        for i in (0, 2, 4):
            squin.cz(probeZ[i], probeZ[i + 1])
        for i in (1, 2, 4):
            squin.sqrt_y(probeZ[i])

        # X syndrome measurement
        for j in range(7):
            squin.cx(data[j], probeX[j])
            squin.depolarize2(P_GATE, data[j], probeX[j])
        synX = squin.broadcast.measure(probeX)

        # Z syndrome measurement
        for j in range(7):
            squin.cx(probeZ[j], data[j])
            squin.depolarize2(P_GATE, probeZ[j], data[j])
        for j in range(7):
            squin.h(probeZ[j])
        synZ = squin.broadcast.measure(probeZ)
        
        syndromes.append((synX, synZ))

    # DECODE data (inlined - exact inverse)
    for i in (1, 2, 4):
        squin.sqrt_y_adj(data[i])
    for i in (0, 2, 4):
        squin.cz(data[i], data[i + 1])
    for i in range(2, 7):
        squin.sqrt_y_adj(data[i])
    squin.cz(data[4], data[6])
    for i in (0, 2):
        squin.cz(data[i], data[i + 3])
    squin.sqrt_y_adj(data[6])
    for i in (1, 3, 5):
        squin.cz(data[i], data[i + 1])
    for i in range(6):
        squin.sqrt_y(data[i])
    
    result = squin.measure(data[6])
    
    return (result, baseX, baseZ, syndromes)


# ============================================================
# Host-side benchmark runner
# ============================================================

def benchmark_compare(R=5, shots=200):
    """Compare passive vs active memory."""
    passive_fail = 0
    active_ps_fail = 0
    active_ps_accept = 0

    for shot_idx in range(shots):
        # PASSIVE
        m_passive = list(emu.task(passive_memory, args=(R,)).batch_run(shots=1))[0]
        if int(m_passive) != 0:
            passive_fail += 1

        # ACTIVE
        result, baseX_bits, baseZ_bits, syndromes = list(
            emu.task(active_memory_measure, args=(R,)).batch_run(shots=1)
        )[0]

        baseX_par = color_parities([int(b) for b in baseX_bits])
        baseZ_par = color_parities([int(b) for b in baseZ_bits])

        postselect_accept = True
        for synX_bits, synZ_bits in syndromes:
            synX_par = color_parities([int(b) for b in synX_bits])
            synZ_par = color_parities([int(b) for b in synZ_bits])
            if synX_par != baseX_par or synZ_par != baseZ_par:
                postselect_accept = False
                break

        if postselect_accept:
            active_ps_accept += 1
            if int(result) != 0:
                active_ps_fail += 1

    passive_fid = 1.0 - passive_fail / shots
    active_ps_fid = 1.0 - (active_ps_fail / active_ps_accept) if active_ps_accept > 0 else 0.0
    active_ps_waste = 1.0 - (active_ps_accept / shots)

    print("\n" + "=" * 70)
    print(f"R = {R} rounds")
    print("=" * 70)
    print(f"Passive fidelity        = {passive_fid:.4f}")
    print(f"Active fidelity         = {active_ps_fid:.4f}")
    print(f"Active waste            = {active_ps_waste:.4f}")
    print("=" * 70)

    return passive_fid, active_ps_fid, active_ps_waste


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("LOGICAL MEMORY BENCHMARK")
    print("=" * 70)
    print(f"P_IDLE = {P_IDLE}, P_GATE = {P_GATE}")
    print("=" * 70)

    results = {}
    for R in [1, 3, 5, 10]:
        p_fid, a_fid, waste = benchmark_compare(R=R, shots=200)
        results[R] = (p_fid, a_fid, waste)

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print("R\tPassive\tActive\tWaste")
    for R in sorted(results.keys()):
        p, a, w = results[R]
        print(f"{R}\t{p:.4f}\t{a:.4f}\t{w:.4f}")
    print("=" * 70)
