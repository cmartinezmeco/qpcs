"""src/chaos/keystream.py - de la orbita a los bytes.

Cuantizacion con bits BAJOS, no altos (guia Fase 3, cap. 4.4): la densidad
invariante del mapa logistico con r=4 es rho(x) = 1/(pi*sqrt(x(1-x))), no
uniforme. Los bits de orden alto de x heredan ese sesgo; los de orden bajo
(en torno a la posicion 32) son, a efectos practicos, uniformes.

EL AVISO DE CICLO CORTO (tarea 3.9, guia cap. 4.5)
--------------------------------------------------
Un float64 tiene un numero finito de estados, asi que CUALQUIER orbita en
coma flotante es periodica: la unica pregunta es cual es su periodo. Si la
orbita cicla antes de agotar la imagen, el keystream se repite y el cifrado
cae por reutilizacion de flujo contra si mismo. No se resuelve -no se puede-:
se MIDE y se avisa, que es lo que hace _avisar_si_el_ciclo_es_corto aqui
abajo. La distribucion medida sobre una muestra de claves se publica en el
README (scripts/bench_chaos.py --ciclos).
"""

from __future__ import annotations

import logging

import numpy as np

from .maps import orbita_logistica, orbita_lorenz
from .types import (
    ESCALA_BITS,
    LORENZ_RANGOS,
    PASO_RK4,
    SUBMUESTREO,
    TRANSITORIO,
    ClaveCaotica,
    Keystream,
    Orbita,
)

logger = logging.getLogger(__name__)


def _avisar_si_el_ciclo_es_corto(estados: Orbita, n_bytes: int) -> None:
    """Avisa (logging.WARNING) si la orbita cicla dentro del tramo consumido.

    El criterio es exacto y no necesita a Floyd: dos estados float64
    IDENTICOS tienen exactamente el mismo futuro, luego la orbita cicla
    dentro del tramo generado si y solo si el tramo contiene un estado
    repetido. Un np.unique cuesta O(n log n) -del orden del 15% de lo que
    cuesta generar la propia orbita- frente a los ~80 s que tarda la
    liebre y la tortuga de detectar_ciclo en recorrer dos millones de
    pasos comparando de uno en uno.

    Y basta con mirar las MUESTRAS consumidas, no la orbita entera: si la
    orbita tiene periodo L, la sucesion submuestreada tiene periodo
    L/gcd(L, SUBMUESTREO), que es menor o igual, asi que un ciclo que
    alcance a repetir keystream se ve tambien aqui.

    No lanza: avisa. Un ciclo corto no impide cifrar ni descifrar (la
    cadena sigue siendo reversible), lo que hace es destruir la seguridad
    del esquema, y esa distincion la tiene que ver quien llama, no
    decidirla esta funcion. Convencion del equipo: logging, nunca print.

    Args:
        estados: muestras consumidas. 1-D para el mapa logistico,
            (n, 3) para Lorenz, donde el estado es el vector completo.
        n_bytes: bytes de keystream que se han pedido, solo para el mensaje.
    """
    if estados.shape[0] < 2:
        return

    if estados.ndim == 1:
        repetidos = int(np.unique(estados).size) < estados.shape[0]
    else:
        # Para Lorenz el estado es (x, y, z) entero. Que se repita la x es
        # condicion NECESARIA pero no suficiente, asi que se usa como criba
        # barata sobre una sola columna y solo si salta se paga la
        # comparacion de filas completas, que es bastante mas cara.
        repetidos = int(np.unique(estados[:, 0]).size) < estados.shape[0]
        if repetidos:
            repetidos = int(np.unique(estados, axis=0).shape[0]) < estados.shape[0]

    if repetidos:
        logger.warning(
            "la orbita CICLA dentro de los %d bytes de keystream pedidos: el "
            "flujo se repite y el cifrado es trivialmente roto por "
            "reutilizacion de keystream contra si mismo (guia Fase 3, cap. "
            "4.5). Cambia la clave.",
            n_bytes,
        )


