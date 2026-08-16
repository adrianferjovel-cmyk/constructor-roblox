"""
Análisis de imágenes con IA de visión (Google Gemini, plan gratuito).

El servidor envía la imagen a Gemini con una consigna de "arquitecto 3D" y
Gemini devuelve un JSON con la estructura descrita como piezas de Roblox
(muros, techos, puertas, ventanas... con medidas, colores y materiales).
El resultado pasa por el QA y se construye como cualquier otro modelo.

Este es el modo de aprendizaje "inteligente": sirve para cualquier imagen
(foto, plano, boceto) y es el camino para lograr reproducciones exactas.

ACTIVACIÓN (una vez):
  1. Crea una clave gratuita en https://aistudio.google.com/apikey
  2. En Render: Environment -> añadir GEMINI_API_KEY = tu clave
  3. El panel ya tendrá la opción 'IA (analiza y propone)'.
"""
from __future__ import annotations

import base64
import json
import os
from typing import List

import requests

from .blueprint import MATERIALES_ROBLOX, Modelo, Parte

MODELO_IA = os.environ.get("GEMINI_MODELO", "gemini-2.0-flash")
URL = ("https://generativelanguage.googleapis.com/v1beta/models/"
       + MODELO_IA + ":generateContent")

CONSIGNA = """Eres un arquitecto 3D para el juego Roblox. Analiza la imagen y descríbela como piezas 3D construibles.

Devuélveme SOLO JSON válido (sin texto alrededor), con esta forma:
{"modelName": "Nombre", "parts": [{"name": "Pared_frente", "shape": "Block", "size": [x,y,z], "position": [x,y,z], "rotation": [x,y,z], "color": [r,g,b], "material": "Wood"}, ...]}

Reglas:
- shape SOLO uno de: Block, Wedge, CornerWedge, Cylinder, Ball.
- material SOLO uno de: Plastic, SmoothPlastic, Wood, WoodPlanks, Metal, MetalSheet, Brick, Concrete, Glass, Neon, Stone, Slate, Rock, Sand, Grass, Fabric, Ceramic, Marble, Granite.
- size y position en studs (1 stud ~ 0.28 m). Apoya la base en y=0 (el suelo). Centra el modelo cerca de x=0, z=0.
- Máximo 250 piezas: agrupa lo que puedas (una pared entera = una caja; no la dividas).
- Sé FIEL a la imagen: proporciones generales, colores principales y las partes que se ven (muros, techo, puertas, ventanas, torres, chimeneas, columnas...).
- No inventes detalles que no se vean en la imagen."""


class SinClave(Exception):
    pass


def analizar(datos: bytes, nombre: str = "Imagen") -> Modelo:
    """Envía la imagen a Gemini y devuelve un Modelo con las piezas propuestas."""
    clave = os.environ.get("GEMINI_API_KEY", "").strip()
    if not clave:
        raise SinClave(
            "Falta GEMINI_API_KEY. Crea una clave gratuita en "
            "https://aistudio.google.com/apikey y pégala en Render → Environment."
        )

    b64 = base64.b64encode(datos).decode()
    payload = {
        "contents": [{
            "parts": [
                {"text": CONSIGNA},
                {"inline_data": {"mime_type": "image/png", "data": b64}},
            ],
        }],
        "generationConfig": {
            "response_mime_type": "application/json",
            "temperature": 0.2,
        },
    }
    resp = requests.post(URL + "?key=" + clave, json=payload, timeout=120)
    if resp.status_code != 200:
        raise RuntimeError(f"Gemini respondió {resp.status_code}: {resp.text[:200]}")
    texto = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
    datos_json = json.loads(texto)

    partes: List[Parte] = []
    for p in datos_json.get("parts", []):
        forma = p.get("shape", "Block")
        if forma not in ("Block", "Wedge", "CornerWedge", "Cylinder", "Ball"):
            forma = "Block"
        material = p.get("material", "Plastic")
        if material not in MATERIALES_ROBLOX:
            material = "Plastic"
        tam = p.get("size") or [4, 4, 4]
        pos = p.get("position") or [0, 2, 0]
        rot = p.get("rotation") or [0, 0, 0]
        col = p.get("color") or [200, 200, 200]
        partes.append(Parte(
            name=p.get("name", ""),
            shape=forma,
            size=[float(tam[0]), float(tam[1]), float(tam[2])],
            position=[float(pos[0]), float(pos[1]), float(pos[2])],
            rotation=[float(rot[0]), float(rot[1]), float(rot[2])],
            color=[max(0, min(255, int(col[0]))),
                   max(0, min(255, int(col[1]))),
                   max(0, min(255, int(col[2])))],
            material=material,
        ))

    base = (nombre or "Imagen").rsplit(".", 1)[0][:40]
    return Modelo(
        modelName=f"{base} (IA)",
        parts=partes,
        razonamiento=[
            f"La IA de visión analizó tu imagen y propuso {len(partes)} piezas "
            f"(paredes, techos, puertas, ventanas...).",
            "Pasa por el QA de construcción y luego puedes ajustarla con frases "
            "como 'más alta', 'otro color' o 'en un solar de X por Y metros'.",
        ],
    )
