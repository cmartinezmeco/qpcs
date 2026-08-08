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
    """Resultado de `shor.factorizar_15`. LEER `ok` ANTES QUE NADA.

    Con ok=True todos los campos son medidas reales: `factores` multiplican a
    `n`, `a` es la base que funciono, `orden` es el orden de `a` modulo `n`
    (verificado con a^orden == 1) y `fase_medida` es la fase de la que salio.

    Con ok=False los campos NO son medidas, son CENTINELAS de "no hay dato":
    factores=(1, n), a=0, orden=0, fase_medida=0.0. El 0 de `a` no es una base
    (no es coprimo con 15 y `c_amod15` lo rechaza) y el 0 de `orden` no es un
    orden. Pintarlos sin mirar `ok` primero ensena ceros como si fueran
    resultados; peor, pasar a=0 de vuelta al circuito levanta ValueError.
    `intentos` es el unico campo que significa lo mismo en los dos casos.
    """

    n: int
    factores: tuple[int, int]
    a: int
    orden: int
    intentos: int
    fase_medida: float
    ok: bool
