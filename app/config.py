import os
from pathlib import Path

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./flowpilot.db")
INVOICE_DIR = Path(os.getenv("INVOICE_DIR", str(Path(__file__).resolve().parent.parent / "sample_data")))
APPROVAL_THRESHOLD = float(os.getenv("APPROVAL_THRESHOLD", "1000"))
OLLAMA_ENABLED = os.getenv("OLLAMA_ENABLED", "false").lower() == "true"
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
