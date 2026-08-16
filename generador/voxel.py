"""
Voxelizador: convierte una IMAGEN en una estructura de bloques para Roblox.

Es el "modo de entrenamiento por imagen" más directo: cada píxel de la foto se
convierte en un bloque de color. Sirve para reproducir fachadas, logotipos,
planos, sprites, mapas... cualquier imagen que quieras ver en 3D. Funciona
para CUALQUIER cosa, no solo para una estructura concreta.

MODOS:
  - 'bloques': cada píxel -> un bloque de color (fachada plana con grosor).
  - 'relieve': el brillo del píxel decide la altura (foto -> relieve 3D).

LÍMITES: la resolución se limita y los colores se agrupan para no pasarse del
máximo de piezas recomendado por Roblox.
"""
from __future__ import annotations

import io
from typing import List, Tuple

from PIL import Image, ImageOps

from .blueprint import Parte

MAX_PIEZAS = 1800      # tope de bloques por modelo
BLOQUE = 2.0           # studs por píxel (escala base)
MODOS = ("bloques", "relieve")


def _cargar(datos: bytes) -> Image.Image:
    img = Image.open(io.BytesIO(datos))
    img = ImageOps.exif_transpose(img)   # respeta la orientación de la foto
    return img.convert("RGB")


def _cuantificar(color: Tuple[int, int, int]) -> List[int]:
    """Agrupa colores parecidos (pasos de 24) para reducir piezas y dar un
    aspecto de 'construcción con bloques' más legible."""
    return [min(255, max(0, round(c / 24) * 24)) for c in color]


def voxelizar(datos: bytes, modo: str = "bloques",
              lado: int = 48, grosor: float = 1.0) -> List[Parte]:
    """Convierte los bytes de una imagen en una lista de Parte (bloques).

    - lado   : resolución objetivo (píxeles en el lado más largo).
    - grosor : profundidad del bloque en studs (modo 'bloques').
    """
    if modo not in MODOS:
        modo = "bloques"
    img = _cargar(datos)

    lado = max(8, min(96, int(lado)))
    escala = min(1.0, lado / max(img.size))
    if escala < 1.0:
        img = img.resize((max(1, round(img.width * escala)),
                          max(1, round(img.height * escala))), Image.LANCZOS)
    w, h = img.size
    px = img.load()

    # Leemos todos los píxeles (x, y, brillo, color)
    celdas = []
    for y in range(h):
        for x in range(w):
            r, g, b = px[x, y][:3]
            celdas.append((x, y, (r + g + b) / 3.0, (r, g, b)))

    # Si hay demasiados píxeles, muestreamos en cuadrícula para no exceder
    # el máximo de piezas de Roblox.
    paso = 1
    if len(celdas) > MAX_PIEZAS:
        paso = max(1, round((len(celdas) / MAX_PIEZAS) ** 0.5))

    alto_max = max(c[2] for c in celdas) or 1.0
    piezas: List[Parte] = []
    for (x, fila, brillo, color) in celdas:
        if x % paso or fila % paso:
            continue
        cx = (x - (w - 1) / 2) * BLOQUE
        # La fila de abajo de la imagen se apoya en el suelo (y=0) y la de
        # arriba queda arriba: así la foto se "levanta" como una fachada.
        base_y = (h - 1 - fila) * BLOQUE
        if modo == "relieve":
            alto = BLOQUE + (brillo / alto_max) * 14.0
            piezas.append(Parte(
                shape="Block",
                size=[BLOQUE, alto, BLOQUE],
                position=[cx, base_y + alto / 2, 0.0],
                rotation=[0, 0, 0],
                color=_cuantificar(color),
                material="SmoothPlastic",
                name=f"Pix_{x}_{fila}",
            ))
        else:
            piezas.append(Parte(
                shape="Block",
                size=[BLOQUE, BLOQUE, BLOQUE * max(0.5, grosor)],
                position=[cx, base_y + BLOQUE / 2, 0.0],
                rotation=[0, 0, 0],
                color=_cuantificar(color),
                material="SmoothPlastic",
                name=f"Pix_{x}_{fila}",
            ))
    return piezas
