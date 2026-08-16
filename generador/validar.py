"""
Loop de validación (QA) de estructuras.

Antes de enviar un modelo a Roblox, este módulo:
  1. Detecta errores de construcción (piezas inválidas, flotantes, ocultas,
     duplicadas, desproporcionadas...).
  2. Comprueba compatibilidad con Roblox (materiales, formas, tamaños).
  3. Autocorrige lo que es seguro (materiales inválidos → Plastic, etc.).
  4. Devuelve un informe legible (errores / avisos / sugerencias).

Regla: una estructura se envía SIEMPRE tras pasar el QA; lo que no se pueda
corregir se reporta como error y no se encola.
"""
from __future__ import annotations

import math
from typing import List, Tuple

from . import catalogo
from .blueprint import Modelo, Parte, MATERIALES_ROBLOX, FORMAS_ROBLOX, MALLAS_ROBLOX

# Piezas que se espera que floten a propósito (por su nombre)
_FLOTAN_A_PROPOSITO = ("globo", "cuerda", "luz", "antena", "bandera", "ave")

# Detalles de superficie: se espera que vayan incrustados en paredes/suelos
# (ventanas, marcos, puertas, molduras...). No son 'piezas ocultas'.
_DETALLES_SUPERFICIE = (
    "ventana", "marco", "cristal", "pomo", "dintel", "escalon",
    "riel", "piquete", "valla", "columna", "banda", "esquinero",
    "cuerda", "globo", "antena", "luz", "forro", "remate", "pinaculo",
    "fronton", "atico", "cumbrera", "dormer",
)


def _aabb(p: Parte) -> Tuple[float, float, float, float, float, float]:
    """Caja de la pieza SIN rotar."""
    sx, sy, sz = p.size
    px, py, pz = p.position
    return (px - sx / 2, py - sy / 2, pz - sz / 2,
            px + sx / 2, py + sy / 2, pz + sz / 2)





def _solapan(a, b, margen=0.0) -> bool:
    (ax1, ay1, az1, ax2, ay2, az2) = a
    (bx1, by1, bz1, bx2, by2, bz2) = b
    return not (ax2 < bx1 - margen or bx2 < ax1 - margen or
                ay2 < by1 - margen or by2 < ay1 - margen or
                az2 < bz1 - margen or bz2 < az1 - margen)


def _distancia(a, b) -> float:
    """Distancia mínima aproximada entre dos AABBs (0 si se tocan)."""
    (ax1, ay1, az1, ax2, ay2, az2) = a
    (bx1, by1, bz1, bx2, by2, bz2) = b
    dx = max(0.0, bx1 - ax2, ax1 - bx2)
    dy = max(0.0, by1 - ay2, ay1 - by2)
    dz = max(0.0, bz1 - az2, az1 - bz2)
    return (dx * dx + dy * dy + dz * dz) ** 0.5


