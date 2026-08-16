# MEMORIA DEL PROYECTO — Constructor Roblox 🎈

> Pega este archivo (o su contenido) al inicio de una nueva sesión para que
> el agente retome el contexto completo sin perder nada.

---

## Qué es este proyecto

Programa en Python + Roblox Studio que convierte **ideas en lenguaje natural**
("crea la casa UP de la película") en **modelos 3D dentro de Roblox**, usando
referencias reales y construcción procedural. El usuario quiere estructuras
fieles a la realidad (investigando referencias) y que el programa tenga
**conocimiento de construcción**: piezas, materiales, dimensiones métricas y
un loop de validación.

## Arquitectura (archivos)

| Archivo | Rol |
|---|---|
| `servidor.py` | Servidor FastAPI (puerto 8080). Endpoints: `POST /crear` (texto→modelo), `POST /build` (blueprint JSON), `POST /antigravity/hook` (compat. cerebro viejo), `GET /roblox/poll` (cola para Roblox), `GET /roblox/ping` (diagnóstico), `GET /estado`, `GET /historial`, `GET /api/estructuras`, `GET /` (panel web). Corre QA antes de encolar. |
| `generador/blueprint.py` | Dataclasses `Parte` y `Modelo` (shape, size, position, rotation, color, material, mesh, meshScale, script, name) + validación base. |
| `generador/catalogo.py` | **Conocimiento de construcción**: 1 stud ≈ 0,28 m; `metros_a_studs`; límites de Roblox (tamaño 0.05–2048, ≤500 piezas recomendadas); catálogo de formas y materiales por uso; `aabb` (caja envolvente CON rotación real, rota los 8 vértices), `bounding_box`, `reescalar`, `escala_para_solar`. |
| `generador/motor.py` | Generadores procedurales: `casa_up` (251 piezas, v3/v4), `torre_eiffel` (17 piezas, escala real: 330 m; helpers `_pata_plano_yx`/`_pata_plano_yz` con eje largo en Y, rotación `rz=atan2(-dx,dy)` / `rx=atan2(dz,dy)`), `casa_victoriana`, `casa_simple`, `arbol`, `rascacielos`. Constantes de colores arriba. |
| `generador/biblioteca.py` | Estructuras conocidas con sinónimos es/en y `referencia` (investigación real: la casa UP es Queen Anne, de Don Shank/Pixar, inspirada en Berkeley CA; planta ~8,6×8,6 m, ~10 m a la chimenea — fuente THEMODELMAKER escala 1:48). |
| `generador/razonador.py` | Interpreta el texto: detecta estructura, escala ("el doble", "escala 2"), pisos, globos, **solar en metros** y ahora órdenes de **réplica** ("replica X", "otra vez", "clona") y **variante** ("parecido a X", "similar") que usan la librería de archivos. |
| `generador/libreria.py` | **Librería en archivos** (`estructuras/*.json`): `listar()`, `replicar(clave, escala)` (réplica exacta) y `variar(clave, hue)` (misma estructura con paleta desplazada). Carga/lee JSON autocontenidos con ficha real y dimensiones. |
| `estructuras/` | **Carpeta de la biblioteca**: un JSON por estructura (plano de referencia + ficha + piezas). Regenerable con `python estructuras/exportar.py`. Se versionan en git. |
| `generador/validar.py` | **Loop de QA**: `informe(modelo)` (errores/avisos/sugerencias: duplicados, ocultas, flotantes, límites, caja en studs Y metros) y `autocorregir(modelo)` (materiales inválidos→Plastic, formas→Block, tamaños ≤0→0.1). Usa `catalogo.aabb` (rotaciones reales). |
| `static/index.html` | Panel web de chat en español. Muestra razonamiento + QA, indicador de conexión Roblox y **sección Librería** (tarjetas con botones Construir/Variante por estructura). |
| `roblox/constructor.lua` | ServerScript para Roblox Studio (funciona en Play). Polling cada 3 s. |
| `roblox/constructor_plugin.lua` | **PLUGIN de Studio (recomendado)**: construye en modo edición. Diseño profesional: UN botón "Constructor" en la barra que abre un panel compacto (DockWidgetPluginGui) con estado, ON/OFF, Casa UP y Limpiar. Instalar: Plugins → Plugin Management → + (reinstalar no recarga el código: hay que reiniciar Studio). |
| `MEMORIA.md` | Este documento. |
| `.freebuff/run.md` | Cómo arrancar el servidor. |

