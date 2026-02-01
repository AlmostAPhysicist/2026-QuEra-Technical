from bloqade import squin

# Inject Pauli error into a register (kernel).
# basis: 0 = X, 1 = Y, 2 = Z
@squin.kernel
def inject_pauli(block, index: int, basis: int):
    if basis == 0:
        squin.x(block[index])
    elif basis == 1:
        squin.y(block[index])
    elif basis == 2:
        squin.z(block[index])
