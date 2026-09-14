import numpy as np
import pytest
from chaos import orbita_logistica, orbita_lorenz
from chaos.types import LORENZ_RANGOS


def test_logistico_punto_fijo():
    """Con r = 2.5 converge a x* = 1 - 1/r = 0.6. Es teoria, no ajuste."""

    orb = orbita_logistica(0.3, 2.5, 2000)
    assert abs(orb[-1] - 0.6) < 1e-9


def test_logistico_periodo_2():
    """Con r = 3.2 el sistema oscila entre dos valores."""

    orb = orbita_logistica(0.4, 3.2, 5000)
    assert abs(orb[-1] - orb[-3]) < 1e-9  # mismo valor cada 2 pasos
    assert abs(orb[-1] - orb[-2]) > 0.1  # y distinto del contiguo


def test_lorenz_conserva_el_atractor():
    """Tras el transitorio, la orbita esta acotada en los rangos
    declarados en LORENZ_RANGOS. Si se sale, la normalizacion de 3.4
    produciria bytes fuera de rango y el cifrado seria irreversible."""

    orb = orbita_lorenz(np.array([1.0, 1.0, 1.0]), 200_000, h=0.01)
    tras = orb[10_000:]
    for j, eje in enumerate("xyz"):
        lo, hi = LORENZ_RANGOS[eje]
        assert tras[:, j].min() > lo and tras[:, j].max() < hi


def test_rk4_converge_con_el_orden_correcto():
    """El error global de RK4 es O(h^4): al dividir h por 2, el error
    debe caer aproximadamente por 16. Esto valida la implementacion
    contra la teoria, no contra otra implementacion.

    Se compara contra una solucion de referencia obtenida con un paso
    mucho mas fino (h/64), que hace de "verdad" para medir el error de
    las otras dos.
    """
    u0 = np.array([1.0, 1.0, 1.0])
    t_total = 1.0

    h_grueso = 0.02
    h_fino = h_grueso / 2
    h_ref = h_grueso / 64

    n_grueso = int(t_total / h_grueso)
    n_fino = int(t_total / h_fino)
    n_ref = int(t_total / h_ref)

    ref = orbita_lorenz(u0, n_ref, h=h_ref)[-1]
    grueso = orbita_lorenz(u0, n_grueso, h=h_grueso)[-1]
    fino = orbita_lorenz(u0, n_fino, h=h_fino)[-1]

    error_grueso = np.linalg.norm(grueso - ref)
    error_fino = np.linalg.norm(fino - ref)

    # Al dividir h por 2, el error de un metodo O(h^4) cae por ~16.
    # Se exige un factor de al menos 8 para dar margen sin ser laxo.
    assert error_fino > 0, "el paso fino no puede tener error exactamente cero"
    assert error_grueso / error_fino > 8.0


@pytest.mark.parametrize("x0", [0.0, 1.0])
def test_x0_en_un_punto_fijo_se_rechaza(x0):
    """Caso borde de la tarea 3.9: x0 = 0 y x0 = 1 son
    los dos puntos fijos triviales del mapa y tienen que dar ValueError.

    Con x0 = 0 la orbita es cero para siempre; con x0 = 1 el primer paso la
    lleva a cero y se queda ahi. En los dos casos el keystream seria un solo
    byte repetido.

    Y no es una comprobacion de cortesia: SIN esta guarda, x0 = 0 llegaba
    hasta lyapunov_logistico y salia declarado CAOTICO. La derivada del mapa
    en x = 0 vale r, asi que el promedio de ln|f'| da ln(4) = 1.386, muy por
    encima de UMBRAL_LYAPUNOV. El punto fijo mas degenerado del mapa pasaba
    la validacion de la tarea 3.3 con nota (medido antes de anadir la guarda).
    """
    with pytest.raises(ValueError, match="puntos fijos"):
        orbita_logistica(x0, 4.0, 100)


def test_x0_fuera_de_cero_uno_tambien_se_rechaza():
    """La guarda es sobre el intervalo ABIERTO, no solo sobre los extremos:
    fuera de (0, 1) el mapa diverge a -inf y el keystream serian NaN."""

    with pytest.raises(ValueError, match=r"fuera de \(0, 1\)"):
        orbita_logistica(1.5, 4.0, 100)
