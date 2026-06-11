from pathlib import Path

from app.config import settings

RUNTIME_MODEL_FILE = Path(__file__).resolve().parents[2] / '.runtime_ollama_model'


def load_saved_model() -> str:
    try:
        saved_model = RUNTIME_MODEL_FILE.read_text(encoding='utf-8').strip()
        return saved_model or settings.ollama_model
    except OSError:
        return settings.ollama_model


def save_model(model: str) -> None:
    RUNTIME_MODEL_FILE.write_text(model.strip(), encoding='utf-8')


def clear_saved_model() -> None:
    try:
        RUNTIME_MODEL_FILE.unlink()
    except OSError:
        pass
