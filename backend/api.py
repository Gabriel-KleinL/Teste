"""FastAPI para otimização dinâmica e hospedagem do frontend existente."""
import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api_models import OtimizacaoInput
from optimization_service import carregar_catalogo, otimizar

app = FastAPI(title="Rotas ES API", version="2.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/municipios")
def municipios():
    return carregar_catalogo()


@app.post("/api/otimizar")
def calcular_rotas(requisicao: OtimizacaoInput):
    try:
        return otimizar(requisicao)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Não foi possível calcular as rotas: {exc}") from exc


FRONTEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
