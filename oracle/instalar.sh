#!/bin/bash
# =============================================================================
# Instala el Constructor Roblox en Oracle Cloud "Always Free" (Ubuntu 22.04+).
#
# USO: ejecuta este script DENTRO de la carpeta del proyecto en la VM:
#     cd IA_Roblox_Studio
#     chmod +x oracle/instalar.sh
#     sudo bash oracle/instalar.sh
#
# Después: edita /etc/constructor-roblox.env y pon tu CLAVE_API.
# =============================================================================
set -e

echo "==> 1/4 Instalando dependencias del sistema..."
apt-get update -y
apt-get install -y python3-pip python3-venv git curl

echo "==> 2/4 Creando entorno virtual e instalando dependencias de Python..."
if [ ! -d .venv ]; then
    python3 -m venv .venv
fi
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

echo "==> 3/4 Configurando el servicio systemd..."
RUTA="$(pwd)"
sed "s|__RUTA__|$RUTA|g" oracle/constructor-roblox.service > /etc/systemd/system/constructor-roblox.service

if [ ! -f /etc/constructor-roblox.env ]; then
    echo "CLAVE_API=cambia-esta-clave" > /etc/constructor-roblox.env
fi

systemctl daemon-reload
systemctl enable --now constructor-roblox

echo "==> 4/4 Hecho."
echo "Edita tu clave:  sudo nano /etc/constructor-roblox.env"
echo "Reinicia:        sudo systemctl restart constructor-roblox"
echo "Estado:          sudo systemctl status constructor-roblox"
echo "Logs:            sudo journalctl -u constructor-roblox -f"
