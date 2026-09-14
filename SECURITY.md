# Política de seguridad

## Lo primero, porque es lo que más importa

**QPCS no protege nada. Es material educativo.**

Es un proyecto académico que implementa y mide cuatro esquemas criptográficos para
entender cómo funcionan por dentro, no para usarlos. Nada de lo que hay aquí ha pasado
por una revisión criptográfica independiente, y hay partes que son inseguras a propósito
porque su función es enseñar *por qué* lo son.

Si has llegado buscando una biblioteca con la que cifrar algo real, esta no es. Usa una
implementación auditada y mantenida.

Concretando dónde están los bordes, que están todos declarados:

- **El QRNG del Módulo 1 es pseudoaleatorio.** Corre sobre un simulador que por debajo
  usa un generador sembrado. Se simula el proceso cuántico; no se ejecuta.
- **El cifrado caótico del Módulo 3 no tiene prueba de seguridad, ni autenticación, ni
  nonce.** Tiene métricas excelentes, que es una cosa distinta. El propio módulo enseña
  que un contador trivial aprueba esas mismas métricas.
- **El Módulo 4 no es un generador de números aleatorios certificado.** Es un análisis
  sobre datos grabados por otros, sin tests de salud en tiempo real de la fuente.
- **Shor factoriza 15**, con el oráculo compilado a mano. No rompe claves.
- **Las claves que aparecen fijas en el código son de demostración** y están etiquetadas
  como tales. Toda la aleatoriedad de verdad sale de `os.urandom`.

Las limitaciones de los cuatro módulos, cada una con su porqué y con qué haría falta para
levantarla, están sin recortar en [`docs/limitaciones.md`](docs/limitaciones.md).

## Versiones que reciben arreglos

| Versión | Estado |
|---|---|
| `main` | Es la única. Los arreglos van ahí. |

No hay versiones publicadas ni ramas de mantenimiento. El proyecto se desarrolló en
cuatro fases y está cerrado; `main` es su estado final.

## Cómo avisar de un problema

**No abras una *issue* pública** para algo que creas explotable. Las *issues* son el sitio
correcto para cualquier otra cosa, pero no para esto.

Usa el aviso privado de GitHub: pestaña **Security** del repositorio → **Report a
vulnerability**. Llega solo a quien mantiene el repositorio y permite discutirlo antes de
que sea público.

Cuenta lo que puedas de esto, y si falta algo tampoco pasa nada:

- Qué fichero o función, con la línea si la tienes localizada.
- Qué hay que hacer para reproducirlo.
- Qué consecuencia tiene, o cuál crees que puede tener.
- La versión de Python o la imagen de Docker con la que lo has visto.

## Qué esperar

Somos tres personas y esto no es nuestro trabajo, así que no prometemos plazos que no
podamos cumplir. Lo que sí:

- Se responde al aviso, aunque sea para decir que no vamos a actuar y por qué.
- Si es real y tiene arreglo, se arregla en `main` y se dice en el mensaje del *commit*
  qué se corrigió.
- Si es real y no vamos a arreglarlo, se escribe como limitación en
  [`docs/limitaciones.md`](docs/limitaciones.md), que es donde el proyecto guarda lo que
  no hace. Una limitación declarada vale más que un arreglo a medias.
- Quien avisa aparece citado si quiere.

## Lo que queda fuera

- **Las limitaciones ya declaradas.** Están en `docs/limitaciones.md` con su explicación.
  Si una está mal argumentada, eso sí interesa: dilo por una *issue* normal.
- **Las claves de demostración del código.** Son fijas queriendo, llevan su comentario, y
  no protegen nada.
- **Las dependencias.** Si el problema está en `qiskit`, `cryptography`, `liboqs` o
  cualquier otra, repórtalo a quien la mantiene. Si te parece que aquí hay que subir una
  versión, eso es una *issue* normal y se agradece.
