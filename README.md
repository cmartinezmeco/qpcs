# QPCS — Quantum & Physics Cryptography Suite

An interdisciplinary suite of quantum cryptography, post-quantum cryptography,
and deterministic chaos encryption modules, developed by a team combining
Physics, Cybersecurity, and Data Engineering backgrounds.

---

## Installation

### Prerequisites

- Windows with **WSL2** (Ubuntu 22.04/24.04) — or native Linux/macOS
- **Docker** (Docker Desktop with WSL2 integration if on Windows)
- **Python 3.11**
- **Git** and **GitHub CLI** (`gh`)
- **Visual Studio Code** with the WSL extension (if working from Windows)

### 1. Clone the repository

git clone https://github.com/cmartinezmeco/qpcs.git
cd qpcs

### 2. Install Python 3.11 (if you don't have it)

sudo add-apt-repository ppa:deadsnakes/ppa -y
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3.11-dev

### 3. Install system dependencies needed to compile liboqs

sudo apt install -y build-essential cmake gcc g++ git libssl-dev ninja-build

### 4. Create the local virtual environment (for development, autocomplete, and tests)

python3.11 -m venv .venv
source .venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt

> The virtual environment is only for comfortable local development
> (autocomplete, linting, standalone tests in the editor). The official
> execution of the project always happens via Docker (see step 6).

### 5. liboqs manual build (required for the local venv only)

liboqs-python==0.14.1 cannot auto-install its C dependency, because it
tries to clone a liboqs git tag (0.14.1) that does not exist upstream.
Build it manually once:

cd ~
git clone --branch 0.14.0 --depth=1 https://github.com/open-quantum-safe/liboqs
cd liboqs
mkdir build && cd build
cmake -DBUILD_SHARED_LIBS=ON -DCMAKE_INSTALL_PREFIX=$HOME/_oqs ..
make -j$(nproc)
make install

Then make the path permanent:

echo 'export OQS_INSTALL_PATH=$HOME/_oqs' >> ~/.bashrc
source ~/.bashrc

> Note: this manual step is only needed for your local .venv. The
> Dockerfile already handles this automatically — see step 6.

### 6. Build and run the Docker container

docker build -t qpcs .
docker run --rm -it -p 8501:8501 qpcs

This guarantees the project runs identically regardless of the host
operating system or locally installed versions.

### 7. Configure VS Code

1. Open the project folder from WSL: `code .`
2. Install the following extensions (recommended for the whole team):
   - Python (Microsoft)
   - Pylance (Microsoft)
   - Docker (Microsoft)
   - Jupyter (Microsoft)
   - GitLens
3. `.vscode/settings.json` is included in the repository and automatically
   configures the formatter (Black) and the `.venv` interpreter for the
   whole team.

### 8. Verify the installation

python -c "import qiskit, oqs, numpy, scipy, matplotlib, cryptography, streamlit, numba; print('Qiskit:', qiskit.__version__); print('liboqs:', oqs.oqs_python_version()); print('All OK')"
pytest tests/

---

## Repository structure

/qpcs
├── .vscode/               <- Shared VS Code configuration
├── docker/                <- Container configurations
├── src/                   <- Source code
│   ├── qkd/                <- Module 1: QKD (BB84) + QRNG
│   ├── pqc/                <- Module 2: Post-Quantum Cryptography + Shor
│   ├── chaos/               <- Module 3: Deterministic chaos encryption
│   └── utils/                <- Visualization helper functions
├── tests/                  <- Unit tests (pytest)
├── notebooks/               <- Prototyping notebooks (Jupyter)
├── Dockerfile
├── requirements.txt
└── README.md

## Project modules

- **Module 1 — QKD + QRNG:** simulation of the BB84 protocol, a quantum
  random number generator, and an interactive dashboard (Streamlit)
  showing the QBER in real time in the presence of an eavesdropper ("Eve").
- **Module 2 — Post-Quantum Cryptography:** performance comparison between
  classical cryptography (RSA/ECC) and post-quantum cryptography
  (Kyber/Dilithium), plus a Shor's algorithm demo using Qiskit.
- **Module 3 — Deterministic chaos:** image encryption using chaotic
  attractors (Lorenz / Logistic Map).
- **Module 4 (optional) — Particle detector noise** as an entropy source
  (TRNG).

## Tech stack

| Area | Technologies |
|---|---|
| Quantum computing | Qiskit, Qiskit-Aer |
| Numerical computation | NumPy, SciPy, Numba |
| Classical cryptography | cryptography |
| Post-quantum cryptography | liboqs-python |
| Visualization / dashboard | Matplotlib, Seaborn, Streamlit |
| Testing | Pytest |
| Containers | Docker |

## Git workflow

- Never work directly on main.
- Descriptive branch names: feature/module1-qkd-physics,
  feature/benchmarking-pqc, fix/chaos-rk4-precision.
- Every change is merged via Pull Request, reviewed and approved by at
  least one other team member before merging.

## Team

- **Physics:** theoretical and physical modeling (BB84, Shor, chaotic
  systems).
- **Cybersecurity:** key reconciliation, PQC, entropy analysis.
- **Data Engineering:** interfaces, optimization, benchmarking, Docker.
