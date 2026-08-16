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

import copy
import json
import os
import re
from typing import List, Optional
import threading
import time
import unicodedata

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from generador.blueprint import Modelo, Parte, desde_json
from generador.razonador import interpretar, NoEncontrada, normalizar
from generador.biblioteca import ESTRUCTURAS
from generador import catalogo, libreria, modelos, planos, voxel, vision
from generador.validar import informe, autocorregir

app = FastAPI(title="Constructor Roblox", version="2.1")

# ---------------------------------------------------------------------------
# Seguridad para la nube: si CLAVE_API está definida (variable de entorno),
# todos los endpoints exigen la cabecera X-API-Key. En local sin clave,
# todo queda abierto como siempre.
# ---------------------------------------------------------------------------
CLAVE_API = os.environ.get("CLAVE_API", "").strip()

# Configuración opcional para importar MODELOS 3D REALES a Roblox
# (Open Cloud Assets API). Sin esto, el endpoint /modelo/subir responde
# con instrucciones en vez de subir.
ROBLOX_API_KEY = os.environ.get("ROBLOX_API_KEY", "").strip()
ROBLOX_USER_ID = os.environ.get("ROBLOX_USER_ID", "").strip()


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

# La cola guarda DICTs (payloads listos para Roblox): los modelos normales
# (con 'parts') y las órdenes especiales como insertModel (con 'accion').

# Último modelo construido (para ajustes iterativos: "más alta", "otro color"...)
_ultimo_modelo: Optional[Modelo] = None

# Diagnóstico de conexión con Roblox
_pings = 0
_ultimo_ping: Optional[float] = None


def _encolar(modelo: Modelo):
    global _ultimo_modelo
    with _cerrojo:
        _ultimo_modelo = modelo
        _cola.append(modelo.a_payload())
        _historial.append({
            "id": modelo.id,
            "modelName": modelo.modelName,
            "partes": len(modelo.parts),
            "razonamiento": modelo.razonamiento,
        })
    print(f"📦 [SERVIDOR] Encolado: '{modelo.modelName}' "
          f"({len(modelo.parts)} piezas).")


def _encolar_orden(payload: dict):
    """Encola una orden especial para el plugin (ej. insertModel)."""
    with _cerrojo:
        _cola.append(payload)
    print(f"📦 [SERVIDOR] Encolada orden: {payload.get('accion')} "
          f"({payload.get('modelName', '')}).")


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


# ---------------------------------------------------------------------------
# Modo de entrenamiento por imagen
# ---------------------------------------------------------------------------
MAX_IMAGEN = 8 * 1024 * 1024   # 8 MB


def _encolar_con_qa(modelo: Modelo):
    """QA + encolar + respuesta estándar (reutilizada por los endpoints)."""
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
        "mensaje": f"¡Listo! Construí '{modelo.modelName}' "
                    f"con {len(modelo.parts)} piezas.",
        "modelo": modelo.a_payload(),
        "razonamiento": modelo.razonamiento,
        "qa": qa,
        "cambios": cambios,
    }


@app.post("/imagen", dependencies=[Depends(requerir_clave)])
async def desde_imagen(archivo: UploadFile = File(...),
                        modo: str = Form("volumen"),
                        lado: int = Form(48)):
    """Convierte una imagen en una ESTRUCTURA 3D (volumen / relieve / fachada)."""
    datos = await archivo.read()
    if not datos:
        return {"status": "error", "mensaje": "El archivo está vacío."}
    if len(datos) > MAX_IMAGEN:
        return {"status": "error", "mensaje": "La imagen pesa más de 8 MB."}
    try:
        partes = voxel.voxelizar(datos, modo=modo, lado=lado)
    except Exception as e:
        return {"status": "error", "mensaje": f"No pude leer la imagen: {e}"}
    base = (archivo.filename or "imagen").rsplit(".", 1)[0][:40]
    etiqueta = {"volumen": "volumen", "bloques": "volumen",
                 "relieve": "relieve", "fachada": "fachada"}.get(modo, modo)
    modelo = Modelo(
        modelName=f"{base} (voxel {etiqueta})",
        parts=partes,
        razonamiento=[
            f"Convertí tu imagen '{archivo.filename or 'imagen'}' en una "
            f"estructura 3D de {len(partes)} bloques (modo '{etiqueta}', "
            f"{lado} px).",
            "Quité el fondo de la foto y le di VOLUMEN real: ya no es un "
            "panel plano, es un objeto por el que se puede caminar alrededor.",
            "Si quieres piezas reales (muros, techo, ventanas), usa el modo IA.",
        ],
    )
    return _encolar_con_qa(modelo)


