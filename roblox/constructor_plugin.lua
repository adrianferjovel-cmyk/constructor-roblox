--[[
==============================================================================
  Constructor Roblox — PLUGIN para Roblox Studio (panel compacto)
==============================================================================

  Un SOLO botón en la barra de plugins ("Constructor"). Al pulsarlo se abre
  un panel compacto con todo lo necesario:

    • Indicador de estado ..... punto verde (en línea) / rojo (sin conexión)
    • Construcción automática . interruptor ON/OFF (queda recordado)
    • Casa UP .................. lanza "crea la casa UP de la película"
    • Limpiar .................. borra los modelos creados por el plugin

  Construye en el Workspace en MODO EDICIÓN: lo construido se guarda con
  Ctrl+S y no se pierde al detener el juego.

  INSTALAR: Plugins > Plugin Management > botón "+" > seleccionar este archivo.
  REQUISITO: Game Settings > Security > Allow HTTP Requests (activado).
==============================================================================
--]]

local HttpService = game:GetService("HttpService")

-- =========================================================================
-- CONFIGURACIÓN DEL SERVIDOR
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
-- Construcción de partes y modelos
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

-- Inserta un MODELO REAL ya subido a Roblox (Open Cloud Assets API):
-- el servidor sube un .glb/.obj/.fbx y este plugin lo trae con
-- game:GetObjects("rbxassetid://<id>") y lo deja anclado en Workspace.
local function insertarModeloReal(datos)
    local assetId = datos.assetId
    if not assetId then
        warn("[Constructor/Plugin] Orden insertModel sin assetId.")
        return
    end
    local ok, objetos = pcall(function()
        return game:GetObjects("rbxassetid://" .. tostring(assetId))
    end)
    if not ok then
        warn("[Constructor/Plugin] No pude insertar el modelo real ("
            .. tostring(objetos) .. "). ¿Es tuyo y está aprobado?")
        return
    end
    local raiz
    if #objetos == 1 then
        raiz = objetos[1]
    else
        raiz = Instance.new("Model")
        raiz.Name = datos.modelName or "Modelo real"
        for _, obj in ipairs(objetos) do
            obj.Parent = raiz
        end
    end
    raiz.Name = datos.modelName or raiz.Name
    raiz:SetAttribute(ATRIBUTO, true)
    -- Anclar todas las mallas para que no caigan
    local function anclar(inst)
        if inst:IsA("BasePart") then
            inst.Anchored = true
        end
        for _, hijo in ipairs(inst:GetChildren()) do
            anclar(hijo)
        end
    end
    anclar(raiz)
    raiz.Parent = game.Workspace
    print("[Constructor/Plugin] ✔ Modelo real insertado: '" .. raiz.Name
        .. "' (assetId " .. tostring(assetId) .. ") en Workspace."
        .. " Ctrl+S para guardarlo.")
end

-- =========================================================================
-- Comunicación con el servidor
-- =========================================================================
local function ping()
    local ok = pcall(function()
        HttpService:GetAsync(URL_PING, true, cabeceras())
    end)
    if ok then
        print("[Constructor/Plugin] ✔ Conectado a " .. URL_BASE)
        return true
    else
        warn("[Constructor/Plugin] ✘ Sin conexión con " .. URL_BASE
            .. ". ¿Está el servidor arriba y la CLAVE_API correcta?")
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
            local exito, err
            if datos.data.accion == "insertModel" then
                exito, err = pcall(insertarModeloReal, datos.data)
            else
                exito, err = pcall(construirModelo, datos.data)
            end
            if not exito then
                warn("[Constructor/Plugin] Error construyendo: " .. tostring(err))
            end
        end
    end
    return ok
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
        print("[Constructor/Plugin] ✔ Enviada: '" .. texto
            .. "' (se construirá en unos segundos)")
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
-- Interfaz compacta (DockWidgetPluginGui)
-- =========================================================================
local function nuevo(clase, props, padre)
    local obj = Instance.new(clase)
    for k, v in pairs(props) do
        obj[k] = v
    end
    obj.Parent = padre
    return obj
end

local NEGRO    = Color3.fromRGB(35, 35, 39)
local CARD     = Color3.fromRGB(60, 60, 68)
local BORDE    = Color3.fromRGB(92, 92, 100)
local TEXTO    = Color3.fromRGB(235, 235, 240)
local GRIS     = Color3.fromRGB(150, 150, 160)
local VERDE    = Color3.fromRGB(64, 200, 120)
local ROJO     = Color3.fromRGB(240, 90, 90)
local AZUL     = Color3.fromRGB(0, 162, 255)
local AMARILLO = Color3.fromRGB(235, 190, 60)

