"""Write the API contract to openapi.json (the frontend generates its types from it)."""

import json
import os
from pathlib import Path

os.environ.setdefault("AUTH_ENABLED", "false")  # the contract is identical; no secrets needed

from app.main import app  # noqa: E402

OUT = Path(__file__).resolve().parents[2] / "openapi.json"

if __name__ == "__main__":
    OUT.write_text(json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n")
    print(f"wrote {OUT}")