@app.post("/analizar-imagen", dependencies=[Depends(requerir_clave)])
async def analizar_imagen(archivo: UploadFile = File(...)):
    """IA de visión: propone un blueprint semántico a partir de la imagen."""
    datos = await archivo.read()
    if not datos:
        return {"status": "error", "mensaje": "El archivo está vacío."}
    if len(datos) > MAX_IMAGEN:
        return {"status": "error", "mensaje": "La imagen pesa más de 8 MB."}
    try:
        modelo = vision.analizar(datos, nombre=archivo.filename or "imagen")
    except vision.SinClave as e:
        return {"status": "error", "mensaje": str(e)}
    except Exception as e:
        return {"status": "error", "mensaje": f"La IA no pudo analizarla: {e}"}
    return _encolar_con_qa(modelo)


# ---------------------------------------------------------------------------
# Ciclo de aprendizaje: ajustar el último modelo y guardarlo en la librería
# ---------------------------------------------------------------------------
_COLORES = {
    "rojo": [210, 70, 70], "azul": [70, 100, 220], "verde": [80, 180, 90],
    "amarillo": [230, 200, 60], "rosa": [230, 120, 170],
    "morado": [150, 90, 200], "violeta": [150, 90, 200],
    "naranja": [230, 140, 50], "marron": [140, 90, 50], "marrón": [140, 90, 50],
    "negro": [40, 40, 40], "blanco": [230, 230, 230], "gris": [140, 140, 140],
    "cyan": [80, 200, 220], "celeste": [130, 190, 230],
}


class PeticionAjuste(BaseModel):
    texto: str


class PeticionGuardar(BaseModel):
    modelName: str
    sinonimos: List[str] = Field(default_factory=list)
    referencia: str = ""
    parts: List[dict] = Field(default_factory=list)


