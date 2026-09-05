# Limitaciones de QPCS

Las limitaciones de los **cuatro módulos**, juntas y sin recortar. Hasta la Fase 4
estaban repartidas entre las cuatro guías de fase, que no forman parte del
repositorio: quien clonaba esto no tenía forma de saber dónde está el borde de
cada módulo sin preguntarle a alguno de los tres.

> Tarea 4.12 de la Fase 4. Entregable: este fichero.

## Cómo se lee este documento

Cada limitación se escribe siempre en **tres partes**:

| Parte | Qué dice |
|---|---|
| **Qué no hace** | El hecho, sin suavizar. |
| **Por qué se decidió así** | La razón, que casi siempre es de alcance, no de ignorancia. |
| **Qué haría falta** | Lo que habría que construir para levantarla. |

La tercera parte es la que distingue una lista de limitaciones de una lista de
excusas. «No implementamos *decoy states*» es una excusa. «No implementamos
*decoy states*, que es lo que haría falta para BB84 con láseres atenuados
reales; simulamos fuentes de fotón único ideales, y añadirlos exigiría modelar
la estadística de fotones de la fuente» es una limitación escrita por alguien que
sabe dónde está el borde de su trabajo.

Donde una limitación está **medida** y no solo declarada, se enlaza el test o la
figura que la fija. Esa es la regla 8 del proyecto: ninguna afirmación sin
respaldo.

---

## Transversales

Valen para los cuatro módulos a la vez.

### T1 — Es un proyecto académico, no auditado

**Qué no hace.** Nada de lo que hay aquí ha pasado por una auditoría de seguridad
externa, ni por revisión criptográfica independiente, ni se ha usado en
producción. No debe protegerse nada real con este código.

**Por qué se decidió así.** El objetivo declarado del proyecto es entender y
demostrar mecanismos —BB84, la migración post-cuántica, el cifrado caótico, la
extracción de entropía—, no entregar una biblioteca criptográfica. Auditar cuatro
módulos habría consumido la totalidad del tiempo disponible sin añadir nada al
objetivo.

**Qué haría falta.** Una revisión externa por alguien ajeno al equipo, un modelo
de amenaza explícito por módulo, y análisis de canales laterales (temporización,
caché, consumo). Para el Módulo 2 existe una alternativa mucho más barata que
auditar nuestro código: usar `liboqs` directamente, que es exactamente lo que el
módulo ya hace para ML-KEM y ML-DSA.

### T2 — Las simulaciones cuánticas son pseudoaleatorias

**Qué no hace.** El QRNG del Módulo 1 y el circuito de Shor del Módulo 2 no
manejan aleatoriedad cuántica: corren sobre `AerSimulator`
([`src/qkd/qrng.py`](../src/qkd/qrng.py), [`src/qkd/bb84.py`](../src/qkd/bb84.py),
[`src/pqc/shor.py`](../src/pqc/shor.py)), que por debajo usa un generador clásico
sembrado. Medir |+⟩ mil veces en un simulador da lo mismo que llamar mil veces a
un PRNG, y lo dice el propio parámetro `seed_simulator`.

**Por qué se decidió así.** Es la consecuencia inevitable de no tener hardware
cuántico, y se declaró como tal desde la Fase 1 en vez de venderlo como
aleatoriedad cuántica, que es lo que suena bien y es media verdad.

**Qué haría falta.** Ejecutar los circuitos en hardware real (IBM Quantum), con
todo lo que eso arrastra: colas, ruido del dispositivo, calibración y errores de
lectura, que son justo lo que un simulador ideal no tiene. El Módulo 4 cubre este
hueco por el otro lado —extrae entropía de ruido físico grabado en vez de
generarla—, con sus propios límites (§ Módulo 4).

### T3 — La reproducibilidad a largo plazo no está garantizada

**Qué no hace.** Fijar versiones con `==` en `requirements.txt` no basta para que
esto siga construyendo dentro de cinco años.

