"""
CONOCIMIENTO DE ROBLOX STUDIO — el programa es un nato conocedor del motor.

REGLA ESTRICTA: antes de construir, ajustar o responder cualquier cosa sobre
Roblox, el programa consulta este módulo. Aquí vive el conocimiento real de
Roblox Studio: piezas, materiales, terreno, coordenadas, transformaciones,
jerarquía, scripts y Luau.

Unidades: Roblox mide en STUDDS (1 stud ≈ 0,28 m reales). Ejes del mundo:
  +X derecha, +Y arriba, +Z hacia el fondo (frente de la cámara por defecto),
  -Z al frente de la fachada, -X izquierda.

Todo lo listado aquí son valores REALES de Roblox (verificados en la
documentación de la Creator Hub), no invenciones.
"""
from __future__ import annotations

# ===========================================================================
# 1) PIEZAS (instancias que se pueden poner en el Workspace)
# ===========================================================================
PIEZAS = {
    "Part": "Cuerpo sólido básico (Block/Wedge/CornerWedge/Cylinder/Ball). Es lo que usa el programa para construir.",
    "MeshPart": "Pieza con malla 3D importada (.obj/.fbx/.gltf). La forma real la da el archivo.",
    "Union": "Fusión booleana de varias piezas (Add/Subtract/Intersect). Bueno para formas complejas.",
    "Wedge": "Cuña (prisma triangular).",
    "CornerWedge": "Esquina cortada (triángulo en esquina).",
    "Cylinder": "Cilindro facetado (12 lados).",
    "Ball": "Esfera nativa (para globos, pomos, ruedas).",
    "TrussPart": "Estructura metálica (escaleras, andamios) con la que el jugador puede trepar.",
    "SpawnLocation": "Punto de aparición del jugador.",
    "Seat": "Asiento estático.",
    "VehicleSeat": "Asiento de vehículo.",
    "Decal": "Textura pegada a una cara de una pieza.",
    "Texture": "Textura repetible sobre una pieza.",
    "SurfaceGui": "Interfaz 2D pegada a la superficie de una pieza.",
    "PartOperation": "Base de las operaciones booleanas (Union/Separate/Subtract).",
}

FORMAS_PART = {
    "Block": "Caja regular (x, y, z).",
    "Wedge": "Cuña: triángulo en el plano X-Y (la cara inclinada baja de +Z a -Z).",
    "CornerWedge": "Esquina: medio cubo cortado por la diagonal.",
    "Cylinder": "Cilindro con 12 lados, eje en Y.",
    "Ball": "Esfera.",
}

# ===========================================================================
# 2) MATERIALES (Enum.Material — TODOS los que existen de verdad)
# ===========================================================================
MATERIALES = [
    "Plastic", "SmoothPlastic", "Neon", "Wood", "WoodPlanks", "WoodRounded",
    "Metal", "MetalSheet", "CorrodedMetal", "DiamondPlate", "Brick",
    "Concrete", "Marble", "Granite", "Slate", "Sandstone", "Rock", "Pebble",
    "Cobblestone", "Limestone", "Basalt", "Ice", "Glacier", "Snow", "Glass",
    "Fabric", "Carpet", "Leather", "Cardboard", "Ceramic", "Clay", "Foil",
    "Grass", "LeafyGrass", "Mud", "Pavement", "Plate", "RiverRock", "Rubber",
    "Sand", "Salt", "Stone", "Texture", "Wall", "Glacial", "CrackedLava",
    "Cracks", "ForceField", "Headlight", "Hinge", "Pipe", "PlasticBricks",
    "Ground",
]

MATERIALES_USO = {
    "madera_siding": ["WoodPlanks"],           # revestimiento de paredes (listones)
    "madera_lisa": ["Wood", "WoodRounded"],
    "estructura": ["Concrete", "Brick", "Stone", "Metal", "SmoothPlastic"],
    "techo": ["WoodPlanks", "Slate", "Rubber", "Metal"],
    "cristal": ["Glass"],
    "suelo": ["Concrete", "Pavement", "Stone", "Cobblestone", "Slate"],
    "natural": ["Grass", "LeafyGrass", "Sand", "Rock", "Mud", "Snow", "Ice"],
    "metal": ["Metal", "MetalSheet", "DiamondPlate", "CorrodedMetal"],
    "ladrillo": ["Brick"],
    "decorativo": ["Fabric", "Carpet", "Leather", "Cardboard", "Ceramic",
                   "Marble", "Granite", "Plastic"],
    "agua": ["Water"],
}

