"""
Voxelizador: convierte una IMAGEN en una ESTRUCTURA 3D de bloques para Roblox.

Principio (importante): NUNCA construimos la imagen literal (un panel plano).
Quitamos el fondo de la foto y EXTRUIMOS la silueta con volumen real, de modo
que el resultado es un objeto 3D por el que se puede caminar alrededor.

MODOS:
  - 'volumen' : extruye la silueta del objeto con profundidad real
                (~30 % del ancho). Ideal para fotos y planos de objetos.
  - 'relieve' : el brillo del píxel decide la altura (efecto relieve 3D).
  - 'fachada' : panel plano de poco grosor. SOLO para cosas realmente planas
                (logos, mapas, retratos). El QA avisa si se abusa de él.

Funciona para CUALQUIER imagen. Para estructuras con partes reales (muros,
techos, ventanas), el modo 'IA' del servidor propone un blueprint semántico.
"""
from __future__ import annotations

import io
from typing import List, Tuple

from PIL import Image, ImageOps

from .blueprint import Parte

MAX_PIEZAS = 1800      # tope de bloques por modelo
BLOQUE = 2.0           # studs por píxel (escala base)
MODOS = ("volumen", "relieve", "fachada")
UMBRAL_FONDO = 45.0    # distancia de color para considerar píxel como fondo


def _cargar(datos: bytes) -> Image.Image:
    img = Image.open(io.BytesIO(datos))
    img = ImageOps.exif_transpose(img)   # respeta la orientación de la foto
    return img.convert("RGB")


def _cuantificar(color: Tuple[int, int, int]) -> List[int]:
    """Agrupa colores parecidos (pasos de 24) para reducir piezas y dar un
    aspecto de 'construcción con bloques' más legible."""
    return [min(255, max(0, round(c / 24) * 24)) for c in color]


def _dist(c1, c2) -> float:
    return ((c1[0] - c2[0]) ** 2 + (c1[1] - c2[1]) ** 2 + (c1[2] - c2[2]) ** 2) ** 0.5


def _color_fondo(px, w: int, h: int) -> Tuple[int, int, int]:
    """El fondo suele dominar las esquinas de la foto: lo estimamos con la
    media de los 4 píxeles de esquina."""
    esquinas = [px[0, 0], px[w - 1, 0], px[0, h - 1], px[w - 1, h - 1]]
    return tuple(round(sum(c[i] for c in esquinas) / len(esquinas))
                 for i in range(3))


def voxelizar(datos: bytes, modo: str = "volumen",
              lado: int = 48, grosor: float = 1.0) -> List[Parte]:
    """Convierte los bytes de una imagen en una lista de Parte (bloques 3D).

    - lado   : resolución objetivo (píxeles en el lado más largo).
    - grosor : profundidad extra en modo 'fachada' (studs por bloque).
    """
    if modo not in MODOS:
        modo = "volumen"
    img = _cargar(datos)

    lado = max(8, min(96, int(lado)))
    escala = min(1.0, lado / max(img.size))
    if escala < 1.0:
        img = img.resize((max(1, round(img.width * escala)),
                          max(1, round(img.height * escala))), Image.LANCZOS)
    w, h = img.size
    px = img.load()

    # 1) Separa el objeto del fondo (quita los píxeles parecidos al fondo).
    fondo = _color_fondo(px, w, h)
    celdas = []
    for y in range(h):
        for x in range(w):
            c = px[x, y][:3]
            if _dist(c, fondo) >= UMBRAL_FONDO:
                celdas.append((x, y, (c[0] + c[1] + c[2]) / 3.0, c))
    if not celdas:  # sin objeto claro: usamos toda la imagen
        for y in range(h):
            for x in range(w):
                c = px[x, y][:3]
                celdas.append((x, y, (c[0] + c[1] + c[2]) / 3.0, c))

    # 2) Si hay demasiados píxeles, muestreamos en cuadrícula.
    paso = 1
    if len(celdas) > MAX_PIEZAS:
        paso = max(1, round((len(celdas) / MAX_PIEZAS) ** 0.5))

    # 3) Ancho real del objeto (para darle volumen proporcional).
    xs = [c[0] for c in celdas]
    ancho_obj = (max(xs) - min(xs) + 1) * BLOQUE
    alto_max = max(c[2] for c in celdas) or 1.0

    piezas: List[Parte] = []
    for (x, fila, brillo, color) in celdas:
        if x % paso or fila % paso:
            continue
        cx = (x - (w - 1) / 2) * BLOQUE
        base_y = (h - 1 - fila) * BLOQUE   # la fila de abajo se apoya en y=0

        if modo == "relieve":
            alto = BLOQUE + (brillo / alto_max) * 14.0
            tam, pos = [BLOQUE, alto, BLOQUE], [cx, base_y + alto / 2, 0.0]
        elif modo == "fachada":
            tam = [BLOQUE, BLOQUE, BLOQUE * max(0.5, grosor)]
            pos = [cx, base_y + BLOQUE / 2, 0.0]
        else:  # volumen: silueta extruida con profundidad real
            prof = max(3.0, ancho_obj * 0.30)
            tam = [BLOQUE, BLOQUE, prof]
            pos = [cx, base_y + BLOQUE / 2, 0.0]

        piezas.append(Parte(
            shape="Block",
            size=tam,
            position=pos,
            rotation=[0, 0, 0],
            color=_cuantificar(color),
            material="SmoothPlastic",
            name=f"Pix_{x}_{fila}",
        ))
    return piezas
