"""tests/qkd/test_scaffold.py — tarea 1.1.

Comprueba que la API publica del paquete qkd existe. Si alguien renombra o
borra algo sin avisar al equipo, este test se pone rojo.
"""

import qkd


def test_api_publica_existe():
    nombres = (
        "QRNG",
        "run_bb84",
        "sift",
        "intercept_resend",
        "estimate_qber",
        "cascade",
        "ParityOracle",
        "privacy_amplify",
        "secure_key_length",
        "binary_entropy",
        "run_protocol",
        "run_until_qber",
    )
    for nombre in nombres:
        assert hasattr(qkd, nombre), f"falta {nombre} en la API publica de qkd"
