"""
Motor de generación procedural: construye estructuras 3D (listas de Partes)
a partir de descripciones. Cada función recibe una escala y opciones, y
devuelve una lista de Parte lista para Roblox.

Las proporciones están pensadas en "studs" de Roblox (1 stud ≈ 0,28 m).
"""
from __future__ import annotations

import math
import random
from typing import Callable, Dict, List, Optional

from . import catalogo
from .blueprint import Parte

# ===========================================================================
# Helpers: fábricas de partes
# ===========================================================================

def _caja(x, y, z, px, py, pz, color, material="Plastic",
          rot=(0, 0, 0), nombre="", mesh=None, mesh_scale=None) -> Parte:
    return Parte(
        shape="Block", size=[x, y, z],
        position=[px, py, pz], rotation=list(rot),
        color=list(color), material=material,
        mesh=mesh, meshScale=list(mesh_scale) if mesh_scale else None,
        name=nombre,
    )


def _cuña(x, y, z, px, py, pz, color, material="Plastic",
          rot=(0, 0, 0), nombre="") -> Parte:
    return Parte(
        shape="Wedge", size=[x, y, z],
        position=[px, py, pz], rotation=list(rot),
        color=list(color), material=material, name=nombre,
    )


def _cilindro(x, y, z, px, py, pz, color, material="Plastic",
              rot=(0, 0, 0), nombre="", suave=True) -> Parte:
    """Cilindro: PartType.Cylinder (suave=False) o Block + SpecialMesh (suave=True)."""
    if suave:
        return _caja(x, y, z, px, py, pz, color, material,
                     rot=rot, nombre=nombre, mesh="Cylinder")
    return Parte(
        shape="Cylinder", size=[x, y, z],
        position=[px, py, pz], rotation=list(rot),
        color=list(color), material=material, name=nombre,
    )


def _esfera(d, px, py, pz, color, material="Plastic",
            nombre="", mesh_scale=None) -> Parte:
    """Esfera de parte nativa (Ball), con escala no uniforme posible."""
    return Parte(
        shape="Ball", size=[d, d, d],
        position=[px, py, pz], rotation=[0, 0, 0],
        color=list(color), material=material,
        meshScale=list(mesh_scale) if mesh_scale else None,
        name=nombre,
    )


def _techo_dos_aguas(largo_x, ancho_z, altura, y_base, color,
                     material="WoodPlanks", alero=2.0) -> List[Parte]:
    """Techo a dos aguas hecho de dos losas inclinadas (robusto, sin depender
    de la orientación de las cuñas). La cumbrera corre a lo largo del eje X.

    - largo_x : longitud de la cumbrera (eje X)
    - ancho_z : distancia entre aleros (eje Z)
    - altura  : subida desde el alero hasta la cumbrera
    - y_base  : altura de los aleros
    """
    import math
    semi = ancho_z / 2.0
    largo_losa = math.sqrt(semi ** 2 + altura ** 2)
    angulo = math.degrees(math.atan2(altura, semi))
    espesor = 1.2

    partes = []
    # Losa del lado +Z: baja hacia el alero frontal (rotación X positiva
    # lleva el extremo +Z hacia abajo en Roblox).
    partes.append(_caja(
        largo_x + alero, espesor, largo_losa,
        0, y_base + altura / 2.0, semi / 2.0,
        color, material, rot=(angulo, 0, 0),
        nombre="Techo_lado_posZ",
    ))
    # Losa del lado -Z: simétrica.
    partes.append(_caja(
        largo_x + alero, espesor, largo_losa,
        0, y_base + altura / 2.0, -semi / 2.0,
        color, material, rot=(-angulo, 0, 0),
        nombre="Techo_lado_negZ",
    ))
    # Cumbrera: un listón que cubre la unión de las dos losas (color oscurecido).
    color_cumbrera = tuple(max(0, c - 35) for c in color)
    partes.append(_caja(
        largo_x + alero, espesor * 2.2, 1.6,
        0, y_base + altura + 0.4, 0,
        color_cumbrera, material, nombre="Cumbrera",
    ))
    return partes


# ===========================================================================
# Estructuras conocidas
# ===========================================================================

# --- Paletas de colores de la casa UP (Pixar, 2009) ------------------------
CREMA = (242, 226, 178)        # siding de la planta baja (crema)
AZUL = (98, 134, 188)          # pared izquierda del piso superior
ROSA = (214, 140, 168)         # pared derecha del piso superior
VERDE_HABITACION = (158, 196, 184)  # habitación lateral
TEJA = (46, 58, 100)           # techo azul marino
VERDE_MOLDU = (86, 110, 74)    # molduras / detalles (verde apagado)
MARRON_OSCURO = (88, 56, 40)   # madera vieja (zócalos, entreplanta)
PIEDRA = (136, 134, 132)       # cimientos
MADERA_PORCHE = (158, 122, 84) # piso del porche
BLANCO_SUCIO = (222, 218, 204) # valla y marcos
VENTANA = (110, 150, 190)      # cristal azul claro
PUERTA = (110, 72, 46)
MANIJA = (240, 200, 70)        # pomo amarillo
LADRILLO = (152, 90, 70)
CESPE = (106, 168, 92)         # césped
CUERDA = (96, 92, 88)          # cuerdas de los globos

PALETA_GLOBOS = [
    (214, 62, 62),    # rojo
    (66, 96, 214),    # azul
    (238, 214, 66),   # amarillo
    (78, 168, 78),    # verde
    (236, 138, 52),   # naranja
    (146, 76, 178),   # morado
    (232, 122, 168),  # rosa
    (80, 198, 216),   # cian
]