## Cómo arrancar

1. `python servidor.py` → panel en `http://127.0.0.1:8080`.
2. En Roblox Studio: **Game Settings → Security → Allow HTTP Requests** ACTIVADO.
3. Instalar `roblox/constructor_plugin.lua` (Plugins → Plugin Management → +).
4. Pedir algo en el panel → el plugin lo construye en Workspace en ~2 s → **Ctrl+S**.

## Decisiones y convenciones importantes

- **Idioma**: todo comentario y respuesta en español.
- **Materiales**: `Roof` y `RubberRoof` NO existen en Enum.Material (dio error en Roblox: "Roof is not a valid member"). Techo se hace con `WoodPlanks`/`Slate`/`Rubber`. El plugin/script usan `pcall` al leer `Enum.Material[...]` para no romper.
- **El QA es obligatorio**: `servidor.py` corre `autocorregir` + `informe` antes de encolar; si hay errores no envía.
- **Plugins vs ServerScript**: los cambios hechos en *Play* se pierden al detener el juego; por eso se usa el plugin (construye en edición y se guarda con Ctrl+S).
- El modelo construido lleva el atributo `ConstructorRoblox` (el botón "Limpiar" del plugin lo usa).
- Roblox solo permite localhost (127.0.0.1) desde Studio; un juego publicado NO puede acceder a la máquina local.

## Deploy en la nube (15 ago 2026)

- Objetivo del usuario: mover el servidor a la nube (PC débil: Intel i3 4130).
- Preparado: `servidor.py` escucha en 0.0.0.0, puerto `PORT` si `RENDER=1`
  (Render lo inyecta) o `SERVIDOR_PUERTO`/8080 en local. Seguridad con
  `CLAVE_API` (env): si está definida, todos los endpoints exigen header
  `X-API-Key`; el panel web tiene campo de clave guardado en localStorage.
- Archivos de deploy: `requirements.txt`, `render.yaml` (blueprint free,
  `generateValue` para CLAVE_API).
- Plugin y ServerScript: `URL_BASE` + `CLAVE_API` configurables al inicio,
  headers en GetAsync/PostAsync (get(url, true, cabeceras())).
- Recomendación: **Render free** (sin tarjeta, 750 h/mes, spin-down 15 min,
  despierta en ~1 min al abrir Studio) para empezar; **Oracle Always Free**
  (VM 2 OCPU/12 GB siempre encendida, tarjeta requerida) para lo definitivo.
- PASOS EN MEMORIA de la casa UP: pendiente mejorar fidelidad (el usuario
  dijo que la casa actual "evidentemente no es la de la película"); objetivo
  2 aún por definir por el usuario.

## Librería de estructuras (carpeta `estructuras/`)

- Cada estructura vive en un JSON autocontenido: `id`, `nombre`, `sinonimos`, `referencia` (ficha real), `parametros`, `dimensiones_studs` y `dimensiones_metros`, `piezas`, `qa` y `partes` (el blueprint a E=1).
- Se regeneran con `python estructuras/exportar.py` (usa el motor + QA).
- Endpoints: `GET /api/estructuras` (metadatos para el panel) y `POST /estructuras/{clave}/construir` con body `{modo: replica|variante, escala, hue, solar}`.
- El razonador usa la librería para "replica X / clona / otra vez" y "parecido a X / variante" (salvo que haya cambios estructurales tipo "sin globos"/"pisos", que van al motor).
- El plugin/ServerScript NO leen archivos: reciben el blueprint por HTTP como siempre (la librería vive en el servidor).

## Modo de entrenamiento por imagen (15 ago 2026)

