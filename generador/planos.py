"""
Motor de recreación de PLANOS arquitectónicos → Roblox.

Un PLANO describe una construcción con las MEDIDAS REALES que se usan en
arquitectura (en metros): dimensiones de planta, altura de cada piso, huecos
en los muros (puertas y ventanas con sus medidas reales), techo con su
pendiente, torres, chimeneas, porche... El motor:

  1. Convierte metros → studs de forma milimétrica (1 stud ≈ 0,28 m).
  2. Construye los muros con sus huecos (recorta segmentos y pinta bandas).
  3. Coloca puertas, ventanas, techo, torres, chimeneas, porche, valla.
  4. Devuelve Partes listas para Roblox (que pasan el QA como siempre).

Así el programa recrea cualquier construcción DESDE SU PLANO (medidas reales),
no de memoria visual. Los planos viven en 'estructuras/planos/*.json' y se
pueden añadir sin tocar código.
"""
from __future__ import annotations

import json
import math
import os
import random
from typing import List, Tuple

from . import catalogo
from .blueprint import Parte

CARPETA_PLANOS = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "estructuras", "planos",
)


# ===========================================================================
# Helpers locales
# ===========================================================================
def m(metros: float) -> float:
    """Metros reales → studs de Roblox (conversión milimétrica)."""
    return catalogo.metros_a_studs(metros)


def _caja(x, y, z, px, py, pz, color, material="Plastic",
          rot=(0, 0, 0), nombre="") -> Parte:
    return Parte(shape="Block", size=[x, y, z],
                 position=[px, py, pz], rotation=list(rot),
                 color=list(color), material=material, name=nombre)


def _cilindro(x, y, z, px, py, pz, color, material="Plastic", nombre="") -> Parte:
    return Parte(shape="Cylinder", size=[x, y, z],
                 position=[px, py, pz], rotation=[0, 0, 0],
                 color=list(color), material=material, name=nombre)


def _esfera(d, px, py, pz, color, material="Plastic",
            nombre="", mesh_scale=None) -> Parte:
    return Parte(shape="Ball", size=[d, d, d],
                 position=[px, py, pz], rotation=[0, 0, 0],
                 color=list(color), material=material,
                 meshScale=list(mesh_scale) if mesh_scale else None,
                 name=nombre)


def _techo_gablete_frente(largo_x, ancho_z, altura, y_base, color,
                          material="WoodPlanks", alero=2.0) -> List[Parte]:
    """Cumbrera en Z: el gablete (triángulo) queda visible en la fachada (+Z)."""
    semi = largo_x / 2.0
    largo_losa = math.sqrt(semi ** 2 + altura ** 2)
    angulo = math.degrees(math.atan2(altura, semi))
    espesor = 1.2
    partes = [
        _caja(largo_losa, espesor, ancho_z + alero, semi / 2.0,
              y_base + altura / 2.0, 0, color, material,
              rot=(0, 0, -angulo), nombre="Techo_lado_posX"),
        _caja(largo_losa, espesor, ancho_z + alero, -semi / 2.0,
              y_base + altura / 2.0, 0, color, material,
              rot=(0, 0, angulo), nombre="Techo_lado_negX"),
    ]
    cumbrera = tuple(max(0, c - 35) for c in color)
    partes.append(_caja(1.6, espesor * 2.2, ancho_z + alero,
                        0, y_base + altura + 0.4, 0,
                        cumbrera, material, nombre="Cumbrera_gablete"))
    return partes


def _techo_dos_aguas(largo_x, ancho_z, altura, y_base, color,
                     material="WoodPlanks", alero=2.0) -> List[Parte]:
    """Cumbrera en X: dos losas inclinadas front/back (gabletes laterales)."""
    semi = ancho_z / 2.0
    largo_losa = math.sqrt(semi ** 2 + altura ** 2)
    angulo = math.degrees(math.atan2(altura, semi))
    espesor = 1.2
    partes = [
        _caja(largo_x + alero, espesor, largo_losa, 0,
              y_base + altura / 2.0, semi / 2.0, color, material,
              rot=(angulo, 0, 0), nombre="Techo_lado_posZ"),
        _caja(largo_x + alero, espesor, largo_losa, 0,
              y_base + altura / 2.0, -semi / 2.0, color, material,
              rot=(-angulo, 0, 0), nombre="Techo_lado_negZ"),
    ]
    cumbrera = tuple(max(0, c - 35) for c in color)
    partes.append(_caja(largo_x + alero, espesor * 2.2, 1.6,
                        0, y_base + altura + 0.4, 0,
                        cumbrera, material, nombre="Cumbrera"))
    return partes


