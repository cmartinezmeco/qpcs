"""src/chaos/cipher.py - orquestador: cifrar_imagen / descifrar_imagen.

Ata la cadena completa: keystream -> permutacion -> difusion (ida y
vuelta). El descifrado invierte las etapas EN ORDEN INVERSO: la
composicion de funciones se deshace al reves.

Este modulo NO usa np.random en ningun sitio: el cifrado es enteramente
determinista a partir de la clave. Si aparece un np.random aqui, es un bug.

REPARTO DEL MATERIAL DERIVADO DE LA CLAVE

El reparto obvio seria "M bytes para la difusion y M valores para la
permutacion". Aqui se piden 2M + 2 bytes de keystream, y el motivo se
deriva, no se decide por gusto:

  - La difusion son DOS pasadas, ida y vuelta. Si las dos usan el MISMO
    segmento k, el keystream se cancela al componerlas:

        c_i = p_i ^ k_i ^ c_{i-1}                             (ida)
        d_i = c_i ^ k_i ^ d_{i+1} = p_i ^ c_{i-1} ^ d_{i+1}   (vuelta)

    y el byte de salida deja de depender de k_i. Con dos segmentos
    disjuntos (k_ad y k_atr) esa cancelacion no existe.
  - Los 2 bytes sueltos del final son los dos IV, uno por pasada. Un IV
    aqui es "un byte inicial derivado tambien de la clave", asi que
    sacarlo del propio keystream es exactamente eso y no hay que
    inventar otra fuente.

Los M valores de la permutacion NO son bytes: son valores de la orbita en
float64, porque permutacion_desde_orbita ordena por magnitud y 256 valores
posibles darian empates masivos. Salen de la misma orbita que el
keystream, con la misma receta de transitorio y submuestreo: un solo
flujo con dos usos.
"""

from __future__ import annotations

import hashlib

import numpy as np

from .diffusion import deshacer_adelante, difundir_adelante
from .keystream import keystream
from .lyapunov import lyapunov_logistico
from .maps import orbita_logistica, orbita_lorenz
from .permutation import invertir_permutacion, permutacion_desde_orbita
from .types import (
    LORENZ_RHO,
    PASO_RK4,
    SUBMUESTREO,
    TRANSITORIO,
    UMBRAL_LYAPUNOV,
    ClaveCaotica,
    Imagen,
    ImagenCifrada,
    Keystream,
    Orbita,
)


def _validar_clave(clave: ClaveCaotica) -> None:
    """Rechaza claves que no producen caos, con un motivo legible.

    Es la razon de ser de esta funcion: r = 3.83
    esta DENTRO del rango caotico nominal (3.57, 4] y sin embargo tiene
    periodo 3. Un modulo que solo comprobara el rango cifraria con un
    keystream de tres bytes repetidos y las metricas se hundirian. Aqui
    se CALCULA lambda y se rechaza si no supera UMBRAL_LYAPUNOV.

    Para Lorenz no se calcula el espectro en cada llamada: sigma, rho y
    beta son constantes del contrato (types.py), no partes variables de
    la clave, asi que lambda_1 no depende de la clave y ya esta verificado
    por test_lorenz_espectro_suma_la_divergencia. Recalcular Benettin en
    cada cifrado seria medir una constante durante varios segundos.

    Raises:
        ValueError: si la clave no es utilizable, con el motivo dentro.
    """
    if clave.sistema == "logistico":
        # No se confia en el assert de ClaveCaotica.__post_init__: con
        # python -O los assert desaparecen y la validacion con ellos.
        if clave.r is None:
            raise ValueError("una clave del sistema 'logistico' necesita r")
        if not 0.0 < clave.x0 < 1.0:
            raise ValueError(
                f"x0 = {clave.x0} fuera de (0, 1): 0 y 1 son puntos fijos del "
                f"mapa logistico y la orbita se queda clavada en ellos"
            )
        diagnostico = lyapunov_logistico(clave.x0, clave.r)
        if not diagnostico.es_caotico:
            raise ValueError(
                f"clave no caotica: lambda = {diagnostico.lyapunov:.4f} "
                f"(+/- {diagnostico.sigma:.4f}) no supera el umbral "
                f"{UMBRAL_LYAPUNOV}. Con r = {clave.r} el mapa logistico es "
                f"periodico, no caotico, y el keystream se repetiria: el "
                f"modulo se niega a cifrar en vez de producir una imagen "
                f"'cifrada' con una secuencia de periodo corto"
            )
    else:
        if clave.y0 is None or clave.z0 is None:
            raise ValueError("una clave del sistema 'lorenz' necesita y0 y z0")
        if clave.rho is not None and clave.rho != LORENZ_RHO:
            # keystream_lorenz integra con LORENZ_RHO, la constante del
            # contrato, y NO lee clave.rho. Aceptar aqui un rho distinto
            # significaria que dos claves distintas producen exactamente el
            # mismo cifrado: un campo de la clave que no hace nada y un
            # espacio de claves mas pequeno de lo que la clave aparenta.
            # Mejor un error que esa mentira silenciosa.
            raise ValueError(
                f"rho = {clave.rho} no se puede usar: la dinamica de Lorenz "
                f"de este modulo esta fijada en LORENZ_RHO = {LORENZ_RHO} "
                f"como constante del contrato (types.py), asi que un rho "
                f"distinto en la clave no cambiaria el cifrado. Dejalo a None"
            )


