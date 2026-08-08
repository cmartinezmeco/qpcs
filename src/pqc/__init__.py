"""API publica del modulo pqc. Solo lo que se exporta desde aqui es "publico".

Espejo de src/qkd/__init__.py: la frontera estable del modulo 2.

Esta lista es la frontera DE VERDAD, no una version reducida de ella: incluye
todo lo que consumen de fuera el dashboard, `scripts/make_pqc_plots.py` y los
tests. Antes se quedaba en las funciones de cada tarea mientras esos tres
consumidores importaban otros nueve nombres directamente de `pqc.benchmark`,
`pqc.kem` y `pqc.sig` (RUTA_JSON, cargar_json, abrir_kem...), asi que la frase
de arriba era falsa y `test_api_publica_existe` daba una sensacion de
superficie congelada que no era cierta: se podia renombrar cualquiera de esos
nueve y el test seguia verde.
"""

from .benchmark import (
    RUTA_JSON,
    SUFIJO_CAPA_API,
    SUFIJO_CON_KEYGEN,
    SUFIJO_HIBRIDO,
    cargar_json,
    entorno,
    entorno_del_json,
    guardar_json,
    medir_classical,
    medir_hibrido,
    medir_kem,
    medir_sig,
    tabla_medidas,
    tabla_tamanos,
    tamanos_classical,
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
from .hybrid import MECANISMOS_ADMITIDOS, cifrar_mensaje, descifrar_mensaje
from .kem import abrir_kem, kem_desencapsular, kem_encapsular, kem_generar
from .shor import (
    c_amod15,
    circuito_orden_15,
    factorizar_15,
    histograma_fases_15,
    medir_fase_15,
    orden_desde_fase,
    qft_dagger,
)
from .sig import abrir_firma, firmar, verificar

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
    "abrir_kem",
    "kem_generar",
    "kem_encapsular",
    "kem_desencapsular",
    # hybrid (2.5)
    "MECANISMOS_ADMITIDOS",
    "cifrar_mensaje",
    "descifrar_mensaje",
    # sig (2.6)
    "abrir_firma",
    "firmar",
    "verificar",
    # shor (2.2 / 2.3)
    "qft_dagger",
    "c_amod15",
    "circuito_orden_15",
    "medir_fase_15",
    "histograma_fases_15",
    "orden_desde_fase",
    "factorizar_15",
    # benchmark (2.7): medidas
    "medir_kem",
    "medir_sig",
    "medir_classical",
    "medir_hibrido",
    "tamanos_kem",
    "tamanos_sig",
    "tamanos_classical",
    "tabla_medidas",
    "tabla_tamanos",
    # benchmark (2.7): el JSON y sus etiquetas, que consumen las figuras (2.9)
    # y el dashboard sin volver a medir
    "RUTA_JSON",
    "SUFIJO_CAPA_API",
    "SUFIJO_HIBRIDO",
    "SUFIJO_CON_KEYGEN",
    "entorno",
    "entorno_del_json",
    "guardar_json",
    "cargar_json",
]