# ===========================================================================
# Muros con huecos (puertas y ventanas) y bandas de color
# ===========================================================================
def _muro(p: List[Parte], lado: str, inicio: float, longitud: float,
          base_perp: float, y0: float, altura: float, g: float,
          color: Tuple, material: str, huecos: List[dict],
          divisiones: List[dict], E: float):
    """Construye una pared corrida recortando los huecos de su lado.

    - lado       : 'frente' | 'trasera' | 'izq' | 'der'
    - inicio     : coordenada del eje por donde empieza la pared
    - longitud   : longitud de la pared a lo largo de su eje
    - base_perp  : coordenada perpendicular (plano de la pared)
    - divisiones : bandas verticales de color (ej. azul/rosa del piso superior)
    """
    es_eje_z = lado in ("izq", "der")

    aperturas = [h for h in huecos if h.get("lado") == lado]
    bandas = [d for d in divisiones if d.get("lado") == lado]

    bordes = [inicio, inicio + longitud]
    for h in aperturas:
        centro = m(h["centro_m"]) * E
        ancho = m(h["ancho_m"]) * E
        if inicio - 0.02 <= centro <= inicio + longitud + 0.02:
            bordes += [centro - ancho / 2, centro + ancho / 2]
    for d in bandas:
        bordes += [m(d["desde_m"]) * E, m(d["hasta_m"]) * E]
    bordes = sorted(c for c in set(round(b, 3) for b in bordes)
                    if inicio - 0.02 <= c <= inicio + longitud + 0.02)

    for a, b in zip(bordes, bordes[1:]):
        if b - a <= 0.05 * E:
            continue
        centro = (a + b) / 2
        largo = b - a
        color_seg, mat_seg = color, material
        for d in bandas:
            if m(d["desde_m"]) * E - 0.01 <= centro <= m(d["hasta_m"]) * E + 0.01:
                color_seg = tuple(d.get("color", color))
                mat_seg = d.get("material", material)
                break
        prefijo = {"frente": "Frente", "trasera": "Trasera",
                   "izq": "Lateral_izq", "der": "Lateral_der"}[lado]
        if es_eje_z:
            p.append(_caja(g, altura, largo, base_perp, y0 + altura / 2,
                           centro, color_seg, mat_seg,
                           nombre=f"{prefijo}_muro"))
        else:
            p.append(_caja(largo, altura, g, centro, y0 + altura / 2,
                           base_perp, color_seg, mat_seg,
                           nombre=f"{prefijo}_muro"))

    for h in aperturas:
        if h.get("tipo") == "puerta":
            _puerta(p, es_eje_z, base_perp, y0, h, E)
        else:
            _ventana(p, es_eje_z, base_perp, y0, h, E)


def _puerta(p: List[Parte], es_eje_z: bool, base_perp: float, y0: float,
            h: dict, E: float):
    centro = m(h["centro_m"]) * E
    ancho = m(h["ancho_m"]) * E
    alto = m(h["alto_m"]) * E
    color = tuple(h.get("color", (110, 72, 46)))
    marco = tuple(h.get("color_marco", (222, 218, 204)))
    if es_eje_z:
        p.append(_caja(0.5 * E, alto + 0.4 * E, ancho + 0.5 * E,
                       base_perp, y0 + alto / 2, centro, marco, "Wood",
                       nombre="Marco_puerta"))
        p.append(_caja(0.18 * E, alto - 0.2 * E, ancho - 0.2 * E,
                       base_perp + 0.18 * E, y0 + alto / 2, centro,
                       color, "Wood", nombre="Hoja_puerta"))
    else:
        p.append(_caja(ancho + 0.5 * E, alto + 0.4 * E, 0.5 * E,
                       centro, y0 + alto / 2, base_perp, marco, "Wood",
                       nombre="Marco_puerta"))
        p.append(_caja(ancho - 0.2 * E, alto - 0.2 * E, 0.18 * E,
                       centro, y0 + alto / 2 - 0.1 * E, base_perp + 0.18 * E,
                       color, "Wood", nombre="Hoja_puerta"))
        p.append(_esfera(0.16 * E, centro + ancho / 2 - 0.3 * E,
                         y0 + alto * 0.55, base_perp + 0.4 * E,
                         (240, 200, 70), nombre="Pomo_puerta"))


