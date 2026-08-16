"""
Librería de estructuras en archivos (carpeta 'estructuras/').

La biblioteca es la "memoria" del programa: cada estructura vive en un JSON
autocontenido con su ficha real, dimensiones y todas sus piezas. Con ella el
servidor puede:

  • REPLICAR  : reconstruir la estructura exacta (con escala / solar).
  • VARIAR    : crear algo nuevo "parecido" (tonos de color desplazados).

Ventaja: aunque se pierda el motor procedural, la biblioteca sigue funcionando,
y cualquier persona puede añadir estructuras nuevas simplemente copiando un
JSON (o regenerándolos con `python estructuras/exportar.py`).
"""
from __future__ import annotations

import json
import math
import os
import random
from typing import List, Optional, Tuple

from .blueprint import Modelo, Parte

CARPETA = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "estructuras"
)


# ===========================================================================
# Carga de la carpeta
# ===========================================================================

def _cargar_todo() -> dict:
    """Carga todos los JSON de 'estructuras/' en un dict clave -> datos."""
    datos: dict = {}
    if not os.path.isdir(CARPETA):
        return datos
    for nombre in sorted(os.listdir(CARPETA)):
        if nombre.endswith(".json"):
            clave = nombre[:-5]
            try:
                with open(os.path.join(CARPETA, nombre), encoding="utf-8") as f:
                    datos[clave] = json.load(f)
            except Exception:
                print(f"[libreria] Aviso: '{nombre}' no se pudo leer (¿JSON roto?).")
    return datos


def listar() -> List[dict]:
    """Metadatos de todas las estructuras de la biblioteca (para el panel)."""
    return [
        {
            "clave": k,
            "nombre": v.get("nombre", k),
            "referencia": v.get("referencia", ""),
            "dimensiones_metros": v.get("dimensiones_metros"),
            "piezas": v.get("piezas", len(v.get("partes", []))),
            "sinonimos": v.get("sinonimos", []),
        }
        for k, v in sorted(_cargar_todo().items())
    ]


def existe(clave: str) -> bool:
    return clave in _cargar_todo()


def buscar(texto: str) -> List[str]:
    """Busca en la biblioteca de archivos (incluidas las entradas aprendidas)
    por clave, sinónimos o nombre; la coincidencia más larga gana."""
    from .biblioteca import normalizar
    t = normalizar(texto)
    pares: List[tuple] = []
    for clave, datos in _cargar_todo().items():
        nc = normalizar(clave)
        if nc and nc in t:
            pares.append((len(nc), clave))
        for s in datos.get("sinonimos", []):
            sn = normalizar(s)
            if sn and sn in t:
                pares.append((len(sn), clave))
        nombre = normalizar(datos.get("nombre", ""))
        if nombre and nombre in t:
            pares.append((len(nombre), clave))
    mejor: dict = {}
    for largo, clave in pares:
        mejor[clave] = max(mejor.get(clave, 0), largo)
    return [c for c, _ in sorted(mejor.items(),
                                 key=lambda kv: (-kv[1], kv[0]))]


def _partes_desde(datos: dict) -> List[Parte]:
    """Convierte el JSON de piezas a objetos Parte (ignorando claves extra)."""
    partes = []
    for p in datos.get("partes", []):
        partes.append(Parte(**{k: v for k, v in p.items()
                               if k in Parte.__dataclass_fields__}))
    return partes


# ===========================================================================
# Replicar y variar
# ===========================================================================

def replicar(clave: str, escala: float = 1.0,
             razonamiento: Optional[List[str]] = None) -> Modelo:
    """RÉPLICA EXACTA desde la biblioteca (con escala aplicada)."""
    datos = _cargar_todo().get(clave)
    if datos is None:
        raise KeyError(f"'{clave}' no está en la biblioteca de estructuras/.")

    partes = _partes_desde(datos)
    if abs(escala - 1.0) > 1e-9:
        from . import catalogo
        partes = catalogo.reescalar(partes, escala)

    raz = razonamiento or [
        f"Repliqué '{datos.get('nombre', clave)}' desde la biblioteca de "
        f"estructuras ({len(partes)} piezas).",
        f"Ficha real: {datos.get('referencia', 'sin referencia')}",
        f"Dimensiones a E=1: {_dims(datos)}.",
    ]
    return Modelo(
        modelName=f"{datos.get('nombre', clave)} (réplica, esc. {escala:.2f})",
        parts=partes,
        razonamiento=raz,
    )