- **La casa UP procedural se ELIMINÓ** a petición del usuario (no le hacía honor a la película y no quería que se reconstruyera con ese conocimiento): fuera de `biblioteca.py` y de `estructuras/casa_up.json`. Si la piden, el razonador responde que no está y sugiere el modo imagen. El motor `motor.casa_up` queda en el código pero sin registrar.
- **`generador/voxel.py`** (funciona SIN claves): convierte cualquier imagen en bloques 3D. Modos: `bloques` (fachada plana, cada píxel = bloque) y `relieve` (brillo → altura). Colores cuantificados a pasos de 24, resolución limitada (≤96 px, ≤1800 piezas). Endpoint `POST /imagen` (multipart: archivo, modo, lado).
- **`generador/vision.py`** (IA de visión, Gemini free): envía la imagen a Gemini con consigna de 'arquitecto 3D' y devuelve un blueprint semántico (muros/techos/puertas...). Requiere `GEMINI_API_KEY` (clave gratuita en https://aistudio.google.com/apikey → Render → Environment). Endpoint `POST /analizar-imagen`.
- Panel: sección "📸 Entrena con una imagen" (elegir archivo + modo + resolución + vista previa).
- Dependencias nuevas: `pillow`, `python-multipart`, `requests` (en requirements.txt).
- Lección: los params de FastAPI junto a `UploadFile` deben ser `Form(...)`, no query.

## Estado actual (15 ago 2026)

- **En la nube**: servidor desplegado en Render (`https://constructor-roblox.onrender.com`), plugin conectado. CLAVE_API generada por Render (¡NO subir a GitHub los `roblox/` con la clave! El repo es público). GEMINI_API_KEY pendiente de poner por el usuario para el modo IA.
- Flujo completo funcionando: panel web → /crear (o librería) → razonador → motor/librería → QA → cola → plugin → Roblox.
- Casa UP v3/v4: cuerpo casi cuadrado (38×30 studs), fachada multicolor (crema abajo, azul/rosa arriba), techo azul marino, torre en esquina con cúpula y punta, buhardilla (dormer), habitación lateral verde-azul, césped, valla con tramos laterales, pomo amarillo, 110 globos con cuerdas, ajuste a solar en metros.
- **Torre Eiffel añadida**: 17 piezas, dimensiones reales (330 m, base 125×125 m, plataformas a 57/115/300 m), E=1 = escala real en studs; pídela "en un solar de X por Y metros" para escalar. Caja QA en metros = 127×332×127 (real).
- QA: detecta piezas ocultas/flotantes/duplicadas, límites, caja en studs y metros, con cajas rotadas reales (aabb). Avisos benignos restantes: escalón enterrado en la base, buhardilla parcialmente tras el techo, "modelo enorme" en estructuras a escala real.
- El usuario quería antes una versión "más fiel" hecha con otra IA (fachada azul/rosa) — esa dirección la mantiene.

## Próximos pasos sugeridos (sin empezar aún)

1. Añadir más estructuras con ficha de dimensiones reales (barco Flying Dutchman, aldea de Hyrule, etc.) en `motor.py` + `biblioteca.py`. Plantilla: funciones `_pata_plano_yx/_yz` + ficha en `biblioteca.py` + registrar en `GENERADORES`.
1b. **Rediseñar la casa UP para que sea fiel a la película** (pendiente, prioridad del usuario).
2. Estructuras con comportamiento (scripts Lua incrustados: puertas, globos flotantes, luces).
3. ~~Guardar blueprints en disco~~ **HECHO**: carpeta `estructuras/` + `libreria.py` (replicar/variar). Siguiente: añadir más estructuras al JSON manualmente o exportando.
4. Integración con Rojo para sincronizar el plugin/scripts.
5. Vistas previas 3D en el plugin antes de construir.

## Lecciones del QA de la Torre Eiffel

- Los AABB sin rotación mienten para piezas inclinadas: siempre usar `catalogo.aabb` (rota los 8 vértices).
- Losas inclinadas: construir con el eje largo en **Y** y rotar con `rz = atan2(-dx, dy)` (plano Y-X) / `rx = atan2(dz, dy)` (plano Y-Z). El eje largo en X/Z con esas fórmulas apunta en la dirección contraria.
- El ajuste a solar usa `bounding_box` → ahora con cajas reales da medidas exactas (la torre a 60×60 m de solar dio caja 60×157×60 m).

## Errores ya resueltos (no repetir)

- "Roof is not a valid member of Enum.Material" → quitar Roof/RubberRoof, usar WoodPlanks.
- Construcción solo en Play se perdía → usar el plugin (edición).
- Los rieles de la valla flotaban → acercarlos a los piquetes (±0.3 en vez de ±0.9).
- Punta de torre oculta dentro de la cúpula → subirla a `y_cornisa + 11*E`.
- Falsos positivos de flotación con escalas decimales → margen de 0.05 studs en el apoyo.
