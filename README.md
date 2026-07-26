<div align="center">

# 🔐 QPCS — Quantum & Physics Cryptography Suite

**An interdisciplinary cryptography suite bridging quantum physics, post-quantum security and deterministic chaos.**

[![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Qiskit](https://img.shields.io/badge/Qiskit-1.0.2-6929C4?logo=qiskit&logoColor=white)](https://www.ibm.com/quantum/qiskit)
[![liboqs](https://img.shields.io/badge/liboqs-0.14.0-00A3E0)](https://openquantumsafe.org/)
[![Docker](https://img.shields.io/badge/Docker-ready-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)
[![Tests](https://img.shields.io/badge/tests-pytest-0A9EDC?logo=pytest&logoColor=white)](https://docs.pytest.org/)

</div>

---

## 📑 Table of contents

- [Overview](#-overview)
- [Quick start](#-quick-start-docker--recommended)
- [Full installation](#️-full-installation-local-development)
- [Verify your setup](#-verify-your-setup)
- [Troubleshooting](#-troubleshooting)
- [Repository structure](#-repository-structure)
- [Project modules](#-project-modules)
- [Tech stack](#-tech-stack)
- [Contributing & Git workflow](#-contributing--git-workflow)
- [Team](#-team)

---

## 🔎 Overview

QPCS is a modular suite combining **quantum key distribution**, **post-quantum cryptography** and **chaos-based encryption**, built by a team spanning Physics, Cybersecurity and Data Engineering.

| | |
|---|---|
| 🧪 **Module 1** | BB84 quantum key distribution + QRNG + eavesdropper simulation |
| 🛡️ **Module 2** | Post-quantum cryptography benchmarks + Shor's algorithm demo |
| 🌀 **Module 3** | Image encryption via chaotic attractors |
| ⚛️ **Module 4** | *(optional)* Particle detector noise as an entropy source |

---

## ⚡ Quick start (Docker — recommended)

> **The container is the source of truth.** It works identically on Windows (WSL2), Linux and macOS, and requires no manual `liboqs` build.

**1.** Clone the repository:

```bash
git clone https://github.com/cmartinezmeco/qpcs.git
```

**2.** Enter the project folder:

```bash
cd qpcs
```

**3.** Build the image (first build takes ~5–10 min — it compiles `liboqs` from source):

```bash
docker build -t qpcs .
```

**4.** Run it:

```bash
docker run --rm -it -p 8501:8501 qpcs
```

✅ If you see `QPCS - proyecto inicializado correctamente`, you're done.

---

## 🛠️ Full installation (local development)

The local virtual environment is **only** for comfortable editor work — autocomplete, linting, quick tests. Official execution always goes through Docker.

### Prerequisites

| Requirement | Notes |
|---|---|
| **WSL2 + Ubuntu 22.04/24.04** | Windows users only. Native Linux/macOS works too. |
| **Docker** | Docker Desktop with WSL2 integration enabled, or Docker Engine. |
| **Python 3.11** | Not 3.12+ — see [Troubleshooting](#-troubleshooting). |
| **Git + GitHub CLI** | `gh` for authentication against this private repo. |
| **VS Code + WSL extension** | Recommended editor setup. |

<br/>

### Step 1 — Authenticate with GitHub

> ⚠️ This repo is **private**. Accept your invitation at [`/invitations`](https://github.com/cmartinezmeco/qpcs/invitations) first, then authenticate with **your own** account:

```bash
gh auth login
```

<details>
<summary>📖 What to select in the prompts</summary>

<br/>

| Prompt | Choose |
|---|---|
| What account do you want to log into? | **GitHub.com** |
| Preferred protocol for Git operations? | **HTTPS** |
| Authenticate Git with your GitHub credentials? | **Yes** |
| How would you like to authenticate? | **Login with a web browser** |

</details>

<br/>

### Step 2 — Clone the repository

```bash
git clone https://github.com/cmartinezmeco/qpcs.git
```

```bash
cd qpcs
```

<br/>

### Step 3 — Install Python 3.11

<details>
<summary>💡 Skip this if <code>python3.11 --version</code> already works</summary>

<br/>

Ubuntu 24.04 ships Python 3.12 by default, so 3.11 comes from the deadsnakes PPA.

</details>

<br/>

```bash
sudo add-apt-repository ppa:deadsnakes/ppa -y
```

```bash
sudo apt update
```

```bash
sudo apt install -y python3.11 python3.11-venv python3.11-dev
```

Check it:

```bash
python3.11 --version
```

<br/>

### Step 4 — Install system build dependencies

Needed to compile `liboqs` (written in C):

```bash
sudo apt install -y build-essential cmake gcc g++ git libssl-dev ninja-build
```

<br/>

### Step 5 — Create the virtual environment

```bash
python3.11 -m venv .venv
```

```bash
source .venv/bin/activate
```

> ✅ Your prompt should now start with `(.venv)`.

```bash
pip install --upgrade pip
```

```bash
pip install -r requirements.txt
```

<br/>

### Step 6 — Build `liboqs` manually

> 🔴 **Required for the local venv only.** The Dockerfile does this automatically — skip this step if you only use Docker.
>
> **Why:** `liboqs-python==0.14.1` tries to auto-clone a `liboqs` git tag named `0.14.1`, which **does not exist upstream** (only `0.14.0` does). The auto-install therefore fails with `No oqs shared libraries found`. We build `0.14.0` manually instead.

```bash
cd ~
```

```bash
git clone --branch 0.14.0 --depth=1 https://github.com/open-quantum-safe/liboqs
```

```bash
cd liboqs && mkdir build && cd build
```

```bash
cmake -DBUILD_SHARED_LIBS=ON -DCMAKE_INSTALL_PREFIX=$HOME/_oqs ..
```

```bash
make -j$(nproc)
```

```bash
make install
```

Make the library path permanent:

```bash
echo 'export OQS_INSTALL_PATH=$HOME/_oqs' >> ~/.bashrc
```

```bash
source ~/.bashrc
```

<br/>

### Step 7 — Configure VS Code

Open the project from WSL:

```bash
code .
```

Install these extensions:

| Extension | Publisher | Purpose |
|---|---|---|
| **Python** | Microsoft | Language support |
| **Pylance** | Microsoft | Type checking & autocomplete |
| **Docker** | Microsoft | Container management |
| **Jupyter** | Microsoft | Notebook prototyping |
| **GitLens** | GitKraken | Commit history & peer review |

> 📌 `.vscode/settings.json` is committed to the repo and auto-configures **Black** and the `.venv` interpreter for the whole team.

---

## ✅ Verify your setup

**In your local venv:**

```bash
python -c "import qiskit, oqs, numpy, scipy, matplotlib, cryptography, streamlit, numba; print('Qiskit:', qiskit.__version__); print('liboqs:', oqs.oqs_python_version()); print('All OK')"
```

**Inside the container:**

```bash
docker run --rm qpcs python -c "import qiskit, oqs; print('Qiskit:', qiskit.__version__); print('liboqs:', oqs.oqs_python_version()); print('All OK')"
```

**Run the test suite:**

```bash
pytest tests/
```

Expected output:

```
Qiskit: 1.0.2
liboqs: 0.14.1
All OK
```

---

## 🩺 Troubleshooting

<details>
<summary><b>❌ <code>RuntimeError: No oqs shared libraries found</code></b></summary>

<br/>

`liboqs-python` failed to auto-install its C dependency. Two causes:

**1.** You skipped **Step 6** → build `liboqs` manually.

**2.** `OQS_INSTALL_PATH` isn't set in your current shell. Check it:

```bash
echo $OQS_INSTALL_PATH
```

If empty:

```bash
export OQS_INSTALL_PATH=$HOME/_oqs
```

If a broken half-installed folder exists, remove it and retry:

```bash
rm -rf ~/_oqs
```

</details>

<details>
<summary><b>❌ <code>fatal: Remote branch 0.14.1 not found in upstream origin</code></b></summary>

<br/>

Expected — that tag doesn't exist upstream. Don't fight it: follow **Step 6** and build `0.14.0` manually.

</details>

<details>
<summary><b>❌ Dependencies fail to install in my venv</b></summary>

<br/>

Check you're on Python 3.11, not 3.12+:

```bash
python --version
```

Qiskit-Aer, Numba and liboqs-python have wheel/compilation issues on newer Python versions. If it says 3.12, delete the venv and recreate it:

```bash
rm -rf .venv && python3.11 -m venv .venv && source .venv/bin/activate
```

</details>

<details>
<summary><b>❌ <code>git clone</code> asks for a password / permission denied</b></summary>

<br/>

The repo is **private**. Make sure you have:

**1.** Accepted the collaborator invitation.

**2.** Authenticated with **your own** GitHub account:

```bash
gh auth status
```

Never use someone else's token.

</details>

<details>
<summary><b>🐢 Docker build is very slow / transfers gigabytes</b></summary>

<br/>

Check `.dockerignore` exists and excludes `.venv/`. The build context should be **kilobytes**, not GB.

</details>

---

## 📁 Repository structure

```
qpcs/
│
├── 📂 .vscode/              # Shared VS Code configuration (Black, interpreter)
├── 📂 docker/               # Container configurations
│
├── 📂 src/                  # Source code
│   ├── 📂 qkd/              # Module 1 · QKD (BB84) + QRNG
│   ├── 📂 pqc/              # Module 2 · Post-Quantum Cryptography + Shor
│   ├── 📂 chaos/            # Module 3 · Deterministic chaos encryption
│   └── 📂 utils/            # Shared visualization helpers (Matplotlib)
│
├── 📂 tests/                # Unit tests (pytest)
├── 📂 notebooks/            # Jupyter prototyping (equations, quick maths)
│
├── 🐳 Dockerfile            # Reproducible environment (builds liboqs)
├── 📄 requirements.txt      # Pinned dependencies (==, never >=)
├── 📄 .dockerignore
├── 📄 .gitignore
└── 📄 README.md
```

---

## 🧩 Project modules

### 🧪 Module 1 — QKD + QRNG

Simulation of the **BB84 protocol**, a quantum random number generator, and an interactive Streamlit dashboard showing the **QBER** in real time in the presence of an eavesdropper ("Eve").

> The QBER rises from 0% to ~25% when Eve intercepts — a direct consequence of the no-cloning theorem and wavefunction collapse.

### 🛡️ Module 2 — Post-Quantum Cryptography

Performance comparison between classical cryptography (**RSA/ECC**) and post-quantum cryptography (**ML-KEM/ML-DSA**, the NIST-standardized successors of Kyber/Dilithium), plus a **Shor's algorithm** demo using Qiskit.

> This half is **not a simulation**: ML-KEM and ML-DSA run for real on `liboqs`, the same code that protects production systems today.

A real message encrypted with **ML-KEM-768** (KEM → HKDF-SHA256 → AES-256-GCM) and signed with **ML-DSA-65** — sample run, keys are freshly generated on every call and never seeded:

```text
message         : La criptografia post-cuantica protege esto en 2035.
kem_ciphertext  : 1088 B -> 52f550b7a56f6ad45b22db1627db6711 ...
nonce           :   12 B -> e0e6580fe247bbe131e509fb          (fresh per message)
aead_ciphertext :   67 B -> 0f949829636ec755bcd6293ecb65d5d9 ...
decrypted       : La criptografia post-cuantica protege esto en 2035.   ✅

signed          : comunicado oficial QPCS
public key      : 1952 B
signature       : 3309 B -> c644797e421aacfc8cd89cfc6be513a6 ...
verifies        : True    ✅  (flip one bit of the message → False)
```

The honest trade-off in one line: an **Ed25519** signature takes 64 bytes, an **ML-DSA-65** one takes 3309 — about 50× more. That cost in bytes, not in CPU, is what migrating actually buys you. Round-trips, tamper detection and sizes are pinned by tests: `tests/pqc/test_hybrid.py`, `tests/pqc/test_sig.py`, `tests/pqc/test_classical.py`.

### 🌀 Module 3 — Deterministic chaos

Image encryption using **chaotic attractors** (Lorenz / Logistic Map), with entropy and pixel-correlation tests proving no statistical information leaks.

### ⚛️ Module 4 *(optional)* — Particle detector noise

Using thermal/quantum noise from silicon sensors (CERN Open Data) as a **true random number generator** entropy source.

---

## 🧰 Tech stack

| Area | Technologies |
|---|---|
| ⚛️ **Quantum computing** | `Qiskit` · `Qiskit-Aer` |
| 🔢 **Numerical computation** | `NumPy` · `SciPy` · `Numba` |
| 🔒 **Classical cryptography** | `cryptography` |
| 🛡️ **Post-quantum cryptography** | `liboqs-python` |
| 📊 **Visualization / dashboard** | `Matplotlib` · `Seaborn` · `Streamlit` |
| 🧪 **Testing** | `Pytest` |
| 🐳 **Containers** | `Docker` |

---

## 🤝 Contributing & Git workflow

> 🚫 **Never work directly on `main`.**

**1.** Create a descriptive branch:

```bash
git checkout -b feature/module1-qkd-physics
```

<details>
<summary>📖 Branch naming convention</summary>

<br/>

| Pattern | Example |
|---|---|
| `feature/<module>-<what>` | `feature/module1-qkd-physics` |
| `feature/<what>` | `feature/benchmarking-pqc` |
| `fix/<what>` | `fix/chaos-rk4-precision` |
| `docs/<what>` | `docs/qkd-theory` |

</details>

<br/>

**2.** Stage and commit your work:

```bash
git add .
```

```bash
git commit -m "feat: implement BB84 basis sifting"
```

**3.** Push the branch:

```bash
git push -u origin feature/module1-qkd-physics
```

**4.** Open a Pull Request:

```bash
gh pr create --fill
```

### Review rules

| Rule | Detail |
|---|---|
| ✅ **1 PR = 1 task** | Small, reviewable changes. |
| 👀 **1 approval required** | Reviewed by at least one other team member before merge. |
| 🧪 **Tests are mandatory** | New logic without a test doesn't get merged. |
| 🐳 **Docker is the truth** | "Works in my venv" isn't good enough. |
| 📌 **Pinned versions only** | `==` in `requirements.txt`, never `>=`. |

---

## 👥 Team

| Role | Responsibilities |
|---|---|
| ⚛️ **Physics** | Theoretical & physical modeling — BB84, Shor's algorithm, chaotic systems. |
| 🛡️ **Cybersecurity** | Key reconciliation, PQC integration, entropy analysis. |
| 📊 **Data Engineering** | Interfaces, optimization, benchmarking, Docker & CI. |

---

<div align="center">

**QPCS** · Built with Qiskit, liboqs and a healthy respect for the no-cloning theorem.

</div>