# ===========================================================================
# 3) TERRENO
# ===========================================================================
TERRENO = {
    "instancia": "Terrain (siempre existe en Workspace; se manipula con el plugin Terrain de Studio o con APIs de Lua).",
    "materiales": ["Grass", "Sand", "Rock", "Mud", "Snow", "Ice", "Water",
                   "Slate", "Basalt", "Ground", "LeafyGrass", "CrackedLava",
                   "Pebble", "Glacier", "RiverRock"],
    "herramientas": ["Generar", "Añadir", "Restar", "Pintar", "Suavizar",
                     "Aplanar", "Erosión", "Sellar", "Región"],
    "regla": "El terreno es una rejilla de celdas 4×4 studs. Para 'terreno' en un plano, el programa usa Césped (Grass) como pieza o describe las celdas; el plugin de Studio es lo que mejor pinta terreno.",
}

# ===========================================================================
# 4) COORDENADAS Y TRANSFORMACIONES
# ===========================================================================
COORDENADAS = {
    "unidad": "stud (1 stud ≈ 0,28 m). Roblox mide SIEMPRE en studs.",
    "ejes": "X → derecha · Y → arriba · Z → fondo (el -Z es el frente de la fachada por defecto).",
    "origen": "El centro del mundo es (0, 0, 0); en un lugar nuevo la Baseplate ocupa y=0.",
    "posicion": "Property 'Position' (Vector3) = centro de la pieza.",
    "csize": "Property 'Size' (Vector3) = tamaño en studs por eje.",
    "rotacion_grados": "En el BLUEPRINT la rotación va en GRADOS (x, y, z). En Lua se usa CFrame.Angles(rad, rad, rad) → siempre convertir.",
    "cframe": "CFrame combina posición + rotación. CFrame.new(pos) * CFrame.Angles(rx, ry, rz).",
    "anclado": "Property 'Anchored' = true → la pieza no cae ni la mueve la física (lo usa SIEMPRE el constructor).",
    "collision": "Property 'CanCollide' = true → los jugadores/piezas chocan contra ella.",
    "regla_programa": "El constructor genera posiciones en studs (metres→studs) y rotación en grados; el plugin aplica CFrame.new(pos) * CFrame.Angles(math.rad(...)).",
}

TRANSFORMACIONES = {
    "mover": "Cambiar Position (o CFrame). En edición: herramienta Mover (teclas W/E/R para mover/rotar/escalar).",
    "rotar": "CFrame.Angles alrededor de los ejes locales. En el blueprint: grados (x, y, z).",
    "escalar": "Property Size; o escalar el modelo entero con 'Scale' en Studio. El programa usa reescalar() que multiplica tamaño Y posición.",
    "escala_por_ejes": "Se puede escalar distinto por eje (más alto = sy>1) con reescalar_ejes().",
    "union_booleana": "Para recortar huecos reales (puertas/ventanas) se puede usar Subtract de Uniones en Studio.",
}

# ===========================================================================
# 5) JERARQUÍA (cómo se organiza el Workspace)
# ===========================================================================
JERARQUIA = {
    "workspace": "Workspace = el mundo del juego. Todo lo visible vive aquí.",
    "model": "Model = grupo de piezas (una casa completa es un Model).",
    "folder": "Folder = carpeta para organizar (sin física, solo contenedor).",
    "regla_nombres": "Los nombres en Explorer son únicos entre hermanos; usa nombres claros ('Casa UP', 'Torre_segmento_0').",
    "regla_programa": "El constructor SIEMPRE agrupa todo en un Model con el nombre del modelo, y añade un atributo ConstructorRoblox=true para poder limpiarlo.",
    "atributos": "Los modelos del constructor llevan SetAttribute('ConstructorRoblox', true).",
}

