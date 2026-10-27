import json

from app.main import app
from scripts.export_openapi import OUT


def test_openapi_snapshot_is_current():
    """Contract changes must be deliberate: run `make openapi` and commit the diff."""
    committed = json.loads(OUT.read_text())
    assert committed == json.loads(json.dumps(app.openapi(), sort_keys=True))
