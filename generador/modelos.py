"""
Importación de MODELOS 3D REALES a Roblox (la vía FIEL).

Lección del proyecto: reconstruir estructuras a mano con piezas (aunque sea
desde planos) NUNCA llega a la fidelidad de un modelo real esculpido por un
artista. La solución real que usa la comunidad de Roblox es:

  1. Conseguir el modelo 3D real de la estructura (gratis en Sketchfab /
     Printables / etc., o generado con IA imagen→3D como Meshy).
  2. Subirlo a Roblox con la API oficial Open Cloud Assets
     (POST https://apis.roblox.com/assets/v1/assets) → devuelve un assetId.
  3. El plugin de Studio inserta el modelo con game:GetObjects("rbxassetid://id").

Esto funciona para CUALQUIER estructura que tenga un modelo 3D en la web,
no solo la casa UP: la API es la misma para todo.

REQUISITOS (una vez por cuenta, ~3 minutos):
  - ROBLOX_API_KEY: clave Open Cloud con permiso "Assets API: Create" y
    permisos Read/Write sobre tu juego. Se crea en
    https://create.roblox.com/credentials
  - ROBLOX_USER_ID: tu ID de Roblox (la URL de tu perfil:
    https://www.roblox.com/users/<ID>/profile)

Nota: los archivos .glb/.obj/.fbx se suben tal cual (la API acepta
"Model"). Si solo consigues un .stl (modelos de impresión 3D, sin color),
este módulo lo convierte a .obj primero.
"""
from __future__ import annotations

import os
import struct
from typing import Optional

import requests

# ===========================================================================
# Registro de modelos reales conocidos (fuentes verificadas)
# ===========================================================================
# Formato: clave -> {nombre, fuente, descarga, licencia, autor, notas}
REGISTRO = {
    "casa_up": {
        "nombre": "Casa UP (Carl y Ellie, Pixar)",
        "fuente": "Sketchfab",
        "url": "https://sketchfab.com/3d-models/"
                "up-house-8767f650da1f4408b57d06862eac5ea3",
        "licencia": "CC Attribution (uso libre con atribución)",
        "autor": "AaronSong",
        "formato": ".glb / .obj (con color)",
        "notas": ("Descarga gratis creando una cuenta de Sketchfab (se puede "
                  "entrar con Google). Botón 'Download 3D Model' → elige "
                  ".glb (lleva el color incluido)."),
    },
    "torre_eiffel": {
        "nombre": "Torre Eiffel (París)",
        "fuente": "Sketchfab (buscar 'Eiffel Tower')",
        "url": "https://sketchfab.com/search?q=eiffel%20tower",
        "licencia": "Depende del modelo (filtrar por 'Downloadable')",
        "autor": "varios",
        "formato": ".glb / .obj",
        "notas": ("Busca 'Eiffel Tower' en Sketchfab y filtra por modelos "
                  "descargables gratuitos."),
    },
}

# Límite oficial de la API: 20 MB por archivo
MAX_BYTES = 20 * 1024 * 1024


def buscar(clave: str) -> Optional[dict]:
    """Devuelve la ficha del modelo real conocido (o None)."""
    return REGISTRO.get(clave)


def disponibles() -> list:
    return sorted(REGISTRO.keys())


# ===========================================================================
# Subida a Roblox (Open Cloud Assets API)
# ===========================================================================
class SinConfiguracion(Exception):
    """Faltan ROBLOX_API_KEY / ROBLOX_USER_ID (env)."""


