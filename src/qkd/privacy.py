"""src/qkd/privacy.py — tarea 1.6 (Marco). Toeplitz + longitud segura.

Amplificacion de privacidad: al salir de Cascade (tarea 1.5) Alice y Bob
tienen la MISMA cadena de n bits, pero no es secreta: Eve tiene informacion
parcial (del canal cuantico, acotada por h(Q); y de las paridades oidas en
la reconciliacion, exactamente leak_ec bits). No sabemos QUE bits conoce, y
la idea bonita es que no hace falta saberlo: se comprime la cadena con una
funcion hash 2-universal elegida al azar (matriz de Toeplitz) y la salida es
uniforme desde el punto de vista de Eve (leftover hash lemma).

Referencia: Bennett, Brassard, Crepeau y Maurer, "Generalized privacy
amplification", IEEE Trans. Inf. Theory 41 (1995).
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt
from scipy.linalg import matmul_toeplitz

from .types import Bits


def binary_entropy(q: float) -> float:
    """Entropia binaria de Shannon: h(q) = -q log2 q - (1-q) log2 (1-q).

    Por convenio h(0) = h(1) = 0 (el limite de la formula). h(0.5) = 1.
    De aqui sale el umbral del 11%: h(0.11) ~ 0.5, y con f = 1 la condicion
    de clave positiva 1 - 2 h(Q) > 0 equivale a Q < 11% (Shor-Preskill).
    """
    if q <= 0.0 or q >= 1.0:
        return 0.0
    return float(-q * np.log2(q) - (1 - q) * np.log2(1 - q))


def secure_key_length(
    n: int,
    qber: float,
    leak_ec: int,
    epsilon: float = 1e-9,
    sigma: float = 0.0,
    n_sigma: float = 0.0,
) -> int:
    """Longitud de clave segura (Devetak-Winter + leftover hash lemma).

        ell = n(1 - h(Q)) - leak_ec - 2 log2(1/eps)

    Cada termino tiene nombre y culpable:
      - n(1 - h(Q)):     lo que queda tras descontar lo que Eve pudo sacar
                         del canal cuantico (cota paranoica: TODO el QBER se
                         atribuye a Eve). Viene de la tarea 1.4.
      - leak_ec:         los bits gritados por el canal publico corrigiendo
                         errores. Viene del ParityOracle de la tarea 1.5.
      - 2 log2(1/eps):   el peaje del leftover hash lemma (~60 bits con
                         eps = 1e-9). Constante, ridiculo e imprescindible
                         para poder decir "eps-seguro" con propiedad.

    MEJORA C1: Q es un ESTIMADOR sobre una muestra, y su incertidumbre
    (sigma, que estimate_qber ya calcula y el dashboard ya ensena) no entraba
    en esta formula: se usaba el valor puntual. Con la muestra a la baja por
    azar, la clave sale mas larga de lo que la cota paranoica permitiria. Los
    parametros `sigma` y `n_sigma` permiten usar la cota superior
    min(1, Q + n_sigma*sigma) en el termino h(). Por defecto n_sigma = 0, es
    decir, el comportamiento es EXACTAMENTE el de antes: la capacidad queda
    disponible sin cambiar ningun resultado ya publicado.

    Devuelve 0 si no queda nada que destilar: el protocolo debe abortar
    (lo hace run_protocol, y hay un test que lo comprueba).
    """
    q_cota = min(1.0, qber + n_sigma * sigma)
    ell = n * (1 - binary_entropy(q_cota)) - leak_ec - 2 * np.log2(1 / epsilon)
    return max(0, int(np.floor(ell)))


def privacy_amplify(key: Bits, ell: int, seed: Bits) -> Bits:
    """Comprime `key` (n bits) a `ell` bits con una matriz de Toeplitz.

    Una matriz de Toeplitz T (ell x n, diagonales constantes) queda definida
    por n + ell - 1 bits de semilla, y la familia {K -> T K mod 2} es
    2-universal: es la construccion que se usa en QKD real.

    La semilla es PUBLICA: el leftover hash lemma vale incluso si Eve conoce
    la funcion hash; lo que no puede conocer es la entrada completa. El unico
    requisito es elegirla al azar DESPUES de que Eve haya obtenido su
    informacion (por eso run_protocol la genera al final de la cadena).

    T @ k se calcula por FFT con scipy.linalg.matmul_toeplitz (O(n log n));
    con n < 2^20 las sumas parciales caben exactas en float64 (< 2^53), asi
    que el % 2 final es fiable. Construir T explicitamente seria una matriz
    de ~1 GB con n = 10^5: no (los tests si la construyen, pero en pequeno,
    para validar bit a bit el camino FFT).
    """
    n = key.size
    if ell <= 0:
        # Sin capacidad de destilar nada: clave vacia. El aborto explicito
        # (con motivo legible) lo gestiona run_protocol, no esta funcion.
        return np.empty(0, dtype=np.uint8)
    if seed.size != n + ell - 1:
        raise ValueError(f"la semilla debe tener n+ell-1 = {n + ell - 1} bits")

    c = seed[:ell].astype(np.float64)  # primera columna de T
    r = seed[ell - 1 :].astype(np.float64)  # primera fila (comparten esquina)
    # La anotacion explicita es para mypy --strict: scipy no publica stubs y
    # matmul_toeplitz devolveria Any si no fijamos el tipo aqui.
    out: npt.NDArray[np.float64] = matmul_toeplitz((c, r), key.astype(np.float64))
    # rint antes del modulo: la FFT devuelve floats con error ~1e-12 sobre
    # enteros exactos; redondear primero evita que 6.9999... % 2 se convierta
    # en un bit erroneo.
    return (np.rint(out).astype(np.int64) % 2).astype(np.uint8)
