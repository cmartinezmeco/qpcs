"""src/chaos/lyapunov.py - exponente de Lyapunov y validacion del caos.

El logaritmo SI es una funcion trascendente, pero eso aqui no rompe el
determinismo: lambda es un diagnostico que decide si una clave es valida,
y no entra en el keystream (guia Fase 3, cap. 4.2). Puede diferir en el
bit doce entre maquinas y no afecta a nada.
"""

from __future__ import annotations

from .maps import _campo_lorenz, orbita_logistica, orbita_lorenz
from .types import LORENZ_BETA, LORENZ_RHO, LORENZ_SIGMA, PASO_RK4, DiagnosticoCaos, Orbita, UMBRAL_LYAPUNOV


def lyapunov_logistico(
    x0: float, r: float, n: int = 100_000, transitorio: int = 1000
) -> DiagnosticoCaos:
    """Exponente de Lyapunov del mapa logistico.

    lambda = (1/N) * sum ln|f'(x_n)|, con f'(x) = r * (1 - 2x).

    Para r=4 el valor exacto es ln(2) = 0.6931471805... (el mapa logistico
    con r=4 es conjugado con el mapa de la tienda, ver guia Fase 3 cap. 3.4).
    Ese numero es el test.

    Args:
        x0: condicion inicial.
        r: parametro del mapa.
        n: iteraciones usadas para el promedio, tras el transitorio.
        transitorio: iteraciones descartadas antes de empezar a promediar.

    Returns:
        DiagnosticoCaos con lambda, su error estandar, y es_caotico
        decidido contra UMBRAL_LYAPUNOV.
    """
    orb = orbita_logistica(x0, r, n + transitorio)[transitorio:]
    derivadas = np.abs(r * (1.0 - 2.0 * orb))
    # Proteccion: si la orbita cae exactamente en x = 0.5, la derivada es
    # 0 y el log es -inf. Es de medida nula pero pasa con float.
    derivadas = np.maximum(derivadas, 1e-300)
    logs = np.log(derivadas)
    lam = float(logs.mean())
    sigma = float(logs.std(ddof=1) / np.sqrt(logs.size))
    return DiagnosticoCaos(lyapunov=lam, n_iteraciones=n, sigma=sigma,es_caotico=lam > UMBRAL_LYAPUNOV,ciclo_detectado=None)


def espectro_lyapunov_lorenz(
    u0: Orbita | None = None, n: int = 50_000, tau: float = 0.5
) -> tuple[float, float, float]:
    """Espectro completo de exponentes de Lyapunov de Lorenz (Benettin).

    Devuelve (lambda_1, lambda_2, lambda_3). Verificacion gratis: la suma
    de los tres debe igualar -(sigma + 1 + beta) = -13.6666..., que es la
    divergencia del campo vectorial (guia Fase 3, cap. 3.4).

    Args:
        u0: condicion inicial. Si None, se usa (1.0, 1.0, 1.0).
        n: numero de renormalizaciones del algoritmo de Benettin.
        tau: intervalo de tiempo entre renormalizaciones.

    Returns:
        Los tres exponentes, de mayor a menor.
    """

    dt = PASO_RK4
    pasos_por_tau = int(round(tau / dt))

    if u0 is None:
        u = np.array([1.0, 1.0, 1.0], dtype=np.float64)
    else:
        u = np.asarray(u0, dtype=np.float64).copy()

    # Matriz identidad 3x3 para los 3 vectores ortonormales de perturbacion (Benettin)
    Q = np.eye(3, dtype=np.float64)
    acumuladores = np.zeros(3, dtype=np.float64)

    for _ in range(n):
        # 1. Integrar la trayectoria de referencia durante el intervalo tau
        for _ in range(pasos_por_tau):
            k1 = _campo_lorenz(u)
            k2 = _campo_lorenz(u + (dt / 2.0) * k1)
            k3 = _campo_lorenz(u + (dt / 2.0) * k2)
            k4 = _campo_lorenz(u + dt * k3)
            u = u + (dt / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)

        # 2. Integrar las 3 trayectorias perturbadas linealmente / por vectores
        perturbaciones = u + 1e-8 * Q
        nuevas_pert = np.empty_like(perturbaciones)
        
        for j in range(3):
            u_p = perturbaciones[j]
            for _ in range(pasos_por_tau):
                k1 = _campo_lorenz(u_p)
                k2 = _campo_lorenz(u_p + (dt / 2.0) * k1)
                k3 = _campo_lorenz(u_p + (dt / 2.0) * k2)
                k4 = _campo_lorenz(u_p + dt * k3)
                u_p = u_p + (dt / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)
            nuevas_pert[j] = u_p

        # 3. Calcular las separaciones y aplicar ortonormalizacion de Gram-Schmidt
        diferencias = nuevas_pert - u
        
        for j in range(3):
            norma = float(np.linalg.norm(diferencias[j]))
            if norma == 0.0:
                norma = 1e-300
            acumuladores[j] += np.log(norma / 1e-8)
            # Normalizar el vector para el siguiente paso
            Q[j] = diferencias[j] / norma

        # Ortogonalizacion de Gram-Schmidt modificada para mantener base ortonormal
        for j in range(3):
            for k in range(j):
                prod_escalar = np.dot(Q[j], Q[k])
                Q[j] -= prod_escalar * Q[k]
            norma_q = float(np.linalg.norm(Q[j]))
            if norma_q > 0:
                Q[j] /= norma_q

    # Promediar sobre el tiempo total (n * tau)
    tiempo_total = n * tau
    espectro = acumuladores / tiempo_total
    # Ordenar de mayor a menor por convencion
    espectro_ordenado = sorted(espectro, reverse=True)
    return (float(espectro_ordenado[0]), float(espectro_ordenado[1]), float(espectro_ordenado[2]))


def detectar_ciclo(orb: Orbita) -> int | None:
    """Longitud del ciclo de una orbita en precision finita, por Floyd.

    Cualquier orbita en float64 es periodica (espacio de estados finito).
    Esta funcion mide esa longitud en vez de ignorarla (guia Fase 3, cap. 4.5).

    Returns:
        La longitud del ciclo detectado, o None si no se detecta dentro
        del numero de pasos disponible en la orbita.
    """

    n = len(orb)
    if n < 3:
        return None

    # Algoritmo de Floyd (la liebre y la tortuga) adaptado a la secuencia de la orbita precalculada
    # Usamos una tolerancia estricta de coma flotante para la igualdad en precision finita
    tortoise = 0
    hare = 1

    while hare < n:
        if np.allclose(orb[tortoise], orb[hare], atol=1e-14, rtol=0):
            # Ciclo detectado, ahora medimos la longitud exacta recorriendo el bucle
            inicio_ciclo = tortoise
            current = hare
            longitud = 0
            while True:
                current = (current + 1) % n
                longitud += 1
                if np.allclose(orb[inicio_ciclo], orb[current], atol=1e-14, rtol=0) or current <= inicio_ciclo:
                    break
            return max(longitud, 1)

        tortoise += 1
        hare += 2
        if hare >= n:
            break

    # Metodo alternativo de respaldo: buscar si el ultimo estado se repite en la orbita
    val_final = orb[-1]
    for i in range(n - 2, -1, -1):
        if np.allclose(orb[i], val_final, atol=1e-14, rtol=0):
            return n - 1 - i

    return None