local dock = plugin:CreateDockWidgetPluginGui("ConstructorPanel", DockWidgetPluginGuiInfo.new(
    Enum.InitialDockState.Right, false, false, 320, 230, 280, 200
))
dock.Title = "Constructor Roblox"

local root = nuevo("Frame", {
    BackgroundColor3 = NEGRO,
    BorderSizePixel = 0,
    Size = UDim2.new(1, 0, 1, 0),
}, dock)
nuevo("UIPadding", {
    PaddingTop = UDim.new(0, 12),
    PaddingBottom = UDim.new(0, 12),
    PaddingLeft = UDim.new(0, 14),
    PaddingRight = UDim.new(0, 14),
}, root)

-- Cabecera: punto de estado + título
local cabecera = nuevo("Frame", {
    BackgroundTransparency = 1,
    Size = UDim2.new(1, 0, 0, 26),
}, root)
local punto = nuevo("Frame", {
    BackgroundColor3 = AMARILLO,
    BorderSizePixel = 0,
    Size = UDim2.new(0, 12, 0, 12),
    Position = UDim2.new(0, 0, 0, 3),
}, cabecera)
nuevo("UICorner", { CornerRadius = UDim.new(1, 0) }, punto)
nuevo("TextLabel", {
    BackgroundTransparency = 1,
    Text = "Constructor Roblox",
    TextColor3 = TEXTO,
    TextSize = 15,
    Font = Enum.Font.GothamBold,
    TextXAlignment = Enum.TextXAlignment.Left,
    TextTruncate = Enum.TextTruncate.AtEnd,
    Size = UDim2.new(1, -22, 1, 0),
    Position = UDim2.new(0, 20, 0, 0),
}, cabecera)

-- Estado de conexión
local estado = nuevo("TextLabel", {
    BackgroundTransparency = 1,
    Text = "Conectando…",
    TextColor3 = GRIS,
    TextSize = 12,
    Font = Enum.Font.Gotham,
    TextXAlignment = Enum.TextXAlignment.Left,
    TextTruncate = Enum.TextTruncate.AtEnd,
    Size = UDim2.new(1, 0, 0, 18),
    Position = UDim2.new(0, 0, 0, 28),
}, root)

-- Fila: construcción automática (ON/OFF)
local filaActivo = nuevo("Frame", {
    BackgroundColor3 = CARD,
    BorderSizePixel = 0,
    Size = UDim2.new(1, 0, 0, 40),
    Position = UDim2.new(0, 0, 0, 54),
}, root)
nuevo("UICorner", { CornerRadius = UDim.new(0, 8) }, filaActivo)
nuevo("TextLabel", {
    BackgroundTransparency = 1,
    Text = "Construcción automática",
    TextColor3 = TEXTO,
    TextSize = 13,
    Font = Enum.Font.Gotham,
    TextXAlignment = Enum.TextXAlignment.Left,
    Size = UDim2.new(0.62, 0, 1, 0),
    Position = UDim2.new(0, 12, 0, 0),
}, filaActivo)
local botonActivo = nuevo("TextButton", {
    BackgroundColor3 = VERDE,
    BorderSizePixel = 0,
    Text = "ON",
    TextColor3 = Color3.new(1, 1, 1),
    TextSize = 12,
    Font = Enum.Font.GothamBold,
    AutoButtonColor = false,
    Size = UDim2.new(0, 56, 0, 26),
    Position = UDim2.new(1, -68, 0.5, -13),
}, filaActivo)
nuevo("UICorner", { CornerRadius = UDim.new(0, 6) }, botonActivo)

-- Fila: acciones principales
local filaBotones = nuevo("Frame", {
    BackgroundTransparency = 1,
    Size = UDim2.new(1, 0, 0, 40),
    Position = UDim2.new(0, 0, 0, 104),
}, root)
local botonCasaUP = nuevo("TextButton", {
    BackgroundColor3 = AZUL,
    BorderSizePixel = 0,
    Text = "Casa UP",
    TextColor3 = Color3.new(1, 1, 1),
    TextSize = 13,
    Font = Enum.Font.GothamBold,
    AutoButtonColor = false,
    Size = UDim2.new(0.5, -5, 1, 0),
    Position = UDim2.new(0, 0, 0, 0),
}, filaBotones)
nuevo("UICorner", { CornerRadius = UDim.new(0, 8) }, botonCasaUP)
local botonLimpiar = nuevo("TextButton", {
    BackgroundColor3 = CARD,
    BorderSizePixel = 0,
    Text = "Limpiar",
    TextColor3 = TEXTO,
    TextSize = 13,
    Font = Enum.Font.GothamBold,
    AutoButtonColor = false,
    Size = UDim2.new(0.5, -5, 1, 0),
    Position = UDim2.new(0.5, 5, 0, 0),
}, filaBotones)
nuevo("UICorner", { CornerRadius = UDim.new(0, 8) }, botonLimpiar)

