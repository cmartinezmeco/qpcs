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

# Instala el paquete qkd (src/qkd) en el entorno del contenedor, igual que
# hace la CI: sin esto, "from qkd.protocol import ..." falla en el
# dashboard y en pytest dentro del contenedor.
RUN pip install --no-cache-dir -e .

CMD ["python", "main.py"]