No es teórico: durante la Fase 2, `liboqs-python 0.14.1` **desapareció de PyPI** y
la CI se rompió mientras en local seguía funcionando, porque Docker reutilizaba
una capa cacheada de días antes. La caché fue el mecanismo que ocultó el
problema.

**Por qué se decidió así.** Se eligió el compromiso razonable —versiones fijadas,
imagen Docker como fuente de verdad, y una construcción periódica sin caché que
vuelve a bajarlo todo— en vez del compromiso caro: vendorizar las dependencias o
publicar la imagen construida.

**Qué haría falta.** Publicar la imagen en un registro (decisión abierta, ver
[`decisiones.md`](decisiones.md)), o congelar las dependencias en un espejo
propio. Ninguna de las dos es gratis: la primera obliga a mantener la imagen al
día, la segunda a mantener el espejo.

### T4 — Ni cobertura del 100 % ni rendimiento optimizado

**Qué no hace.** La cobertura no llega al 100 % en ningún módulo, y en ninguna
parte se ha optimizado el rendimiento. El Welch del Módulo 4 sobre un millón de
muestras no es instantáneo, y el cifrado del Módulo 3 es NumPy directo.

**Por qué se decidió así.** Las dos cosas quedaron explícitamente fuera de
alcance en las cuatro fases. La cobertura alta por sí misma no dice que los tests
verifiquen algo —el proyecto prefirió tests que comprueban una propiedad contra
la teoría antes que tests que recorren líneas—, y optimizar habría competido con
escribir el cuarto módulo.

**Qué haría falta.** Para el rendimiento, perfilar antes de tocar nada. Para la
cobertura, cerrar las ramas de error que hoy no se ejercitan, que es trabajo
mecánico y de poco valor comparado con lo que hay.

---

## Módulo 1 — QKD: BB84 y QRNG

### M1.1 — Sin *decoy states* ni defensa frente a PNS

**Qué no hace.** El protocolo simula una fuente de **fotón único ideal**: cada
pulso lleva exactamente un fotón. No hay estados señuelo (*decoy states*) ni, por
tanto, defensa frente al ataque de división del número de fotones (PNS).

**Por qué se decidió así.** Un BB84 real se implementa con láseres atenuados,
cuya estadística de fotones es poissoniana: algunos pulsos llevan dos o más
fotones, y de esos Eve puede quedarse uno sin perturbar nada. Modelar eso es un
módulo entero, y el objetivo de la Fase 1 era la cadena completa hasta la clave
destilada, no el endurecimiento de la fuente.

**Qué haría falta.** Modelar la estadística de fotones de la fuente, añadir al
menos dos intensidades de señuelo, y estimar por separado el rendimiento y el
error de los pulsos de un solo fotón. Eso cambia la fórmula de clave segura, no
solo el simulador.

### M1.2 — La clave segura usa la cota asintótica, no el régimen de clave finita

**Qué no hace.** `secure_key_length`
([`src/qkd/privacy.py`](../src/qkd/privacy.py)) implementa la cota de
**Devetak–Winter** más el peaje del *leftover hash lemma*:

```
ell = n·(1 − h(Q)) − leak_ec − 2·log2(1/ε)
```

Es la expresión **asintótica**. No lleva las correcciones de clave finita
completas —términos de suavizado, penalización por el muestreo aleatorio de la
fracción de test— más allá del parámetro opcional `n_sigma`, que permite usar la
cota superior `Q + n_sigma·σ` en vez del QBER puntual y que por defecto vale 0.

**Por qué se decidió así.** La cota asintótica es la que aparece en la teoría que
el módulo enseña, y con `n_sigma = 0` reproduce exactamente las cifras ya
publicadas. Introducir el análisis de clave finita completo habría cambiado todos
los números del módulo por una corrección que, con los tamaños de bloque de la
demostración, es pequeña frente a la incertidumbre que el propio QBER estimado ya
arrastra.

