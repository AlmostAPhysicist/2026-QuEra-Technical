from bloqade import squin
from bloqade.types import Qubit
from kirin.dialects.ilist import IList
from typing import Any

# Physical single-qubit preparation (kernel)
@squin.kernel
def setPhysicalQubit(theta: float, phi: float, q: Qubit) -> None:
    squin.rz(theta, q)
    squin.rx(phi, q)

# QuEra MSD injection encoder circuit ([[7,1,3]])
@squin.kernel
def encode_713_block(reg: IList[Qubit, Any]) -> None:
    # Layer 1: √Y† on ancilla qubits
    for i in range(6):
        squin.sqrt_y_adj(reg[i])

    # Layer 2: CZ entangling layer
    for i in (1, 3, 5):
        squin.cz(reg[i], reg[i + 1])

    # Layer 3: rotate input qubit
    squin.sqrt_y(reg[6])

    # Layer 4: long-range CZ
    for i in (0, 2):
        squin.cz(reg[i], reg[i + 3])

    # Layer 5: couple input into block
    squin.cz(reg[4], reg[6])

    # Layer 6: √Y on qubits 2–6
    for i in range(2, 7):
        squin.sqrt_y(reg[i])

    # Layer 7: final CZ layer
    for i in (0, 2, 4):
        squin.cz(reg[i], reg[i + 1])

    # Layer 8: final √Y layer
    for i in (1, 2, 4):
        squin.sqrt_y(reg[i])

# Decoder = exact inverse of encoder
@squin.kernel
def decode_713_block(reg: IList[Qubit, Any]) -> None:
    for i in (1, 2, 4):
        squin.sqrt_y_adj(reg[i])

    for i in (0, 2, 4):
        squin.cz(reg[i], reg[i + 1])

    for i in range(2, 7):
        squin.sqrt_y_adj(reg[i])

    squin.cz(reg[4], reg[6])

    for i in (0, 2):
        squin.cz(reg[i], reg[i + 3])

    squin.sqrt_y_adj(reg[6])

    for i in (1, 3, 5):
        squin.cz(reg[i], reg[i + 1])

    for i in range(6):
        squin.sqrt_y(reg[i])

# Logical preparation kernel
@squin.kernel
def prepareLogicalQubit(theta: float, phi: float) -> IList[Qubit, Any]:
    reg = squin.qalloc(7)
    setPhysicalQubit(theta, phi, reg[6])
    encode_713_block(reg)
    return reg
