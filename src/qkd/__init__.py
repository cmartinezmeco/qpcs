"""API publica del modulo qkd. Solo lo que se exporta desde aqui es "publico".

MEJORA E4: los tipos de resultado de types.py se declaraban "contratos
internos" y no se reexportaban, pero los dos consumidores externos (el
dashboard y el script de graficas) los importan y leen sus campos: son
superficie publica de hecho. Se reconocen como tales aqui, de modo que la
frontera declarada coincida con la real y test_scaffold.py pueda vigilarla.
"""

from .bb84 import run_bb84, sift
from .eve import intercept_resend
from .privacy import binary_entropy, privacy_amplify, secure_key_length
from .protocol import run_protocol, run_until_qber
from .qber import estimate_qber
from .qrng import QRNG
from .reconciliation import ParityOracle, cascade
from .types import ProtocolResult, QberEstimate, ReconciliationResult, SiftedKeys

__all__ = [
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
    # Tipos de resultado (MEJORA E4).
    "SiftedKeys",
    "QberEstimate",
    "ReconciliationResult",
    "ProtocolResult",
]
