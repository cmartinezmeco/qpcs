"""src/qkd/qber.py — tarea 1.4 (Gonzalo). Estimacion de QBER sobre muestra."""

from __future__ import annotations

import numpy as np

from .types import QberEstimate, SiftedKeys


def estimate_qber(
    keys: SiftedKeys, sample_fraction: float, rng: np.random.Generator
) -> QberEstimate:
    """Estima el QBER sacrificando una muestra aleatoria de la clave cribada.
    QBER = fraccion de posiciones donde Alice y Bob difieren.
    sigma = sqrt(q(1-q)/m): la incertidumbre de una binomial de m muestras.
    Los bits de la muestra se DESCARTAN: se han publicado, Eve los conoce.
    """
    # Numero de bits cribados (donde Alice y Bob usaron la misma base):
    # tamano del array de bits de Alice en la clave cribada.
    n = keys.alice.size
    m = int(round(sample_fraction * n))  # Numero de bits en la muestra
    if m == 0:
        raise ValueError("muestra vacia: no se puede estimar el QBER")

    # Selecciona m indices aleatorios distintos de [0, n) para la muestra.
    idx = rng.choice(n, size=m, replace=False)
    # Mascara para marcar que posiciones se han seleccionado para la muestra.
    mask = np.zeros(n, dtype=bool)
    mask[idx] = True

    # Numero de posiciones de la muestra donde Alice y Bob difieren, es
    # decir, el numero de errores en la muestra.
    errors = int(np.count_nonzero(keys.alice[mask] != keys.bob[mask]))
    q = errors / m  # QBER: fraccion de errores en la muestra.
    # Incertidumbre de la estimacion del QBER (sigma). Se evita un
    # argumento negativo de la raiz con un minimo de 1e-12.
    sigma = float(np.sqrt(max(q * (1 - q), 1e-12) / m))

    # Claves con los bits que NO fueron seleccionados para la muestra (los
    # que siguen siendo secretos). ~mask selecciona lo no muestreado, y se
    # copia explicitamente para evitar mutaciones accidentales.
    remaining = SiftedKeys(
        alice=keys.alice[~mask].copy(),
        bob=keys.bob[~mask].copy(),
        indices=keys.indices[~mask].copy(),
        n_sent=keys.n_sent,
    )
    return QberEstimate(qber=q, n_sample=m, sigma=sigma, remaining=remaining)
