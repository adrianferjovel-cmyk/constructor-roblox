"""
Servidor puente cerebro <-> Roblox, ampliado con un motor de construcción.

Endpoints:
  POST /crear            -> recibe una frase en lenguaje natural y la convierte
                            en un modelo (razonador + motor).
  POST /build            -> recibe un blueprint JSON directamente.
  POST /antigravity/hook -> compatible con el "cerebro" original (formato viejo).
  GET  /roblox/poll      -> Roblox hace polling aquí y construye.
  GET  /historial        -> lista de modelos generados en esta sesión.
  GET  /api/estructuras  -> qué sabe construir el programa.
  GET  /                 -> panel web de chat.
"""
from __future__ import annotations

import os
from typing import List, Optional
import threading
import time

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from generador.blueprint import Modelo, Parte, desde_json
from generador.razonador import interpretar, NoEncontrada
from generador.biblioteca import ESTRUCTURAS
from generador.validar import informe, autocorregir

app = FastAPI(title="Constructor Roblox", version="2.1")

# ---------------------------------------------------------------------------
# Seguridad para la nube: si CLAVE_API está definida (variable de entorno),
# todos los endpoints exigen la cabecera X-API-Key. En local sin clave,
# todo queda abierto como siempre.
# ---------------------------------------------------------------------------
CLAVE_API = os.environ.get("CLAVE_API", "").strip()


def requerir_clave(x_api_key: str = Header(default="")) -> None:
    if not CLAVE_API:
        return
    if x_api_key != CLAVE_API:
        raise HTTPException(status_code=401, detail="Clave API inválida")

# ---------------------------------------------------------------------------
# Cola de instrucciones para Roblox (polling)
# ---------------------------------------------------------------------------
_cola: List[Modelo] = []
_historial: List[dict] = []
_cerrojo = threading.Lock()

# Diagnóstico de conexión con Roblox
_pings = 0
_ultimo_ping: Optional[float] = None


def _encolar(modelo: Modelo):
    with _cerrojo:
        _cola.append(modelo)
        _historial.append({
            "id": modelo.id,
            "modelName": modelo.modelName,
            "partes": len(modelo.parts),
            "razonamiento": modelo.razonamiento,
        })
    print(f"📦 [SERVIDOR] Encolado: '{modelo.modelName}' "
          f"({len(modelo.parts)} piezas).")


# ---------------------------------------------------------------------------
# Modelos de petición
# ---------------------------------------------------------------------------
class PeticionTexto(BaseModel):
    texto: str


class PeticionBuild(BaseModel):
    modelName: str = "Modelo"
    parent: str = "Workspace"
    parts: List[dict] = Field(default_factory=list)
    razonamiento: List[str] = Field(default_factory=list)


class PartPropertiesViejo(BaseModel):
    """Formato del 'cerebro' original (compatibilidad)."""
    sizeX: float
    sizeY: float
    sizeZ: float
    posX: float
    posY: float
    posZ: float
    rotX: float = 0.0
    rotY: float = 0.0
    rotZ: float = 0.0
    r: int = 200
    g: int = 200
    b: int = 200
    material: str = "Plastic"
    scriptCode: Optional[str] = ""


class AgentPayload(BaseModel):
    actionType: str
    modelName: str
    parts: List[PartPropertiesViejo]


def _convertir_viejo(payload: AgentPayload) -> Modelo:
    """Convierte el formato del cerebro original al blueprint nuevo."""
    partes = []
    for p in payload.parts:
        partes.append(Parte(
            shape="Block",
            size=[p.sizeX, p.sizeY, p.sizeZ],
            position=[p.posX, p.posY, p.posZ],
            rotation=[p.rotX, p.rotY, p.rotZ],
            color=[p.r, p.g, p.b],
            material=p.material if p.material else "Plastic",
            script=p.scriptCode or "",
        ))
    return Modelo(modelName=payload.modelName, parts=partes,
                  razonamiento=["Recibido del cerebro (formato original)."])


# ---------------------------------------------------------------------------
# Rutas
# ---------------------------------------------------------------------------
@app.post("/crear", dependencies=[Depends(requerir_clave)])
def crear(peticion: PeticionTexto):
    """Convierte una frase en lenguaje natural en un modelo y lo encola."""
    texto = peticion.texto.strip()
    if not texto:
        return {"status": "error", "mensaje": "Escribe algo, por favor."}
    try:
        modelo, clave = interpretar(texto)
    except NoEncontrada as e:
        return {"status": "error", "mensaje": str(e)}
    # Loop de QA: autocorrige lo seguro y comprueba compatibilidad
    modelo, cambios = autocorregir(modelo)
    qa = informe(modelo)
    if not qa["resumen"]["es_valido"]:
        return {
            "status": "error",
            "mensaje": "El QA detectó problemas: " + "; ".join(qa["errores"][:4]),
            "qa": qa,
        }
    _encolar(modelo)
    return {
        "status": "success",
        "mensaje": f"¡Listo! Construí '{modelo.modelName}' con {len(modelo.parts)} piezas.",
        "modelo": modelo.a_payload(),
        "razonamiento": modelo.razonamiento,
        "qa": qa,
        "cambios": cambios,
    }