**Qué haría falta.** Un análisis de clave finita al uso, con su parámetro de
suavizado y su corrección por el tamaño de la muestra de test. Parte del
andamiaje ya está puesto: `estimate_qber` calcula σ y el dashboard la enseña; lo
que falta es la fórmula que la consuma de verdad y no como opción.

### M1.3 — El canal clásico se supone autenticado

**Qué no hace.** El intercambio público de bases, la reconciliación y la
estimación del QBER se hacen sobre un canal clásico que el módulo **supone
autenticado**. No hay autenticación: ni MAC, ni firma, ni clave previa compartida
para arrancarla.

**Por qué se decidió así.** Es la hipótesis estándar de las pruebas de seguridad
de BB84, y sin ella el protocolo cae ante un *man in the middle* trivial que
suplanta a Bob frente a Alice y a Alice frente a Bob. Implementarla es un
problema clásico bien resuelto y ortogonal a lo que el módulo demuestra.

**Qué haría falta.** Un MAC de Wegman–Carter con una clave corta precompartida,
renovada con parte de la clave destilada en cada ronda. Es lo que hace que QKD
sea *key growing* y no *key distribution*: hace falta un secreto inicial, y eso
conviene decirlo antes que esconderlo.

### M1.4 — Un solo ataque implementado: intercept-resend

**Qué no hace.** Eve solo sabe hacer una cosa
([`src/qkd/eve.py`](../src/qkd/eve.py)): interceptar una fracción de los fotones,
medirlos en una base aleatoria y reenviar lo que midió. No hay ataques de
clonación óptima, ni colectivos, ni coherentes, ni ataques al hardware
(*blinding* de detectores, caballo de Troya).

**Por qué se decidió así.** El intercept-resend es el que exhibe la física que el
módulo enseña: da un QBER del 25 % con Eve al 100 %, y ese 25 % se deriva a mano
en la teoría y se comprueba en el código.

**Qué haría falta.** Para los ataques colectivos, nada en el código: la cota de
Devetak–Winter que el módulo ya usa los cubre por construcción, y esa es
justamente su gracia. Para los ataques al hardware haría falta un modelo del
dispositivo, que un simulador no tiene.

### M1.5 — El QRNG del módulo es pseudoaleatorio

**Qué no hace.** No es un generador cuántico de números aleatorios, por lo dicho
en **T2**. Es un PRNG con una interfaz cuántica encima.

**Por qué se decidió así.** Es la consecuencia de correr en simulador, y fue la
primera declaración de honestidad del proyecto.

**Qué haría falta.** Hardware cuántico, o una fuente física. El Módulo 4 hace lo
segundo: extrae entropía de ruido de detector real y la destila con el **mismo**
`privacy_amplify` de este módulo. Cierra el círculo, pero con los límites de
§ Módulo 4 — y en particular sin ser un QRNG certificado.

---

## Módulo 2 — Criptografía post-cuántica y Shor

### M2.1 — Shor factoriza juguetes, con un oráculo compilado a mano

**Qué no hace.** El circuito factoriza **N = 15** con un oráculo `a^k mod 15`
compilado a mano para cada base `a`. **N = 21 no está implementado**: necesita su
propio `c_amod21` con 5 cúbits de trabajo, y el dashboard lo dice cuando se
selecciona. Esto no rompe RSA ni se acerca.

**Por qué se decidió así.** Un oráculo modular genérico y reversible es un
proyecto en sí mismo, y para lo que el módulo enseña —la estimación de fase, los
picos en los múltiplos de 1/r, las fracciones continuas— basta con un caso
trabajado hasta el final.

**Qué haría falta.** Para N = 21, escribir su oráculo. Para algo que amenace a
RSA-2048, miles de cúbits **lógicos** con corrección de errores, que no existen:
el salto no es ingeniería incremental.

### M2.2 — No se ataca la dureza de los retículos

**Qué no hace.** El módulo no analiza ni pone a prueba la seguridad de ML-KEM y
ML-DSA. No hay estimación de coste de ataque, ni reducción de bases, ni análisis
de los parámetros de FIPS 203/204.

