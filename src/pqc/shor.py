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

import numpy as np
from qiskit import QuantumCircuit
from qiskit.circuit import Gate

from .types import FactorizacionShor

# Parte de la tarea 5.3 """src/pqc/shor.py (envoltorio clasico)"""
from fractions import Fraction
from math import gcd
# from .shor import medir_fase_15 # la parte cuantica (2.2), no hay que ponerlo porque lo estamos haciendo en el mismo archivo.

def qft_dagger(n: int) -> QuantumCircuit:
    """Transformada cuantica de Fourier INVERSA sobre n qubits (QFT^dagger). Lee una fase codificada en amplitudes.

    Es el bloque final de la estimacion de fase: lleva la fase codificada en
    las amplitudes al registro de conteo, listo para medir. Se construye como
    la inversa de la QFT (swaps + rotaciones controladas con signo negativo) y
    se devuelve como circuito reutilizable.
    """
    qc = QuantumCircuit(n, name="QFT_dg") # circuito de n qubits, sin bits clasicos
    for q in range(n // 2):
        qc.swap(q, n - q - 1) # swaps para invertir el orden de los qubits
    for j in range(n):
        for m in range(j):
            qc.cp(-np.pi / float(2 ** (j - m)), m, j) # rotaciones controladas
        qc.h(j) # Hadamard final en cada qubit
    return qc

def c_amod15(a: int, power: int) -> Gate:
    """Puerta controlada que multiplica por a^(2^power) modulo 15.

    El operador U|y> = |a*y mod 15> elevado a la potencia 2^power, en su
    version controlada, para engancharlo a cada qubit del registro de conteo
    de la estimacion de fase. Solo estan permitidos los `a` coprimos con 15
    ({2, 4, 7, 8, 11, 13, 14}); con otros `a` la funcion debe fallar.
    """
    if a not in (2, 4, 7, 8, 11, 13):
        raise ValueError("a debe ser coprimo con 15: {2,4,7,8,11,13}")
    U = QuantumCircuit(4) # circuito de 4 qubits para el operador U
    for _ in range(power):
        if a in (2, 13):
            U.swap(2, 3); U.swap(1, 2); U.swap(0, 1) # permutacion cíclica
        if a in (7, 8):
            U.swap(0, 1); U.swap(1, 2); U.swap(2, 3)
        if a in (4, 11):
            U.swap(1, 3); U.swap(0, 2)
        if a in (7, 11, 13):
            for q in range(4):
                U.x(q) # puerta NOT en todos los qubits
    gate = U.to_gate() # convertir el circuito en una puerta reutilizable
    gate.name = f"{a}^{power} mod 15" # le ponemos un nombre descriptivo para el diagrama
    return gate.control() # version controlada


def circuito_orden_15(a: int, n_count: int = 8) -> QuantumCircuit:
    """Circuito completo de estimacion de fase para hallar el orden de a mod 15.

    n_count qubits de conteo en superposicion (Hadamard), las `c_amod15`
    controladas, la `qft_dagger` y la medida del registro de conteo. n_count=8
    da resolucion de fase suficiente para los ordenes de N=15 (r in {1,2,4}).
    """
    qc = QuantumCircuit(n_count + 4, n_count) # n_count qubits de conteo + 4 qubits de trabajo, n_count bits clasicos
    for q in range(n_count):
        qc.h(q) # conteo en superposicion uniforme
    qc.x(n_count) # registro de trabajo = |1>
    for q in range(n_count): # exponenciacion modular controlada
        qc.append(c_amod15(a, 2 ** q), [q] + list(range(n_count, n_count + 4))) # controlada por el qubit q del registro de conteo
    qc.append(qft_dagger(n_count), range(n_count)) # QFT inversa sobre el registro de conteo
    qc.measure(range(n_count), range(n_count)) # medir el registro de conteo en los bits clasicos
    return qc

def medir_fase_15(
    a: int, rng: np.random.Generator, n_count: int = 8, shots: int = 1
) -> float:
    """Ejecuta `circuito_orden_15` y devuelve la fase medida s/r en [0, 1).

    Lee el registro de conteo (entero m) y devuelve m / 2**n_count. El
    `rng` se usa para sembrar el muestreo del simulador de forma reproducible:
    misma semilla -> misma fase, para que los tests no parpadeen.
    """
    backend = AerSimulator(seed_simulator=seed) # semilla reproducible para el simulador
    qc = circuito_orden_15(a, n_count) # circuito de estimacion de fase
    result = backend.run(qc, shots=1, memory=True).result() # ejecutar el circuito y obtener la memoria de resultados
    medido = int(result.get_memory()[0], 2) # bitstring -> entero
    return medido / (2 ** n_count) # fase en [0, 1)

def orden_desde_fase(fase: float, n: int = 15) -> int:
    """Recupera el orden r a partir de la fase medida por fracciones continuas.

    La fase ideal es s/r con 0 <= s < r; la aproximacion racional de `fase`
    con denominador < n da el candidato a r. Devuelve el r hallado (0 si la
    fase es 0 o no produce un denominador util, caso que el llamador descarta).
    """
    frac = Fraction(phi).limit_denominator(N) # aproximacion racional de la fase medida
    r = frac.denominator # el orden candidato es el denominador de la fraccion reducida
    return r if r > 1 else None # si r <= 1, no es un orden util (fase = 0 o 1)

def factorizar_15(rng: np.random.Generator,
max_intentos: int = 20) -> FactorizacionShor: 
    """ Esta función hace el bucle de Shor para factorizar N=15, probando bases aleatorias
    `a` coprimas con 15 y midiendo la fase para derivar el orden r. Reintenta hasta
    `max_intentos` veces si r es impar o si a^(r/2) == -1 (mod N). Devuelve un objeto
    `FactorizacionShor` con los resultados de la factorización. """

    """Factoriza N=15 (o N coprimo-compatible) con el algoritmo de Shor.

    Bucle: elige `a` coprimo con N con `rng`, mide la fase, deriva el orden r y
    prueba gcd(a^(r/2) +/- 1, N). Reintenta hasta `intentos` veces si r es
    impar o a^(r/2) == -1 (mod N). Devuelve un `FactorizacionShor` con:

      - n:            el N factorizado
      - factores:     (p, q) con p*q == N (o (1, N) si fracasa)
      - a:            la base que funciono (o la ultima probada)
      - orden:        el orden r hallado
      - intentos:     cuantas iteraciones costo
      - fase_medida:  la fase de la iteracion que tuvo exito
      - ok:           True si p*q == N con p, q no triviales

    N=15 es requisito duro; N=21 objetivo firme (ver docstring del modulo)."""
    
    N = 15
    coprimos = [2, 4, 7, 8, 11, 13] # bases coprimas con 15
    for intento in range(1, max_intentos + 1):
        a = int(rng.choice(coprimos)) #  elige una base coprima con 15 al azar
        g = gcd(a, N) # prueba de suerte clasica: si g > 1, ya tenemos un factor
        if g > 1: # golpe de suerte clasico
            return FactorizacionShor(N, (g, N // g), a, 1, intento,
0.0, ok=True) # si g > 1, ya tenemos un factor trivial
        phi = medir_fase_15(a, n_count=8, seed=int(rng.integers(1_000_000))) # mide la fase s/r con QPE
        r = orden_desde_fase(phi, N) # obtiene el orden r a partir de la fase medida
        if r is None or r % 2 != 0: # orden inutil o impar: reintenta
            continue
        x = pow(a, r // 2, N) # calcula a^(r/2) mod N
        if x == N - 1: # a^(r/2) == -1: reintenta
            continue
        p, q = gcd(x - 1, N), gcd(x + 1, N) # posibles factores no triviales
        if 1 < p < N: # si p es un factor no trivial, devolvemos el resultado exitoso
            return FactorizacionShor(N, (p, N // p), a, r, intento, phi, ok=True)
        if 1 < q < N: # si q es un factor no trivial, devolvemos el resultado exitoso
            return FactorizacionShor(N, (q, N // q), a, r, intento, phi, ok=True)
    return FactorizacionShor(N, (1, N), 0, 0, max_intentos, 0.0, ok=False) # si agotamos los intentos sin exito, devolvemos un resultado fallido