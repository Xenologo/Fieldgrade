#!/usr/bin/env bash
set -euo pipefail

python -m venv .venv
. .venv/bin/activate

pip install -r termite_fieldpack/requirements.txt
pip install -r mite_ecology/requirements.txt
pip install -e termite_fieldpack
pip install -e mite_ecology

cd termite_fieldpack
./bin/termite init
./bin/termite ingest ../README.md
BUNDLE=$(./bin/termite seal --label demo)
./bin/termite verify "$BUNDLE"
cd ../mite_ecology
./bin/mite-ecology init
./bin/mite-ecology import-bundle "$BUNDLE"
./bin/mite-ecology gnn
./bin/mite-ecology gat
./bin/mite-ecology motifs
./bin/mite-ecology ga
./bin/mite-ecology export
echo "Done."