@app.post("/build", dependencies=[Depends(requerir_clave)])
def build(peticion: PeticionBuild):
    """Recibe un blueprint JSON directamente (para el agente o scripts)."""
    modelo = desde_json({
        "modelName": peticion.modelName,
        "parent": peticion.parent,
        "parts": [p for p in peticion.parts],
        "razonamiento": peticion.razonamiento,
    })
    modelo, cambios = autocorregir(modelo)
    qa = informe(modelo)
    if not qa["resumen"]["es_valido"]:
        return {
            "status": "error",
            "mensaje": "El QA detectó problemas: " + "; ".join(qa["errores"][:4]),
            "qa": qa,
        }
    _encolar(modelo)
    return {
        "status": "success",
        "mensaje": f"Blueprint encolado: '{modelo.modelName}' ({len(modelo.parts)} piezas).",
        "id": modelo.id,
        "qa": qa,
        "cambios": cambios,
    }


@app.post("/antigravity/hook", dependencies=[Depends(requerir_clave)])
def receive_from_brain(payload: AgentPayload):
    """Compatible con el cerebro original: convierte y encola."""
    modelo = _convertir_viejo(payload)
    errores = modelo.validar()
    if errores:
        return {"status": "error", "mensaje": "Blueprint inválido: " + "; ".join(errores)}
    _encolar(modelo)
    return {"status": "success", "message": "Orden recibida", "id": modelo.id}


@app.get("/roblox/ping", dependencies=[Depends(requerir_clave)])
def roblox_ping():
    """Roblox avisa aquí cada pocos segundos para confirmar que está vivo."""
    global _pings, _ultimo_ping
    _pings += 1
    _ultimo_ping = time.time()
    print(f"📡 [SERVIDOR] Ping de Roblox recibido (total: {_pings}).")
    return {"ok": True, "pings": _pings}


@app.get("/roblox/poll", dependencies=[Depends(requerir_clave)])
def send_to_roblox():
    """Roblox consulta aquí; devuelve la siguiente instrucción pendiente."""
    with _cerrojo:
        if _cola:
            modelo = _cola.pop(0)
            return {"hasData": True, "data": modelo.a_payload()}
    return {"hasData": False}


@app.get("/historial", dependencies=[Depends(requerir_clave)])
def historial():
    return {"historial": _historial}


@app.get("/estado", dependencies=[Depends(requerir_clave)])
def estado():
    """Resumen del estado del sistema (para el panel de diagnóstico)."""
    hace = round(time.time() - _ultimo_ping, 1) if _ultimo_ping else None
    return {
        "cola": len(_cola),
        "pings": _pings,
        "ultimo_ping": _ultimo_ping,
        "roblox_conectado": hace is not None and hace < 60,
        "hace_segundos": hace,
    }


@app.get("/api/estructuras", dependencies=[Depends(requerir_clave)])
def api_estructuras():
    return {
        "estructuras": [
            {"clave": k, "nombre": v["nombre"], "referencia": v["referencia"]}
            for k, v in ESTRUCTURAS.items()
        ]
    }


@app.get("/", response_class=HTMLResponse)
def panel():
    return FileResponse("static/index.html")


@app.get("/guia", response_class=HTMLResponse)
def guia():
    """Guía visual interactiva del deploy (sin protección: no expone nada)."""
    return FileResponse("static/guia.html")


app.mount("/static", StaticFiles(directory="static"), name="static")


if __name__ == "__main__":
    import uvicorn
    # En Render la plataforma inyecta RENDER=1 y PORT; en local usamos 8080
    # (o SERVIDOR_PUERTO si quieres otro puerto).
    if os.environ.get("RENDER") == "1":
        puerto = int(os.environ.get("PORT", "10000"))
    else:
        puerto = int(os.environ.get("SERVIDOR_PUERTO", "8080"))
    host = os.environ.get("HOST", "0.0.0.0")   # 0.0.0.0 para la nube
    print(f"🌍 Servidor en http://{host}:{puerto} "
          f"(CLAVE_API: {'sí' if CLAVE_API else 'no'})")
    uvicorn.run(app, host=host, port=puerto, access_log=False)
