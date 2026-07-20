"""src/pqc/types.py - contratos del modulo PQC (Fase 2)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Familia = Literal["RSA", "ECC", "ML-KEM", "ML-DSA"]
Operacion = Literal[
    "keygen", "encaps", "decaps", "sign", "verify", "encrypt", "decrypt"
]


@dataclass(frozen=True)
class Medida:
    familia: Familia
    mecanismo: str
    operacion: Operacion
    repeticiones: int
    media_ms: float
    sigma_ms: float
    p50_ms: float


@dataclass(frozen=True)
class Tamanos:
    mecanismo: str
    clave_publica: int
    clave_privada: int
    texto_cifrado: int
    firma: int


@dataclass(frozen=True)
class MensajeCifrado:
    kem_ciphertext: bytes
    nonce: bytes
    aead_ciphertext: bytes
    mecanismo: str


@dataclass(frozen=True)
class ResultadoFirma:
    mensaje: bytes
    firma: bytes
    clave_publica: bytes
    mecanismo: str


@dataclass(frozen=True)
class FactorizacionShor:
    n: int
    factores: tuple[int, int]
    a: int
    orden: int
    intentos: int
    fase_medida: float
    ok: bool
