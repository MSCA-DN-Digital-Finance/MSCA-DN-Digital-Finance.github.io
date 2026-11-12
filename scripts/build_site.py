#!/usr/bin/env python3
"""Build the DIGITAL organization landing page without external dependencies."""
from pathlib import Path
import shutil
ROOT=Path(__file__).resolve().parents[1]
out=ROOT/'_site'
if out.exists():shutil.rmtree(out)
shutil.copytree(ROOT/'site',out)
(out/'.nojekyll').touch()
print(f'Built research resources home → {out}')
