# Fieldgrade on Android (Termux)

This repo is designed to run **fully offline/locally** on Android via Termux:
- **Termite Fieldpack** (ingest → seal → verify)
- **mite_ecology** (import → synth → gnn/gat/ga → export → replay-verify)
- **Fieldgrade UI/API** (FastAPI) + **Job Worker** (SQLite-backed queue)

## 0) Termux prerequisites

Install Termux from **F-Droid** and then in Termux:

```bash
pkg update -y && pkg upgrade -y
pkg install -y python git clang make cmake pkg-config openssl libffi rust unzip zip
```

Enable shared storage access:

```bash
termux-setup-storage
```

After that, shared storage is available under:

```bash
ls ~/storage/shared/
```

> Note on OneDrive: Android does **not** mount OneDrive as a normal filesystem folder.
> If your ZIP is in OneDrive, download it to the device (e.g., **Download** folder), or use the file picker.

## 1) Unzip the repo

If your ZIP is in your Downloads folder:

```bash
cd ~/storage/shared/Download
unzip FIELDGRADE_FULLSTACK_*.zip -d fieldgrade
cd fieldgrade
```

(If you already unzipped it elsewhere, just `cd` into the extracted folder.)

## 2) Setup (creates .venv)

```bash
bash scripts/termux_setup.sh
```

This installs:
- runtime deps (`requirements.txt`)
- dev/test deps (`requirements-dev.txt`)
- editable installs of `termite_fieldpack`, `mite_ecology`, and `fieldgrade_ui`

## 3) Run

### Option A: Quickstart (UI only; embedded worker enabled when FG_WORKERS=1)

```bash
bash scripts/termux_quickstart.sh
```

Visit (on-device):

- `http://127.0.0.1:8787`

Or expose to LAN (same Wi‑Fi):

```bash
FG_HOST=0.0.0.0 FG_PORT=8787 bash scripts/termux_run_ui.sh
```

### Option B: Recommended for “volume” (UI server + separate worker)

**Terminal 1 (server):**
```bash
FG_HOST=0.0.0.0 FG_PORT=8787 FG_WORKERS=1 FG_ENABLE_WORKER=0 bash scripts/termux_run_ui.sh
```

**Terminal 2 (worker):**
```bash
bash scripts/termux_run_worker.sh
```

This avoids duplicated work if you later run multiple HTTP workers.

## 4) Use the Jobs panel (Autopilot)

Open the UI → **Jobs**:
- choose a label
- upload a PDF/CSV/XLSX/etc
- click **Enqueue pipeline job**

The worker will run:

1. `termite ingest`
2. `termite seal`
3. `termite verify`
4. `mite_ecology init`
5. `mite_ecology import-bundle`
6. `mite_ecology auto-run`
7. `mite_ecology replay-verify`

You can watch logs live inside the UI.

## 5) Diagnostics

```bash
source .venv/bin/activate
python -m fieldgrade_ui doctor
```

## 6) Troubleshooting

- **“python-multipart not installed”**: run `bash scripts/termux_setup.sh` (runtime deps are pinned in `fieldgrade_ui/requirements.txt`).
- **Can’t see shared storage**: run `termux-setup-storage` again and restart Termux.
- **LAN access doesn’t work**: ensure `FG_HOST=0.0.0.0` and your phone + laptop are on the same Wi‑Fi.
