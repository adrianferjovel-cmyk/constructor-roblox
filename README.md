# Constructor Roblox 🎈

Programa que convierte **ideas en lenguaje natural** en **modelos 3D para
Roblox**, usando referencias reales. Dices *"crea la casa UP de la película"*
y el programa investiga qué es, genera una estructura procedural fiel
(~180 piezas) y la deja lista para que Roblox la construya.

## Cómo funciona

```
Tú escribes una idea
      │  (panel web o API)
      ▼
┌─────────────────────┐
│  RAZONADOR          │  identifica la estructura (sinónimos es/ing)
│  (generador/)       │  extrae parámetros (escala, pisos, globos...)
└─────────────────────┘
      ▼
┌─────────────────────┐
│  MOTOR PROCEDURAL    │  genera el blueprint: pieza por pieza
│  (motor.py)          │  forma, tamaño, posición, color, material, malla
└─────────────────────┘
      ▼
┌─────────────────────┐
│  SERVIDOR (servidor.py) │  cola de instrucciones
└─────────────────────┘
      ▼  (polling cada 3 s)
┌─────────────────────┐
│  ROBLOX (constructor.lua) │  construye el modelo en Workspace
└─────────────────────┘
```

## Estructura del proyecto

| Archivo | Qué hace |
|---|---|
| `servidor.py` | Servidor FastAPI: `/crear` (texto), `/build` (JSON), `/antigravity/hook` (cerebro original), `/roblox/poll`, `/historial`, panel web |
| `generador/blueprint.py` | Modelo de datos (Parte, Modelo) con validación contra formas/materiales reales de Roblox |
| `generador/motor.py` | Motor procedural: construye las estructuras pieza por pieza (la casa UP incluida) |
| `generador/biblioteca.py` | Estructuras conocidas: sinónimos en español/inglés + la referencia real que respalda cada diseño |
| `generador/razonador.py` | Interpreta tu frase: detecta estructura, escala, pisos, globos... y explica su razonamiento |
| `static/index.html` | Panel web de chat (se abre en `http://127.0.0.1:8080`) |
| `roblox/constructor.lua` | Script para Roblox Studio: hace polling y construye el modelo |

## Cómo usarlo

### 1. Arranca el servidor

```bash
python servidor.py
```

### 2. Prueba en el panel web

Abre `http://127.0.0.1:8080` y escribe, por ejemplo:

- *"crea la casa UP de la película"*
- *"hazme la casa de Carl Fredricksen al doble de grande"*
- *"un rascacielos de 30 pisos"*
- *"la casa victoriana sin globos"*
- *"un árbol"*

### 3. Construye en Roblox Studio (dos formas)

**Opción A — Plugin (recomendado):** construye en *modo edición*, siempre
activo, y lo construido se guarda con Ctrl+S.

1. Activa las peticiones HTTP: **Game Settings ▸ Security ▸ Allow HTTP Requests**.
2. **Plugins ▸ Plugin Management ▸ botón +** y selecciona
   `roblox/constructor_plugin.lua`.
3. Aparecerá la barra **Constructor Roblox** en la pestaña Plugins, con botones
   para activar/detener, comprobar estado, lanzar la casa UP y limpiar.
4. Escribe algo en el panel web (o pulsa el botón *Casa UP*) y el modelo
   aparecerá en Workspace en ~2 segundos. Pulsa **Ctrl+S** para guardarlo.

**Opción B — ServerScript:** para cuando el juego esté corriendo (Play).

1. Crea un **Script** dentro de **ServerScriptService** y pega
   `roblox/constructor.lua`.
2. Con el servidor corriendo, pulsa **Play**.
3. Escribe algo en el panel web: el modelo aparecerá en Workspace.
   ⚠️ Al detener el juego, lo construido en Play se descarta (normal en
   Roblox). Usa el plugin para construir en edición y guardar.

## Deploy en la nube (Render, plan gratuito)

Para no consumir recursos de tu PC, el servidor puede vivir en la nube.
El proyecto ya está preparado (`render.yaml`, `requirements.txt`, puerto y
host configurables, clave de seguridad).

**Pasos:**
1. Sube la carpeta del proyecto a un repositorio de GitHub (incluye
   `servidor.py`, `generador/`, `static/`, `requirements.txt`, `render.yaml`).
2. En [render.com](https://render.com) (gratis, sin tarjeta): **New ▸ Blueprint**
   y conecta el repo. Render detecta `render.yaml`, instala y arranca solo.
3. Espera el build (~2 min). Obtén la URL, p. ej.
   `https://constructor-roblox.onrender.com`.
4. En el dashboard del servicio, copia **CLAVE_API** (se genera sola).
5. En `roblox/constructor_plugin.lua` (y/o `constructor.lua`) cambia:
   `URL_BASE = "https://tu-servicio.onrender.com"` y `CLAVE_API = "tu clave"`.
   Reinstala el plugin.
6. Abre la URL de la nube en el navegador y pega la clave en el campo
   **"Clave API"** del panel.

**Notas del plan gratuito:** el servicio se duerme tras 15 min sin tráfico
(el plugin lo despierta solo al abrir Studio, espera ~1 min la primera vez)
y hay 750 horas de instancia/mes. Mientras Studio esté abierto con el plugin
activo, el servicio está despierto (y consume horas); al cerrar Studio se
sumerge. Uso normal de unas horas al día no agota el límite.

**Alternativa más potente (sin límites):** Oracle Cloud *Always Free* — VM
real siempre encendida (~2 OCPU/12 GB, 10 TB de ancho de banda); requiere
tarjeta para verificar (no cobran) y configuración SSH. Para subir el servidor
ahí: `pip install -r requirements.txt`, `python servidor.py` con `CLAVE_API`
y abrir el puerto en el firewall.

**Bonus:** con el servidor en la nube, incluso un juego *publicado* en Roblox
puede construir (Roblox bloquea localhost, pero no URLs públicas).

## API

| Endpoint | Descripción |
|---|---|
| `POST /crear` `{"texto": "la casa UP"}` | Convierte texto → modelo y lo encola |
| `POST /build` | Encola un blueprint JSON directamente |
| `POST /antigravity/hook` | Compatible con el "cerebro" original (formato viejo de partes) |
| `GET /roblox/poll` | Roblox consulta aquí; devuelve el siguiente modelo pendiente |
| `GET /historial` | Modelos generados en la sesión |
| `GET /api/estructuras` | Qué sabe construir el programa |

## La casa UP (el ejemplo estrella)

El diseño está basado en la **casa victoriana estilo Queen Anne** de la
película *Up* (Pixar, 2009), inspirada a su vez en una casa real de la calle
Sixth Street en Berkeley, California. Incluye:

- Cuerpo de dos plantas color crema con molduras verdes
- Torre con cúpula (la habitación de Carl)
- Porche delantero de madera con columnas y baranda de piquetes
- Chimenea de ladrillo, valla de piquetes y arbustos
- Opcional: la nube de ~85 globos de colores que la hace volar

## Ideas para ampliar

- Más estructuras en `generador/biblioteca.py` + `motor.py` (naves, castillos, vehículos...).
- Conexión con un LLM (OpenAI/Claude) para que el *razonamiento* sea libre, no solo plantillas.
- Guardar blueprints en disco y reutilizarlos ("usa la casa UP de la sesión pasada").
- Scripts Lua generados dinámicamente (puertas que se abren, globos que flotan, etc.).