-- Pie: URL del servidor + pista
local pieUrl = nuevo("TextLabel", {
    BackgroundTransparency = 1,
    Text = URL_BASE:gsub("https://", ""),
    TextColor3 = GRIS,
    TextSize = 11,
    Font = Enum.Font.Gotham,
    TextXAlignment = Enum.TextXAlignment.Left,
    TextWrapped = true,
    Size = UDim2.new(1, 0, 0, 16),
    Position = UDim2.new(0, 0, 1, -34),
}, root)
nuevo("TextLabel", {
    BackgroundTransparency = 1,
    Text = "Ctrl+S guarda lo construido",
    TextColor3 = GRIS,
    TextSize = 11,
    Font = Enum.Font.Gotham,
    TextXAlignment = Enum.TextXAlignment.Left,
    Size = UDim2.new(1, 0, 0, 16),
    Position = UDim2.new(0, 0, 1, -16),
}, root)

-- =========================================================================
-- Lógica de la interfaz
-- =========================================================================
local function setEstado(conectado)
    if conectado then
        punto.BackgroundColor3 = VERDE
        estado.Text = "Servidor en línea"
        estado.TextColor3 = VERDE
    else
        punto.BackgroundColor3 = ROJO
        estado.Text = "Sin conexión con el servidor"
        estado.TextColor3 = ROJO
    end
end

local activo = plugin:GetSetting("Activo")
if activo == nil then activo = true end

local function pintarActivo()
    botonActivo.Text = activo and "ON" or "OFF"
    botonActivo.BackgroundColor3 = activo and VERDE or ROJO
end
pintarActivo()

botonActivo.MouseButton1Click:Connect(function()
    activo = not activo
    plugin:SetSetting("Activo", activo)
    pintarActivo()
    print("[Constructor/Plugin] Polling " .. (activo and "ACTIVADO" or "DETENIDO"))
end)

botonCasaUP.MouseButton1Click:Connect(function()
    lanzar("crea la casa UP de la pelicula")
end)

botonLimpiar.MouseButton1Click:Connect(function()
    limpiar()
end)

-- Efecto hover profesional
local function hover(btn, normal, brillo)
    btn.MouseEnter:Connect(function()
        btn.BackgroundColor3 = brillo
    end)
    btn.MouseLeave:Connect(function()
        btn.BackgroundColor3 = normal
    end)
end
hover(botonActivo, botonActivo.BackgroundColor3, VERDE:Lerp(Color3.new(1, 1, 1), 0.25))
hover(botonCasaUP, AZUL, AZUL:Lerp(Color3.new(1, 1, 1), 0.25))
hover(botonLimpiar, CARD, CARD:Lerp(Color3.new(1, 1, 1), 0.25))

-- =========================================================================
-- Barra de herramientas: UN solo botón que abre/cierra el panel
-- =========================================================================
local toolbar = plugin:CreateToolbar("Constructor Roblox")
local botonPanel = toolbar:CreateButton(
    "Constructor",
    "Abrir o cerrar el panel del Constructor Roblox",
    "",
    "Constructor"
)
botonPanel.Click:Connect(function()
    dock.Enabled = not dock.Enabled
    botonPanel:SetActive(dock.Enabled)
end)

-- =========================================================================
-- Bucle principal: consulta el servidor cada 2 segundos (en edición)
-- =========================================================================
task.spawn(function()
    local contador = 0
    setEstado(ping())
    while true do
        if activo then
            contador = contador + 1
            if contador % 10 == 1 then
                setEstado(ping())  -- actualiza el indicador cada ~20 s
            else
                local ok = poll()
                if not ok then
                    setEstado(false)
                end
            end
        end
        task.wait(INTERVALO)
    end
end)

print("[Constructor/Plugin] 🎈 Cargado. Pulsa 'Constructor' en la pestaña Plugins para abrir el panel.")
