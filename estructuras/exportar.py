"""
Exporta cada estructura del motor a un archivo JSON en la carpeta 'estructuras/'.

Cada archivo es un "plano de referencia" autocontenido: nombre, sinónimos,
referencia real, dimensiones en studs y metros, y todas sus piezas. El servidor
lo usa para REPLICAR estructuras exactas o crear VARIANTES (colores distintos),
aunque el motor Python no esté disponible.

Regenerar la biblioteca:
    python estructuras/exportar.py

Los archivos generados son texto plano y se pueden versionar en git.
"""
from __future__ import annotations

import json
import os
import sys

# Permite importar generador/ desde cualquier carpeta
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from generador.biblioteca import ESTRUCTURAS          # noqa: E402
from generador import motor, catalogo, planos         # noqa: E402
from generador.blueprint import Modelo                 # noqa: E402
from generador.validar import autocorregir, informe    # noqa: E402

CARPETA = os.path.dirname(os.path.abspath(__file__))


def exportar() -> None:
    creados, omitidos = [], []
    for clave, info in ESTRUCTURAS.items():
        # Si la estructura tiene un PLANO arquitectónico (estructuras/planos/),
        # esa es su forma FIEL de construcción: no se exporta la versión
        # procedural vieja a la librería (evita reconstruir "de memoria").
        if clave in planos.disponibles():
            omitidos.append(clave + " (tiene plano → se construye del plano)")
            continue
        generador = motor.GENERADORES.get(clave)
        if generador is None:
            omitidos.append(clave)
            continue
        # Parámetros por defecto de la estructura (para que el plano
        # exportado sea representativo del diseño completo).
        kwargs: dict = {"escala": 1.0}
        if "globos" in info.get("parametros", {}):
            kwargs["globos"] = True

        try:
            partes = generador(**kwargs)
        except Exception as e:                                    # pragma: no cover
            print(f"  ✗ {clave}: no se pudo generar ({e})")
            omitidos.append(clave)
            continue

        modelo = Modelo(modelName=f"{info['nombre']} (biblioteca)", parts=partes)
        modelo, _ = autocorregir(modelo)
        qa = informe(modelo)

        bx, by, bz = catalogo.bounding_box(partes)
        archivo = {
            "id": clave,
            "nombre": info["nombre"],
            "sinonimos": info["sinonimos"],
            "referencia": info["referencia"],
            "parametros": info.get("parametros", {}),
            "dimensiones_studs": {
                "x": round(bx, 2), "y": round(by, 2), "z": round(bz, 2),
            },
            "dimensiones_metros": {
                "x": round(catalogo.studs_a_metros(bx), 2),
                "y": round(catalogo.studs_a_metros(by), 2),
                "z": round(catalogo.studs_a_metros(bz), 2),
            },
            "piezas": len(partes),
            "qa": {"errores": len(qa["errores"]), "avisos": len(qa["avisos"])},
            "partes": [p.a_json() for p in partes],
        }

        ruta = os.path.join(CARPETA, f"{clave}.json")
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(archivo, f, ensure_ascii=False, indent=2)
        creados.append((clave, len(partes), len(qa["avisos"])))

    print("✅ Biblioteca exportada en:", CARPETA)
    for clave, n, avisos in creados:
        print(f"  • {clave:18s} {n:4d} piezas  ({avisos} avisos QA)")
    if omitidos:
        print("Omitidos (sin generador):", ", ".join(omitidos))


if __name__ == "__main__":
    exportar()