def casa_up_legacy(escala: float = 1.0, globos: bool = True, semilla: int = 7) -> List[Parte]:
    """Réplica aproximada de la casa de Carl y Ellie (Up, Pixar 2009).

    Arquitectura: victoriana estilo Queen Anne — cuerpo de dos plantas casi
    cuadrado, torre cilíndrica con cúpula en la esquina delantera derecha,
    porche de madera con columnas y baranda, valla de piquetes, chimenea de
    ladrillo y (opcionalmente) la nube de globos que la hace volar.

    DIMENSIONES REALES DE REFERENCIA: según el modelista THEMODELMAKER
    (planos CAD del diseñador de Pixar Don Shank, escala 1:48), la casa es
    casi cuadrada en planta (~180×180 mm ≈ 8,6 × 8,6 m reales) y mide
    ~210 mm ≈ 10 m hasta la cima de la chimenea. En studs de Roblox
    (1 stud ≈ 0,28 m): ~31×31 studs de planta y ~36 studs de alto.
    """
    E = escala
    partes: List[Parte] = []

    # ---- Base de piedra + césped ---------------------------------------------
    partes.append(_caja(46 * E, 4 * E, 48 * E, 0, 2 * E, 0, PIEDRA,
                        "Concrete", nombre="Cimientos"))
    partes.append(_caja(42 * E, 1.2 * E, 36 * E, 0, 4.6 * E, 0, CESPE,
                        "Grass", nombre="Cesped"))

    # ---- Cuerpo principal: dos plantas ---------------------------------------
    ancho, prof, alto1, alto2 = 38 * E, 30 * E, 13 * E, 13 * E   # cuerpo casi cuadrado
    y_piso1 = 5.2 * E                # base de las paredes (sobre el césped)
    y_piso2 = y_piso1 + alto1
    y_cornisa = y_piso2 + alto2
    # Paredes planta 1 (crema) y zócalo de madera
    for lado in (-1, 1):
        partes.append(_caja(1 * E, alto1, prof, lado * ancho / 2, y_piso1 + alto1 / 2, 0,
                            CREMA, "SmoothPlastic", nombre=f"Pared_lateral_{lado:+d}"))
    for lado in (-1, 1):
        partes.append(_caja(ancho, alto1, 1 * E, 0, y_piso1 + alto1 / 2, lado * prof / 2,
                            CREMA, "SmoothPlastic", nombre=f"Pared_front_{lado:+d}"))
    # Zócalo de madera oscura en la base de las paredes
    for lado in (-1, 1):
        partes.append(_caja(ancho + 2 * E, 2 * E, 1.2 * E, 0, y_piso1 + 1 * E, lado * prof / 2,
                            MARRON_OSCURO, "Wood", nombre=f"Zocalo_{lado:+d}"))
    # Listón de moldura verde entre las dos plantas
    for lado in (-1, 1):
        partes.append(_caja(ancho + 1 * E, 0.9 * E, 1.3 * E, 0, y_piso1 + alto1 + 0.4 * E,
                            lado * prof / 2, VERDE_MOLDU, "Wood",
                            nombre=f"Liston_pisos_{lado:+d}"))
    # Entreplanta (piso de la segunda planta)
    partes.append(_caja(ancho, 1.2 * E, prof, 0, y_piso2 - 0.6 * E, 0,
                        MADERA_PORCHE, "Wood", nombre="Entreplanta"))
    # ---- Paredes del piso superior: mitad izquierda azul, derecha rosa -------
    mitad = ancho / 2
    for lado in (-1, 1):   # fachada y trasera
        partes.append(_caja(mitad, alto2, 1 * E, -mitad / 2, y_piso2 + alto2 / 2,
                            lado * prof / 2, AZUL, "SmoothPlastic",
                            nombre=f"Pared2_azul_{lado:+d}"))
        partes.append(_caja(mitad, alto2, 1 * E, +mitad / 2, y_piso2 + alto2 / 2,
                            lado * prof / 2, ROSA, "SmoothPlastic",
                            nombre=f"Pared2_rosa_{lado:+d}"))
    partes.append(_caja(1 * E, alto2, prof, -ancho / 2, y_piso2 + alto2 / 2, 0,
                        AZUL, "SmoothPlastic", nombre="Pared2_lateral_izq"))
    partes.append(_caja(1 * E, alto2, prof, +ancho / 2, y_piso2 + alto2 / 2, 0,
                        ROSA, "SmoothPlastic", nombre="Pared2_lateral_der"))
    # Divisor de madera verde entre las dos mitades
    for lado in (-1, 1):
        partes.append(_caja(0.8 * E, alto2 + 0.2 * E, 1.3 * E, 0, y_piso2 + alto2 / 2,
                            lado * prof / 2, VERDE_MOLDU, "Wood",
                            nombre=f"Divisor_pisos_{lado:+d}"))

    # ---- Molduras (detalle Queen Anne) ---------------------------------------
    y_cornisa = y_piso2 + alto2
    for lado in (-1, 1):
        partes.append(_caja(ancho + 2.4 * E, 1 * E, 1.6 * E, 0, y_cornisa - 0.6 * E,
                            lado * prof / 2, VERDE_MOLDU, "Wood", nombre=f"Cornisa_{lado:+d}"))
    # Esquineras verticales
    for sx in (-1, 1):
        for sz in (-1, 1):
            partes.append(_caja(1.6 * E, (alto1 + alto2) * E, 1.6 * E,
                                sx * ancho / 2, y_piso1 + (alto1 + alto2) / 2, sz * prof / 2,
                                VERDE_MOLDU, "Wood", nombre=f"Esquinera_{sx:+d}{sz:+d}"))

    # ---- Techo principal a dos aguas ------------------------------------------
    partes += _techo_dos_aguas(ancho, prof, 10 * E, y_cornisa,
                               TEJA, "WoodPlanks", alero=3 * E)

    # ---- Frontones triangulares (cierran los extremos del techo) --------------
    # Dos cuñas por lado, con la pendiente hacia el centro (z=0).
    # Frontones: el izquierdo azul y el derecho rosa (igual que las paredes)
    for sx, color in ((-1, AZUL), (1, ROSA)):
        for sz in (-1, 1):
            partes.append(_cuña(
                prof / 2, 10 * E, 1.4 * E,
                sx * (ancho / 2 + 1.6 * E), y_cornisa + 5 * E, sz * prof / 4,
                color, "SmoothPlastic", rot=(0, 90 * sx, 0),
                nombre=f"Fronton_{sx:+d}{sz:+d}",
            ))

    # ---- Torre octogonal con cúpula (la habitación de Carl) -------------------
    tx, tz = 18 * E, 8.5 * E            # esquina delantera derecha
    torre_r = 5.5 * E
    torre_alto = (alto1 + alto2 + 4) * E   # sobresale claramente del techo
    y_torre = y_piso1 + torre_alto / 2
    partes.append(_cilindro(torre_r * 2, torre_alto, torre_r * 2, tx, y_torre, tz,
                            CREMA, "SmoothPlastic", nombre="Torre"))
    # Cinturón de molduras de la torre
    for yy in (y_piso2, y_cornisa):
        partes.append(_cilindro((torre_r + 0.7) * 2, 1.0 * E, (torre_r + 0.7) * 2,
                                tx, yy, tz, VERDE_MOLDU, "Wood", nombre="Cinturon_torre"))
    # Cúpula de la torre (elipsoide achatado)
    partes.append(_esfera(torre_r * 1.9, tx, y_cornisa + 6.2 * E, tz,
                          TEJA, "WoodPlanks", nombre="Cupula_torre",
                          mesh_scale=[1, 0.75, 1]))
    # Punta de la torre (sobresale de la cúpula)
    partes.append(_esfera(1.8 * E, tx, y_cornisa + 11 * E, tz,
                          TEJA, "Metal", nombre="Punta_torre"))
    # Ventana redonda de la torre (la de Carl)
    partes.append(_cilindro(5.4 * E, 2.8 * E, 5.4 * E, tx, y_torre + 3 * E, tz + torre_r * 0.98,
                            VENTANA, "Glass", nombre="Ventana_torre", suave=False))
    partes.append(_cilindro(6.2 * E, 1.0 * E, 6.2 * E, tx, y_torre + 3 * E, tz + torre_r * 0.98,
                            VERDE_MOLDU, "Wood", nombre="Marco_ventana_torre", suave=False))

    # ---- Ventanas de la fachada (2 por planta) --------------------------------
    for planta, yy in enumerate((y_piso1 + 6 * E, y_piso2 + 6 * E)):
        for vx in (-8 * E, 8 * E):
            marco = _caja(5.8 * E, 7 * E, 0.5 * E, vx, yy, prof / 2 + 0.35 * E,
                          BLANCO_SUCIO, "Wood", nombre=f"Marco_v_{planta}_{int(vx):+d}")
            cristal = _caja(4.2 * E, 5.2 * E, 0.6 * E, vx, yy, prof / 2 + 0.4 * E,
                            VENTANA, "Glass", nombre=f"Cristal_v_{planta}_{int(vx):+d}")
            partes += [marco, cristal]
    # Ventanas laterales (una por lado, en la 2ª planta)
    for sx in (-1, 1):
        partes.append(_caja(0.5 * E, 6.6 * E, 5.8 * E, sx * ancho / 2 + 0.35 * E,
                            y_piso2 + 6 * E, 0, BLANCO_SUCIO, "Wood",
                            nombre=f"Marco_vlateral_{sx:+d}"))
        partes.append(_caja(0.6 * E, 4.8 * E, 4.2 * E, sx * ancho / 2 + 0.4 * E,
                            y_piso2 + 6 * E, 0, VENTANA, "Glass",
                            nombre=f"Cristal_vlateral_{sx:+d}"))

    # ---- Puerta principal ------------------------------------------------------
    partes.append(_caja(5.2 * E, 8.2 * E, 0.5 * E, 0, y_piso1 + 4.1 * E, prof / 2 + 0.35 * E,
                        BLANCO_SUCIO, "Wood", nombre="Marco_puerta"))
    partes.append(_caja(4.2 * E, 6.8 * E, 0.6 * E, 0, y_piso1 + 3.6 * E, prof / 2 + 0.4 * E,
                        PUERTA, "Wood", nombre="Puerta"))
    # Pomo amarillo
    partes.append(_esfera(0.6 * E, 1.7 * E, y_piso1 + 3.9 * E, prof / 2 + 0.75 * E,
                          MANIJA, "Metal", nombre="Pomo"))

    # ---- Porche de madera con columnas ----------------------------------------
    porche_x, porche_z = 20 * E, 7 * E
    px, pz = 2 * E, prof / 2 + porche_z / 2 - 0.5 * E
    partes.append(_caja(porche_x, 1.5 * E, porche_z, px, y_piso1 - 0.75 * E, pz,
                        MADERA_PORCHE, "Wood", nombre="Piso_porche"))
    # Escalones
    for i, (w, h) in enumerate(((porche_x * 0.8, 1.2 * E), (porche_x * 0.55, 1.2 * E))):
        partes.append(_caja(w, h, porche_z * 0.8, px, y_piso1 - 1.5 * E - i * 1.2 * E,
                            pz + (porche_z / 2) * (0.55 + 0.22 * i),
                            PIEDRA, "Concrete", nombre=f"Escalon_{i}"))
    # Columnas del porche
    for cx in (px - porche_x / 2 + 1.5 * E, px + porche_x / 2 - 1.5 * E):
        partes.append(_caja(1.1 * E, 11 * E, 1.1 * E, cx, y_piso1 + 6 * E, pz + porche_z / 2,
                            BLANCO_SUCIO, "Wood", nombre="Columna_porche"))
        partes.append(_caja(1.6 * E, 1.6 * E, 1.6 * E, cx, y_piso1 + 11.4 * E, pz + porche_z / 2,
                            BLANCO_SUCIO, "Wood", nombre="Capitel_porche"))
    # Techo del porche (losita inclinada hacia el frente)
    import math as _m
    partes.append(_caja(porche_x + 2 * E, 1 * E, 5.5 * E,
                        px, y_piso1 + 12.2 * E, pz + porche_z / 2 - 0.8 * E,
                        TEJA, "WoodPlanks", rot=(-20, 0, 0), nombre="Techo_porche"))
    # Baranda del porche (rieles + piquetes)
    y_riel = (y_piso1 - 0.75 * E) + 1.4 * E
    partes.append(_caja(porche_x, 0.5 * E, 0.5 * E, px, y_riel, pz + porche_z / 2 - 0.6 * E,
                        BLANCO_SUCIO, "Wood", nombre="Riel_porche"))
    partes.append(_caja(porche_x, 0.5 * E, 0.5 * E, px, y_riel + 2 * E, pz + porche_z / 2 - 0.6 * E,
                        BLANCO_SUCIO, "Wood", nombre="Riel_porche_2"))
    n_piquetes = int(porche_x / (2 * E))
    for i in range(n_piquetes + 1):
        cx = px - porche_x / 2 + i * 2 * E
        partes.append(_caja(0.5 * E, 3 * E, 0.5 * E, cx, y_riel + 1 * E, pz + porche_z / 2 - 0.6 * E,
                            BLANCO_SUCIO, "Wood", nombre=f"Piquete_{i}"))

    # ---- Chimenea de ladrillo (clavada en la pendiente del techo) --------------
    cx_ch, cz_ch = -12 * E, 8 * E
    y_ch = y_cornisa + 10 * E * (prof / 2 - cz_ch) / (prof / 2)
    partes.append(_caja(3.2 * E, 7 * E, 3.2 * E, cx_ch, y_ch + 3.2 * E, cz_ch,
                        LADRILLO, "Brick", nombre="Chimenea"))
    partes.append(_caja(3.8 * E, 1.4 * E, 3.8 * E, cx_ch, y_ch + 7.2 * E, cz_ch,
                        PIEDRA, "Concrete", nombre="Remate_chimenea"))

    # ---- Buhardilla (dormer) en el lado derecho del techo ----------------------
    dx_d, dz_d = 6 * E, 5.5 * E
    y_techo_d = y_cornisa + 10 * E * (prof / 2 - dz_d) / (prof / 2)
    partes.append(_caja(4.6 * E, 2.2 * E, 4.0 * E, dx_d, y_techo_d + 1.2 * E, dz_d,
                        CREMA, "SmoothPlastic", nombre="Buhardilla"))
    partes.append(_caja(2.8 * E, 2.4 * E, 0.4 * E, dx_d, y_techo_d + 1.2 * E,
                        dz_d + 2.05 * E, BLANCO_SUCIO, "Wood", nombre="Marco_buhardilla"))
    partes.append(_caja(2.0 * E, 1.6 * E, 0.5 * E, dx_d, y_techo_d + 1.2 * E,
                        dz_d + 2.1 * E, VENTANA, "Glass", nombre="Cristal_buhardilla"))
    partes += _techo_dos_aguas(5.4 * E, 4.6 * E, 1.5 * E, y_techo_d + 2.4 * E,
                               TEJA, "WoodPlanks", alero=0.9 * E)

    # ---- Habitación lateral (ampliación verde-azulada) -------------------------
    rx, rz = ancho / 2 + 4 * E, -5 * E
    partes.append(_caja(8 * E, 9 * E, 12 * E, rx, y_piso1 + 4.5 * E, rz,
                        VERDE_HABITACION, "SmoothPlastic", nombre="Habitacion_lateral"))
    partes.append(_caja(8.8 * E, 0.7 * E, 12.8 * E, rx, y_piso1 + 9.4 * E, rz,
                        TEJA, "WoodPlanks", nombre="Techo_habitacion"))
    partes.append(_caja(5.6 * E, 4.4 * E, 0.5 * E, rx, y_piso1 + 4.8 * E, rz + 6.25 * E,
                        BLANCO_SUCIO, "Wood", nombre="Marco_habitacion"))
    partes.append(_caja(4.2 * E, 3.0 * E, 0.6 * E, rx, y_piso1 + 4.8 * E, rz + 6.3 * E,
                        VENTANA, "Glass", nombre="Cristal_habitacion"))

    # ---- Valla de piquetes (frente + tramos laterales del porche) --------------
    valla_z = 23.7 * E
    for i in range(21):
        cx = -20 * E + i * 2 * E
        partes.append(_caja(0.5 * E, 3.4 * E, 0.5 * E, cx, 5.7 * E, valla_z,
                            BLANCO_SUCIO, "Wood", nombre=f"Valla_piquete_{i}"))
    for dz in (-0.3 * E, 0.3 * E):
        partes.append(_caja(40 * E, 0.5 * E, 0.4 * E, 0, 6.4 * E, valla_z + dz,
                            BLANCO_SUCIO, "Wood", nombre="Valla_riel"))
    # Tramos laterales delanteros (izquierdo y derecho)
    for sx in (-1, 1):
        z0, z1 = 13 * E, valla_z - 0.9 * E
        for i in range(int((z1 - z0) / (2 * E)) + 1):
            cz = z0 + i * 2 * E
            partes.append(_caja(0.5 * E, 3.4 * E, 0.5 * E, sx * 21.7 * E, 5.7 * E, cz,
                                BLANCO_SUCIO, "Wood", nombre=f"Valla_lat_{sx:+d}_{i}"))
        for ry in (5.9 * E, 7.0 * E):
            partes.append(_caja(0.4 * E, 0.5 * E, (z1 - z0) * E, sx * 21.7 * E, ry,
                                (z0 + z1) / 2, BLANCO_SUCIO, "Wood",
                                nombre=f"Valla_riel_lat_{sx:+d}"))

    # ---- Arbustos sobre el césped ----------------------------------------------
    for ax, az in ((-12 * E, prof / 2 - 1 * E), (13 * E, prof / 2 - 1 * E),
                   (18 * E, -6 * E)):
        partes.append(_esfera(4 * E, ax, y_piso1 + 1.0 * E, az, (62, 120, 62),
                              "LeafyGrass", nombre="Arbusto", mesh_scale=[1, 0.8, 1]))

    # ---- Los globos (opcional) --------------------------------------------------
    if globos:
        partes += _nube_globos(escala, semilla)

    return partes


