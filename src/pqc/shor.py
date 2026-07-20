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


def qft_dagger(n: int) -> QuantumCircuit:
    """Transformada cuantica de Fourier INVERSA sobre n qubits (QFT^dagger).

    Es el bloque final de la estimacion de fase: lleva la fase codificada en
    las amplitudes al registro de conteo, listo para medir. Se construye como
    la inversa de la QFT (swaps + rotaciones controladas con signo negativo) y
    se devuelve como circuito reutilizable.
    """
    raise NotImplementedError


def c_amod15(a: int, power: int) -> Gate:
    """Puerta controlada que multiplica por a^(2^power) modulo 15.

    El operador U|y> = |a*y mod 15> elevado a la potencia 2^power, en su
    version controlada, para engancharlo a cada qubit del registro de conteo
    de la estimacion de fase. Solo estan permitidos los `a` coprimos con 15
    ({2, 4, 7, 8, 11, 13, 14}); con otros `a` la funcion debe fallar.
    """
    raise NotImplementedError


def circuito_orden_15(a: int, n_count: int = 8) -> QuantumCircuit:
    """Circuito completo de estimacion de fase para hallar el orden de a mod 15.

    n_count qubits de conteo en superposicion (Hadamard), las `c_amod15`
    controladas, la `qft_dagger` y la medida del registro de conteo. n_count=8
    da resolucion de fase suficiente para los ordenes de N=15 (r in {1,2,4}).
    """
    raise NotImplementedError


def medir_fase_15(
    a: int, rng: np.random.Generator, n_count: int = 8, shots: int = 1
) -> float:
    """Ejecuta `circuito_orden_15` y devuelve la fase medida s/r en [0, 1).

    Lee el registro de conteo (entero m) y devuelve m / 2**n_count. El
    `rng` se usa para sembrar el muestreo del simulador de forma reproducible:
    misma semilla -> misma fase, para que los tests no parpadeen.
    """
    raise NotImplementedError


def orden_desde_fase(fase: float, n: int = 15) -> int:
    """Recupera el orden r a partir de la fase medida por fracciones continuas.

    La fase ideal es s/r con 0 <= s < r; la aproximacion racional de `fase`
    con denominador < n da el candidato a r. Devuelve el r hallado (0 si la
    fase es 0 o no produce un denominador util, caso que el llamador descarta).
    """
    raise NotImplementedError


def factorizar_15(
    rng: np.random.Generator, n: int = 15, intentos: int = 10
) -> FactorizacionShor:
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

    N=15 es requisito duro; N=21 objetivo firme (ver docstring del modulo).
    """
    raise NotImplementedError