def subir_modelo(ruta_archivo: str, nombre: str,
                 api_key: str, user_id: str,
                 descripcion: str = "") -> str:
    """Sube un modelo 3D (.glb/.obj/.fbx) a Roblox y devuelve el assetId.

    Usa la API oficial documentada:
      POST https://apis.roblox.com/assets/v1/assets
      (multipart: request JSON + fileContent)

    La respuesta es una operación asíncrona: se consulta hasta que termina
    y devuelve el assetId del Model subido.
    """
    ruta_archivo = os.path.abspath(ruta_archivo)
    if not os.path.isfile(ruta_archivo):
        raise FileNotFoundError(f"No existe el archivo: {ruta_archivo}")
    tam = os.path.getsize(ruta_archivo)
    if tam > MAX_BYTES:
        raise ValueError(
            f"El archivo pesa {tam/1e6:.1f} MB; la API de Roblox admite "
            f"hasta {MAX_BYTES/1e6:.0f} MB."
        )

    ext = os.path.splitext(ruta_archivo)[1].lower()
    tipos = {
        ".fbx": "model/fbx",
        ".glb": "model/gltf-binary",
        ".gltf": "model/gltf+json",
        ".obj": "model/obj",
    }
    if ext not in tipos:
        raise ValueError(f"Formato '{ext}' no soportado. Usa .fbx, .glb, "
                         ".gltf u .obj (los que acepta la API de Roblox).")

    request_json = {
        "assetType": "Model",
        "displayName": (nombre or "Modelo real")[:64],
        "description": (descripcion or "Importado por Constructor Roblox "
                        "(Open Cloud Assets API)")[:1024],
        "creationContext": {"creator": {"userId": str(user_id)}},
    }

    cabeceras = {"x-api-key": api_key}
    with open(ruta_archivo, "rb") as f:
        resp = requests.post(
            "https://apis.roblox.com/assets/v1/assets",
            headers=cabeceras,
            data={"request": requests.models.complexjson.dumps(request_json)},
            files={"fileContent": (os.path.basename(ruta_archivo), f,
                                   tipos[ext])},
            timeout=120,
        )

    if resp.status_code not in (200, 201, 202):
        raise RuntimeError(
            f"Roblox rechazó la subida (HTTP {resp.status_code}): "
            f"{resp.text[:300]}"
        )

    # La subida es asíncrona: poll de la operación
    try:
        cuerpo = resp.json()
        operacion = (cuerpo.get("path") or "").replace("operations/", "")
    except Exception:
        raise RuntimeError(f"Respuesta inesperada de Roblox: {resp.text[:200]}")
    if not operacion:
        raise RuntimeError(f"Roblox no devolvió operación: {resp.text[:200]}")

    for _ in range(60):  # hasta ~2 min
        estado = requests.get(
            f"https://apis.roblox.com/assets/v1/operations/{operacion}",
            headers=cabeceras, timeout=30,
        )
        if estado.status_code != 200:
            raise RuntimeError(f"Error consultando la operación: {estado.text[:200]}")
        datos = estado.json()
        if datos.get("done"):
            asset = datos.get("response", {})
            asset_id = asset.get("assetId")
            if not asset_id:
                raise RuntimeError(f"La operación terminó sin assetId: {datos}")
            return str(asset_id)
        import time
        time.sleep(2)

    raise TimeoutError("La subida a Roblox tardó demasiado (2 min). Reintenta.")


# ===========================================================================
# Conversión STL → OBJ (para modelos de impresión 3D, sin color)
# ===========================================================================
def stl_a_obj(ruta_stl: str, ruta_obj: str) -> str:
    """Convierte un archivo STL (binario o ASCII) a OBJ.

    Útil cuando la única fuente del modelo es un STL de un sitio de
    impresión 3D (Printables, Thingiverse, MakerWorld...). El OBJ resultante
    no lleva color (los STL no lo tienen), pero la forma es exacta y se
    puede importar a Roblox y colorear después.
    """
    ruta_stl = os.path.abspath(ruta_stl)
    if not os.path.isfile(ruta_stl):
        raise FileNotFoundError(f"No existe el STL: {ruta_stl}")

    with open(ruta_stl, "rb") as f:
        cabecera = f.read(5)

    vertices: list = []
    caras: list = []

    if cabecera == b"solid":  # ASCII
        with open(ruta_stl, "r", encoding="utf-8", errors="replace") as f:
            for linea in f:
                partes = linea.split()
                if len(partes) == 4 and partes[0] == "vertex":
                    vertices.append((float(partes[1]), float(partes[2]),
                                     float(partes[3])))
                elif len(partes) == 5 and partes[0] == "facet" \
                        and partes[1] == "normal":
                    pass  # las normales se recalculan
    else:  # binario
        with open(ruta_stl, "rb") as f:
            f.seek(80)
            n_caras = struct.unpack("<I", f.read(4))[0]
            for _ in range(n_caras):
                f.read(12)  # normal
                for _ in range(3):
                    x, y, z = struct.unpack("<3f", f.read(12))
                    vertices.append((x, y, z))
                f.read(2)  # atributos

    if len(vertices) % 3 != 0:
        raise ValueError("El STL no tiene un número de triángulos válido.")

    n_tri = len(vertices) // 3
    with open(ruta_obj, "w", encoding="utf-8") as f:
        f.write("# Convertido desde STL por Constructor Roblox\n")
        for v in vertices:
            f.write(f"v {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}\n")
        for i in range(n_tri):
            a, b, c = i * 3 + 1, i * 3 + 2, i * 3 + 3
            f.write(f"f {a} {b} {c}\n")
    return os.path.abspath(ruta_obj)