def _nube_globos(escala: float = 1.0, semilla: int = 7, n: int = 110) -> List[Parte]:
    """Genera una nube de globos de colores sobre la casa (domo determinista)."""
    rng = random.Random(semilla)
    partes: List[Parte] = []
    E = escala
    centro_y = 60 * E
    radio = 20 * E
    for i in range(n):
        # Posición en un domo (solo la mitad superior de una esfera)
        theta = rng.uniform(0, 2 * 3.14159)
        phi = rng.uniform(0, 3.14159 / 2.2)   # hasta ~82° (domo achatado)
        r = radio * (0.55 + 0.45 * rng.random())
        px = r * 1.35 * _cos(theta) * _sin(phi)
        pz = r * 1.35 * _sin(theta) * _sin(phi)
        py = centro_y + r * _cos(phi) * 0.9
        d = (2.2 + 1.2 * rng.random()) * E
        color = PALETA_GLOBOS[i % len(PALETA_GLOBOS)]
        partes.append(_esfera(d, px, py, pz, color, "SmoothPlastic",
                              nombre=f"Globo_{i}"))
    # Cuerdas: hilos finos que bajan desde la nube hacia el techo y la chimenea
    rng2 = random.Random(semilla + 1)
    for i in range(14):
        dx = rng2.uniform(-10, 10) * E
        dz = rng2.uniform(-6, 8) * E
        partes.append(_cilindro(0.3 * E, 16 * E, 0.3 * E, dx, 50.5 * E, dz,
                                CUERDA, "Fabric", nombre=f"Cuerda_{i}",
                                suave=True))
    return partes