**Por qué se decidió así.** El módulo demuestra la **migración**: que se puede
cifrar y firmar de verdad con los estándares post-cuánticos, y cuánto cuesta
comparado con RSA y las curvas. La confianza en los retículos se hereda del
proceso de estandarización del NIST, no de este repositorio.

**Qué haría falta.** Un estimador de seguridad de retículos y los análisis de los
equipos que propusieron los esquemas. Es trabajo de criptoanálisis, no de
implementación.

### M2.3 — El «híbrido» es KEM + simétrico, no clásico + post-cuántico, y no hay TLS

**Qué no hace.** [`src/pqc/hybrid.py`](../src/pqc/hybrid.py) es híbrido en el
sentido **KEM + AEAD** (ML-KEM-768 → HKDF-SHA256 → AES-256-GCM). **No** es el
híbrido del que habla la literatura de migración, que combina además un KEM
clásico (X25519) con el post-cuántico para tener defensa en profundidad si uno de
los dos cae. Tampoco hay integración con TLS ni con ningún protocolo de red.

**Por qué se decidió así.** Está escrito en el propio *docstring* del fichero
desde la tarea 2.5: combinarlo con X25519 era una capa extra fuera del alcance. El
objetivo era un sobre post-cuántico que cifre un mensaje real de punta a punta, y
eso está hecho y probado
([`tests/pqc/test_hybrid.py`](../tests/pqc/test_hybrid.py)).

**Qué haría falta.** Para el híbrido de verdad, concatenar los dos secretos
compartidos en el HKDF y subir la versión de la etiqueta de dominio; es poco
código y sobre todo una decisión de formato. Para TLS, una integración con
`oqs-provider` u OpenSSL, que es un proyecto aparte.

### M2.4 — Sin gestión de claves

**Qué no hace.** Las claves se generan en memoria en cada llamada y no se
guardan, ni se rotan, ni se revocan, ni se almacenan cifradas. No hay
certificados ni cadena de confianza.

**Por qué se decidió así.** La gestión de claves es donde se rompen los sistemas
reales, y hacerla a medias es peor que no hacerla: da una falsa sensación de
completitud. El módulo prefiere no tenerla y decirlo.

**Qué haría falta.** Un almacén de claves con su formato serializado, política de
rotación, y —si se quiere autenticar a alguien y no solo firmar bytes— una PKI o
un modelo de confianza equivalente.

### M2.5 — Los tiempos medidos no dicen nada sobre canales laterales

**Qué no hace.** El *benchmark* mide rendimiento medio para comparar coste. **No
es un análisis de tiempo constante**: nada de lo medido descarta que exista una
fuga por temporización en ninguna de las implementaciones.

**Por qué se decidió así.** Son dos preguntas distintas y aquí se responde solo a
la primera. Un análisis de canal lateral necesita instrumentación, entradas
elegidas adversarialmente y estadística sobre las colas de la distribución, no
sobre la media.

**Qué haría falta.** Herramientas de análisis de tiempo constante sobre la
biblioteca, no sobre nuestro envoltorio: quien puede tener una fuga es `liboqs`,
no las líneas de Python que lo llaman.

### M2.6 — El benchmark es específico de una máquina, y sus medias son ruidosas

**Qué no hace.** Los tiempos de [`docs/benchmark_pqc.json`](benchmark_pqc.json)
valen para la máquina, el `liboqs` y el Python que el propio JSON registra.
Compararlos entre máquinas sin mirar ese bloque no significa nada. Además, en las
filas más rápidas la media queda entre un 20 % y un 37 % por encima de su propia
mediana: el ruido de planificador y de recolector de basura cae sobre la media, no
sobre la mediana.

**Por qué se decidió así.** Se publica la media **con su σ** y también la p50,
precisamente para que el lector pueda recalcular cualquier factor con el
estadístico robusto. Suprimir la media habría escondido el problema en vez de
enseñarlo.

