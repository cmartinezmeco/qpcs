# La base va fijada por digest y no solo por etiqueta. "3.11-slim-bookworm"
# es una etiqueta movil: apunta a una imagen distinta cada vez que Debian
# publica parches, asi que dos construcciones separadas por unas semanas no
# parten del mismo sitio. Este proyecto compara figuras por MD5 bit a bit y
# presume de que "si funciona en Docker, funciona": eso solo es cierto si la
# primera linea del Dockerfile nombra una imagen concreta.
#
# El digest corresponde a python:3.11-slim-bookworm. Para subirlo mas
# adelante, resolver la etiqueta otra vez y sustituirlo aqui; hay que
# regenerar las figuras en el mismo commit porque su MD5 puede moverse.
FROM python:3.11-slim-bookworm@sha256:528257d48c1da0dcecc2e725d1ae34498d60c965f1241e39cd6a85a8859bdf84

# Dependencias del sistema para compilar liboqs y liboqs-python
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    ninja-build \
    gcc \
    git \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Compilar liboqs 0.16.0 (la versión que SÍ existe como tag, evitando
# el desajuste con liboqs-python==0.16.0)
RUN git clone --branch 0.16.0 --depth=1 https://github.com/open-quantum-safe/liboqs /opt/liboqs && \
    mkdir /opt/liboqs/build && cd /opt/liboqs/build && \
    cmake -DBUILD_SHARED_LIBS=ON -DCMAKE_INSTALL_PREFIX=/opt/_oqs -GNinja .. && \
    ninja install && \
    rm -rf /opt/liboqs

ENV OQS_INSTALL_PATH=/opt/_oqs

WORKDIR /app

# requirements-dev.txt (ruff/black/mypy) entra en la imagen a partir de la
# Fase 2: la CI ya no instala nada en el runner, corre el lint y los tipos
# DENTRO del contenedor (ver .github/workflows/ci.yml), asi que las
# herramientas tienen que vivir aqui. Es la misma imagen que usa el dashboard;
# el peso extra de las herramientas de dev es despreciable.
COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir -r requirements-dev.txt

COPY . .

# Instala los paquetes de src/ (qkd, pqc y chaos: packages.find los coge los
# tres, ver pyproject.toml) en el entorno del contenedor. Sin esto, "from
# qkd.protocol import ...", "from pqc.shor import ..." y "from chaos import
# cifrar_imagen" fallan en el dashboard y en pytest dentro del contenedor.
RUN pip install --no-cache-dir -e .

# Todo lo que hay encima de esta linea necesita root: instalar paquetes del
# sistema, compilar liboqs y escribir en site-packages. Lo que va debajo, no.
#
# Un contenedor que sirve una aplicacion web como root es un riesgo gratuito:
# si algo de la cadena falla, el proceso comprometido arranca con todos los
# permisos dentro del contenedor. Streamlit no necesita ninguno.
#
# El UID 1000 no es arbitrario. El servicio "figuras" de docker-compose.yml
# monta el repositorio del anfitrion dentro del contenedor y regenera los PNG
# ahi; con el proceso corriendo como root, esos ficheros aparecian en la
# maquina del anfitrion como root:root y no se podian borrar sin sudo. Es de
# donde salia el .coverage de root que arrastraba el directorio de trabajo.
# 1000 es el primer UID de usuario en Debian y en la practica coincide con el
# del usuario del anfitrion en Linux y en WSL.
RUN groupadd --gid 1000 qpcs \
    && useradd --uid 1000 --gid 1000 --create-home --shell /bin/bash qpcs \
    && chown -R qpcs:qpcs /app

USER qpcs

# El CMD por defecto levanta el dashboard, que es lo que el Quick Start del
# README promete con "docker run --rm -it -p 8501:8501 qpcs". Durante mucho
# tiempo apunto a un placeholder de la Fase 1 que solo imprimia una linea y
# terminaba, asi que el contenedor arrancaba y se cerraba sin dashboard;
# nadie lo detecto hasta que la CI empezo a comprobar el arranque de verdad.
# El servicio "app" de docker-compose.yml repite el mismo comando con las
# mismas banderas (--server.address=0.0.0.0 es obligatoria: ver su
# comentario).
CMD ["streamlit", "run", "dashboard/qkd_app.py", "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true"]