def informe(modelo: Modelo) -> dict:
    """Ejecuta el QA completo y devuelve un informe serializable."""
    errores: List[str] = []
    avisos: List[str] = []
    sugerencias: List[str] = []
    partes = modelo.parts

    # --- 1) Validación base (forma, material, malla, tamaños > 0) -------------
    for e in modelo.validar():
        errores.append(e)

    # --- 2) Límites de tamaño y piezas -----------------------------------------
    lim = catalogo.LIMITES
    if len(partes) > lim["piezas_recomendadas"]:
        avisos.append(f"El modelo tiene {len(partes)} piezas (se recomienda "
                      f"≤ {lim['piezas_recomendadas']} para rendimiento móvil).")
    if len(partes) > lim["piezas_max"]:
        errores.append(f"Demasiadas piezas ({len(partes)} > {lim['piezas_max']}). "
                       "Divide el modelo en varios o simplifica.")

    # --- 3) Bounding box general ------------------------------------------------
    bx, by, bz = catalogo.bounding_box(partes)
    if max(bx, by, bz) > lim["caja_max"]:
        avisos.append(f"El modelo es enorme ({bx:.0f}×{by:.0f}×{bz:.0f} studs). "
                      "Revisa la escala.")

    # --- 4) Duplicados exactos ---------------------------------------------------
    vistos = {}
    for i, p in enumerate(partes):
        clave = (p.shape, tuple(round(v, 2) for v in p.size),
                 tuple(round(v, 2) for v in p.position))
        if clave in vistos:
            avisos.append(f"Pieza #{i} ('{p.name or p.shape}') parece duplicada "
                          f"de la #{vistos[clave]}.")
        else:
            vistos[clave] = i

    # --- 5) Piezas ocultas (contenidas por completo en otra más grande) ---------
    cajas = [catalogo.aabb(p) for p in partes]
    for i, p in enumerate(partes):
        ci = cajas[i]
        vol_i = p.size[0] * p.size[1] * p.size[2]
        nombre_i = (p.name or "").lower()
        if any(k in nombre_i for k in _DETALLES_SUPERFICIE):
            continue   # detalles de fachada: es normal que vayan en la pared
        for j, q in enumerate(partes):
            if j == i:
                continue
            cj = cajas[j]
            vol_j = q.size[0] * q.size[1] * q.size[2]
            if vol_j < 1.0 or vol_j <= vol_i:
                continue
            if (cj[0] <= ci[0] and cj[1] <= ci[1] and cj[2] <= ci[2] and
                    cj[3] >= ci[3] and cj[4] >= ci[4] and cj[5] >= ci[5]):
                avisos.append(f"Pieza #{i} ('{p.name or p.shape}') está oculta "
                              f"dentro de #{j} ('{q.name or q.shape}').")
                break

    # --- 6) Piezas flotantes ------------------------------------------------------
    for i, p in enumerate(partes):
        nombre = (p.name or "").lower()
        if any(k in nombre for k in _FLOTAN_A_PROPOSITO):
            continue
        if p.size[1] < 0.05:
            continue
        apoyada = False
        for j, q in enumerate(partes):
            if j == i:
                continue
            # margen de 0.05 studs: el contacto borde a borde cuenta como apoyo
            # (evita falsos positivos por errores de punto flotante en escalas)
            if not _solapan(cajas[i], cajas[j], margen=0.05):
                continue
            apoyada = True
            break
        if not apoyada:
            # ¿flota sobre el suelo (y=0)? Solo avisamos si no hay nada debajo
            suelo = cajas[i][1]  # y inferior
            if suelo > lim["flotacion_max"]:
                avisos.append(f"Pieza #{i} ('{p.name or p.shape}') parece "
                              f"flotar sin apoyo (a y={suelo:.1f}).")

    # --- 7) ¿Es una estructura 3D o la imagen literal? ---------------------------
    if len(partes) >= 60 and bx > 0:
        ancho_base = max(bx, bz)
        fondo_base = min(bx, bz)
        if ancho_base > 0 and fondo_base / ancho_base < 0.15:
            avisos.append(
                f"El modelo es casi PLANO (fondo {fondo_base:.0f} vs ancho "
                f"{ancho_base:.0f} studs): parece la IMAGEN LITERAL, no una "
                "estructura 3D. Usa el modo 'Volumen 3D' o el modo IA, o "
                "pídele 'más profunda'."
            )

    # --- 8) Sugerencias de material/uso ------------------------------------------
    conteo_uso = {}
    for p in partes:
        uso = catalogo.uso_sugerido(p)
        conteo_uso[uso] = conteo_uso.get(uso, 0) + 1
    sugerencias.append("Composición: " + ", ".join(
        f"{k}×{v}" for k, v in sorted(conteo_uso.items())))
    if conteo_uso.get("techo", 0) > 0 and not any(
            p.material in catalogo.MATERIALES_POR_USO["techo"] for p in partes):
        sugerencias.append("Tienes piezas de techo: usa un material de techo "
                           "(WoodPlanks, Slate, Rubber, Metal).")

    return {
        "errores": errores,
        "avisos": avisos,
        "sugerencias": sugerencias,
        "resumen": {
            "piezas": len(partes),
            "caja_studs": [round(v, 1) for v in (bx, by, bz)],
            "caja_metros": [round(catalogo.studs_a_metros(v), 2) for v in (bx, by, bz)],
            "es_valido": not errores,
        },
    }


def autocorregir(modelo: Modelo) -> Tuple[Modelo, List[str]]:
    """Corrige lo que es seguro y devuelve (modelo_corregido, cambios)."""
    cambios: List[str] = []
    partes: List[Parte] = []
    for i, p in enumerate(modelo.parts):
        q = Parte(
            shape=p.shape, size=list(p.size), position=list(p.position),
            rotation=list(p.rotation), color=list(p.color),
            material=p.material, mesh=p.mesh,
            meshScale=list(p.meshScale) if p.meshScale else None,
            script=p.script, name=p.name,
        )
        if q.shape not in FORMAS_ROBLOX:
            cambios.append(f"#{i}: forma '{q.shape}' → Block")
            q.shape = "Block"
        if q.material not in MATERIALES_ROBLOX:
            cambios.append(f"#{i}: material '{q.material}' → Plastic")
            q.material = "Plastic"
        if q.mesh and q.mesh not in MALLAS_ROBLOX:
            cambios.append(f"#{i}: malla '{q.mesh}' eliminada")
            q.mesh = None
        for eje in range(3):
            if q.size[eje] <= 0:
                cambios.append(f"#{i}: tamaño {eje} inválido ({q.size[eje]}) → 0.1")
                q.size[eje] = 0.1
        partes.append(q)
    modelo_corregido = Modelo(
        id=modelo.id, modelName=modelo.modelName, parts=partes,
        parent=modelo.parent, razonamiento=modelo.razonamiento,
    )
    return modelo_corregido, cambios