def _cos(a: float) -> float:
    import math
    return math.cos(a)


def _sin(a: float) -> float:
    import math
    return math.sin(a)


def _pata_plano_yx(x1, x2, y1, y2, grosor, color, material, nombre):
    """Losa con el eje largo en Y, inclinada en el plano Y-X: va de (x1, y1)
    a (x2, y2), centrada en z=0. La rotación rz alinea el eje Y con la
    dirección (dx, dy): rz = atan2(-dx, dy)."""
    dx, dy = x2 - x1, y2 - y1
    largo = math.hypot(dx, dy)
    rz = math.degrees(math.atan2(-dx, dy))
    return _caja(grosor, largo, grosor, (x1 + x2) / 2, (y1 + y2) / 2, 0,
                 color, material, rot=(0, 0, rz), nombre=nombre)


def _pata_plano_yz(z1, z2, y1, y2, grosor, color, material, nombre):
    """Losa con el eje largo en Y, inclinada en el plano Y-Z: va de (z1, y1)
    a (z2, y2), centrada en x=0. La rotación rx alinea el eje Y con la
    dirección (dz, dy): rx = atan2(dz, dy)."""
    dz, dy = z2 - z1, y2 - y1
    largo = math.hypot(dz, dy)
    rx = math.degrees(math.atan2(dz, dy))
    return _caja(grosor, largo, grosor, 0, (y1 + y2) / 2, (z1 + z2) / 2,
                 color, material, rot=(rx, 0, 0), nombre=nombre)


