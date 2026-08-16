"""
Catálogo de conocimiento de construcción para Roblox.

Este módulo es lo que el programa "sabe" sobre cómo construir en Roblox:
conversión de medidas reales a studs, catálogo de formas y materiales,
límites técnicos y reglas de compatibilidad. Toda estructura nueva debe
consultar este módulo para adaptarse correctamente a Roblox.

UNIDADES:
  - Roblox mide en "studs". 1 stud ≈ 0,28 metros (medida estándar).
  - Para recrear un objeto real "milimétricamente": metros → studs.
"""
from __future__ import annotations

import math
from typing import List, Optional, Tuple

from .blueprint import Parte

# ===========================================================================
# Conversión de unidades
# ===========================================================================

STUD_A_METRO = 0.28   # 1 stud ≈ 0,28 m


def metros_a_studs(metros: float) -> float:
    """Convierte metros reales a studs de Roblox (1 stud ≈ 0,28 m)."""
    return metros / STUD_A_METRO


def studs_a_metros(studs: float) -> float:
    return studs * STUD_A_METRO


# ===========================================================================
# Límites técnicos de Roblox
# ===========================================================================

LIMITES = {
    "tamano_min": 0.05,          # studs por eje (menor puede dar fallos de física)
    "tamano_max": 2048.0,        # studs por eje (límite duro de Roblox)
    "piezas_recomendadas": 500,  # por modelo (rendimiento en móvil)
    "piezas_max": 2000,          # tope duro antes de partir el modelo
    "flotacion_max": 3.0,        # studs de separación sin apoyo antes de avisar
    "caja_max": 512.0,           # studs por eje del modelo completo
}

# ===========================================================================
# Catálogo de formas (Enum.PartType)
# ===========================================================================

FORMAS = {
    "Block":       {"nota": "caja básica: paredes, suelos, masas, muebles"},
    "Wedge":       {"nota": "cuña/rampa: pendientes, aleros, cuestas"},
    "CornerWedge": {"nota": "esquina cortada: techos a cuatro aguas, chaflanes"},
    "Cylinder":    {"nota": "cilindro facetado: columnas, troncos, tuberías"},
    "Ball":        {"nota": "esfera nativa: copas de árbol, pomos, globos, ruedas"},
}

# ===========================================================================
# Materiales de Roblox agrupados por uso (solo valores que existen)
# ===========================================================================

MATERIALES_POR_USO = {
    "estructura": ["Concrete", "Brick", "Stone", "Wood", "WoodPlanks",
                   "Metal", "MetalSheet", "SmoothPlastic"],
    "techo":      ["WoodPlanks", "Slate", "Rubber", "Metal"],
    "madera":     ["Wood", "WoodPlanks", "WoodRounded"],
    "cristal":    ["Glass", "Neon"],
    "suelo":      ["Concrete", "Pavement", "Stone", "Cobblestone", "Slate"],
    "natural":    ["Grass", "LeafyGrass", "Sand", "Rock", "Mud", "Snow", "Ice"],
    "metal":      ["Metal", "MetalSheet", "DiamondPlate", "CorrodedMetal"],
    "ladrillo":   ["Brick"],
    "decorativo": ["Fabric", "Carpet", "Leather", "Cardboard", "Ceramic",
                   "Marble", "Granite", "Plastic"],
}

_USO_POR_MATERIAL: dict = {}
for _uso, _mat_list in MATERIALES_POR_USO.items():
    for _m in _mat_list:
        _USO_POR_MATERIAL.setdefault(_m, _uso)


def uso_sugerido(parte: Parte) -> str:
    """Clasifica una pieza: ¿para qué sirve según su forma/material/nombre?"""
    nombre = (parte.name or "").lower()
    if "techo" in nombre or "teja" in nombre or "cumbrera" in nombre or "alero" in nombre:
        return "techo"
    if "ventana" in nombre or "cristal" in nombre:
        return "cristal"
    if "puerta" in nombre or "marco" in nombre or "columna" in nombre:
        return "madera"
    if parte.shape in ("Wedge", "CornerWedge"):
        return "techo/rampa"
    if parte.shape == "Ball":
        return "esfera decorativa"
    return _USO_POR_MATERIAL.get(parte.material, "estructura")


# ===========================================================================
# Medición y escala
# ===========================================================================

