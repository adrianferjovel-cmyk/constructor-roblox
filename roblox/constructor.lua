--[[
==============================================================================
  Constructor Roblox — construye modelos enviados por el servidor local.

  CÓMO USARLO:
  1. En Roblox Studio, crea un Script dentro de ServerScriptService.
  2. Pega este código y reemplaza la URL si tu servidor corre en otro puerto.
  3. IMPORTANTE: activa "Allow HTTP Requests" en
     Game Settings ▸ Security ▸ Allow HTTP Requests.
  4. Ejecuta el servidor (python servidor.py) y luego juega (Play).

  El script consulta http://127.0.0.1:8080/roblox/poll cada 3 segundos.
  Cuando hay un modelo pendiente, lo construye en Workspace.
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

local URL = URL_BASE .. "/roblox/poll"
local URL_PING = URL_BASE .. "/roblox/ping"
local INTERVALO = 3  -- segundos entre consultas

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
    Sphere      = Enum.PartType.Ball,   -- alias
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

local function construirParte(datos, padre)
    local parte = Instance.new("Part")
    parte.Name = datos.name or ("Pieza_" .. tostring(#padre:GetChildren() + 1))

    -- Forma
    parte.Shape = FORMAS[datos.shape] or Enum.PartType.Block

    -- Tamaño
    if datos.size and #datos.size >= 3 then
        parte.Size = Vector3.new(datos.size[1], datos.size[2], datos.size[3])
    end

    -- Posición y rotación (grados -> radianes)
    if datos.position and #datos.position >= 3 then
        local rot = datos.rotation or {0, 0, 0}
        parte.CFrame = CFrame.new(
            datos.position[1], datos.position[2], datos.position[3]
        ) * CFrame.Angles(
            math.rad(rot[1] or 0), math.rad(rot[2] or 0), math.rad(rot[3] or 0)
        )
    end

    -- Color
    if datos.color and #datos.color >= 3 then
        parte.Color = Color3.fromRGB(datos.color[1], datos.color[2], datos.color[3])
    end

    -- Material (protegido: un valor desconocido no debe romper la construcción)
    local material = nil
    pcall(function()
        material = Enum.Material[datos.material]
    end)
    if material then
        parte.Material = material
    end

    parte.Anchored = true
    parte.CanCollide = true

    -- Malla opcional (SpecialMesh)
    if datos.mesh then
        local malla = Instance.new("SpecialMesh")
        malla.MeshType = MALLAS[datos.mesh] or Enum.MeshType.Sphere
        if datos.meshScale and #datos.meshScale >= 3 then
            malla.Scale = Vector3.new(datos.meshScale[1], datos.meshScale[2], datos.meshScale[3])
        end
        malla.Parent = parte
    end

    -- Script Lua incrustado (opcional)
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

    local padre = workspace
    if datos.parent and workspace:FindFirstChild(datos.parent) then
        padre = workspace[datos.parent]
    end

    for _, datosParte in ipairs(datos.parts or {}) do
        construirParte(datosParte, modelo)
    end

    modelo.Parent = padre
    print("[Constructor] ✔ Modelo construido: " .. modelo.Name)
end

-- Avisa al servidor que Roblox está vivo (diagnóstico de conexión)
local function pingServidor()
    local ok = pcall(function()
        HttpService:GetAsync(URL_PING, true, cabeceras())
    end)
    if ok then
        print("[Constructor] ✔ Conectado a " .. URL_BASE)
    else
        warn("[Constructor] ✘ No puedo alcanzar " .. URL_BASE
            .. ". Revisa que el servidor esté arriba y que "
            .. "'Allow HTTP Requests' esté ACTIVADO (Game Settings ▸ Security).")
    end
end

-- Bucle de polling
local contador = 0
while true do
    contador = contador + 1
    if contador % 5 == 1 then
        pingServidor()  -- un ping cada ~15 segundos
    end
    local ok, resultado = pcall(function()
        return HttpService:GetAsync(URL, true, cabeceras())
    end)

    if ok then
        local datos = HttpService:JSONDecode(resultado)
        if datos.hasData and datos.data then
            local exito, err = pcall(construirModelo, datos.data)
            if not exito then
                warn("[Constructor] Error construyendo el modelo: " .. tostring(err))
            end
        end
    else
        -- Sin servidor: avisa una vez y sigue intentando
        warn("[Constructor] Sin conexión con el servidor (¿python servidor.py?). " .. tostring(resultado))
        task.wait(5)
    end

    task.wait(INTERVALO)
end