def torre_eiffel(escala: float = 1.0, **_) -> List[Parte]:
    """Torre Eiffel (París, 1889) — estructura de celosía de hierro forjado.

    DIMENSIONES REALES (fuente: datos oficiales de la Torre Eiffel):
      - Altura total: 330 m (300 m de torre + 24 m de antena).
      - Base: 125 × 125 m.
      - 1ª plataforma a 57 m (≈70 m de lado).
      - 2ª plataforma a 115 m (≈40 m de lado).
      - Cima a 300 m (plataforma superior de ~19 m).
      - Peso: ~10 100 t. Color oficial "marrón torre Eiffel" (3 tonos).

    Diseño procedural: 4 patas convergentes (2 planos en cruz), 3 tramos
    cada una, 3 plataformas, linterna y antena. A E=1 el modelo es a escala
    real (1 stud ≈ 0,28 m); usa el ajuste a solar para escalarlo.
    """
    S = 1.0 / catalogo.STUD_A_METRO   # studs por metro
    E = escala
    hierro = (126, 98, 74)
    mat = "CorrodedMetal"
    g = 2.2 * E * S                   # grosor de las losas (m → studs)
    partes: List[Parte] = []

    # --- Patas: 2 planos en cruz (X e Z), 3 tramos que convergen ------------
    # (y1 → y2, radio1 → radio2 en metros: las patas se juntan al subir)
    tramos = [
        (0.0, 57.0, 62.5, 35.0),     # base → 1ª plataforma
        (57.0, 115.0, 35.0, 20.0),   # 1ª → 2ª plataforma
        (115.0, 300.0, 20.0, 3.0),   # 2ª → cima
    ]
    for i, (y1, y2, r1, r2) in enumerate(tramos):
        for sx in (-1, 1):
            partes.append(_pata_plano_yx(
                sx * r1 * S * E, sx * r2 * S * E, y1 * S * E, y2 * S * E,
                g, hierro, mat, nombre=f"PataX_t{i}_{sx:+d}"))
        for sz in (-1, 1):
            partes.append(_pata_plano_yz(
                sz * r1 * S * E, sz * r2 * S * E, y1 * S * E, y2 * S * E,
                g, hierro, mat, nombre=f"PataZ_t{i}_{sz:+d}"))

    # --- Plataformas (1ª a 57 m, 2ª a 115 m, superior a 300 m) ---------------
    for y_plat, lado in ((57.0, 70.0), (115.0, 40.0), (300.0, 19.0)):
        partes.append(_caja(lado * S * E, 2.0 * S * E, lado * S * E,
                            0, y_plat * S * E, 0,
                            hierro, mat, nombre=f"Plataforma_{int(y_plat)}"))

    # --- Linterna de la cima y antena -----------------------------------------
    partes.append(_cilindro(8.0 * S * E, 6.0 * S * E, 8.0 * S * E,
                            0, 303.0 * S * E, 0,
                            hierro, mat, nombre="Linterna", suave=False))
    partes.append(_cilindro(3.0 * S * E, 26.0 * S * E, 3.0 * S * E,
                            0, 319.0 * S * E, 0,
                            hierro, mat, nombre="Antena", suave=False))
    return partes


# --- Otras estructuras de ejemplo -------------------------------------------

def casa_victoriana(escala: float = 1.0, globos: bool = False, **_) -> List[Parte]:
    """Una casa victoriana genérica (variante sin los globos de Up)."""
    return casa_up(escala, globos=False)


def casa_simple(escala: float = 1.0, **_) -> List[Parte]:
    """Una casita básica: caja + techo a dos aguas + puerta + ventanas."""
    E = escala
    partes = []
    ancho, prof, alto = 24 * E, 18 * E, 12 * E
    y = 6 * E
    partes.append(_caja(ancho, alto, prof, 0, y, 0, CREMA, "SmoothPlastic", nombre="Casa"))
    partes.append(_caja(ancho, 1.2 * E, prof + 1.2 * E, 0, 0.6 * E, 0,
                        PIEDRA, "Concrete", nombre="Cimientos"))
    partes += _techo_dos_aguas(ancho, prof, 6 * E, alto, MARRON_OSCURO,                                "WoodPlanks", alero=1.5 * E)
    partes.append(_caja(4 * E, 7 * E, 0.6 * E, 0, 3.5 * E, prof / 2 + 0.3 * E,
                        PUERTA, "Wood", nombre="Puerta"))
    for vx in (-6 * E, 6 * E):
        partes.append(_caja(4 * E, 5 * E, 0.5 * E, vx, 5.5 * E, prof / 2 + 0.3 * E,
                            VENTANA, "Glass", nombre="Ventana"))
    partes.append(_caja(2.5 * E, 5 * E, 2.5 * E, -7 * E, 15 * E, -4 * E,
                        LADRILLO, "Brick", nombre="Chimenea"))
    return partes


