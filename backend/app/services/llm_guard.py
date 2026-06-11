from fastapi import HTTPException

from app.generator import generator_service


def ensure_llm_ready() -> None:
    try:
        generator_service.ensure_ready()
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