def _slug(texto: str) -> str:
    t = unicodedata.normalize("NFD", texto.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    t = re.sub(r"[^a-z0-9]+", "_", t).strip("_")
    return t or "estructura"


@app.get("/ultimo", dependencies=[Depends(requerir_clave)])
def ultimo():
    """El último modelo construido (para ajustarlo o guardarlo)."""
    if _ultimo_modelo is None:
        return {"status": "error", "mensaje": "Todavía no has construido nada."}
    return {"status": "success", "modelo": _ultimo_modelo.a_payload(),
            "razonamiento": _ultimo_modelo.razonamiento}


@app.post("/ajustar", dependencies=[Depends(requerir_clave)])
def ajustar(peticion: PeticionAjuste):
    """Aplica frases de ajuste ('más alta', 'el doble', 'otro color'...) al
    último modelo construido y lo re-encola."""
    global _ultimo_modelo
    if _ultimo_modelo is None:
        return {"status": "error",
                "mensaje": "Primero construye algo (texto, librería o imagen)."}
    t = normalizar(peticion.texto)
    if not t:
        return {"status": "error", "mensaje": "Escribe un ajuste, por favor."}

    partes = [copy.deepcopy(p) for p in _ultimo_modelo.parts]
    cambios: List[str] = []
    sx = sy = sz = 1.0

    # Escala general
    if "doble" in t or "dos veces" in t or "el doble" in t:
        sx = sy = sz = 2.0
        cambios.append("la hice el DOBLE de grande")
    elif "triple" in t or "tres veces" in t:
        sx = sy = sz = 3.0
        cambios.append("la hice el TRIPLE de grande")
    elif "mitad" in t or "mas pequena" in t or "mas chica" in t:
        sx = sy = sz = 0.5
        cambios.append("la reduje a la mitad")

    # Por ejes
    if "alta" in t or "alto" in t:
        sy = 1.3 if sy == 1.0 else sy
        cambios.append("la hice MÁS ALTA (x1.3 en altura)")
    if "baja" in t or "bajo" in t:
        sy = 0.7 if sy == 1.0 else sy
        cambios.append("la hice MÁS BAJA (x0.7 en altura)")
    if "ancha" in t or "ancho" in t:
        sx = 1.3 if sx == 1.0 else sx
        cambios.append("la hice MÁS ANCHA")
    if "estrecha" in t:
        sx = 0.7 if sx == 1.0 else sx
        cambios.append("la hice MÁS ESTRECHA")
    if "profunda" in t:
        sz = 1.3 if sz == 1.0 else sz
        cambios.append("la hice MÁS PROFUNDA")

    if (sx, sy, sz) != (1.0, 1.0, 1.0):
        partes = catalogo.reescalar_ejes(partes, sx, sy, sz)

    # Colores
    if "otro color" in t or "cambia de color" in t or "cambiale el color" in t:
        for p in partes:
            p.color = libreria.desplazar_tono(p.color, 0.15)
        cambios.append("le cambié el tono de color")
    for nombre, rgb in _COLORES.items():
        if nombre in t:
            for p in partes:
                p.color = list(rgb)
            cambios.append(f"la pinté de {nombre}")
            break

    if not cambios:
        return {"status": "error",
                "mensaje": "No entendí el ajuste. Prueba con: 'más alta', 'más baja', "
                            "'el doble', 'más ancha', 'otro color', 'roja'..."}

    modelo = Modelo(
        modelName=f"{_ultimo_modelo.modelName} (ajustado)",
        parts=partes,
        razonamiento=_ultimo_modelo.razonamiento
        + [f"Ajuste aplicado: {', '.join(cambios)}."],
    )
    return _encolar_con_qa(modelo)


@app.post("/guardar", dependencies=[Depends(requerir_clave)])
def guardar_en_biblioteca(peticion: PeticionGuardar):
    """Guarda un modelo aprendido como entrada nueva de la biblioteca
    (estructuras/<clave>.json). Después se puede pedir con 'replica <clave>'."""
    nombre = (peticion.modelName or "").strip()
    if not nombre:
        return {"status": "error", "mensaje": "El modelo necesita un nombre."}
    modelo = desde_json({
        "modelName": nombre,
        "parts": [p for p in peticion.parts],
        "razonamiento": ["Guardado por el usuario tras aprenderlo."],
    })
    modelo, cambios = autocorregir(modelo)
    qa = informe(modelo)
    if not qa["resumen"]["es_valido"]:
        return {"status": "error",
                "mensaje": "El QA detectó problemas: " + "; ".join(qa["errores"][:4]),
                "qa": qa}
    if not modelo.parts:
        return {"status": "error", "mensaje": "El modelo no tiene piezas."}

    clave = _slug(nombre)
    bx, by, bz = catalogo.bounding_box(modelo.parts)
    archivo = {
        "id": clave,
        "nombre": nombre,
        "sinonimos": peticion.sinonimos or [nombre.lower()],
        "referencia": (peticion.referencia or
                        "Aprendido por el programa (imagen o ajustes)."),
        "parametros": {},
        "dimensiones_studs": {"x": round(bx, 2), "y": round(by, 2),
                               "z": round(bz, 2)},
        "dimensiones_metros": {"x": round(catalogo.studs_a_metros(bx), 2),
                                "y": round(catalogo.studs_a_metros(by), 2),
                                "z": round(catalogo.studs_a_metros(bz), 2)},
        "piezas": len(modelo.parts),
        "qa": {"errores": len(qa["errores"]), "avisos": len(qa["avisos"])},
        "partes": [p.a_json() for p in modelo.parts],
    }
    ruta = os.path.join("estructuras", clave + ".json")
    try:
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(archivo, f, ensure_ascii=False, indent=2)
    except OSError as e:
        return {"status": "error",
                "mensaje": f"No pude escribir el archivo en el servidor: {e}"}
    print(f"💾 [SERVIDOR] Guardada en la biblioteca: {clave}.json")
    return {
        "status": "success",
        "mensaje": f"¡Guardada! '{nombre}' quedó en la librería como '{clave}'. "
                    f"Ya puedes pedir 'replica {clave}' o construirla desde el panel.",
        "clave": clave,
        "dimensiones_metros": archivo["dimensiones_metros"],
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
            datos = _cola.pop(0)
            return {"hasData": True, "data": datos}
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
    """Lo que sabe construir el programa (biblioteca en archivos)."""
    return {"estructuras": libreria.listar()}


@app.get("/api/planos", dependencies=[Depends(requerir_clave)])
def api_planos():
    """Los PLANOS arquitectónicos disponibles (medidas reales en metros)."""
    lista = []
    for clave in planos.disponibles():
        p = planos.cargar(clave)
        lista.append({
            "clave": clave,
            "nombre": p.get("nombre", clave),
            "ancho_m": p.get("ancho_m"),
            "fondo_m": p.get("fondo_m"),
            "grosor_muro_m": p.get("grosor_muro_m"),
            "plantas": len(p.get("plantas", [])),
            "techo": p.get("techo", {}).get("tipo", ""),
            "pendiente": p.get("techo", {}).get("pendiente_grados"),
            "globos": p.get("globos", 0),
            "detalle": ("Recreada desde su PLANO arquitectónico con medidas "
                         "reales de arquitectura, convertidas a Roblox "
                         "milimétricamente (1 stud ≈ 0,28 m)."),
        })
    return {"planos": lista}


class PeticionPlano(BaseModel):
    escala: float = 1.0
    solar: Optional[str] = None      # "largo x ancho" en metros, opcional


@app.post("/planos/{clave}/construir", dependencies=[Depends(requerir_clave)])
def construir_desde_plano(clave: str, peticion: PeticionPlano):
    """Construye una estructura DESDE SU PLANO arquitectónico (medidas
    reales en metros) y la encola para Roblox tras pasar el QA."""
    clave = clave.strip().lower()
    if clave not in planos.disponibles():
        return {"status": "error",
                "mensaje": f"'{clave}' no tiene plano. Disponibles: "
                            f"{', '.join(planos.disponibles())}."}
    plano = planos.cargar(clave)
    partes = planos.construir(plano, escala=peticion.escala)
    planta0 = plano.get("plantas", [{}])[0]
    razonamiento = [
        f"Recreado desde su PLANO arquitectónico: planta "
        f"{plano.get('ancho_m')} × {plano.get('fondo_m')} m, pisos de "
        f"{planta0.get('altura_m', '?')} m, techo a "
        f"{plano.get('techo', {}).get('pendiente_grados', '?')}°.",
        "Medidas reales de arquitectura convertidas a Roblox "
        "milimétricamente (1 stud ≈ 0,28 m).",
        f"Diseño: {len(partes)} piezas construidas desde el plano.",
    ]
    if peticion.solar:
        m = re.match(r"\s*(\d+(?:[.,]\d+)?)\s*[xX×]\s*(\d+(?:[.,]\d+)?)\s*",
                     peticion.solar)
        if m:
            largo = float(m.group(1).replace(",", "."))
            ancho = float(m.group(2).replace(",", "."))
            if largo > 0 and ancho > 0:
                bx, _, bz = catalogo.bounding_box(partes)
                factor = catalogo.escala_para_solar(bx, bz, largo, ancho)
                partes = catalogo.reescalar(partes, factor)
                razonamiento.append(
                    f"Solar: ajustado a {largo:.2f} × {ancho:.2f} m "
                    f"(factor {factor:.3f}x)."
                )
    nombre_modelo = (f"{plano.get('nombre', clave)} "
                     f"(plano real, esc. {peticion.escala:.2f})")
    modelo = Modelo(modelName=nombre_modelo, parts=partes,
                    razonamiento=razonamiento)
    return _encolar_con_qa(modelo)


class PeticionLibreria(BaseModel):
    modo: str = "replica"            # "replica" | "variante"
    escala: float = 1.0
    hue: Optional[float] = None      # desplazamiento de tono (-0.5 .. 0.5)
    solar: Optional[str] = None      # "largo x ancho" en metros, opcional


@app.post("/estructuras/{clave}/construir", dependencies=[Depends(requerir_clave)])
def construir_desde_libreria(clave: str, peticion: PeticionLibreria):
    """Replica o varía una estructura guardada en la biblioteca, la pasa por
    el QA y la encola para que Roblox la construya."""
    clave = clave.strip().lower()
    if not libreria.existe(clave):
        disponibles = ", ".join(e["clave"] for e in libreria.listar())
        return {"status": "error",
                "mensaje": f"'{clave}' no está en la biblioteca. "
                            f"Disponibles: {disponibles}."}
    try:
        if peticion.modo == "variante":
            modelo = libreria.variar(clave, escala=peticion.escala,
                                     hue=peticion.hue)
        else:
            modelo = libreria.replicar(clave, escala=peticion.escala)
    except KeyError as e:
        return {"status": "error", "mensaje": str(e)}

    # Solar opcional: "30 x 20" metros -> reescala para que encaje
    if peticion.solar:
        m = re.match(r"\s*(\d+(?:[.,]\d+)?)\s*[xX×]\s*(\d+(?:[.,]\d+)?)\s*",
                     peticion.solar)
        if m:
            largo = float(m.group(1).replace(",", "."))
            ancho = float(m.group(2).replace(",", "."))
            if largo > 0 and ancho > 0:
                bx, _, bz = catalogo.bounding_box(modelo.parts)
                factor = catalogo.escala_para_solar(bx, bz, largo, ancho)
                modelo.parts = catalogo.reescalar(modelo.parts, factor)
                modelo.razonamiento.append(
                    f"Solar: ajustado a {largo:.2f} × {ancho:.2f} m "
                    f"(factor {factor:.3f}x)."
                )

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
        "mensaje": f"¡Listo! Construí '{modelo.modelName}' "
                    f"con {len(modelo.parts)} piezas.",
        "modelo": modelo.a_payload(),
        "razonamiento": modelo.razonamiento,
        "qa": qa,
        "cambios": cambios,
    }


# ---------------------------------------------------------------------------
# Modelos 3D REALES (importación fiel con Open Cloud Assets API)
# ---------------------------------------------------------------------------
@app.get("/api/modelos", dependencies=[Depends(requerir_clave)])
def api_modelos():
    """Modelos 3D reales disponibles y sus fuentes (para el panel)."""
    lista = []
    for clave in modelos.disponibles():
        ficha = modelos.buscar(clave)
        ficha = dict(ficha or {})
        ficha["clave"] = clave
        ficha["configurado"] = bool(ROBLOX_API_KEY and ROBLOX_USER_ID)
        lista.append(ficha)
    return {
        "modelos": lista,
        "configurado": bool(ROBLOX_API_KEY and ROBLOX_USER_ID),
        "instrucciones": (
            "Para importar el modelo real: (1) descárgalo de su fuente "
            "(p.ej. Sketchfab, gratis), (2) súbelo aquí con 'Importar a "
            "Roblox'. El servidor lo sube con la API oficial Open Cloud "
            "Assets y el plugin lo inserta en Studio."
            if not (ROBLOX_API_KEY and ROBLOX_USER_ID) else
            "La importación está configurada: sube el archivo y el plugin "
            "lo insertará en Studio en unos segundos."
        ),
    }


@app.post("/modelo/subir", dependencies=[Depends(requerir_clave)])
async def subir_modelo_real(archivo: UploadFile = File(...),
                            nombre: str = Form("")):
    """Sube un modelo 3D real (.glb/.obj/.fbx/.stl) a Roblox vía Open Cloud
    Assets API y encola al plugin para que lo inserte en Studio."""
    if not (ROBLOX_API_KEY and ROBLOX_USER_ID):
        return {
            "status": "error",
            "mensaje": "Falta configurar la importación de modelos reales. "
                        "En Render → tu servicio → Environment, añade:\n"
                        "  ROBLOX_API_KEY = tu clave Open Cloud de Roblox\n"
                        "  ROBLOX_USER_ID = tu ID de Roblox\n"
                        "Clave: https://create.roblox.com/credentials "
                        "(permiso 'Assets API: Create'). Tu ID: en tu perfil, "
                        "https://www.roblox.com/users/<ID>/profile. "
                        "Guarda y espera el redeploy.",
        }

    datos = await archivo.read()
    if not datos:
        return {"status": "error", "mensaje": "El archivo está vacío."}
    if len(datos) > modelos.MAX_BYTES:
        return {"status": "error",
                "mensaje": "El archivo supera los 20 MB que admite Roblox."}

    nombre_base = (nombre or (archivo.filename or "modelo_real"))
    nombre_limpio = re.sub(r"\.[^.]+$", "", nombre_base)[:60]

    # Guardar el archivo en modelos/ (carpeta de trabajo del servidor)
    os.makedirs("modelos", exist_ok=True)
    ext = os.path.splitext(archivo.filename or "")[1].lower()
    ruta = os.path.join("modelos", f"subida{ext or '.glb'}")
    with open(ruta, "wb") as f:
        f.write(datos)

    # STL no lo acepta la API: convertir a OBJ (sin color, forma exacta)
    if ext == ".stl":
        try:
            ruta = modelos.stl_a_obj(ruta, os.path.join("modelos", "subida.obj"))
        except Exception as e:
            return {"status": "error",
                    "mensaje": f"No pude convertir el STL: {e}"}

    try:
        asset_id = modelos.subir_modelo(
            ruta, nombre_limpio, ROBLOX_API_KEY, ROBLOX_USER_ID,
            descripcion="Importado por Constructor Roblox (Open Cloud Assets)",
        )
    except (modelos.SinConfiguracion, ValueError, RuntimeError,
            TimeoutError, OSError) as e:
        return {"status": "error", "mensaje": f"No pude subirlo a Roblox: {e}"}

    _encolar_orden({
        "accion": "insertModel",
        "assetId": asset_id,
        "modelName": f"{nombre_limpio} (modelo real)",
        "razonamiento": [
            f"Modelo 3D REAL '{nombre_limpio}' subido a Roblox "
            f"(assetId {asset_id}) con la API oficial Open Cloud Assets.",
            "El plugin lo insertará en Studio como modelo importado "
            "(MeshParts), con la forma y colores del artista original.",
        ],
    })
    return {
        "status": "success",
        "mensaje": (f"¡Modelo real '{nombre_limpio}' subido a Roblox "
                     f"(assetId {asset_id})! El plugin lo está insertando "
                     "en Studio."),
        "assetId": asset_id,
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