**Qué haría falta.** Volver a medir en la máquina de interés, siempre dentro del
contenedor. El script lo hace con `--medir`; sin esa bandera solo redibuja desde
el JSON, de modo que tocar un color no puede cambiar un número publicado.

---

## Módulo 3 — Caos determinista

### M3.1 — Sin prueba de seguridad, y con cuatro ataques conocidos contra la familia

**Qué no hace.** El cifrado caótico **no tiene ninguna prueba de seguridad**: ni
reducción a un problema difícil, ni argumento de indistinguibilidad. Y hay cuatro
ataques conocidos contra esta familia de esquemas, documentados y no
implementados:

1. **Texto plano elegido.** El *keystream* no depende del texto plano, así que
   cifrar una imagen de ceros lo revela entero. Es el que hunde a la familia.
2. **Reutilización de clave.** Dos imágenes con la misma clave comparten
   *keystream*.
3. **Recuperación de estado** a partir de suficiente salida observada: un mapa
   suave y de dimensión baja no está diseñado para resistirlo, a diferencia de un
   cifrado de flujo real.
4. **Degradación por precisión finita** (ver M3.5).

**Por qué se decidió así.** El módulo existe para **enseñar por qué** este tipo
de esquema —abundantísimo en la literatura— no es criptografía, y para medirlo
contra AES-256-GCM en el mismo banco. Arreglarlo lo convertiría en otra cosa y
borraría la lección.

**Qué haría falta.** Un diseño distinto. La conclusión honesta del módulo es que
para cifrar imágenes en serio se usa AES-GCM, que es la fila con la que se
compara.

### M3.2 — No autentica: no hay integridad ni detección de manipulación

**Qué no hace.** El esquema caótico cifra pero no autentica. Un atacante puede
alterar el criptograma y el descifrado devolverá píxeles, no un error.

**Por qué se decidió así.** El módulo compara una construcción de la literatura
del caos con AES-**GCM**, que sí autentica, y esa asimetría es parte de lo que se
quiere enseñar: el coste de un modo autenticado es lo que la mayoría de esos
artículos ni menciona.

**Qué haría falta.** Encapsularlo en un esquema *encrypt-then-MAC*, lo que
equivale a admitir que la seguridad la aporta el MAC y no el caos.

### M3.3 — Determinista, sin *nonce*

**Qué no hace.** Con la misma clave y la misma imagen, la salida es idéntica bit
a bit. No hay *nonce* ni IV público que rompa esa igualdad.

**Por qué se decidió así.** Es una decisión deliberada y con contrapartida: el
determinismo es lo que permite **verificarlo**, y el módulo lo aprovecha con un
vector de prueba versionado
([`vectors/keystream_v1.json`](../vectors/keystream_v1.json)) y una comprobación
en CI de que el criptograma es idéntico en el venv local y dentro del contenedor.
Sin determinismo no hay vector, y sin vector un fallo silencioso de
reproducibilidad no se detecta.

**Qué haría falta.** Un *nonce* público mezclado en la semilla, exactamente como
hace la fila de AES del banco. Eso invalidaría el vector de prueba tal como está
hoy, y por eso es una decisión de grupo y no un cambio de una línea.

### M3.4 — `hash_plano` filtra información

**Qué no hace.** El contenedor `ImagenCifrada`
([`src/chaos/types.py`](../src/chaos/types.py)) viaja con `hash_plano`, el SHA-256
del texto **plano**. Eso es una fuga: permite confirmar una conjetura sobre el
contenido —si sospechas qué imagen es, la cifras tú y comparas—, que es justo lo
que un criptograma no debe permitir.

**Por qué se decidió así.** Está ahí para verificar el viaje de ida y vuelta en
los tests y en el dashboard, y se declaró como fuga desde la Fase 3 en vez de
quitarlo y perder la comprobación.

