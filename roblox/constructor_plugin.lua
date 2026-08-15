--[[
==============================================================================
  Constructor Roblox — PLUGIN para Roblox Studio
==============================================================================

  ¿Para qué sirve?
  Construye los modelos del servidor local (http://127.0.0.1:8080) dentro del
  Workspace en MODO EDICIÓN. Como trabaja en edición, lo construido NO se
  pierde al detener el juego: pulsa Ctrl+S y queda guardado en tu archivo.

  CÓMO INSTALARLO:
  1. En Roblox Studio: Plugins > Plugin Management > botón "+" (agregar).
  2. Selecciona este archivo (roblox/constructor_plugin.lua).
  3. Aparecerá la barra "Constructor Roblox" en la pestaña Plugins.

  REQUISITO: Game Settings > Security > Allow HTTP Requests (activado).

  BOTONES DE LA BARRA:
  • Activo/Detener — pausa o reanuda el polling.
  • Estado        — comprueba la conexión con el servidor.
  • Casa UP       — lanza "crea la casa UP" al servidor (atajo rápido).
  • Limpiar       — borra del Workspace los modelos creados por el plugin.
==============================================================================
--]]

local HttpService = game:GetService("HttpService")

-- =========================================================================
-- CONFIGURACIÓN DEL SERVIDOR
--   LOCAL: http://127.0.0.1:8080   (CLAVE_API vacía)
--   NUBE : https://tu-servicio.onrender.com  (pega CLAVE_API del dashboard)
-- =========================================================================
local URL_BASE = "http://127.0.0.1:8080"
local CLAVE_API = ""

local URL_POLL = URL_BASE .. "/roblox/poll"
local URL_PING = URL_BASE .. "/roblox/ping"
local URL_CREAR = URL_BASE .. "/crear"
local INTERVALO = 2      -- segundos entre consultas
local ATRIBUTO = "ConstructorRoblox"

local function cabeceras()
    if CLAVE_API and CLAVE_API ~= "" then
        return { ["X-API-Key"] = CLAVE_API }
    end
    return {}
end

-- Formas de parte soportadas (Enum.PartType)
local FORMAS = {
    Block       = Enum.PartType.Block,
    Wedge       = Enum.PartType.Wedge,
    CornerWedge = Enum.PartType.CornerWedge,
    Cylinder    = Enum.PartType.Cylinder,
    Ball        = Enum.PartType.Ball,
    Sphere      = Enum.PartType.Ball,
}

-- Mallas opcionales (SpecialMesh / Enum.MeshType)
local MALLAS = {
    Sphere   = Enum.MeshType.Sphere,
    Cylinder = Enum.MeshType.Cylinder,
    Head     = Enum.MeshType.Head,
    Torso    = Enum.MeshType.Torso,
    Wedge    = Enum.MeshType.Wedge,
    Brick    = Enum.MeshType.Brick,
}

-- =========================================================================
-- Construcción de partes y modelos (igual que el ServerScript)
-- =========================================================================
local function construirParte(datos, padre)
    local parte = Instance.new("Part")
    parte.Name = datos.name or ("Pieza_" .. tostring(#padre:GetChildren() + 1))
    parte.Shape = FORMAS[datos.shape] or Enum.PartType.Block

    if datos.size and #datos.size >= 3 then
        parte.Size = Vector3.new(datos.size[1], datos.size[2], datos.size[3])
    end

    if datos.position and #datos.position >= 3 then
        local rot = datos.rotation or {0, 0, 0}
        parte.CFrame = CFrame.new(
            datos.position[1], datos.position[2], datos.position[3]
        ) * CFrame.Angles(
            math.rad(rot[1] or 0), math.rad(rot[2] or 0), math.rad(rot[3] or 0)
        )
    end

    if datos.color and #datos.color >= 3 then
        parte.Color = Color3.fromRGB(datos.color[1], datos.color[2], datos.color[3])
    end

    local material = nil
    pcall(function()
        material = Enum.Material[datos.material]
    end)
    if material then
        parte.Material = material
    end

    parte.Anchored = true
    parte.CanCollide = true

    if datos.mesh then
        local malla = Instance.new("SpecialMesh")
        malla.MeshType = MALLAS[datos.mesh] or Enum.MeshType.Sphere
        if datos.meshScale and #datos.meshScale >= 3 then
            malla.Scale = Vector3.new(
                datos.meshScale[1], datos.meshScale[2], datos.meshScale[3]
            )
        end
        malla.Parent = parte
    end

    if datos.script and datos.script ~= "" then
        local script = Instance.new("Script")
        script.Name = "Comportamiento"
        script.Source = datos.script
        script.Parent = parte
    end

    parte.Parent = padre
    return parte
end

local function construirModelo(datos)
    local modelo = Instance.new("Model")
    modelo.Name = datos.modelName or "Modelo"
    modelo:SetAttribute(ATRIBUTO, true)

    local padre = game.Workspace
    if datos.parent and game.Workspace:FindFirstChild(datos.parent) then
        padre = game.Workspace[datos.parent]
    end

    for _, datosParte in ipairs(datos.parts or {}) do
        construirParte(datosParte, modelo)
    end

    modelo.Parent = padre
    print("[Constructor/Plugin] ✔ Construido: '" .. modelo.Name
        .. "' (" .. #(datos.parts or {}) .. " piezas) en Workspace."
        .. " Guárdalo con Ctrl+S para no perderlo.")
end

-- =========================================================================
-- Comunicación con el servidor
-- =========================================================================
local function ping()
    local ok = pcall(function()
        HttpService:GetAsync(URL_PING, true, cabeceras())
    end)
    if ok then
        print("[Constructor/Plugin] ✔ Servidor local conectado (127.0.0.1:8080)")
        return true
    else
        warn("[Constructor/Plugin] ✘ Sin conexión. ¿Está corriendo 'python servidor.py'?")
        return false
    end
end

local function poll()
    local ok, resultado = pcall(function()
        return HttpService:GetAsync(URL_POLL, true, cabeceras())
    end)
    if ok then
        local datos = HttpService:JSONDecode(resultado)
        if datos.hasData and datos.data then
            local exito, err = pcall(construirModelo, datos.data)
            if not exito then
                warn("[Constructor/Plugin] Error construyendo: " .. tostring(err))
            end
        end
    end
end

local function lanzar(texto)
    local ok, resp = pcall(function()
        return HttpService:PostAsync(
            URL_CREAR,
            HttpService:JSONEncode({ texto = texto }),
            Enum.HttpContentType.ApplicationJson,
            false,
            cabeceras()
        )
    end)
    if ok then
        print("[Constructor/Plugin] ✔ Enviada: '" .. texto .. "' (Roblox la construirá en unos segundos)")
    else
        warn("[Constructor/Plugin] ✘ No pude enviar la orden: " .. tostring(resp))
    end
end

local function limpiar()
    local borrados = 0
    for _, hijo in ipairs(game.Workspace:GetChildren()) do
        if hijo:IsA("Model") and hijo:GetAttribute(ATRIBUTO) then
            hijo:Destroy()
            borrados = borrados + 1
        end
    end
    print("[Constructor/Plugin] 🧹 Modelos del constructor eliminados: " .. borrados)
end

-- =========================================================================
-- Barra de herramientas (pestaña Plugins)
-- =========================================================================
local toolbar = plugin:CreateToolbar("Constructor Roblox")

local botonActivo = toolbar:CreateButton(
    "Activo",
    "Reanudar o detener la construcción automática",
    ""
)
local botonEstado = toolbar:CreateButton(
    "Estado",
    "Comprobar la conexión con el servidor",
    ""
)
local botonCasaUP = toolbar:CreateButton(
    "Casa UP",
    "Lanza 'crea la casa UP de la película' al servidor",
    ""
)
local botonLimpiar = toolbar:CreateButton(
    "Limpiar",
    "Elimina los modelos creados por el constructor",
    ""
)

-- Recordar si el polling debe estar activo entre sesiones de Studio
local activo = plugin:GetSetting("Activo")
if activo == nil then activo = true end
botonActivo:SetActive(activo)

botonActivo.Click:Connect(function()
    activo = not activo
    plugin:SetSetting("Activo", activo)
    botonActivo:SetActive(activo)
    print("[Constructor/Plugin] Polling " .. (activo and "ACTIVADO" or "DETENIDO"))
end)

botonEstado.Click:Connect(function()
    ping()
end)

botonCasaUP.Click:Connect(function()
    lanzar("crea la casa UP de la pelicula")
end)

botonLimpiar.Click:Connect(function()
    limpiar()
end)

-- =========================================================================
-- Bucle principal: consulta el servidor cada 2 segundos (en edición)
-- =========================================================================
task.spawn(function()
    local contador = 0
    while true do
        if activo then
            contador = contador + 1
            if contador % 10 == 1 then
                ping()  -- un ping cada ~20 segundos
            end
            poll()
        end
        task.wait(INTERVALO)
    end
end)

print("[Constructor/Plugin] 🎈 Cargado. Esperando órdenes del servidor local...")