def _rotar_punto(p: Tuple[float, float, float], rot) -> Tuple[float, float, float]:
    """Rota un punto según CFrame.Angles(rx, ry, rz) en grados (orden X, Y, Z)."""
    rx, ry, rz = (math.radians(r) for r in rot)
    x, y, z = p
    # alrededor de X
    y, z = y * math.cos(rx) - z * math.sin(rx), y * math.sin(rx) + z * math.cos(rx)
    # alrededor de Y
    x, z = x * math.cos(ry) + z * math.sin(ry), -x * math.sin(ry) + z * math.cos(ry)
    # alrededor de Z
    x, y = x * math.cos(rz) - y * math.sin(rz), x * math.sin(rz) + y * math.cos(rz)
    return (x, y, z)


def aabb(parte: Parte) -> Tuple[float, float, float, float, float, float]:
    """Caja envolvente real de la pieza, teniendo en cuenta su rotación
    (rota los 8 vértices y toma min/max).

    Devuelve (x1, y1, z1, x2, y2, z2).
    """
    sx, sy, sz = parte.size
    px, py, pz = parte.position
    if not any(abs(r) > 0.5 for r in parte.rotation):
        return (px - sx / 2, py - sy / 2, pz - sz / 2,
                px + sx / 2, py + sy / 2, pz + sz / 2)
    xs, ys, zs = [], [], []
    for dx in (-sx / 2, sx / 2):
        for dy in (-sy / 2, sy / 2):
            for dz in (-sz / 2, sz / 2):
                qx, qy, qz = _rotar_punto((dx, dy, dz), parte.rotation)
                xs.append(px + qx)
                ys.append(py + qy)
                zs.append(pz + qz)
    return (min(xs), min(ys), min(zs), max(xs), max(ys), max(zs))


def bounding_box(partes: List[Parte]) -> Tuple[float, float, float]:
    """Devuelve (largo_x, alto_y, fondo_z) del modelo en studs, con
    rotaciones reales (caja envolvente mínima aproximada)."""
    if not partes:
        return (0.0, 0.0, 0.0)
    cajas = [aabb(p) for p in partes]
    return (max(c[3] for c in cajas) - min(c[0] for c in cajas),
            max(c[4] for c in cajas) - min(c[1] for c in cajas),
            max(c[5] for c in cajas) - min(c[2] for c in cajas))


def reescalar(partes: List[Parte], factor: float) -> List[Parte]:
    """Multiplica tamaño y posición de todas las piezas por 'factor'."""
    out = []
    for p in partes:
        out.append(Parte(
            shape=p.shape,
            size=[s * factor for s in p.size],
            position=[c * factor for c in p.position],
            rotation=list(p.rotation),
            color=list(p.color),
            material=p.material,
            mesh=p.mesh,
            meshScale=[s * factor for s in p.meshScale] if p.meshScale else None,
            script=p.script,
            name=p.name,
        ))
    return out


def reescalar_ejes(partes: List[Parte], sx: float = 1.0, sy: float = 1.0,
                   sz: float = 1.0) -> List[Parte]:
    """Escala tamaños y posiciones con factores DISTINTOS por eje
    (ej. 'más alta' = sy > 1)."""
    out = []
    for p in partes:
        out.append(Parte(
            shape=p.shape,
            size=[p.size[0] * sx, p.size[1] * sy, p.size[2] * sz],
            position=[p.position[0] * sx, p.position[1] * sy, p.position[2] * sz],
            rotation=list(p.rotation),
            color=list(p.color),
            material=p.material,
            mesh=p.mesh,
            meshScale=[p.meshScale[0] * sx, p.meshScale[1] * sy,
                       p.meshScale[2] * sz] if p.meshScale else None,
            script=p.script,
            name=p.name,
        ))
    return out


def escala_para_solar(base_largo, base_fondo, metros_largo, metros_ancho) -> float:
    """Escala E para que un modelo (diseñado a E=1, con estas dimensiones en
    studs) quepa en un solar de metros_largo × metros_ancho."""
    st_largo = metros_a_studs(metros_largo)
    st_ancho = metros_a_studs(metros_ancho)
    if base_largo <= 0 or base_fondo <= 0:
        return 1.0
    return min(st_largo / base_largo, st_ancho / base_fondo)


def escala_para_altura(base_alto, metros_alto) -> float:
    """Escala E para que el modelo (diseñado a E=1) mida como máximo metros_alto."""
    if base_alto <= 0:
        return 1.0
    return metros_a_studs(metros_alto) / base_alto