def variar(clave: str, escala: float = 1.0, hue: Optional[float] = None,
           semilla: Optional[int] = None,
           razonamiento: Optional[List[str]] = None) -> Modelo:
    """VARIANTE: réplica con tonos de color desplazados (algo 'parecido pero
    distinto'). 'hue' va de -0.5 a 0.5; si no se pasa, se elige al azar."""
    datos = _cargar_todo().get(clave)
    if datos is None:
        raise KeyError(f"'{clave}' no está en la biblioteca de estructuras/.")

    partes = _partes_desde(datos)
    if semilla is not None:
        random.seed(semilla)
    if hue is None:
        hue = random.uniform(-0.20, 0.20)

    cambios = 0
    for p in partes:
        if p.color and len(p.color) == 3:
            nuevo = _desplazar_tono(p.color, hue)
            if nuevo != p.color:
                p.color = nuevo
                cambios += 1

    if abs(escala - 1.0) > 1e-9:
        from . import catalogo
        partes = catalogo.reescalar(partes, escala)

    raz = razonamiento or [
        f"Creé una VARIANTE de '{datos.get('nombre', clave)}': la misma "
        f"estructura con la paleta de colores desplazada (tono {hue:+.2f}, "
        f"{cambios} piezas recoloradas).",
        f"Referencia base: {datos.get('referencia', 'sin referencia')}",
    ]
    return Modelo(
        modelName=f"{datos.get('nombre', clave)} (variante, esc. {escala:.2f})",
        parts=partes,
        razonamiento=raz,
    )


# ===========================================================================
# Utilidades de color (RGB -> HSV -> RGB)
# ===========================================================================

def desplazar_tono(rgb: List[int], delta: float) -> List[int]:
    """Desplaza el tono (matiz) de un color RGB. delta en (-0.5, 0.5)."""
    return _desplazar_tono(rgb, delta)


def _desplazar_tono(rgb: List[int], delta: float) -> List[int]:
    r, g, b = (c / 255.0 for c in rgb[:3])
    mx, mn = max(r, g, b), min(r, g, b)
    l = (mx + mn) / 2.0
    if mx == mn:
        return list(rgb)  # gris: el tono no aporta
    d = mx - mn
    s = d / (2.0 - mx - mn) if l > 0.5 else d / (mx + mn)
    if mx == r:
        h = ((g - b) / d + (6 if g < b else 0)) / 6.0
    elif mx == g:
        h = ((b - r) / d + 2) / 6.0
    else:
        h = ((r - g) / d + 4) / 6.0
    h = (h + delta) % 1.0

    def _hsv_a_rgb(hh: float, ss: float, ll: float) -> Tuple[int, int, int]:
        if ss == 0:
            c = int(ll * 255)
            return (c, c, c)
        q = ll * (1 + ss) if ll < 0.5 else ll + ss - ll * ss
        p = 2 * ll - q
        for k, hue_k in ((0, hh + 1 / 3), (1, hh), (2, hh - 1 / 3)):
            if hue_k < 0:
                hue_k += 1
            if hue_k > 1:
                hue_k -= 1
            if hue_k < 1 / 6:
                v = p + (q - p) * 6 * hue_k
            elif hue_k < 1 / 2:
                v = q
            elif hue_k < 2 / 3:
                v = p + (q - p) * (2 / 3 - hue_k) * 6
            else:
                v = p
            if k == 0:
                r2 = v
            elif k == 1:
                g2 = v
            else:
                b2 = v
        return (int(round(r2 * 255)), int(round(g2 * 255)), int(round(b2 * 255)))

    nuevo = _hsv_a_rgb(h, s, l)
    if nuevo == tuple(rgb[:3]):
        return list(rgb)
    return list(nuevo)


def _dims(datos: dict) -> str:
    m = datos.get("dimensiones_metros")
    if m and m.get("x") and m.get("z"):
        return f"{m['x']} × {m['y']} × {m['z']} m"
    s = datos.get("dimensiones_studs")
    if s:
        return f"{s['x']} × {s['y']} × {s['z']} studs"
    return "desconocidas"