**Qué haría falta.** Sacarlo del objeto transmitido y dejarlo como dato de prueba
fuera de banda, o sustituirlo por un MAC del **criptograma**, que es lo que un
esquema autenticado haría de todas formas (ver M3.2).

### M3.5 — Ciclos finitos: toda órbita en `float64` acaba repitiéndose

**Qué no hace.** No hay garantía matemática de que el *keystream* no se repita.
Cualquier órbita en aritmética de precisión finita es eventualmente periódica; si
cicla antes de agotar la imagen, el flujo se repite.

**Por qué se decidió así.** Es una propiedad del sustrato, no del código, y no se
puede eliminar: se puede medir y se puede avisar. Se midió sobre nueve claves y
ninguna cicla en 4 × 10⁶ pasos, y el módulo emite un `logging.WARNING` cuando la
órbita que acaba de generar sí cicla, en vez de cifrar en silencio con un flujo
que se repite.

**Qué haría falta.** Aritmética de precisión arbitraria —y entonces se pierden el
rendimiento y el determinismo bit a bit entre plataformas— o un generador con
periodo demostrable, que es otra vez dejar de ser caos.

### M3.6 — Solo escala de grises de 8 bits

**Qué no hace.** Solo imágenes en escala de grises de 8 bits. Sin color, vídeo,
audio, compresión ni GPU.

**Por qué se decidió así.** Alcance. Añadir color es aplicar lo mismo tres veces
y no enseña nada nuevo sobre el mecanismo.

**Qué haría falta.** Poco, y es precisamente por eso que no se hizo: habría
añadido superficie sin añadir contenido.

### M3.7 — NPCR y UACI frente a un cambio en el *plano* no alcanzan sus valores canónicos

**Qué no hace.** Las métricas diferenciales clásicas del campo no dan aquí las
cifras que da la literatura, y **no pueden darlas**. Con la difusión encadenada
por XOR que el módulo especifica, el esquema entero es afín sobre GF(2): un
cambio de un bit en el plano se propaga como un delta XOR **constante**. Toda
diferencia de intensidad vale entonces exactamente 1, lo que acota la UACI en
**0,392 %** —frente al 33,4635 % del criterio de cierre— y deja la NPCR dependiendo
de dónde caiga el píxel tocado en el orden permutado (de 0 % a 100 %, ≈50 % de
media) en vez de clavada en el 99,6 %.

Por eso la tabla publicada mide NPCR y UACI entre **dos criptogramas
independientes**, que es la única lectura bajo la cual los tres esquemas del banco
son comparables.

**Por qué se decidió así.** Es un hallazgo de la Fase 3, medido y derivado, no un
resultado que se esconde: la predicción exacta está aseverada contra la
implementación en `test_avalancha_ante_un_cambio_en_el_plano` y la cota en
`test_uaci_diferencial_esta_acotada_por_la_linealidad_del_XOR`
([`tests/chaos/test_cipher.py`](../tests/chaos/test_cipher.py)). Además,
`medir_imagen` deja `npcr` y `uaci` en `None` a propósito cuando no hay dos
criptogramas que comparar, en vez de devolver un número de aspecto correcto
(`test_medir_imagen_no_se_inventa_npcr_ni_uaci`).

**Qué haría falta.** Que la difusión mezclara **dos operaciones de grupo
distintas** (suma modular y XOR). Eso alcanza los valores canónicos, pero es un
cambio de esquema: toca el núcleo de un módulo cerrado e invalida el vector de
prueba. Es la decisión abierta **A1**, ver [`decisiones.md`](decisiones.md).

---

## Módulo 4 — Ruido de detector

### M4.1 — No es un QRNG certificado, y no debe usarse como tal

**Qué no hace.** Este módulo demuestra la cadena completa de extracción de
entropía sobre ruido de detector y mide su min-entropía con los estimadores de
NIST SP 800-90B. **No es un generador de números aleatorios certificado.** En
concreto no tiene:

