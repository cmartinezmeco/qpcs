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

# Compilar liboqs 0.14.0 (la versión que SÍ existe como tag, evitando
# el desajuste con liboqs-python==0.14.1)
RUN git clone --branch 0.14.0 --depth=1 https://github.com/open-quantum-safe/liboqs /opt/liboqs && \
    mkdir /opt/liboqs/build && cd /opt/liboqs/build && \
    cmake -DBUILD_SHARED_LIBS=ON -DCMAKE_INSTALL_PREFIX=/opt/_oqs -GNinja .. && \
    ninja install && \
    rm -rf /opt/liboqs

ENV OQS_INSTALL_PATH=/opt/_oqs

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "main.py"]
