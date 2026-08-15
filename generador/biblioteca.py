"""
Biblioteca de estructuras conocidas.

Cada entrada asocia un generador del motor con:
  - sinonimos   : cómo la puede nombrar el usuario (español / inglés)
  - referencia  : qué es en la realidad (investigación que respalda el diseño)
  - parametros  : opciones extra que el generador acepta (ej. globos, pisos)
"""
from __future__ import annotations

from typing import Dict, List
from . import motor

ESTRUCTURAS: Dict[str, dict] = {
    "casa_up": {
        "nombre": "Casa UP (Pixar)",
        "sinonimos": [
            "casa up", "casa de up", "la casa de up", "up house", "casa de carl",
            "casa de carl fredricksen", "casa de carl y ellie", "casa voladora",
            "casa de la pelicula up", "casa de la pelicula de up", "casa con globos",
            "casa del abuelo carl", "casa de los globos", "up",
        ],
        "referencia": (
            "Casa victoriana estilo Queen Anne de la película 'Up' (Pixar, 2009). "
            "Diseñada por el artista de Pixar Don Shank e inspirada en una casa "
            "victoriana real de la calle Sixth Street en Berkeley, California. "
            "Dimensiones reales (modelo 1:48 de THEMODELMAKER con planos CAD de "
            "Don Shank): planta casi cuadrada ~8,6 × 8,6 m y ~10 m hasta la "
            "chimenea. Elementos clave: cuerpo de dos plantas casi cuadrado con "
            "fachada multicolor (crema abajo, azul y rosa arriba) y molduras "
            "verdes, torre con cúpula en la esquina delantera derecha (la "
            "habitación de Carl), buhardilla (dormer) en el techo, porche de "
            "madera con columnas y baranda, valla de piquetes blancos, chimenea "
            "de ladrillo, techo a dos aguas azul marino y la nube de globos de "
            "helio con sus cuerdas."
        ),
        "parametros": {"globos": "incluir la nube de globos (True/False)",
                       "escala": "factor de escala (1.0 = tamaño estándar)"},
    },
    "casa_victoriana": {
        "nombre": "Casa victoriana genérica",
        "sinonimos": [
            "casa victoriana", "casa queen anne", "casa antigua", "casa clasica",
            "victorian house", "queen anne house", "casa de epoca",
        ],
        "referencia": (
            "Casa victoriana estilo Queen Anne genérica: dos plantas, torre con "
            "cúpula, porche de madera y valla de piquetes. Este estilo, popular en "
            "EE. UU. entre 1880 y 1910, es la base arquitectónica de la casa de Up."
        ),
        "parametros": {"escala": "factor de escala"},
    },
    "casa_simple": {
        "nombre": "Casa simple",
        "sinonimos": [
            "casa simple", "casa basica", "casa sencilla", "casita",
            "simple house", "small house", "casa pequeña", "casa",
        ],
        "referencia": "Casita básica de dos aguas: cimientos de piedra, paredes "
                      "crema, techo marrón, puerta y ventanas.",
        "parametros": {"escala": "factor de escala"},
    },
    "arbol": {
        "nombre": "Árbol",
        "sinonimos": [
            "arbol", "un arbol", "arbol grande", "roble", "tree", "oak tree",
            "arbol de hoja caduca",
        ],
        "referencia": "Árbol de copa redondeada: tronco cilíndrico de madera y "
                      "copa compuesta por varias esferas de follaje verde.",
        "parametros": {"escala": "factor de escala"},
    },
    "torre_eiffel": {
        "nombre": "Torre Eiffel (París)",
        "sinonimos": [
            "torre eiffel", "la torre eiffel", "torre de paris",
            "la torre de paris", "eiffel tower", "la torre eiffel de paris",
            "torre metalica de paris",
        ],
        "referencia": (
            "Torre de celosía de hierro forjado de 330 m (300 m de torre + "
            "24 m de antena), construida en 1889 por Gustave Eiffel para la "
            "Exposición Universal de París. Base de 125 × 125 m, 1ª plataforma "
            "a 57 m (≈70 m de lado), 2ª a 115 m (≈40 m), cima a 300 m; peso "
            "~10 100 toneladas; pintada de 'marrón torre Eiffel' en tres tonos. "
            "Diseño procedural simplificado: 4 patas convergentes en cruz, 3 "
            "plataformas, linterna y antena. A E=1 el modelo es a escala real "
            "(1 stud ≈ 0,28 m); pídela 'en un solar de X por Y metros' para "
            "escalarla."
        ),
        "parametros": {"escala": "E=1 = tamaño real en studs (~330 m de alto)"},
    },
    "rascacielos": {
        "nombre": "Rascacielos",
        "sinonimos": [
            "rascacielos", "edificio alto", "torre de oficinas", "skyscraper",
            "edificio", "torre moderna", "oficinas",
        ],
        "referencia": "Rascacielos simple de núcleo azulado con bandas de cristal "
                      "cada dos pisos y antena roja con luz intermitente en la cima.",
        "parametros": {"pisos": "número de pisos (por defecto 20)",
                       "escala": "factor de escala"},
    },
}

# Índice sinónimo -> clave
_SINONIMO_A_CLAVE: Dict[str, str] = {}
for _clave, _info in ESTRUCTURAS.items():
    for _s in _info["sinonimos"]:
        _SINONIMO_A_CLAVE[_s] = _clave


def normalizar(texto: str) -> str:
    """Minúsculas y sin acentos para comparar sin fricciones."""
    import unicodedata
    texto = texto.lower().strip()
    texto = "".join(
        c for c in unicodedata.normalize("NFD", texto)
        if unicodedata.category(c) != "Mn"
    )
    return texto


def buscar(texto: str) -> List[str]:
    """Devuelve las claves de estructuras que coinciden con el texto."""
    t = normalizar(texto)
    coincidencias = []
    # 1) Coincidencia exacta de sinónimo
    for sinonimo, clave in _SINONIMO_A_CLAVE.items():
        if sinonimo in t:
            if clave not in coincidencias:
                coincidencias.append(clave)
    # 2) Coincidencia parcial de nombre
    for clave, info in ESTRUCTURAS.items():
        base = normalizar(info["nombre"])
        if base in t and clave not in coincidencias:
            coincidencias.append(clave)
    return coincidencias


def listar() -> List[str]:
    return list(ESTRUCTURAS.keys())