- **Tests de salud en tiempo real** sobre la fuente. Un generador para uso
  criptográfico real ejecuta continuamente el *repetition count test* y el
  *adaptive proportion test* de SP 800-90B, para detectar que la fuente se ha
  degradado o averiado **mientras** produce bits. Aquí el análisis es *offline*,
  sobre datos grabados.
- **Modelo del atacante** (ver M4.4).
- **Certificación** de ningún tipo.

**Por qué se decidió así.** El módulo llena un hueco concreto del proyecto —el
QRNG del Módulo 1 es pseudoaleatorio (M1.5)— demostrando el mecanismo de punta a
punta. Certificar una fuente de entropía es un proceso industrial que empieza por
controlar el dispositivo físico, que es justo lo que no tenemos (M4.2).

**Qué haría falta.** Control físico del detector, los dos tests de salud
corriendo en continuo con su política de qué hacer cuando saltan, un modelo del
atacante, y un proceso de certificación.

### M4.2 — Los datos son de segunda mano, y la señal es un *proxy*, no un ADC crudo

**Qué no hace.** No controlamos el detector ni sabemos con exactitud qué
preprocesado se aplicó antes de publicar los datos. Y hay un matiz más fuerte,
escrito en [`data/FUENTE.md`](../data/FUENTE.md), que no se suaviza aquí:

- **El plan B no se activó**: los datos son **reales** y públicos (CMS ZeroBias,
  CERN Open Data, licencia CC0, registro 31316).
- Pero la señal analizada es `nPFCands` —el número de candidatos reconstruidos por
  Particle Flow en cada evento—, **no una lectura directa de un ADC** ni un *run*
  de pedestal en sentido estricto. Es un *proxy* razonado: en eventos ZeroBias la
  mayoría de esos candidatos son fluctuaciones de baja actividad, así que su
  variación evento a evento lleva la firma estadística del ruido subyacente, pero
  **un paso más lejos** del ADC crudo que un pedestal ideal.
- Se intentó primero llegar a colecciones de bajo nivel de verdad (digis de ECAL,
  `siStripDigis`, `BeamSpotOnline`, `LumiScalers` —que incluía un campo
  `lumiNoise_` que habría sido ideal—) y las cinco fallaron: `uproot` no puede
  deserializar las clases C++ propietarias de CMSSW en que están serializadas. Es
  una limitación conocida de `uproot` frente a formatos anteriores a NanoAOD, no
  un descuido de esta exploración.

**Por qué se decidió así.** Entre un dato real que es un *proxy* y un dato
sintético perfecto se eligió el real, y se escribió con precisión qué es. La
alternativa —el plan B de ruido sintético— habría dado una verdad conocida de
antemano contra la que verificar el análisis, y se descartó porque los datos
reales resultaron alcanzables dentro del límite de tres días.

**Qué haría falta.** Acceso a un *run* de pedestal crudo en un formato legible sin
CMSSW, o directamente un banco de laboratorio: un sensor, un amplificador y un
ADC bajo nuestro control. Eso último es lo único que además levantaría la mitad de
M4.1.

### M4.3 — La frecuencia de muestreo es una convención, no una medida

**Qué no hace.** `fs = 1000.0` **no es una frecuencia física medida**. Los eventos
ZeroBias no llegan a intervalos regulares del reloj del acelerador, y no se ha
investigado la tasa de eventos real del *run* de 2016G.

**Por qué se decidió así.** Se fija un valor nominal solo para que el eje de
frecuencias del análisis de Welch tenga una escala consistente. Todo el análisis
espectral —el exponente α, la detección de picos, el filtrado— es válido *en
unidades de la propia señal*.

**Consecuencia, que hay que leer literalmente:** cualquier frecuencia que el
módulo identifique se interpreta como «por cada mil eventos», **no en Hz reales**.
En particular, un pico detectado no es la red eléctrica a 50 Hz por mucho que
caiga en el número 50.

**Qué haría falta.** La tasa de eventos real del *run*, o datos con marca de
tiempo por evento.

### M4.4 — No hay modelo de atacante

