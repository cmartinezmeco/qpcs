"""src/chaos/lyapunov.py - exponente de Lyapunov y validacion del caos.

El logaritmo SI es una funcion trascendente, pero eso aqui no rompe el
determinismo: lambda es un diagnostico que decide si una clave es valida,
y no entra en el keystream. Puede diferir en el
bit doce entre maquinas y no afecta a nada.
"""

from __future__ import annotations

import numpy as np

from .maps import _campo_lorenz, orbita_logistica
from .types import (
    PASO_RK4,
    UMBRAL_LYAPUNOV,
    DiagnosticoCaos,
    Orbita,
)


def lyapunov_logistico(
    x0: float, r: float, n: int = 100_000, transitorio: int = 1000
) -> DiagnosticoCaos:
    """Exponente de Lyapunov del mapa logistico.

    lambda = (1/N) * sum ln|f'(x_n)|, con f'(x) = r * (1 - 2x).

    Para r=4 el valor exacto es ln(2) = 0.6931471805... (el mapa logistico
    con r=4 es conjugado con el mapa de la tienda).
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
    return DiagnosticoCaos(
        lyapunov=lam,
        n_iteraciones=n,
        sigma=sigma,
        es_caotico=lam > UMBRAL_LYAPUNOV,
        ciclo_detectado=None,
    )


def espectro_lyapunov_lorenz(
    u0: Orbita | None = None,
    n: int = 50_000,
    tau: float = 0.5,
    transitorio: int = 2000,
) -> tuple[float, float, float]:
    """Espectro completo de exponentes de Lyapunov de Lorenz (Benettin).

    Devuelve (lambda_1, lambda_2, lambda_3). Verificacion gratis: la suma
    de los tres debe igualar -(sigma + 1 + beta) = -13.6666..., que es la
    divergencia del campo vectorial.

    Args:
        u0: condicion inicial. Si None, se usa (1.0, 1.0, 1.0).
        n: numero de renormalizaciones del algoritmo de Benettin.
        tau: intervalo de tiempo entre renormalizaciones.
        transitorio: pasos de RK4 a descartar ANTES de la primera
            renormalizacion. Sin esto, si u0 no esta ya sobre el
            atractor (p.ej. el [1,1,1] por defecto), la fase inicial
            de acomodacion contamina el promedio.

    Returns:
        Los tres exponentes, de mayor a menor.
    """

    dt = PASO_RK4
    pasos_por_tau = int(round(tau / dt))

    if u0 is None:
        u = np.array([1.0, 1.0, 1.0], dtype=np.float64)
    else:
        u = np.asarray(u0, dtype=np.float64).copy()

    # Descartar el transitorio ANTES de empezar a medir. Es la misma idea
    # que TRANSITORIO en lyapunov_logistico, aplicada aqui.
    for _ in range(transitorio):
        k1 = _campo_lorenz(u)
        k2 = _campo_lorenz(u + (dt / 2.0) * k1)
        k3 = _campo_lorenz(u + (dt / 2.0) * k2)
        k4 = _campo_lorenz(u + dt * k3)
        u = u + (dt / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)

    # Matriz identidad 3x3 para los 3 vectores ortonormales de perturbacion (Benettin)
    Q = np.eye(3, dtype=np.float64)
    acumuladores = np.zeros(3, dtype=np.float64)
    epsilon = 1e-8

    for _ in range(n):
        # 1. Integrar la trayectoria de referencia Y las 3 perturbadas
        # EN PARALELO, el mismo numero de pasos cada una. Las cuatro
        # arrancan del mismo punto temporal y avanzan el mismo tau.
        #
        # BUG ENCONTRADO AQUI (investigacion completa en el PR de la
        # tarea 3.4): la version original
        # integraba la referencia un tau, y LUEGO integraba las
        # perturbadas OTRO tau mas desde ahi, comparando al final contra
        # la referencia SIN ese segundo tau. Eso compara dos puntos con
        # un tau entero de desfase temporal en vez de comparar la misma
        # ventana temporal. Con lambda_1 ~ 0.9 y tau=0.5 ese desfase
        # bastaba para que lambda_1 saliera ~42 en vez de ~0.9: NO era
        # un problema de precision ni de "salirse del regimen lineal",
        # era comparar el minuto 1 de una trayectoria contra el minuto 2
        # de la otra.
        perturbaciones = u + epsilon * Q
        u_sig = u.copy()
        nuevas_pert = perturbaciones.copy()

        for _ in range(pasos_por_tau):
            # Avanza la referencia un paso de RK4.
            k1 = _campo_lorenz(u_sig)
            k2 = _campo_lorenz(u_sig + (dt / 2.0) * k1)
            k3 = _campo_lorenz(u_sig + (dt / 2.0) * k2)
            k4 = _campo_lorenz(u_sig + dt * k3)
            u_sig = u_sig + (dt / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)

            # Avanza las 3 perturbadas el MISMO paso, en paralelo.
            for j in range(3):
                up = nuevas_pert[j]
                k1 = _campo_lorenz(up)
                k2 = _campo_lorenz(up + (dt / 2.0) * k1)
                k3 = _campo_lorenz(up + (dt / 2.0) * k2)
                k4 = _campo_lorenz(up + dt * k3)
                nuevas_pert[j] = up + (dt / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)

        u = u_sig

        # 2. Vectores de separacion, todavia SIN ortogonalizar.
        V = (nuevas_pert - u) / epsilon

        # 3. Gram-Schmidt de V, EN ESTE ORDEN: se ortogonaliza primero
        # y se acumulan las normas de la ortogonalizacion (r_jj de la
        # descomposicion QR), no la norma bruta de V antes de ortogonalizar.
        # Sin este orden, las tres direcciones colapsan hacia la de
        # maximo crecimiento en pocos pasos, y lo que se acumula en las
        # tres posiciones acaba siendo la misma tasa (lambda_1 repetido
        # tres veces). Este fue el SEGUNDO bug encontrado, ya corregido
        # antes de dar con el del desfase temporal de arriba.
        for j in range(3):
            for k in range(j):
                proyeccion = np.dot(V[j], Q[k])
                V[j] -= proyeccion * Q[k]
            r_jj = float(np.linalg.norm(V[j]))
            if r_jj == 0.0:
                r_jj = 1e-300
            acumuladores[j] += np.log(r_jj)
            Q[j] = V[j] / r_jj

    # Promediar sobre el tiempo total (n * tau)
    tiempo_total = n * tau
    espectro = acumuladores / tiempo_total
    espectro_ordenado = sorted(espectro, reverse=True)
    return (
        float(espectro_ordenado[0]),
        float(espectro_ordenado[1]),
        float(espectro_ordenado[2]),
    )


def detectar_ciclo(orb: Orbita) -> int | None:
    """Longitud del ciclo de una orbita en precision finita, por Floyd.

    Cualquier orbita en float64 es periodica (espacio de estados finito).
    Esta funcion mide esa longitud en vez de ignorarla.

    Returns:
        La longitud del ciclo detectado, o None si no se detecta dentro
        del numero de pasos disponible en la orbita.
    """

    n = len(orb)
    if n < 3:
        return None

    # Algoritmo de Floyd (la liebre y la tortuga) adaptado a la secuencia
    # de la orbita precalculada. Tolerancia estricta de coma flotante
    # para la igualdad en precision finita.
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
                if (
                    np.allclose(orb[inicio_ciclo], orb[current], atol=1e-14, rtol=0)
                    or current <= inicio_ciclo
                ):
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
