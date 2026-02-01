from bloqade import squin
from kirin.dialects.ilist import IList
from bloqade.types import MeasurementResult
from typing import Any

from .encoding import prepareLogicalQubit, decode_713_block

@squin.kernel
def logical_X_roundtrip(theta: float, phi: float) -> IList[MeasurementResult, Any]:
    logical = prepareLogicalQubit(theta, phi)
    # Apply logical X_L (transversal X on all 7 qubits)
    squin.broadcast.x(logical)
    # Decode back
    decode_713_block(logical)
    # Measure everything
    return squin.broadcast.measure(logical)
