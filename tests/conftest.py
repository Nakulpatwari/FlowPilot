import os
import tempfile
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    monkeypatch.setenv("INVOICE_DIR", str(Path(__file__).resolve().parents[1] / "sample_data"))
    monkeypatch.setenv("APPROVAL_THRESHOLD", "1000")
    # db/config are imported by the app, so reload modules to use the test DB.
    import app.config as config
    import app.db as db
    import app.models as models
    import app.runtime as runtime
    import app.main as main
    config.DATABASE_URL = f"sqlite:///{db_path.as_posix()}"
    config.INVOICE_DIR = Path(__file__).resolve().parents[1] / "sample_data"
    config.APPROVAL_THRESHOLD = 1000.0
    db.engine.dispose()
    db.engine = __import__("sqlalchemy").create_engine(f"sqlite:///{db_path.as_posix()}", connect_args={"check_same_thread": False})
    db.SessionLocal.configure(bind=db.engine)
    db.Base.metadata.drop_all(bind=db.engine)
    db.init_db()
    main.app.router.on_startup = []
    with TestClient(main.app) as c:
        yield c
    db.engine.dispose()