def _valores_de_permutacion(clave: ClaveCaotica, m: int) -> Orbita:
    """Los m valores de orbita que se ordenan para construir sigma.

    Misma receta que el keystream (transitorio + submuestreo), pero
    quedandose con el valor en float64 en vez de con sus 8 bits bajos.

    Para Lorenz se usa UNA SOLA coordenada, la x, y no las tres
    intercaladas. Motivo medido: x, y, z normalizadas con LORENZ_RANGOS
    tienen distribuciones distintas (la z se concentra mas abajo), asi que
    intercalarlas hace que el rango de cada valor dependa de i mod 3. En
    una prueba de 4096 valores los indices con i%3==2 salian con rango
    medio 5174 frente a 6604 y 6653 de las otras dos clases: la
    permutacion quedaria sesgada por la posicion. Con una sola coordenada
    todos los valores vienen de la misma distribucion y el orden no
    arrastra ninguna estructura. Cuesta el triple de integracion, y es lo
    que hay que pagar por una permutacion sin sesgo.

    No se normaliza a (0, 1): argsort solo mira el ORDEN y es invariante
    frente a cualquier transformacion monotona, asi que normalizar seria
    decoracion con coste en coma flotante.
    """
    n_iter = TRANSITORIO + m * SUBMUESTREO
    if clave.sistema == "logistico":
        if clave.r is None:
            raise ValueError("una clave del sistema 'logistico' necesita r")
        orb = orbita_logistica(clave.x0, clave.r, n_iter)
        return orb[TRANSITORIO::SUBMUESTREO][:m]

    if clave.y0 is None or clave.z0 is None:
        raise ValueError("una clave del sistema 'lorenz' necesita y0 y z0")
    u0 = np.array([clave.x0, clave.y0, clave.z0], dtype=np.float64)
    trayectoria = orbita_lorenz(u0, n_iter, PASO_RK4)
    muestras = trayectoria[TRANSITORIO::SUBMUESTREO][:m]
    coordenada: Orbita = muestras[:, 0]
    return coordenada


def _material(clave: ClaveCaotica, m: int) -> tuple[Keystream, Keystream, int, int]:
    """(k_adelante, k_atras, iv_adelante, iv_atras) para m pixeles.

    Un unico keystream de 2m + 2 bytes, troceado siempre igual. La
    longitud se deriva de m -y m de las dimensiones, que viajan en
    ImagenCifrada-, nunca de otra cosa: regenerar el keystream con otra
    longitud desalinea el flujo desde el primer byte, y es de los
    errores mas faciles de cometer en este modulo.
    """
    ks = keystream(clave, 2 * m + 2)
    return ks[:m], ks[m : 2 * m], int(ks[2 * m]), int(ks[2 * m + 1])


def _difundir_atras(p: Keystream, k: Keystream, iv: int) -> Keystream:
    """Difusion encadenada de fin a principio: c_i depende de c_{i+1}.

    Es la misma operacion que difundir_adelante sobre el array invertido,
    asi que se reutiliza en vez de duplicar el bucle. Existe porque la
    avalancha de la pasada de ida es UNIDIRECCIONAL: cambiar el ultimo
    pixel del plano solo afectaria al ultimo del cifrado y NPCR saldria
    casi cero en ese caso.
    """
    return np.ascontiguousarray(difundir_adelante(p[::-1], k[::-1], iv)[::-1])


def _deshacer_atras(c: Keystream, k: Keystream, iv: int) -> Keystream:
    """Inversa exacta de _difundir_atras."""
    return np.ascontiguousarray(deshacer_adelante(c[::-1], k[::-1], iv)[::-1])