def arbol(escala: float = 1.0, **_) -> List[Parte]:
    """Un árbol: tronco cilíndrico + copa de esferas."""
    E = escala
    partes = []
    partes.append(_cilindro(1.6 * E, 10 * E, 1.6 * E, 0, 5 * E, 0,
                            (110, 74, 46), "Wood", nombre="Tronco"))
    for dx, dy, dz, d in ((0, 13, 0, 7), (-2.5, 11.5, 1.5, 4.5), (2.5, 11.5, -1.5, 4.5),
                          (-1.5, 15, -2, 4), (2, 14.5, 2.5, 4.5), (0, 16.5, 0, 4)):
        partes.append(_esfera(d * E, dx * E, dy * E, dz * E, (52, 118, 52),
                              "LeafyGrass", nombre="Copa",
                              mesh_scale=[1, 0.9, 1]))
    return partes


def rascacielos(escala: float = 1.0, pisos: int = 20, **_) -> List[Parte]:
    """Un rascacielos simple: núcleo, bandas de ventanas y antena."""
    E = escala
    alto = pisos * 4 * E
    ancho = 12 * E
    partes = []
    partes.append(_caja(ancho, alto, ancho, 0, alto / 2, 0,
                        (120, 140, 160), "SmoothPlastic", nombre="Edificio"))
    # Bandas de cristal cada 2 pisos
    for i in range(1, pisos, 2):
        y = i * 4 * E + 2 * E
        partes.append(_caja(ancho + 0.4 * E, 1.2 * E, ancho + 0.4 * E, 0, y, 0,
                            (70, 110, 150), "Glass", nombre=f"Banda_{i}"))
    partes.append(_cilindro(1 * E, 8 * E, 1 * E, 0, alto + 5 * E, 0,
                            (180, 40, 40), "Neon", nombre="Antena"))
    partes.append(_esfera(2.5 * E, 0, alto + 10 * E, 0, (255, 60, 60), "Neon",
                          nombre="Luz_antena"))
    return partes