def _ventana(p: List[Parte], es_eje_z: bool, base_perp: float, y0: float,
             h: dict, E: float):
    centro = m(h["centro_m"]) * E
    ancho = m(h["ancho_m"]) * E
    alto = m(h["alto_m"]) * E
    y_base = m(h.get("y_base_m", 1.0)) * E
    marco = tuple(h.get("color_marco", (222, 218, 204)))
    cristal = tuple(h.get("color_cristal", (110, 150, 190)))
    yc = y0 + y_base + alto / 2
    if es_eje_z:
        p.append(_caja(0.45 * E, alto + 0.6 * E, ancho + 0.6 * E,
                       base_perp, yc, centro, marco, "Wood",
                       nombre="Marco_ventana"))
        p.append(_caja(0.2 * E, alto, ancho,
                       base_perp + 0.25 * E, yc, centro,
                       cristal, "Glass", nombre="Cristal_ventana"))
    else:
        p.append(_caja(ancho + 0.6 * E, alto + 0.6 * E, 0.45 * E,
                       centro, yc, base_perp, marco, "Wood",
                       nombre="Marco_ventana"))
        p.append(_caja(ancho, alto, 0.2 * E,
                       centro, yc, base_perp + 0.25 * E,
                       cristal, "Glass", nombre="Cristal_ventana"))