def keystream_logistico(clave: ClaveCaotica, n_bytes: int) -> Keystream:
    """Genera n_bytes deterministas a partir de la clave logistica.

    Receta (ver guia Fase 3, cap. 4.4):

      1. Iterar TRANSITORIO pasos y descartarlos. Es lo que produce la
         sensibilidad a la clave: una diferencia de 1e-15 en x0 se
         amplifica como e^(lambda*n) y tras 1000 pasos las dos orbitas
         no tienen ninguna relacion.

      2. Tomar una muestra cada SUBMUESTREO pasos, para romper la
         correlacion entre valores consecutivos de la recurrencia.

      3. Cuantizar con bits bajos: x * ESCALA_BITS (2^32), luego mod 256.
         Los bits altos llevan el sesgo de la densidad invariante
         rho(x) = 1/(pi sqrt(x(1-x))); los bajos son uniformes.

    Args:
        clave: debe ser de sistema "logistico".
        n_bytes: cuantos bytes generar.

    Returns:
        Array uint8 de longitud n_bytes.
    """
    assert clave.sistema == "logistico", (
        f"keystream_logistico necesita sistema='logistico', recibido "
        f"{clave.sistema!r}"
    )
    assert clave.r is not None, "clave.r no puede ser None para el sistema logistico"

    n_iter = TRANSITORIO + n_bytes * SUBMUESTREO
    orb = orbita_logistica(clave.x0, clave.r, n_iter)
    muestras = orb[TRANSITORIO::SUBMUESTREO][:n_bytes]
    _avisar_si_el_ciclo_es_corto(muestras, n_bytes)
    escalado = muestras * ESCALA_BITS  # x * 2**32
    return (escalado.astype(np.uint64) & 0xFF).astype(np.uint8)


def keystream_lorenz(clave: ClaveCaotica, n_bytes: int) -> Keystream:
    """Genera n_bytes deterministas a partir de la clave de Lorenz.

    Integra con RK4, descarta el transitorio, normaliza cada coordenada
    con los rangos DECLARADOS en LORENZ_RANGOS (nunca medidos: ver guia
    Fase 3, cap. 4.4), y cuantiza igual que en el caso logistico.

    Args:
        clave: debe ser de sistema "lorenz".
        n_bytes: cuantos bytes generar.

    Returns:
        Array uint8 de longitud n_bytes.
    """

    # Cada paso de Lorenz produce 3 coordenadas (x, y, z)
    n_pasos = (n_bytes + 2) // 3
    n_iter = TRANSITORIO + n_pasos * SUBMUESTREO

    u0 = np.array([clave.x0, clave.y0, clave.z0], dtype=np.float64)
    orb = orbita_lorenz(u0, n_iter, PASO_RK4)
    muestras = orb[TRANSITORIO::SUBMUESTREO][:n_pasos]
    _avisar_si_el_ciclo_es_corto(muestras, n_bytes)

    bytes_lista = []
    for i, eje in enumerate(["x", "y", "z"]):
        lo, hi = LORENZ_RANGOS[eje]
        coords = muestras[:, i]
        # Normalización a (0, 1) usando rangos declarados en el contrato (cap. 4.4.4)
        normalizado = (coords - lo) / (hi - lo)
        escalado = normalizado * ESCALA_BITS
        b = (escalado.astype(np.uint64) & 0xFF).astype(np.uint8)
        bytes_lista.append(b)

    # Intercalar las coordenadas: x0, y0, z0, x1, y1, z1, ...
    keystream_mat = np.column_stack(bytes_lista).ravel()
    return keystream_mat[:n_bytes]


def keystream(clave: ClaveCaotica, n_bytes: int) -> Keystream:
    """Punto de entrada unico: despacha segun clave.sistema."""

    if clave.sistema == "logistico":
        return keystream_logistico(clave, n_bytes)
    elif clave.sistema == "lorenz":
        return keystream_lorenz(clave, n_bytes)
    else:
        raise ValueError(f"Sistema desconocido: {clave.sistema}")


def histograma_chi2(datos: Keystream) -> float:
    """Estadistico chi-cuadrado del histograma de 256 valores.

    Bajo la hipotesis de uniformidad, sigue una chi2 con 255 grados de
    libertad (media 255, critico al 5% = 293.25). Ver guia Fase 3, cap. 6.4.
    """

    m = datos.size
    o = np.bincount(datos, minlength=256).astype(np.float64)
    e = m / 256.0
    return float(np.sum((o - e) ** 2 / e))
