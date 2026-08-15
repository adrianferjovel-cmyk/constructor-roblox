"""
Blueprint: el formato de datos que describe una estructura 3D para Roblox.

Una estructura se compone de una lista de Partes. Cada Parte corresponde a
una Part de Roblox (Block, Wedge, CornerWedge, Cylinder o Ball) con sus
propiedades: tamaño, posición, rotación, color, material, y opcionalmente
una malla (SpecialMesh) y un script Lua incrustado.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import List, Optional
import json
import uuid

# --- Formas de parte que existen de verdad en Roblox ----------------------
FORMAS_ROBLOX = {"Block", "Wedge", "CornerWedge", "Cylinder", "Ball"}

# --- Materiales de Roblox (Enum.Material) ---------------------------------
MATERIALES_ROBLOX = {
    "Plastic", "SmoothPlastic", "Neon", "Wood", "WoodPlanks", "WoodRounded",
    "Metal", "MetalSheet", "CorrodedMetal", "DiamondPlate", "Brick",
    "Concrete", "Marble", "Granite", "Slate", "Sandstone", "Rock", "Pebble",
    "Cobblestone", "Limestone", "Basalt", "Ice", "Glacier", "Snow",
    "Glass", "Fabric", "Carpet", "Leather", "Cardboard", "Ceramic",
    "Clay", "Foil", "Grass", "LeafyGrass", "Mud", "Pavement", "Plate",
    "RiverRock", "Rubber", "Sand", "Salt", "Stone",
    "Texture", "Wall", "Glacial", "CrackedLava", "Cracks", "ForceField",
    "Headlight", "Hinge", "Pipe", "PlasticBricks", "Ground",
}

# --- Mallas de Roblox (Enum.MeshType) -------------------------------------
MALLAS_ROBLOX = {"Head", "Torso", "Wedge", "Sphere", "Cylinder", "Brick"}


@dataclass
class Parte:
    """Una sola pieza de la estructura (equivalente a una Part de Roblox)."""
    shape: str = "Block"
    size: List[float] = field(default_factory=lambda: [4.0, 4.0, 4.0])
    position: List[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])
    rotation: List[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])  # grados
    color: List[int] = field(default_factory=lambda: [200, 200, 200])
    material: str = "Plastic"
    mesh: Optional[str] = None          # "Sphere", "Cylinder", ... (SpecialMesh)
    meshScale: Optional[List[float]] = None
    script: str = ""                    # código Lua opcional incrustado
    name: str = ""

    def validar(self) -> List[str]:
        """Devuelve la lista de errores del blueprint (vacía si es válido)."""
        errores = []
        if self.shape not in FORMAS_ROBLOX:
            errores.append(f"Forma '{self.shape}' no existe en Roblox. "
                           f"Usa: {sorted(FORMAS_ROBLOX)}")
        if self.material not in MATERIALES_ROBLOX:
            errores.append(f"Material '{self.material}' no existe en Roblox.")
        if self.mesh and self.mesh not in MALLAS_ROBLOX:
            errores.append(f"Malla '{self.mesh}' no existe en Roblox.")
        for eje, v in zip("XYZ", self.size):
            if v <= 0:
                errores.append(f"El tamaño en {eje} debe ser mayor que 0 (es {v}).")
        return errores

    def a_json(self) -> dict:
        return asdict(self)


@dataclass
class Modelo:
    """Una estructura completa lista para enviar a Roblox."""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    modelName: str = "Modelo"
    parts: List[Parte] = field(default_factory=list)
    parent: str = "Workspace"
    razonamiento: List[str] = field(default_factory=list)  # explicación para el usuario

    def validar(self) -> List[str]:
        errores = []
        for i, p in enumerate(self.parts):
            for e in p.validar():
                errores.append(f"Parte #{i} ({p.name or p.shape}): {e}")
        return errores

    def a_json(self) -> dict:
        datos = asdict(self)
        return datos

    def a_payload(self) -> dict:
        """El formato que consume el script de Roblox vía /roblox/poll."""
        return {
            "id": self.id,
            "modelName": self.modelName,
            "parent": self.parent,
            "parts": [p.a_json() for p in self.parts],
        }


def desde_json(datos: dict) -> Modelo:
    """Reconstruye un Modelo desde un dict (útil para /build y el hook)."""
    partes = []
    for p in datos.get("parts", []):
        parte = Parte(**{k: v for k, v in p.items()
                         if k in Parte.__dataclass_fields__})
        partes.append(parte)
    return Modelo(
        id=datos.get("id", uuid.uuid4().hex[:8]),
        modelName=datos.get("modelName", "Modelo"),
        parent=datos.get("parent", "Workspace"),
        parts=partes,
        razonamiento=datos.get("razonamiento", []),
    )
