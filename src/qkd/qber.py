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
    n = keys.alice.size # Número de bits cribados (donde Alice y Bob usaron la misma base). Se obtiene del tamaño del array de bits de Alice en la clave cribada.
    m = int(round(sample_fraction * n)) # Número de bits en la muestra
    if m == 0:
        raise ValueError("muestra vacia: no se puede estimar el QBER")
    
    idx = rng.choice(n, size=m, replace=False) # Selecciona m índices aleatorios distintos del rango [0, n) para formar la muestra.
    mask = np.zeros(n, dtype=bool) # Esta máscara se usará para marcar qué posiciones se han seleccionado para la muestra.
    mask[idx] = True

    errors = int(np.count_nonzero(keys.alice[mask] != keys.bob[mask])) # Cuenta el número de posiciones en la muestra donde los bits de Alice y Bob difieren, es decir, el número de errores en la muestra.
    q = errors / m # Calcula el QBER como la fracción de errores en la muestra.
    sigma = float(np.sqrt(max(q * (1 - q), 1e-12) / m)) # Calcula la incertidumbre de la estimación del QBER usando la sigma (desviación estándar). Se asegura que el argumento de la raíz cuadrada no sea negativo usando max con un valor muy pequeño (1e-12) para evitar errores numéricos.

    remaining = SiftedKeys(alice=keys.alice[~mask].copy(), 
                           bob=keys.bob[~mask].copy(), 
                           indices=keys.indices[~mask].copy(), 
                           n_sent=keys.n_sent) # Crea un nuevo objeto SiftedKeys con los bits de Alice y Bob que no fueron seleccionados para la muestra (los bits todavía "secretos"). Uso ~mask para seleccionar las posiciones que no están en la muestra y hago una copia explícita de los arrays para evitar mutaciones accidentales.
    return QberEstimate(qber=q, n_sample=m, sigma=sigma, remaining=remaining)