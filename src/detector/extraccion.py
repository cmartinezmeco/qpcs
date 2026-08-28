"""src/detector/extraccion.py - destilar bits uniformes con Toeplitz.

Reutiliza qkd.privacy_amplify, el mismo extractor de la tarea 1.6. El
leftover hash lemma no sabe de donde viene la min-entropia, solo necesita
saber cuanta hay: por eso el mismo codigo sirve para destilar una clave
de BB84 y para destilar entropia de un detector (guia Fase 4, cap. 4.4).

ell = floor(n * H_min - 2 log2(1/eps))

Es la misma formula de la tarea 1.6 SIN el termino leak_ec: alli se
restaban los bits que Cascade publicaba por el canal, y aqui no hay canal
publico que filtre nada.
"""

from __future__ import annotations

from .types import Bits, EstimacionEntropia, ResultadoExtraccion


def extraer(
    simbolos: Bits, estimacion: EstimacionEntropia, epsilon: float
) -> ResultadoExtraccion:
    """Comprime los simbolos digitalizados hasta la longitud que la
    min-entropia sostiene, con el extractor de Toeplitz del modulo 1.

    La semilla de Toeplitz se genera con os.urandom y NO se siembra: tiene
    que ser independiente de la fuente, o el leftover hash lemma deja de
    aplicar. Mismo criterio que las claves de ML-KEM en la fase 2.

    Args:
        simbolos: los bits digitalizados (salida de entropia.digitalizar).
        estimacion: el resultado de entropia.estimar_entropia sobre esos
            mismos simbolos.
        epsilon: parametro de seguridad. El mismo 1e-9 que la tarea 1.6.

    Returns:
        ResultadoExtraccion con los bits finales y su validacion.
    """
    raise NotImplementedError
