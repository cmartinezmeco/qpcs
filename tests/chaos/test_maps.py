def test_logistico_punto_fijo():
    """Con r = 2.5 converge a x* = 1 - 1/r = 0.6. Es teoria, no ajuste."""

    orb = orbita_logistica(0.3, 2.5, 2000)
    assert abs(orb[-1] - 0.6) < 1e-9

def test_logistico_periodo_2():
    """Con r = 3.2 el sistema oscila entre dos valores."""

    orb = orbita_logistica(0.4, 3.2, 5000)
    assert abs(orb[-1] - orb[-3]) < 1e-9 # mismo valor cada 2 pasos
    assert abs(orb[-1] - orb[-2]) > 0.1 # y distinto del contiguo

def test_lorenz_conserva_el_atractor():
    """Tras el transitorio, la orbita esta acotada en los rangos
    declarados en LORENZ_RANGOS. Si se sale, la normalizacion de 3.4
    produciria bytes fuera de rango y el cifrado seria irreversible."""

    orb = orbita_lorenz(np.array([1.0, 1.0, 1.0]), 200_000)
    tras = orb[10_000:]
    for j, eje in enumerate("xyz"):
        lo, hi = LORENZ_RANGOS[eje]
        assert tras[:, j].min() > lo and tras[:, j].max() < hi

def test_rk4_converge_con_el_orden_correcto():
    """El error global de RK4 es O(h^4): al dividir h por 2, el error
    debe caer aproximadamente por 16. Esto valida la implementacion
    contra la teoria, no contra otra implementacion."""