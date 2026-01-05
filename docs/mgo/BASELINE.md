# MGO v0.2 — Baseline (pre PR-01)

Date: 2026-01-05

Branch baseline: `main` @ `72d9732d35de58192a72c092d34c4dfe2afde303`
Local working branch at time of run: `mgo/pr-01-canonical-graphdelta-ledger`

## Tests

Command:

- `C:/Users/georg/Fieldgrade/.venv/Scripts/python.exe -m pytest -q --rootdir C:\Users\georg\Fieldgrade\FIELDGRADE_FULLSTACK_WINDOWS_LAPTOP_STRICT_DSSE_CDX\fg_next`

Result:

- PASS (all tests)

## Notes

- The mission references two external source-of-truth inputs:
  - `/mnt/data/README (7).md`
  - `/mnt/data/KG Observability and Actuation Protocols.pdf`

Those files are not present in this working tree. PR-01 proceeds using the requirements listed in the mission prompt.
If you want strict conformance to the PDF, please attach it into the repo (or provide the text) so we can mechanically cross-check.
