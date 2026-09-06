FROM python:3.11-slim-bookworm

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

# TAREA 4.14: el CMD por defecto lanzaba "python main.py" (un placeholder del
# setup inicial de la Fase 1, commit 5eac863, que solo imprime una linea y
# termina). Con eso, el paso 4 del Quick Start del README
# ("docker run --rm -it -p 8501:8501 qpcs") NO levantaba el dashboard: el
# contenedor arrancaba, imprimia el mensaje y salia. Nadie lo habia probado
# de forma automatica hasta el paso "Arranque rapido" de la CI (tarea 4.14),
# que lo destapo. docker-compose.yml ya sobreescribia este comando para el
# servicio "app" con las mismas flags (--server.address=0.0.0.0 es
# obligatorio, ver su comentario); ahora es tambien el comportamiento por
# defecto de la imagen, que es lo que el README promete.
CMD ["streamlit", "run", "dashboard/qkd_app.py", "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true"]
