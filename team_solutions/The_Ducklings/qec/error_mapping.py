from typing import List, Tuple

# Stabilizer supports for the [[7,1,3]] color code
RED   = [2, 3, 4, 6]
GREEN = [1, 2, 4, 5]
BLUE  = [0, 1, 2, 3]

def parity(bits: List[int], support: List[int]) -> int:
    """Return +1 for even parity, -1 for odd parity on support."""
    return +1 if sum(bits[i] for i in support) % 2 == 0 else -1

def color_parities(bits: List[int]) -> Tuple[int, int, int]:
    """Return stabilizer parities (R,G,B)."""
    return (
        parity(bits, RED),
        parity(bits, GREEN),
        parity(bits, BLUE),
    )

# Syndrome flip pattern -> qubit index (classical single-error decoder)
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

def locate_flipped_qubit(old_syn, new_syn) -> int:
    """Compare parity change and infer likely X error location."""
    flip = tuple(1 if old_syn[i] != new_syn[i] else 0 for i in range(3))
    return SYNDROME_TABLE.get(flip, -1)