**Qué no hace.** No se analiza qué podría hacer alguien capaz de influir en el
detector, de conocer la fase de la red eléctrica, o de tener acceso a otros
canales correlacionados del mismo experimento.

**Por qué se decidió así.** Un modelo de atacante para una fuente de entropía
empieza por delimitar qué parte del dispositivo controla el adversario, y sin
control físico del dispositivo (M4.2) esa pregunta no tiene un enunciado honesto.

**Qué haría falta.** El dispositivo bajo control, y entonces el modelo estándar:
qué observa el atacante, qué puede inyectar, y cuánta min-entropía queda
**condicionada** a lo que él sabe —que es la magnitud que de verdad importa, y no
la min-entropía a secas que este módulo mide.

### M4.5 — La estimación vale para esta muestra concreta

**Qué no hace.** La min-entropía publicada vale para **estos** datos, en **estas**
condiciones. Otro *run*, otra temperatura, otro canal o incluso otro fichero del
mismo *dataset* pueden dar otra cifra. No es una propiedad de «el ruido de
detector»: es la medida de una adquisición.

**Por qué se decidió así.** Es lo que una estimación a partir de una muestra puede
afirmar, y SP 800-90B está construido sobre esa cautela: por eso se aplican tres
estimadores y se toma el **mínimo** de los tres
(`test_se_devuelve_el_minimo`), y por eso el del valor más común usa la cota
superior de su intervalo de confianza al 99 % y no el valor puntual. Equivocarse
por conservador cuesta bits; equivocarse por optimista produce bits que no son
uniformes.

Hay evidencia directa de que la muestra importa: al preparar el subconjunto se
descartó concatenar cinco ficheros del índice porque las medias por fichero iban
de 871 a 1436 —un 65 % de rango, con escalones claros entre ficheros—, lo que
habría metido estructura de baja frecuencia **artificial** en el ajuste del
exponente α. El fichero final es un único bloque contiguo.

**Qué haría falta.** Repetir la estimación sobre varios *runs* y publicar la
dispersión entre ellos, no una cifra sola. Y, para una fuente en servicio, los
tests de salud en continuo de M4.1, que son exactamente el mecanismo que vigila
que la cifra medida un día siga valiendo al siguiente.

### M4.6 — Pasar los tests estadísticos no demuestra que la fuente sea buena

**Qué no hace.** Los bits extraídos pasan el monobit y el χ² de bytes con
tolerancias derivadas (`test_los_bits_extraidos_pasan_el_monobit`,
`test_los_bits_extraidos_pasan_el_chi2_por_las_dos_colas`, en
[`tests/detector/test_extraccion.py`](../tests/detector/test_extraccion.py)).
**Eso no prueba nada sobre la calidad de la fuente.** Es la misma lección que el
Módulo 3 dedica un capítulo entero a denunciar: son condiciones necesarias, no
suficientes. Un contador cifrado con AES las pasa perfectamente y no tiene ni un
bit de entropía real.

**Por qué se decidió así.** Lo que garantiza la salida no son los tests: es la
estimación **conservadora** de la min-entropía más el *leftover hash lemma*. Los
tests solo confirman que no hay un fallo grosero en el camino, y se presentan
así.

**Qué haría falta.** Nada que un test estadístico pueda dar. La garantía viene de
medir bien la entropía de la fuente y de comprimir hasta lo que esa entropía
sostiene, y eso ya está hecho —con los límites de M4.1 a M4.5.

---

## Y aun así

Estas son las limitaciones de un proyecto que sabe dónde están. Cada módulo cerró
declarando su borde: el Módulo 1 que su QRNG es pseudoaleatorio, el Módulo 2 que
Shor no rompe RSA, el Módulo 3 que las métricas del campo no prueban seguridad, y
el Módulo 4 que esto no es un QRNG certificado.

Las decisiones que siguen abiertas, con sus opciones y su estado, están en
[`decisiones.md`](decisiones.md).
