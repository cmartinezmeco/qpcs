"""src/pqc/benchmark.py - tarea 2.7 (Carlos). Medidas de tiempo y tamano.

El entregable del modulo 2 es la comparacion cuantitativa clasico vs
post-cuantico: cuanto tarda cada operacion y cuanto ocupan claves, ciphertexts
y firmas. Este modulo produce esas cifras como `Medida` y `Tamanos` (ver
`types.py`), que luego consume el dashboard.

Reglas de medida (para que las cifras sean defendibles):
  - Reloj: SIEMPRE time.perf_counter, NUNCA time.time. perf_counter es
    monotono y de alta resolucion; time.time puede saltar hacia atras (ajuste
    de NTP) y arruinar una medida.
  - Se reportan media, sigma (desviacion tipica de las repeticiones) y p50
    (mediana). La barra de error es sigma DERIVADA de las muestras, nunca un
    numero inventado a ojo: misma disciplina que el QBER del modulo 1.
  - Conviene un calentamiento (unas pocas repeticiones descartadas) antes de
    cronometrar, para no medir el coste de importar/compilar en frio.

Aqui no hay np.random.Generator: la cripto real genera sus claves con su propio
CSPRNG y no se siembra.
"""

from __future__ import annotations

from .types import Familia, Medida, Operacion, Tamanos


def medir_kem(
    mecanismo: str = "ML-KEM-768",
    operacion: Operacion = "encaps",
    repeticiones: int = 200,
) -> Medida:
    """Cronometra una `operacion` de un KEM (keygen / encaps / decaps).

    Repite `repeticiones` veces con time.perf_counter y devuelve una `Medida`
    con familia="ML-KEM", media, sigma y p50 en milisegundos.
    """
    raise NotImplementedError


def medir_sig(
    mecanismo: str = "ML-DSA-65",
    operacion: Operacion = "sign",
    repeticiones: int = 200,
) -> Medida:
    """Cronometra una `operacion` de firma (keygen / sign / verify).

    Devuelve una `Medida` con familia="ML-DSA". Mismo protocolo de medida que
    `medir_kem`.
    """
    raise NotImplementedError


def medir_classical(
    familia: Familia,
    mecanismo: str,
    operacion: Operacion,
    repeticiones: int = 200,
) -> Medida:
    """Cronometra una `operacion` clasica (RSA o ECC) de `classical.py`.

    `familia` debe ser "RSA" o "ECC" (las post-cuanticas van por `medir_kem` /
    `medir_sig`). Devuelve la `Medida` con esa familia para que las tablas del
    benchmark comparen manzanas con manzanas.
    """
    raise NotImplementedError


def tamanos_kem(mecanismo: str = "ML-KEM-768") -> Tamanos:
    """Tamanos en bytes de un KEM: clave publica, privada y kem_ciphertext.

    El campo `firma` de `Tamanos` no aplica a un KEM: se rellena con 0. Los
    tamanos son deterministas (los fija el mecanismo), asi que basta una
    generacion/encapsulacion para leerlos.
    """
    raise NotImplementedError


def tamanos_sig(mecanismo: str = "ML-DSA-65") -> Tamanos:
    """Tamanos en bytes de un esquema de firma: clave publica, privada y firma.

    El campo `texto_cifrado` no aplica a una firma: se rellena con 0.
    """
    raise NotImplementedError