# ===========================================================================
# 6) SCRIPTS Y LUAU
# ===========================================================================
SCRIPTS = {
    "script": "Script = código que corre en el SERVIDOR (Roblox). Sirve para física, lógica del juego.",
    "localscript": "LocalScript = código que corre en el CLIENTE (el jugador). Para UI e inputs.",
    "modulescript": "ModuleScript = biblioteca reutilizable (return de una tabla).",
    "ubicaciones": "ServerScriptService = scripts de servidor · StarterPlayerScripts = scripts de cliente · ReplicatedStorage = cosas compartidas.",
    "instancias": "Instance.new('Part') crea; parent = quien la contiene; :Destroy() la borra.",
    "luau": "Luau = el lenguaje (variante de Lua de Roblox). Variables con 'local', funciones, eventos con ':' (Connect), tareas con task.wait/task.spawn.",
    "ejemplo_puerta": "local puerta = script.Parent; puerta.ClickDetector.MouseClick:Connect(function() puerta.CFrame = puerta.CFrame * CFrame.new(0, 0, -2) end)",
    "ejemplo_flotar": "task.spawn(function() while true do part.CFrame = part.CFrame * CFrame.new(0, 0.5, 0); task.wait(1) end end)",
    "regla_programa": "Los blueprints pueden llevar 'script' (código Luau) dentro de una pieza; el plugin crea un Script con ese Source. Para comportamiento real (puertas, globos que flotan, luces) se inyecta aquí.",
}

# ===========================================================================
# 7) LÍMITES TÉCNICOS REALES
# ===========================================================================
LIMITES = {
    "tamano_min": 0.05,       # studs (menor da fallos de física)
    "tamano_max": 2048.0,     # studs por eje (límite duro)
    "piezas_recomendadas": 500,   # por modelo (rendimiento móvil)
    "piezas_max": 2000,       # tope duro
    "caja_max": 512.0,        # studs por eje del modelo
    "flotacion_max": 3.0,     # studs sin apoyo antes de avisar
    "angulos_grados": True,   # el blueprint usa grados (Lua usa radianes)
}

# ===========================================================================
# 8) REGLAS ESTRICTAS DEL PROGRAMA (se aplican SIEMPRE)
# ===========================================================================
REGLAS_ESTRICTAS = [
    "SIEMPRE construir en studs: metros → studs (1 stud ≈ 0,28 m) antes de generar piezas.",
    "SOLO usar materiales que existen: si un material no está en MATERIALES, el QA lo corrige a Plastic.",
    "SOLO usar formas que existen: Block/Wedge/CornerWedge/Cylinder/Ball.",
    "Todas las piezas ancladas (Anchored=true) y con nombre propio (nunca 'Part').",
    "Agrupar SIEMPRE en un Model con nombre claro y atributo ConstructorRoblox.",
    "La rotación del blueprint va en grados; al construir en Lua se convierte a radianes.",
    "Nada de materiales 'Roof' ni 'RubberRoof': NO existen en Enum.Material.",
    "Antes de encolar, el QA (generador/validar.py) verifica tamaño, forma, material, flotación y límites.",
    "Si una estructura necesita comportamiento (puertas, luces, movimiento), usar scripts Luau incrustados, no fingirlo con piezas.",
    "Cuando el usuario pregunte por Roblox Studio (piezas, materiales, terreno, Lua...), responder CON ESTE CONOCIMIENTO, no de memoria.",
]

# ===========================================================================
# Acceso
# ===========================================================================
TEMAS = {
    "piezas": PIEZAS,
    "materiales": {"lista": MATERIALES, "por_uso": MATERIALES_USO},
    "terreno": TERRENO,
    "coordenadas": COORDENADAS,
    "transformaciones": TRANSFORMACIONES,
    "jerarquia": JERARQUIA,
    "scripts": SCRIPTS,
    "limites": LIMITES,
    "reglas": REGLAS_ESTRICTAS,
}


def tema(nombre: str) -> dict:
    """Devuelve el contenido de un tema (o {} si no existe)."""
    return TEMAS.get(nombre, {})


def temas_disponibles() -> list:
    return sorted(TEMAS.keys())


def resumen() -> str:
    """Un resumen legible de las reglas estrictas (para el razonador/panel)."""
    return ("\n".join(f"• {r}" for r in REGLAS_ESTRICTAS))