def cifrar_imagen(img: Imagen, clave: ClaveCaotica) -> ImagenCifrada:
    """Cifra una imagen en escala de grises con la clave dada.

    Cadena: generar keystream -> permutar -> difundir hacia adelante ->
    difundir hacia atras (para que la avalancha cubra tambien el ultimo
    pixel).

    La imagen de entrada NO se modifica: la permutacion por indexado
    avanzado (plano[sigma]) ya devuelve un array nuevo. Mutar la entrada
    in place destruiria el original que el test de round-trip necesita
    para comparar, y el fallo se manifestaria como un test que pasa
    cuando no deberia.

    El esquema es DETERMINISTA y no lleva nonce: cifrar dos veces la
    misma imagen con la misma clave da exactamente el mismo resultado.
    Es una limitacion real y documentada, no un descuido: es
    lo que hace que reutilizar la clave con dos imagenes sea catastrofico,
    igual que reutilizar un one-time pad. El baseline AES-256-GCM de la
    tarea 3.8 si lleva nonce fresco, y esa diferencia es parte de la tabla.

    Args:
        img: imagen uint8, cualquier forma (alto, ancho).
        clave: la clave caotica, logistica o Lorenz.

    Returns:
        ImagenCifrada con los datos cifrados y los metadatos necesarios
        para descifrar (forma, sistema, iv, hash del plano).

    Raises:
        ValueError: si la imagen no es uint8 bidimensional, o si la clave
            no produce caos (ver _validar_clave).
    """
    if img.dtype != np.uint8:
        raise ValueError(
            f"la imagen debe ser uint8 y es {img.dtype}: un float en el camino "
            f"del XOR es una conversion silenciosa en el peor caso"
        )
    if img.ndim != 2:
        raise ValueError(f"la imagen debe ser bidimensional y tiene {img.ndim} ejes")
    if img.size == 0:
        raise ValueError("no se puede cifrar una imagen vacia")

    _validar_clave(clave)

    alto, ancho = int(img.shape[0]), int(img.shape[1])
    m = alto * ancho
    k_ad, k_atr, iv_ad, iv_atr = _material(clave, m)

    plano: Keystream = np.ascontiguousarray(img).ravel()
    sigma = permutacion_desde_orbita(_valores_de_permutacion(clave, m), m)

    permutada: Keystream = plano[sigma]
    ida = difundir_adelante(permutada, k_ad, iv_ad)
    vuelta = _difundir_atras(ida, k_atr, iv_atr)

    return ImagenCifrada(
        datos=vuelta.reshape(alto, ancho),
        alto=alto,
        ancho=ancho,
        sistema=clave.sistema,
        iv=iv_ad,
        # OJO: el hash del plano viaja junto al cifrado y FILTRA
        # informacion (permite confirmar una conjetura sobre la imagen sin
        # descifrarla). Se conserva porque el modulo es didactico y la
        # verificacion tiene valor pedagogico, y va documentado en
        # docs/limitaciones.md.
        hash_plano=hashlib.sha256(plano.tobytes()).hexdigest(),
    )


def descifrar_imagen(cifrada: ImagenCifrada, clave: ClaveCaotica) -> Imagen:
    """Descifra una ImagenCifrada con la clave dada.

    Debe ser EXACTAMENTE la inversa de cifrar_imagen: deshacer difusion
    hacia atras, deshacer difusion hacia adelante, aplicar la permutacion
    inversa. Ese orden, y no otro.

    No comprueba hash_plano ni lanza si la clave es incorrecta: un cifrado
    sin autenticacion no puede distinguir "clave equivocada" de "cifrado
    manipulado", y fingir que si es justamente la diferencia con AES-GCM
    que la tabla de la tarea 3.8 tiene que hacer visible. Con la clave
    equivocada devuelve ruido, y quien quiera verificar compara el
    SHA-256 del resultado con cifrada.hash_plano.

    Args:
        cifrada: el resultado de cifrar_imagen.
        clave: debe coincidir con clave.sistema usado al cifrar.

    Returns:
        La imagen original, uint8, bit a bit identica si la clave es correcta.

    Raises:
        ValueError: si el sistema de la clave no es el del contenedor, o
            si la clave no produce caos (ver _validar_clave).
    """
    if cifrada.sistema != clave.sistema:
        raise ValueError(
            f"el contenedor se cifro con el sistema {cifrada.sistema!r} y la "
            f"clave es del sistema {clave.sistema!r}"
        )

    _validar_clave(clave)

    m = cifrada.alto * cifrada.ancho
    k_ad, k_atr, _iv_ad_derivado, iv_atr = _material(clave, m)

    datos: Keystream = np.ascontiguousarray(cifrada.datos).ravel()
    # El IV de ida es el que VIAJA en el contenedor, no el
    # recalculado: es lo que declara el formato. El de vuelta no viaja en
    # ningun campo, asi que se deriva de la clave igual que al cifrar.
    ida = _deshacer_atras(datos, k_atr, iv_atr)
    permutada = deshacer_adelante(ida, k_ad, cifrada.iv)

    sigma = permutacion_desde_orbita(_valores_de_permutacion(clave, m), m)
    plano: Imagen = permutada[invertir_permutacion(sigma)]
    return plano.reshape(cifrada.alto, cifrada.ancho)
