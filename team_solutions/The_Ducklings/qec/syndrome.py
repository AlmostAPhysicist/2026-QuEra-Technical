from bloqade import squin
from bloqade.types import MeasurementResult
from kirin.dialects.ilist import IList
from typing import Any

from .encoding import prepareLogicalQubit
from .errors import inject_pauli

# Measure X-stabilizer syndrome via |+_L> probe (data -> probe)
@squin.kernel
def measure_X_syndrome(theta: float, phi: float, err_index: int, err_basis: int):
    data = prepareLogicalQubit(theta, phi)
    # option: inject a deterministic error for testing
    inject_pauli(data, err_index, err_basis)
    probe = prepareLogicalQubit(0.0, 3.1415926535 / 2)  # |+_L>
    for j in range(7):
        squin.cx(data[j], probe[j])
    return squin.broadcast.measure(probe)

# Measure Z-stabilizer syndrome via |0_L> probe (probe -> data)
@squin.kernel
def measure_Z_syndrome(theta: float, phi: float, err_index: int, err_basis: int):
    data = prepareLogicalQubit(theta, phi)
    inject_pauli(data, err_index, err_basis)
    probe = prepareLogicalQubit(0.0, 0.0)  # |0_L>
    for j in range(7):
        squin.cx(probe[j], data[j])
    # measure probe in X basis
    for j in range(7):
        squin.h(probe[j])
    return squin.broadcast.measure(probe)

# Baseline clean syndrome measurement (no injected error)
@squin.kernel
def measure_clean_syndromes(theta: float, phi: float):
    data = prepareLogicalQubit(theta, phi)

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

# Inject error + measure both syndromes (for error detection)
@squin.kernel
def measure_error_syndromes(theta: float, phi: float,
                            err_index: int, err_basis: int):
    """
    Encode a logical qubit, inject a Pauli error, then measure X and Z syndromes.
    """
    data = prepareLogicalQubit(theta, phi)

    # Inject the specified error
    inject_pauli(data, err_index, err_basis)

    # Measure X syndrome via |+_L> probe
    probeX = prepareLogicalQubit(0.0, 3.1415926535 / 2)
    for j in range(7):
        squin.cx(data[j], probeX[j])
    measX = squin.broadcast.measure(probeX)

    # Measure Z syndrome via |0_L> probe
    probeZ = prepareLogicalQubit(0.0, 0.0)
    for j in range(7):
        squin.cx(probeZ[j], data[j])
    for j in range(7):
        squin.h(probeZ[j])
    measZ = squin.broadcast.measure(probeZ)

    return measX, measZ

# Inject + correct + remeasure verification kernel
@squin.kernel
def verify_correction(theta: float, phi: float,
                      err_index: int, err_basis: int,
                      corr_index: int, corr_basis: int):
    data = prepareLogicalQubit(theta, phi)

    # inject original error
    if err_basis == 0:
        squin.x(data[err_index])
    elif err_basis == 1:
        squin.y(data[err_index])
    elif err_basis == 2:
        squin.z(data[err_index])

    # apply classical correction (Pauli)
    if corr_basis == 0:
        squin.x(data[corr_index])
    elif corr_basis == 1:
        squin.y(data[corr_index])
    elif corr_basis == 2:
        squin.z(data[corr_index])

    # measure X syndrome
    probeX = prepareLogicalQubit(0.0, 3.1415926535 / 2)
    for j in range(7):
        squin.cx(data[j], probeX[j])
    measX = squin.broadcast.measure(probeX)

    # measure Z syndrome
    probeZ = prepareLogicalQubit(0.0, 0.0)
    for j in range(7):
        squin.cx(probeZ[j], data[j])
    for j in range(7):
        squin.h(probeZ[j])
    measZ = squin.broadcast.measure(probeZ)

    return measX, measZ
