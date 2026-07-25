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
    """Puerta controlada que multiplica por a^(2^power) modulo 15.

    El operador U|y> = |a*y mod 15> elevado a la potencia 2^power, en su
    version controlada, para engancharlo a cada qubit del registro de
    conteo de la estimacion de fase. Solo estan permitidos los `a` coprimos
    con 15 ({2, 4, 7, 8, 11, 13}); con otros `a` la funcion falla.
    """
    if a not in (2, 4, 7, 8, 11, 13):
        raise ValueError("a debe ser coprimo con 15: {2,4,7,8,11,13}")
    U = QuantumCircuit(4)
    for _ in range(power):
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


def medir_fase_15(
    a: int, rng: np.random.Generator, n_count: int = 8, shots: int = 1
) -> float:
    """Ejecuta `circuito_orden_15` y devuelve la fase medida s/r en [0, 1).

    Lee el registro de conteo (entero m) y devuelve m / 2**n_count. La
    semilla del simulador se DERIVA de `rng` (nunca de un `seed` suelto),
    para que misma semilla de rng -> misma fase, y los tests no parpadeen.
    El circuito se transpila al set de puertas del backend antes de
    ejecutarlo: AerSimulator no sabe correr las puertas personalizadas
    de `c_amod15` (nombradas "a^k mod 15") sin descomponerlas primero.
    """
    seed = int(rng.integers(1_000_000))
    backend = AerSimulator(seed_simulator=seed)
    qc = circuito_orden_15(a, n_count)
    qc_transpilado = transpile(qc, backend)
    result = backend.run(qc_transpilado, shots=shots, memory=True).result()
    medido = int(result.get_memory()[0], 2)
    return float(medido) / float(2**n_count)


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
    orden r y prueba gcd(a^(r/2) +/- 1, N). Reintenta hasta `max_intentos`
    veces si r es impar o a^(r/2) == -1 (mod N). Devuelve un
    `FactorizacionShor` con:

      - n:            el N factorizado (15)
      - factores:     (p, q) con p*q == N (o (1, N) si fracasa)
      - a:            la base que funciono (o la ultima probada)
      - orden:        el orden r hallado
      - intentos:     cuantas iteraciones costo
      - fase_medida:  la fase de la iteracion que tuvo exito
      - ok:           True si p*q == N con p, q no triviales

    N=15 es requisito duro; N=21 objetivo firme (ver docstring del modulo).
    """
    N = 15
    coprimos = [2, 4, 7, 8, 11, 13]
    for intento in range(1, max_intentos + 1):
        a = int(rng.choice(coprimos))
        g = gcd(a, N)
        if g > 1:
            return FactorizacionShor(N, (g, N // g), a, 1, intento, 0.0, ok=True)

        phi = medir_fase_15(a, rng, n_count=8)
        r = orden_desde_fase(phi, N)
        if r is None or r % 2 != 0:
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
