# Fieldgrade on a Windows laptop

This repo already runs on Windows, but the recommended “laptop-grade” setup is **WSL2 (Ubuntu/Debian)** for a full Linux userland.
If you prefer, you can also run **natively on Windows** via PowerShell.

---

## Option A (recommended): WSL2 + Ubuntu

### 0) Install WSL2 + Ubuntu

1. Enable/install **Windows Subsystem for Linux (WSL)**.
2. Install an Ubuntu distro from the Microsoft Store.
3. Start Ubuntu and complete the first-run user setup.

> Tip: keep your repo inside the WSL filesystem (e.g. `~/src/...`) for best performance.

### 1) Setup

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git

cd ~/src
# copy or git-clone this repo here

python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt

pip install -e termite_fieldpack
pip install -e mite_ecology
pip install -e fieldgrade_ui
```

### 2) Run UI + worker

**Terminal 1 (UI):**
```bash
. .venv/bin/activate
python -m fieldgrade_ui serve
```

**Terminal 2 (worker):**
```bash
. .venv/bin/activate
python -m fieldgrade_ui worker
```

Open:
- `http://127.0.0.1:8787`

---

## Option B: Native Windows (PowerShell)

### 0) Prerequisites

- Python 3.11+ on PATH
- Git on PATH

### 1) Setup + run

**UI:**
```powershell
.\run_ui.ps1
```

**Worker (separate terminal, recommended):**
```powershell
.\run_worker.ps1
```

Open:
- `http://127.0.0.1:8787`

---

## Environment variable notes (Windows paths)

If you use `FG_API_EXTRA_ROOTS` (to allow the UI to read from extra folders), the separator is:

- **Windows:** semicolon `;` (example: `C:\Data;D:\Shared`)
- **Linux/WSL/Termux:** colon `:` (example: `/data:/mnt/shared`)

This repo now auto-detects the platform separator and keeps backward compatibility.