# ===========================================================================
# Construcción desde el plano
# ===========================================================================
def construir(plano: dict, escala: float = 1.0) -> List[Parte]:
    """Convierte un plano (medidas en METROS) en Partes de Roblox."""
    E = escala
    p: List[Parte] = []

    A = m(plano.get("ancho_m", 8.0)) * E
    F = m(plano.get("fondo_m", 8.0)) * E
    g = m(plano.get("grosor_muro_m", 0.25)) * E
    X1, X2 = -A / 2, A / 2
    ZF, ZT = F / 2, -F / 2
    cim = m(plano.get("cimientos_m", 0.5)) * E

    # ---- Cimientos ---------------------------------------------------------
    p.append(_caja(A + 0.6 * E, cim, F + 0.6 * E, 0, cim / 2, 0,
                   plano.get("color_fundacion", (136, 134, 132)),
                   "Concrete", nombre="Cimientos"))

    # ---- Plantas (muros + huecos + bandas de color) ------------------------
    y_actual = cim
    planta0_top = cim
    for planta in plano.get("plantas", []):
        altura = m(planta["altura_m"]) * E
        color = tuple(planta.get("color", (230, 230, 230)))
        material = planta.get("material", "SmoothPlastic")
        huecos = planta.get("huecos", [])
        divisiones = planta.get("divisiones", [])

        _muro(p, "frente", X1, A, ZF - g / 2, y_actual, altura, g,
              color, material, huecos, divisiones, E)
        _muro(p, "trasera", X1, A, ZT + g / 2, y_actual, altura, g,
              color, material, huecos, divisiones, E)
        _muro(p, "izq", ZT, F, X1 + g / 2, y_actual, altura, g,
              color, material, huecos, divisiones, E)
        _muro(p, "der", ZT, F, X2 - g / 2, y_actual, altura, g,
              color, material, huecos, divisiones, E)

        if planta.get("nivel", 0) == 0:
            planta0_top = y_actual + altura
        y_actual += altura

    # ---- Techo ---------------------------------------------------------------
    techo = plano.get("techo")
    ridge_y = y_actual
    if techo:
        pendiente = math.radians(techo.get("pendiente_grados", 35))
        alero = m(techo.get("alero_m", 0.5)) * E
        color_t = tuple(techo.get("color", (46, 58, 100)))
        mat_t = techo.get("material", "WoodPlanks")
        if techo.get("tipo", "gablete_frente") == "gablete_frente":
            altura_t = (A / 2) * math.tan(pendiente)
            p.extend(_techo_gablete_frente(A, F, altura_t, y_actual,
                                           color_t, mat_t, alero))
            ridge_y = y_actual + altura_t
            if techo.get("ventana_atico"):
                semi_f = A / 2
                largo_losa = math.sqrt(semi_f ** 2 + altura_t ** 2)
                angulo_f = math.degrees(math.atan2(altura_t, semi_f))
                p.append(_caja(largo_losa, 0.9 * g, g, semi_f / 2,
                               y_actual + altura_t / 2, ZF - g / 2,
                               techo.get("color_fronton_der", (214, 140, 168)),
                               "SmoothPlastic", rot=(0, 0, -angulo_f),
                               nombre="Fronton_gablete_der"))
                p.append(_caja(largo_losa, 0.9 * g, g, -semi_f / 2,
                               y_actual + altura_t / 2, ZF - g / 2,
                               techo.get("color_fronton_izq", (98, 134, 188)),
                               "SmoothPlastic", rot=(0, 0, angulo_f),
                               nombre="Fronton_gablete_izq"))
                _ventana(p, False, ZF - g / 2, y_actual - 0.1,
                         {"centro_m": 0, "ancho_m": 0.9, "alto_m": 0.85,
                          "y_base_m": catalogo.studs_a_metros(altura_t / 2 - 0.4) / E,
                          "color_marco": (222, 218, 204),
                          "color_cristal": (110, 150, 190)}, E)
        else:
            altura_t = (F / 2) * math.tan(pendiente)
            p.extend(_techo_dos_aguas(A, F, altura_t, y_actual,
                                      color_t, mat_t, alero))
            ridge_y = y_actual + altura_t

    # ---- Torres -------------------------------------------------------------
    for torre in plano.get("torres", []):
        cx = m(torre["centro_x_m"]) * E
        cz = m(torre["centro_z_m"]) * E
        lado = m(torre.get("lado_m", 3.0)) * E
        alto = m(torre.get("alto_m", 8.0)) * E
        tcol = tuple(torre.get("color", (214, 140, 168)))
        tmat = torre.get("material", "SmoothPlastic")
        ty0 = cim
        t_top = ty0 + alto
        for dx, dz, ex in ((lado / 2, 0, "x"), (-lado / 2, 0, "x"),
                           (0, lado / 2, "z"), (0, -lado / 2, "z")):
            if ex == "x":
                p.append(_caja(g, alto, lado, cx + dx, ty0 + alto / 2, cz + dz,
                               tcol, tmat, nombre="Torre_muro"))
            else:
                p.append(_caja(lado, alto, g, cx + dx, ty0 + alto / 2, cz + dz,
                               tcol, tmat, nombre="Torre_muro"))
        n_vent = int(torre.get("ventanas", 2))
        if n_vent > 1:
            paso_v = lado / (n_vent - 1)
        else:
            paso_v = 0
        for i in range(n_vent):
            vx = cx - lado / 2 + i * paso_v
            _ventana(p, False, cz + lado / 2 - 0.15 * E, ty0,
                     {"centro_m": catalogo.studs_a_metros(vx) / E,
                      "ancho_m": torre.get("ventana_ancho_m", 0.9),
                      "alto_m": torre.get("ventana_alto_m", 1.6),
                      "y_base_m": 1.0,
                      "color_marco": (222, 218, 204),
                      "color_cristal": (110, 150, 190)}, E)
        p.append(_caja(lado + 0.5 * E, m(0.4) * E, lado + 0.5 * E,
                       cx, t_top, cz, (222, 218, 204), "Wood",
                       nombre="Cornisa_torre"))
        if torre.get("cupula"):
            p.append(_esfera(lado * 1.15, cx, t_top + lado * 0.45, cz,
                             tuple(torre.get("color_cupula", (46, 58, 100))),
                             "WoodPlanks", nombre="Cupula_torre",
                             mesh_scale=[1, 0.75, 1]))
            p.append(_cilindro(0.12 * E, m(0.8) * E, 0.12 * E,
                               cx, t_top + lado * 0.9, cz,
                               (240, 200, 70), "Neon", nombre="Pinaculo_torre"))

    # ---- Chimeneas ----------------------------------------------------------
    for chim in plano.get("chimeneas", []):
        cx = m(chim["centro_x_m"]) * E
        cz = m(chim["centro_z_m"]) * E
        lado = m(chim.get("lado_m", 0.8)) * E
        alto = m(chim.get("alto_m", 3.0)) * E
        ccol = tuple(chim.get("color", (152, 90, 70)))
        y_base = ridge_y - 0.6 * E
        p.append(_caja(lado, alto, lado, cx, y_base + alto / 2, cz,
                       ccol, chim.get("material", "Brick"), nombre="Chimenea"))
        p.append(_caja(lado + 0.5 * E, 0.4 * E, lado + 0.5 * E,
                       cx, y_base + alto + 0.2 * E, cz,
                       (136, 134, 132), "Concrete", nombre="Sombrerete_chimenea"))

    # ---- Porche -------------------------------------------------------------
    porche = plano.get("porche")
    if porche:
        pcx = m(porche["centro_x_m"]) * E
        ancho = m(porche["ancho_m"]) * E
        fondo = m(porche["fondo_m"]) * E
        pcol = tuple(porche.get("color", (158, 122, 84)))
        p.append(_caja(ancho, 0.2 * E, fondo, pcx, 0.1 * E, ZF + fondo / 2,
                       pcol, "WoodPlanks", nombre="Piso_porche"))
        techo_porche_y = planta0_top - m(0.3) * E
        ncol = int(porche.get("columnas", 3))
        for i in range(ncol):
            cxc = pcx - ancho / 2 + ancho * (i + 0.5) / ncol
            alto_col = techo_porche_y - 0.15 * E
            p.append(_cilindro(0.24 * E, alto_col, 0.24 * E,
                               cxc, 0.15 * E + alto_col / 2,
                               ZF + fondo / 2, (222, 218, 204), "Wood",
                               nombre="Columna_porche"))
        p.append(_caja(ancho + 0.5 * E, 0.22 * E, fondo + 0.5 * E,
                       pcx, techo_porche_y, ZF + fondo / 2,
                       porche.get("color_techo", (86, 110, 74)),
                       "WoodPlanks", nombre="Techo_porche"))
        for i, dy in enumerate((0.12, 0.24)):
            p.append(_caja(ancho * 0.6, 0.12 * E, 0.5 * E,
                           pcx, dy, ZF + fondo + 0.4 * E,
                           pcol, "WoodPlanks", nombre=f"Escalon_porche_{i}"))
        # Baranda del porche
        p.append(_caja(ancho, 0.12 * E, 0.12 * E, pcx, 0.75 * E,
                       ZF + fondo + 0.2 * E, (222, 218, 204), "Wood",
                       nombre="Riel_porche"))
        p.append(_caja(ancho, 0.12 * E, 0.12 * E, pcx, 1.3 * E,
                       ZF + fondo + 0.2 * E, (222, 218, 204), "Wood",
                       nombre="Riel_porche_2"))

    # ---- Césped y valla ------------------------------------------------------
    if plano.get("cesped"):
        p.append(_caja(A + 4 * E, 0.2 * E, F + 4 * E, 0, 0.1 * E, 0,
                       (106, 168, 92), "Grass", nombre="Cesped"))
    if plano.get("valla"):
        ancho_valla = A + 4 * E
        VZ = ZF + 2 * E
        npiq = int(ancho_valla / 2.4)
        for i in range(npiq):
            p.append(_caja(0.5 * E, 2 * E, 0.5 * E,
                           -ancho_valla / 2 + 1.2 * E + i * 2.4 * E, 1 * E, VZ,
                           (222, 218, 204), "Wood", nombre="Piquete_valla"))
        for dy in (0.6 * E, 1.4 * E):
            p.append(_caja(ancho_valla, 0.4 * E, 0.4 * E, 0, dy, VZ,
                           (222, 218, 204), "Wood", nombre="Riel_valla"))

    # ---- Globos ---------------------------------------------------------------
    n_globos = int(plano.get("globos", 0))
    if n_globos:
        rnd = random.Random(int(plano.get("semilla", 7)))
        paleta = [(214, 62, 62), (66, 96, 214), (238, 214, 66), (78, 168, 78),
                  (236, 138, 52), (146, 76, 178), (232, 122, 168), (80, 198, 216)]
        nube_y0 = ridge_y + 2 * E
        nube_y1 = ridge_y + 14 * E
        for i in range(n_globos):
            p.append(_esfera(random.uniform(2.6, 4.4) * E,
                             rnd.uniform(-A / 2, A / 2) * 0.9,
                             rnd.uniform(nube_y0, nube_y1),
                             rnd.uniform(-F / 3, F / 3),
                             rnd.choice(paleta), "Plastic",
                             nombre=f"Globo_{i}"))
        for i, (ax, az) in enumerate(((-2.9, 1.0), (-1.0, 1.5), (0.5, 1.8),
                                      (2.0, 2.0), (0, -0.5), (2.5, 0.3))):
            p.append(_cilindro(0.06 * E, m(2.5) * E, 0.06 * E,
                               m(ax) * E, nube_y0 - m(1.0) * E, m(az) * E,
                               (96, 92, 88), "Plastic", nombre="Cuerda_globo"))

    return p


# ===========================================================================
# Carga de planos desde estructuras/planos/*.json
# ===========================================================================
def cargar(clave: str) -> dict:
    """Carga un plano por su clave ('casa_up'). Lanza KeyError si no existe."""
    ruta = os.path.join(CARPETA_PLANOS, clave + ".json")
    if not os.path.isfile(ruta):
        raise KeyError(f"'{clave}' no tiene plano en {CARPETA_PLANOS}")
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)


def disponibles() -> List[str]:
    if not os.path.isdir(CARPETA_PLANOS):
        return []
    return sorted(n[:-5] for n in os.listdir(CARPETA_PLANOS)
                  if n.endswith(".json"))
