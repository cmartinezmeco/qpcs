"""API publica del modulo pqc. Solo lo que se exporta desde aqui es "publico".

Espejo de src/qkd/__init__.py: la frontera estable del modulo 2. Las firmas ya
existen (con NotImplementedError); las tareas 2.2-2.7 rellenan los cuerpos sin
cambiar esta superficie.
"""

from .benchmark import (
    medir_classical,
    medir_kem,
    medir_sig,
    tamanos_kem,
    tamanos_sig,
)
from .classical import (
    ed25519_firmar,
    ed25519_generar,
    ed25519_verificar,
    rsa_cifrar_oaep,
    rsa_descifrar_oaep,
    rsa_firmar_pss,
    rsa_generar,
    rsa_verificar_pss,
    x25519_generar,
    x25519_intercambio,
)
from .hybrid import cifrar_mensaje, descifrar_mensaje
from .kem import kem_desencapsular, kem_encapsular, kem_generar
from .shor import (
    c_amod15,
    circuito_orden_15,
    factorizar_15,
    medir_fase_15,
    orden_desde_fase,
    qft_dagger,
)
from .sig import firmar, verificar

__all__ = [
    # classical (2.4)
    "rsa_generar",
    "rsa_cifrar_oaep",
    "rsa_descifrar_oaep",
    "rsa_firmar_pss",
    "rsa_verificar_pss",
    "x25519_generar",
    "x25519_intercambio",
    "ed25519_generar",
    "ed25519_firmar",
    "ed25519_verificar",
    # kem (2.5)
    "kem_generar",
    "kem_encapsular",
    "kem_desencapsular",
    # hybrid (2.5)
    "cifrar_mensaje",
    "descifrar_mensaje",
    # sig (2.6)
    "firmar",
    "verificar",
    # shor (2.2 / 2.3)
    "qft_dagger",
    "c_amod15",
    "circuito_orden_15",
    "medir_fase_15",
    "orden_desde_fase",
    "factorizar_15",
    # benchmark (2.7)
    "medir_kem",
    "medir_sig",
    "medir_classical",
    "tamanos_kem",
    "tamanos_sig",
]
