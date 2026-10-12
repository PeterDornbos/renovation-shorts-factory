#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python -c 'import sys; assert sys.version_info[:2] == (3, 11), "Use Python 3.11"'
python -m pip install 'pip==25.3'
python -m pip install --index-url https://download.pytorch.org/whl/cpu 'torch==2.6.0+cpu' 'torchaudio==2.6.0+cpu'
python -m pip install -r requirements-voiceover.txt
python -m pip check
