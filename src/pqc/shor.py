"""src/pqc/shor.py - tareas 2.2 / 2.3 (Gonzalo). Algoritmo de Shor para N=15.

Shor factoriza N reduciendo el problema a HALLAR EL ORDEN de un entero a
modulo N: el menor r > 0 tal que a^r == 1 (mod N). La parte cuantica es la
estimacion de fase (QPE) sobre el operador "multiplicar por a mod N", que
devuelve una fase s/r; de ahi, por fracciones continuas, sale r; y con r par y
a^(r/2) != -1 (mod N), gcd(a^(r/2) +/- 1, N) da un factor no trivial.

N=15 es el caso didactico historico (primer Shor experimental, IBM 2001) y es
REQUISITO DURO de esta tarea. N=21 es el objetivo firme con plan B documentado
(ver la guia de Fase 2); no hace falta bloquearse en el.

Convencion del proyecto: todo lo estocastico recibe un np.random.Generator
EXPLICITO (la eleccion de la base `a` y el muestreo de shots), nunca
aleatoriedad global. La forma de la salida es el contrato `FactorizacionShor`
de `types.py`.

Referencia: P. W. Shor, "Polynomial-Time Algorithms for Prime Factorization
and Discrete Logarithms on a Quantum Computer", SIAM J. Comput. 26 (1997).
"""

from __future__ import annotations

from fractions import Fraction
from math import gcd

import numpy as np
from qiskit import QuantumCircuit, transpile
from qiskit.circuit import Gate
from qiskit_aer import AerSimulator

from .types import FactorizacionShor


