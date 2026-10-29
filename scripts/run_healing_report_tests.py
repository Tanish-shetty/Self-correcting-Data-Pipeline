"""Capture an actual pytest subprocess result for the evidence report."""
import json
import subprocess
import sys
from uuid import uuid4
from datetime import datetime, timezone
from pathlib import Path

root = Path(__file__).resolve().parents[1]
args = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"]
args += ["--basetemp", str(root / "artifacts" / f"pytest-{uuid4().hex}")]
result = subprocess.run(args, cwd=root, capture_output=True, text=True, timeout=120)
target = root / "artifacts/healing-report/tests.json"
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text(json.dumps({"command": "python -m pytest -q -p no:cacheprovider",
                              "scope": "Full suite, including isolated local SQLite persistence tests",
                              "exit_code": result.returncode, "stdout": result.stdout,
                              "stderr": result.stderr, "captured_utc": datetime.now(timezone.utc).isoformat()}, indent=2), encoding="utf-8")
print(result.stdout)
raise SystemExit(result.returncode)