# ===========================================================================
# Casa UP v5 — diseñada pieza a pieza con la referencia real (15 ago 2026)
# ===========================================================================
def casa_up(escala: float = 1.0, globos: bool = True, semilla: int = 7) -> List[Parte]:
    """Casa de Carl y Ellie (Up, Pixar 2009), rediseñada siguiendo la foto de
    referencia del modelo a escala 1:48 (THEMODELMAKER): cuerpo casi cuadrado
    (planta real ~8,6 m = 31 studs), fachada crema abajo y azul/rosa arriba,
    pórtico con columnas y baranda, torre con cúpula en la esquina delantera
    derecha, buhardilla (dormer), chimenea de ladrillo, techo azul marino a
    dos aguas con gabletes y la nube de globos con sus cuerdas."""
    E = escala
    p: List[Parte] = []
    rnd = random.Random(semilla)

    # ---- Dimensiones (planta ~8,6 m reales = 31 studs) -------------------
    A = 31 * E                 # ancho total (X)
    F = 22 * E                 # fondo (Z)
    X1, X2 = -A / 2, A / 2
    ZF = F / 2                 # frente (+Z)
    ZT = -F / 2                # trasero
    PB = 10 * E                # altura planta baja (y 2..12)
    PS = 9 * E                 # altura piso superior (y 12..21)
    g = 2.0 * E                # grosor de pared

    def caja(x, y, z, px, py, pz, color, mat="Plastic", rot=(0, 0, 0), nom=""):
        p.append(_caja(x, y, z, px, py, pz, color, mat, rot=rot, nombre=nom))

    # ---- Cimientos y base ---------------------------------------------------
    caja(A + 2 * E, 2 * E, F + 2 * E, 0, 1 * E, 0, PIEDRA, "Concrete", nom="Cimientos")
    caja(A, 1.2 * E, F, 0, 2.6 * E, 0, CREMA, "SmoothPlastic", nom="Zocalo")

    # ---- Paredes planta baja (crema) ---------------------------------------
    caja(10.5 * E, PB, g, X1 + 5.25 * E, 2 + PB / 2, ZF - g / 2, CREMA,
         "SmoothPlastic", nom="Frente_PB_izq")
    caja(0.5 * E, PB, g, -4.75 * E, 2 + PB / 2, ZF - g / 2, CREMA,
         "SmoothPlastic", nom="Frente_PB_puerta_izq")
    caja(2 * E, PB, g, 0.5 * E + 1 * E, 2 + PB / 2, ZF - g / 2, CREMA,
         "SmoothPlastic", nom="Frente_PB_puerta_der")
    caja(13.5 * E, PB, g, (0.5 + 13.5 / 2) * E, 2 + PB / 2, ZF - g / 2, CREMA,
         "SmoothPlastic", nom="Frente_PB_der")
    caja(A, PB, g, 0, 2 + PB / 2, ZT + g / 2, CREMA, "SmoothPlastic", nom="Trasera_PB")
    caja(g, PB, F, X1 + g / 2, 2 + PB / 2, 0, CREMA, "SmoothPlastic", nom="Lateral_PB_izq")
    caja(g, PB, F, X2 - g / 2, 2 + PB / 2, 0, CREMA, "SmoothPlastic", nom="Lateral_PB_der")

    # ---- Piso superior: azul (izquierda) y rosa (derecha) -------------------
    caja(14 * E, PS, g, X1 + 7 * E, 12 + PS / 2, ZF - g / 2, AZUL,
         "SmoothPlastic", nom="Frente_PS_azul")
    caja(17 * E, PS, g, 7 * E, 12 + PS / 2, ZF - g / 2, ROSA,
         "SmoothPlastic", nom="Frente_PS_rosa")
    caja(14 * E, PS, g, X1 + 7 * E, 12 + PS / 2, ZT + g / 2, AZUL,
         "SmoothPlastic", nom="Trasera_PS_azul")
    caja(17 * E, PS, g, 7 * E, 12 + PS / 2, ZT + g / 2, ROSA,
         "SmoothPlastic", nom="Trasera_PS_rosa")
    caja(g, PS, F, X1 + g / 2, 12 + PS / 2, 0, AZUL, "SmoothPlastic", nom="Lateral_PS_izq")
    caja(g, PS, F, X2 - g / 2, 12 + PS / 2, 0, ROSA, "SmoothPlastic", nom="Lateral_PS_der")

    # ---- Molduras verdes (esquineros, entreplantas, línea de techo) ----------
    for cx, cz in ((X1 + g / 2, ZF - g / 2), (X2 - g / 2, ZF - g / 2),
                   (X1 + g / 2, ZT + g / 2), (X2 - g / 2, ZT + g / 2)):
        caja(1.1 * E, (PB + PS) * E, 1.1 * E, cx, 2 + (PB + PS) / 2, cz,
             VERDE_MOLDU, "Wood", nom="Esquinero_verde")
    caja(A + 1.2 * E, 0.9 * E, g + 1.2 * E, 0, 12 * E, ZF - g / 2, VERDE_MOLDU,
         "Wood", nom="Banda_entreplantas_frente")
    caja(A + 1.2 * E, 0.9 * E, g + 1.2 * E, 0, 12 * E, ZT + g / 2, VERDE_MOLDU,
         "Wood", nom="Banda_entreplantas_tras")
    caja(A + 1.2 * E, 0.9 * E, g + 1.2 * E, 0, 21 * E, ZF - g / 2, VERDE_MOLDU,
         "Wood", nom="Rincon_techo_frente")
    caja(A + 1.2 * E, 0.9 * E, g + 1.2 * E, 0, 21 * E, ZT + g / 2, VERDE_MOLDU,
         "Wood", nom="Rincon_techo_tras")

    # ---- Puerta de entrada (frente, centro-izquierda) -----------------------
    caja(3.2 * E, 7 * E, 0.6 * E, -3 * E, 2.2 + 3.5 * E, ZF - g / 2 - 0.1 * E,
         PUERTA, "Wood", nom="Puerta")
    caja(4 * E, 7.4 * E, 0.5 * E, -3 * E, 2.2 + 3.7 * E, ZF - g / 2 + 0.15 * E,
         BLANCO_SUCIO, "Wood", nom="Marco_puerta")
    p.append(_esfera(0.5 * E, -1.5 * E, 5.3 * E, ZF - g / 2 - 0.35 * E, MANIJA,
                     nombre="Pomo_puerta"))
    caja(5.2 * E, 0.6 * E, 1.2 * E, -3 * E, 2.9 * E, ZF - g / 2 - 0.5 * E,
         VERDE_MOLDU, "Wood", nom="Dintel_puerta")

    # ---- Ventanas (marcos blancos + cristal claro) ---------------------------
    def ventana(cx, cy, cz, ancho=3.2 * E, alto=3.4 * E):
        caja(ancho + 0.8 * E, alto + 0.8 * E, 0.5 * E, cx, cy, cz,
             BLANCO_SUCIO, "Wood", nom="Marco_ventana")
        caja(ancho, alto, 0.35 * E, cx, cy, cz, VENTANA, "Glass", nom="Cristal_ventana")

    ventana(-11 * E, 2.2 + 4.5 * E, ZF - g / 2 - 0.15 * E)   # PB frente izq
    ventana(3 * E, 2.2 + 4.5 * E, ZF - g / 2 - 0.15 * E)      # PB frente der
    ventana(0, 2.2 + 4.5 * E, ZT + g / 2 + 0.15 * E)          # PB trasera
    ventana(X2 - g / 2 + 0.15 * E, 2.2 + 4.5 * E, 0)          # PB lateral der
    ventana(X1 + g / 2 - 0.15 * E, 2.2 + 4.5 * E, -4 * E)     # PB lateral izq
    ventana(-8 * E, 12 + 4.5 * E, ZF - g / 2 - 0.15 * E)      # PS azul
    ventana(2.5 * E, 12 + 4.5 * E, ZF - g / 2 - 0.15 * E)     # PS rosa
    ventana(-6 * E, 12 + 4.5 * E, ZT + g / 2 + 0.15 * E)      # PS trasera

    # ---- Pórtico delantero (columnas, baranda, escalones) --------------------
    caja(9 * E, 0.5 * E, 3.6 * E, -6 * E, 0.35 * E, ZF + 2.5 * E, MADERA_PORCHE,
         "WoodPlanks", nom="Piso_porche")
    caja(3 * E, 0.4 * E, 1.2 * E, -8.2 * E, 0.6 * E, ZF + 4.5 * E, MADERA_PORCHE,
         "WoodPlanks", nom="Escalon_1")
    caja(2.6 * E, 0.4 * E, 1.0 * E, -8.2 * E, 0.95 * E, ZF + 5.3 * E, MADERA_PORCHE,
         "WoodPlanks", nom="Escalon_2")
    for cx in (-9 * E, -6 * E, -3 * E):
        p.append(_cilindro(0.9 * E, 10.4 * E, 0.9 * E, cx, 0.6 + 5.2 * E,
                           ZF + 2.5 * E, BLANCO_SUCIO, "Wood", nombre="Columna_porche"))
    caja(9.5 * E, 0.8 * E, 4 * E, -6 * E, 11.8 * E, ZF + 2.4 * E, VERDE_MOLDU,
         "WoodPlanks", nom="Techo_porche")
    caja(9.5 * E, 0.5 * E, 3.6 * E, -6 * E, 11.4 * E, ZF + 2.4 * E, BLANCO_SUCIO,
         "WoodPlanks", nom="Forro_techo_porche")
    # Baranda del porche (rieles + piquetes)
    caja(9.6 * E, 0.4 * E, 0.25 * E, -6 * E, 1.0 * E, ZF + 4.4 * E, BLANCO_SUCIO,
         "Wood", nom="Riel_porche")
    caja(9.6 * E, 0.4 * E, 0.25 * E, -6 * E, 1.8 * E, ZF + 4.4 * E, BLANCO_SUCIO,
         "Wood", nom="Riel_porche_2")
    for i in range(7):
        caja(0.3 * E, 1.3 * E, 0.25 * E, -10.4 * E + i * 1.5 * E, 1.0 * E,
             ZF + 4.4 * E, BLANCO_SUCIO, "Wood", nom=f"Piquete_porche_{i}")

    # ---- Torre de Carl (esquina delantera derecha, con cúpula) ---------------
    TX, TZ, TA = 9.75 * E, 7.5 * E, 10.5 * E     # centro y ancho
    caja(TA, 27 * E, 1.6 * E, TX, 2 + 13.5 * E, 13.2 * E, ROSA,
         "SmoothPlastic", nom="Torre_frente")
    caja(TA, 27 * E, 1.6 * E, TX, 2 + 13.5 * E, 1.8 * E, ROSA,
         "SmoothPlastic", nom="Torre_tras")
    caja(1.6 * E, 27 * E, TA, TX + 5.25 * E, 2 + 13.5 * E, TZ, ROSA,
         "SmoothPlastic", nom="Torre_lat")
    caja(1.6 * E, 27 * E, TA, TX - 5.25 * E, 2 + 13.5 * E, TZ, ROSA,
         "SmoothPlastic", nom="Torre_lat2")
    ventana(TX - 2.5 * E, 2.2 + 13 * E, 13.7 * E, ancho=2.6 * E, alto=5 * E)  # torre
    ventana(TX + 2.5 * E, 2.2 + 13 * E, 13.7 * E, ancho=2.6 * E, alto=5 * E)
    ventana(TX, 2.2 + 13 * E, 7.9 * E, ancho=2.6 * E, alto=5 * E)              # torre lat
    caja(TA + 1.5 * E, 1.6 * E, TA + 1.5 * E, TX, 29 * E, TZ, BLANCO_SUCIO,
         "Wood", nom="Cornisa_torre")
    # Cúpula (esfera achatada) + remate
    p.append(_esfera(7 * E, TX, 31.4 * E, TZ, TEJA, "WoodPlanks",
                     nombre="Cupula_torre", mesh_scale=[1, 0.75, 1]))
    p.append(_cilindro(0.5 * E, 2.6 * E, 0.5 * E, TX, 33.5 * E, TZ,
                       MANIJA, "Neon", nombre="Pinaculo_torre"))
    p.append(_esfera(1.1 * E, TX, 35.2 * E, TZ, MANIJA, nombre="Remate_torre"))

    # ---- Techo principal a dos aguas (azul marino, cumbrera en X) ------------
    p.extend(_techo_dos_aguas(A, F, 8 * E, 21 * E, TEJA, "WoodPlanks"))

    # ---- Buhardilla (dormer) en el techo delantero ---------------------------
    caja(5.5 * E, 4 * E, 4.6 * E, -1.25 * E, 23.2 * E, 8 * E, CREMA,
         "SmoothPlastic", nom="Dormer_cuerpo")
    ventana(-1.25 * E, 24.2 * E, 10.4 * E, ancho=2.8 * E, alto=2.6 * E)
    p.extend(_techo_dos_aguas(5.5 * E, 4.6 * E, 2.2 * E, 25.4 * E, TEJA,
                              "WoodPlanks", alero=1.2))

    # ---- Chimenea de ladrillo (izquierda, sobre el techo) --------------------
    caja(2.8 * E, 10 * E, 2.8 * E, -10.5 * E, 24 + 5 * E, 5 * E, LADRILLO,
         "Brick", nom="Chimenea")
    caja(3.8 * E, 1.2 * E, 3.8 * E, -10.5 * E, 34.6 * E, 5 * E, PIEDRA,
         "Concrete", nom="Sombrerete_chimenea")

    # ---- Césped y valla de piquetes -------------------------------------------
    caja(A + 12 * E, 0.4 * E, F + 12 * E, 0, 0.2 * E, 0, CESPE, "Grass", nom="Cesped")
    VZ = ZF + 6 * E
    for i in range(18):
        caja(0.5 * E, 2 * E, 0.5 * E, -20.5 * E + i * 2.4 * E, 1 * E, VZ,
             BLANCO_SUCIO, "Wood", nom=f"Piquete_valla_{i}")
    for dy in (0.6 * E, 1.4 * E):
        caja(42 * E, 0.4 * E, 0.4 * E, 0, dy, VZ, BLANCO_SUCIO, "Wood", nom="Riel_valla")
    caja(0.4 * E, 2.2 * E, 12 * E, -20.5 * E, 1.1 * E, ZF + 0.5 * E, BLANCO_SUCIO,
         "Wood", nom="Valla_lateral_izq")
    caja(0.4 * E, 2.2 * E, 12 * E, 20.5 * E, 1.1 * E, ZF + 0.5 * E, BLANCO_SUCIO,
         "Wood", nom="Valla_lateral_der")

    # ---- Globos y cuerdas (opcional) ------------------------------------------
    if globos:
        nube_y0, nube_y1 = 38 * E, 66 * E
        for i in range(85):
            rx = rnd.uniform(-15, 15) * E
            ry = rnd.uniform(nube_y0, nube_y1)
            rz = rnd.uniform(-9, 9) * E
            d = rnd.uniform(2.6, 4.4) * E
            col = rnd.choice(PALETA_GLOBOS)
            p.append(_esfera(d, rx, ry, rz, col, "Plastic", nombre=f"Globo_{i}"))
        for i, (ax, az) in enumerate(((-11, 5), (-6, 8), (-1, 9), (4, 10),
                                      (10, 11), (0, -4), (8, -3), (13, 6))):
            p.append(_cilindro(0.18 * E, 9 * E, 0.18 * E, ax * E, 33.5 * E,
                               az * E, CUERDA, "Plastic", nombre=f"Cuerda_{i}"))

    return p


# ===========================================================================
# Registro de generadores
# ===========================================================================

GENERADORES: Dict[str, Callable[..., List[Parte]]] = {
    "casa_up": casa_up,
    "casa_victoriana": casa_victoriana,
    "casa_simple": casa_simple,
    "arbol": arbol,
    "rascacielos": rascacielos,
    "torre_eiffel": torre_eiffel,
}