def qft_dagger(n: int) -> QuantumCircuit:
    """Transformada cuantica de Fourier INVERSA sobre n qubits (QFT^dagger).

    Es el bloque final de la estimacion de fase: lleva la fase codificada en
    las amplitudes al registro de conteo, listo para medir. Se construye
    como la inversa de la QFT (swaps + rotaciones controladas con signo
    negativo) y se devuelve como circuito reutilizable.
    """
    qc = QuantumCircuit(n, name="QFT_dg")
    for q in range(n // 2):
        qc.swap(q, n - q - 1)
    for j in range(n):
        for m in range(j):
            qc.cp(-np.pi / float(2 ** (j - m)), m, j)
        qc.h(j)
    return qc


def c_amod15(a: int, power: int) -> Gate:
    """Puerta controlada que multiplica por a^power modulo 15.

    El operador U|y> = |a*y mod 15> elevado a la potencia `power`, en su
    version controlada, para engancharlo a cada qubit del registro de
    conteo de la estimacion de fase. Solo estan permitidos los `a` coprimos
    con 15 ({2, 4, 7, 8, 11, 13}); con otros `a` la funcion falla.

    OJO CON EL EXPONENTE: esta funcion implementa a^power, NO a^(2^power).
    El a^(2^q) que necesita la estimacion de fase sale de que quien la llama
    -`circuito_orden_15`- le pasa power = 2**q. Llamarla con `q` en vez de
    con `2**q` da un circuito silenciosamente incorrecto.

    POR QUE `power % 4` Y NO `power`: no es una optimizacion oportunista, es
    una identidad exacta. El bloque que se repite abajo es una rotacion
    ciclica de los cuatro qubits (R, con R^4 = I) seguida, para
    a in {7, 11, 13}, de X sobre los cuatro, que es v -> 15 - v y conmuta con
    la rotacion. Luego BLOQUE^4 = I sobre los DIECISEIS estados de la base
    (no solo sobre los coprimos), igual que a^4 == 1 (mod 15) para las seis
    bases porque el exponente del grupo (Z/15)* es 4. Sin el modulo,
    `circuito_orden_15` con n_count=8 construye 1+2+4+...+128 = 255 copias del
    bloque, de las cuales 252 son la identidad; con el son 3. Las puertas de
    q >= 2 quedan vacias, que es justo lo correcto: la fase s/4 solo tiene dos
    bits significativos y exp(2*pi*i*(s/4)*2^q) = 1 para q >= 2.
    """
    if a not in (2, 4, 7, 8, 11, 13):
        raise ValueError("a debe ser coprimo con 15: {2,4,7,8,11,13}")
    U = QuantumCircuit(4)
    for _ in range(power % 4):
        if a in (2, 13):
            U.swap(2, 3)
            U.swap(1, 2)
            U.swap(0, 1)
        if a in (7, 8):
            U.swap(0, 1)
            U.swap(1, 2)
            U.swap(2, 3)
        if a in (4, 11):
            U.swap(1, 3)
            U.swap(0, 2)
        if a in (7, 11, 13):
            for q in range(4):
                U.x(q)
    gate = U.to_gate()
    gate.name = f"{a}^{power} mod 15"
    return gate.control()


def circuito_orden_15(a: int, n_count: int = 8) -> QuantumCircuit:
    """Circuito completo de estimacion de fase para el orden de a mod 15.

    n_count qubits de conteo en superposicion (Hadamard), las `c_amod15`
    controladas, la `qft_dagger` y la medida del registro de conteo.
    n_count=8 da resolucion de fase suficiente para los ordenes de N=15
    (r in {1,2,4}).

    El exponente que recibe cada puerta es 2**q, y ES AQUI donde se convierte
    en el a^(2^q) de la estimacion de fase: `c_amod15` por si sola implementa
    a^power (ver su docstring).
    """
    qc = QuantumCircuit(n_count + 4, n_count)
    for q in range(n_count):
        qc.h(q)
    qc.x(n_count)
    for q in range(n_count):
        qc.append(c_amod15(a, 2**q), [q] + list(range(n_count, n_count + 4)))
    qc.append(qft_dagger(n_count), range(n_count))
    qc.measure(range(n_count), range(n_count))
    return qc


def medir_fase_15(a: int, rng: np.random.Generator, n_count: int = 8) -> float:
    """Ejecuta `circuito_orden_15` y devuelve UNA fase medida s/r en [0, 1).

    Lee el registro de conteo (entero m) y devuelve m / 2**n_count. La
    semilla del simulador se DERIVA de `rng` (nunca de un `seed` suelto),
    para que misma semilla de rng -> misma fase, y los tests no parpadeen.
    El circuito se transpila al set de puertas del backend antes de
    ejecutarlo: AerSimulator no sabe correr las puertas personalizadas
    de `c_amod15` (nombradas "a^k mod 15") sin descomponerlas primero.

    Un disparo y no varios a proposito: la factorizacion consume UNA fase por
    intento y reintenta con otra base si no le sirve. Para la distribucion
    completa de la fase (el histograma de la figura 3 y del dashboard) esta
    `histograma_fases_15`, que si ejecuta muchos disparos y los devuelve
    todos. Antes habia aqui un parametro `shots` que se le pasaba al backend
    y del que solo se leia el primer disparo: simulaba de mas y tiraba el
    resto.
    """
    seed = int(rng.integers(1_000_000))
    backend = AerSimulator(seed_simulator=seed)
    qc = circuito_orden_15(a, n_count)
    qc_transpilado = transpile(qc, backend)
    result = backend.run(qc_transpilado, shots=1, memory=True).result()
    medido = int(result.get_memory()[0], 2)
    return float(medido) / float(2**n_count)


def histograma_fases_15(
    a: int, rng: np.random.Generator, n_count: int = 8, shots: int = 2048
) -> dict[float, int]:
    """Distribucion de la fase medida sobre `shots` disparos del circuito.

    Devuelve {fase: veces que salio}, con la fase en [0, 1) igual que
    `medir_fase_15`. Es lo que necesita un histograma: los picos caen en los
    multiplos de 1/r y esa es la prueba VISUAL de que la estimacion de fase
    funciona.

    Existe para que el dashboard y `scripts/make_pqc_plots.py` no tengan que
    reimplementar cada uno el mismo transpile + run + conversion de bitstring
    a fase, que es lo que hacian (dos copias de las mismas siete lineas,
    documentadas en los dos sitios como "excepcion consciente" a la regla de
    que ni el script ni el dashboard reimplementan logica del modulo). Con
    esta funcion la excepcion desaparece.

    Como todo lo estocastico del modulo, recibe un np.random.Generator
    EXPLICITO y deriva de el la semilla del simulador: misma semilla de rng,
    mismo histograma.
    """
    seed = int(rng.integers(1_000_000))
    backend = AerSimulator(seed_simulator=seed)
    qc = circuito_orden_15(a, n_count)
    counts = backend.run(transpile(qc, backend), shots=shots).result().get_counts()
    return {int(bits, 2) / 2**n_count: int(veces) for bits, veces in counts.items()}


def orden_desde_fase(fase: float, n: int = 15) -> int | None:
    """Recupera el orden r a partir de la fase medida por fracciones continuas.

    La fase ideal es s/r con 0 <= s < r; la aproximacion racional de `fase`
    con denominador < n da el candidato a r. Devuelve None si la fase es 0
    o no produce un denominador util (caso que el llamador descarta).
    """
    frac = Fraction(fase).limit_denominator(n)
    r = frac.denominator
    return r if r > 1 else None


def factorizar_15(
    rng: np.random.Generator, max_intentos: int = 20
) -> FactorizacionShor:
    """Factoriza N=15 con el algoritmo de Shor.

    Bucle: elige `a` coprimo con 15 con `rng`, mide la fase, deriva el
    orden r, COMPRUEBA que r es el orden de verdad y prueba
    gcd(a^(r/2) +/- 1, N). Reintenta hasta `max_intentos` veces si r no es el
    orden, si es impar o si a^(r/2) == -1 (mod N). Devuelve un
    `FactorizacionShor` con:

      - n:            el N factorizado (15)
      - factores:     (p, q) con p*q == N
      - a:            la base que funciono
      - orden:        el orden r hallado, verificado con a^r == 1 (mod N)
      - intentos:     cuantas iteraciones costo
      - fase_medida:  la fase de la iteracion que tuvo exito
      - ok:           True si p*q == N con p, q no triviales

    SI FRACASA (ok=False, tras agotar `max_intentos`) los campos llevan
    CENTINELAS, no medidas: factores=(1, N), a=0, orden=0, fase_medida=0.0 e
    intentos=max_intentos. Ninguno de esos ceros es una base, un orden ni una
    fase: significan "no hay dato". Quien los pinte tiene que mirar `ok`
    ANTES (el dashboard lo hace en la pestana Shor). a=0 en particular NO es
    una base valida: pasarselo a `c_amod15` levanta ValueError, que es
    exactamente lo que se quiere de un centinela.

    N=15 es requisito duro; N=21 objetivo firme (ver docstring del modulo).
    """
    N = 15
    coprimos = [2, 4, 7, 8, 11, 13]
    for intento in range(1, max_intentos + 1):
        a = int(rng.choice(coprimos))
        g = gcd(a, N)
        if g > 1:
            # RAMA INALCANZABLE HOY, y a proposito: `coprimos` son literalmente
            # los seis coprimos con 15, asi que gcd(a, 15) == 1 siempre. Se
            # queda porque es el "golpe de suerte" del algoritmo de Shor (si
            # la base sorteada comparte factor con N, ya esta factorizado sin
            # tocar el ordenador cuantico) y es la primera linea que hara
            # falta el dia que esto se generalice a N != 15, donde sortear
            # entre TODOS los a < N si puede dar un gcd > 1. Sin ella, esa
            # generalizacion tendria un agujero silencioso.
            return FactorizacionShor(N, (g, N // g), a, 1, intento, 0.0, ok=True)

        phi = medir_fase_15(a, rng, n_count=8)
        r = orden_desde_fase(phi, N)
        # pow(a, r, N) != 1 significa que r NO es el orden de a, y pasa a
        # menudo: con a=7 (orden 4) la fase 2/4 = 0.5 tiene como mejor
        # convergente 1/2, y las fracciones continuas devuelven r=2. Con r=2
        # la aritmetica de abajo AUN ASI factoriza (x = 7, gcd(6,15) = 3), asi
        # que el fallo no se veia en los factores; lo que quedaba mal era el
        # campo `orden`, que se publicaba como si fuera el orden en la metrica
        # del dashboard y en las lineas de referencia del histograma. Un
        # cuarto de las medidas de cada base de orden 4 caia aqui.
        if r is None or r % 2 != 0 or pow(a, r, N) != 1:
            continue

        x = pow(a, r // 2, N)
        if x == N - 1:
            continue

        p, q = gcd(x - 1, N), gcd(x + 1, N)
        if 1 < p < N:
            return FactorizacionShor(N, (p, N // p), a, r, intento, phi, ok=True)
        if 1 < q < N:
            return FactorizacionShor(N, (q, N // q), a, r, intento, phi, ok=True)

    return FactorizacionShor(N, (1, N), 0, 0, max_intentos, 0.0, ok=False)
