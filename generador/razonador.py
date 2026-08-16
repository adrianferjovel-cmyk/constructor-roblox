"""
Razonador: convierte una petición en lenguaje natural en un Modelo (blueprint).

Flujo:
  1. Normaliza el texto (minúsculas, sin acentos).
  2. Busca en la biblioteca de estructuras conocidas (por sinónimos).
  3. Extrae parámetros: escala, globos, pisos, color base.
  4. Llama al generador y construye el Modelo con la explicación del
     razonamiento (qué identificó y por qué).
"""
from __future__ import annotations

import re
from typing import List, Optional, Tuple

from .biblioteca import ESTRUCTURAS, buscar, listar, normalizar
from .blueprint import Modelo
from . import catalogo, libreria, motor


class NoEncontrada(Exception):
    """La petición no coincide con ninguna estructura conocida."""


def _extraer_numero(texto: str) -> Optional[float]:
    """Extrae el primer número del texto (para escala / pisos)."""
    m = re.search(r"(\d+(?:[.,]\d+)?)", texto)
    if not m:
        return None
    return float(m.group(1).replace(",", "."))


def _extraer_escala(texto: str, base: float = 1.0) -> float:
    """Detecta escalas: 'escala 2', 'el doble', '3 veces más grande', etc."""
    t = texto
    m = re.search(r"escala\s+(\d+(?:[.,]\d+)?)", t)
    if m:
        return float(m.group(1).replace(",", "."))
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:veces|x)\s*(?:mas\s*)?grande", t)
    if m:
        return float(m.group(1).replace(",", "."))
    if "doble" in t or "dos veces" in t or "el doble" in t:
        return base * 2
    if "triple" in t or "tres veces" in t:
        return base * 3
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*%", t)
    if m:
        return float(m.group(1).replace(",", ".")) / 100.0
    return base


def _tiene(texto: str, palabras) -> bool:
    return any(p in texto for p in palabras)


# Frases que indican REPLICAR una estructura desde la biblioteca
_FRASES_REPLICA = [
    "replica", "repite", "repeti", "clona", "clon", "copia", "copiame",
    "duplicame", "otra vez", "de nuevo", "vuelve a hacer", "igual que",
    "hazme otra", "haz otra", "lo mismo", "como la anterior",
    "como el anterior", "otra mas", "repitela", "repitelo", "replicame",
]

# Frases que indican una VARIANTE (parecida pero distinta)
_FRASES_VARIANTE = [
    "parecido", "parecida", "similar", "semejante", "variante",
    "variacion", "otra version", "algo como",
]

# Cambios estructurales que obligan a usar el motor (no la biblioteca)
_FRASES_CAMBIO_ESTRUCTURAL = [
    "sin globos", "sin globo", "no globos", "con globos", "mas globos",
    "menos globos", "con la nube", "sin la nube", "pisos",
]


_SOLAR_RE = re.compile(
    r"(?:solar|terreno|espacio|parcela|medida|mida)\s*(?:de\s*)?"
    r"(\d+(?:[.,]\d+)?)\s*(?:x|por)\s*(\d+(?:[.,]\d+)?)\s*m(?:etros)?"
)


def _ajustar_a_solar(texto: str, partes, razonamiento: List[str]):
    """Si el texto pide un solar en metros, recalcula la escala para que el
    modelo (medido con bounding_box) quepa milimétricamente en él."""
    m = _SOLAR_RE.search(texto)
    if not m:
        return partes
    try:
        largo = float(m.group(1).replace(",", "."))
        ancho = float(m.group(2).replace(",", "."))
    except ValueError:
        return partes
    if largo <= 0 or ancho <= 0:
        return partes
    bx, _, bz = catalogo.bounding_box(partes)
    factor = catalogo.escala_para_solar(bx, bz, largo, ancho)
    partes = catalogo.reescalar(partes, factor)
    razonamiento.append(
        f"Solar: ajusté la escala para que encaje en {largo:.2f} × {ancho:.2f} m "
        f"(factor {factor:.3f}x)."
    )
    return partes


def interpretar(texto: str) -> Tuple[Modelo, str]:
    """Devuelve (Modelo, nombre_estructura). Lanza NoEncontrada si no coincide."""
    t = normalizar(texto)
    claves = buscar(texto)

    if not claves:
        disponibles = ", ".join(f"'{e['nombre']}'" for e in ESTRUCTURAS.values())
        raise NoEncontrada(
            f"No reconocí ninguna estructura en: '{texto.strip()}'. "
            f"Por ahora sé construir: {disponibles}. "
            f"También puedes pedir variaciones (escala, colores, sin globos...)."
        )

    clave = claves[0]
    info = ESTRUCTURAS[clave]
    generador = motor.GENERADORES[clave]

    # ---- Parámetros -------------------------------------------------------
    escala = _extraer_escala(texto)
    kwargs: dict = {"escala": escala}

    # ---- ¿RÉPLICA o VARIANTE desde la biblioteca de estructuras/? --------
    modo_replica = _tiene(t, _FRASES_REPLICA)
    modo_variante = _tiene(t, _FRASES_VARIANTE)
    cambio_estructural = _tiene(t, _FRASES_CAMBIO_ESTRUCTURAL)
    if (modo_replica or modo_variante) and not cambio_estructural \
            and libreria.existe(clave):
        if modo_replica:
            modelo = libreria.replicar(clave, escala=escala)
        else:
            modelo = libreria.variar(clave, escala=escala)
        partes = _ajustar_a_solar(t, modelo.parts, modelo.razonamiento)
        modelo.parts = partes
        modelo.razonamiento.append(
            f"Diseño: {len(partes)} piezas tomadas de la biblioteca."
        )
        return modelo, clave

    if "globos" in info.get("parametros", {}):
        if _tiene(t, ["sin globos", "sin globo", "no globos", "sin los globos",
                      "sin la nube", "sin nube", "no voladora", "sin volar"]):
            kwargs["globos"] = False
        else:
            kwargs["globos"] = True

    if "pisos" in info.get("parametros", {}):
        n = _extraer_numero(texto)
        if n and 3 <= n <= 200:
            kwargs["pisos"] = int(n)

    # ---- Razonamiento (qué hizo el programa) --------------------------------
    razonamiento = [
        f"Identifiqué: {info['nombre']} (de tu frase '{texto.strip()}').",
        f"Referencia real: {info['referencia']}",
    ]
    if "globos" in kwargs:
        razonamiento.append(
            "Globos: " + ("SÍ, incluí la nube de globos de colores." if kwargs["globos"]
                          else "no, los omití como pediste.")
        )

    # ---- Generar ----------------------------------------------------------
    partes = generador(**kwargs)
    partes = _ajustar_a_solar(t, partes, razonamiento)
    razonamiento.append(
        f"Diseño: {len(partes)} piezas construidas proceduralmente."
    )
    if _SOLAR_RE.search(t):
        pass  # el ajuste a solar ya añadió su propia línea
    else:
        razonamiento.append(f"Escala aplicada: {escala:.2f}x.")

    nombre_modelo = f"{info['nombre']} (esc. {escala:.2f})"
    return Modelo(modelName=nombre_modelo, parts=partes,
                  razonamiento=razonamiento), clave
