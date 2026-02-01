import numpy as np

def zeroState():
    """|0>"""
    return 0.0, 0.0

def oneState():
    """|1> = X|0>"""
    return 0.0, np.pi

def plusState():
    """|+> = H|0>"""
    return 0.0, np.pi / 2

def minusState():
    """|-> = ZH|0>"""
    return np.pi, np.pi / 2
