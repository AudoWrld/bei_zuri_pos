#!/bin/bash

echo "========================================"
echo "BeiZuri Print Server Installation"
echo "========================================"
echo ""

# Check if running as root for service installation
if [ "$EUID" -ne 0 ]; then 
    echo "This script requires sudo privileges for service installation."
    echo "Please run with: sudo ./install_print_server.sh"
    exit 1
fi

# Get the actual user who ran sudo (not root)
ACTUAL_USER=${SUDO_USER:-$USER}
ACTUAL_HOME=$(eval echo ~$ACTUAL_USER)
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

echo "Installing for user: $ACTUAL_USER"
echo "Installation directory: $SCRIPT_DIR"
echo ""

# Check and install Python3
if ! command -v python3 &> /dev/null; then
    echo "Python3 not found. Installing..."
    apt-get update
    apt-get install -y python3 python3-pip python3-venv
else
    echo "Python3 found!"
    python3 --version
fi

echo ""
echo "Installing system dependencies..."
apt-get update
apt-get install -y libusb-1.0-0-dev udev

echo ""
echo "Creating Python virtual environment..."
sudo -u $ACTUAL_USER python3 -m venv "$SCRIPT_DIR/venv"

echo ""
echo "Installing Python dependencies..."
sudo -u $ACTUAL_USER "$SCRIPT_DIR/venv/bin/pip" install --upgrade pip
sudo -u $ACTUAL_USER "$SCRIPT_DIR/venv/bin/pip" install -r "$SCRIPT_DIR/requirements.txt"

if [ $? -ne 0 ]; then
    echo ""
    echo "ERROR: Failed to install dependencies!"
    exit 1
fi

echo ""
echo "Setting up USB permissions..."
# Add user to necessary groups
usermod -a -G lp $ACTUAL_USER
usermod -a -G dialout $ACTUAL_USER

# Create udev rule for printer
cat > /etc/udev/rules.d/99-thermal-printer.rules << 'EOF'
# Thermal printer USB permissions
SUBSYSTEM=="usb", ATTRS{idVendor}=="0483", ATTRS{idProduct}=="5743", MODE="0666", GROUP="lp"
SUBSYSTEM=="usb", ENV{DEVTYPE}=="usb_device", MODE="0664", GROUP="lp"
EOF

# Reload udev rules
udevadm control --reload-rules
udevadm trigger

echo ""
echo "Creating printer config file..."
cat > "$SCRIPT_DIR/printer_config.json" << 'EOF'
{
  "vendor_id": "0x0483",
  "product_id": "0x5743",
  "out_endpoint": "0x01"
}
EOF

chown $ACTUAL_USER:$ACTUAL_USER "$SCRIPT_DIR/printer_config.json"

echo ""
echo "Creating systemd service..."
cat > /etc/systemd/system/beizuri-print.service << EOF
[Unit]
Description=BeiZuri Print Server
After=network.target

[Service]
Type=simple
User=$ACTUAL_USER
WorkingDirectory=$SCRIPT_DIR
Environment="PATH=$SCRIPT_DIR/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
ExecStart=$SCRIPT_DIR/venv/bin/python $SCRIPT_DIR/print_server.py

# Restart configuration
Restart=always
RestartSec=5
StartLimitInterval=0

# Logging
StandardOutput=append:$SCRIPT_DIR/print_server.log
StandardError=append:$SCRIPT_DIR/print_server_error.log

# Security settings
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

echo ""
echo "Creating management scripts..."

# Create start script (for manual testing)
cat > "$SCRIPT_DIR/start_server.sh" << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"
source venv/bin/activate
python3 print_server.py
EOF

chmod +x "$SCRIPT_DIR/start_server.sh"
chown $ACTUAL_USER:$ACTUAL_USER "$SCRIPT_DIR/start_server.sh"

# Create service management scripts
cat > "$SCRIPT_DIR/restart_service.sh" << 'EOF'
#!/bin/bash
echo "Restarting BeiZuri Print Service..."
sudo systemctl restart beizuri-print.service
echo "Service restarted!"
systemctl status beizuri-print.service --no-pager
EOF

chmod +x "$SCRIPT_DIR/restart_service.sh"
chown $ACTUAL_USER:$ACTUAL_USER "$SCRIPT_DIR/restart_service.sh"

cat > "$SCRIPT_DIR/check_status.sh" << 'EOF'
#!/bin/bash
echo "========================================"
echo "BeiZuri Print Server Status"
echo "========================================"
systemctl status beizuri-print.service --no-pager
echo ""
echo "Recent Logs:"
echo "----------------------------------------"
journalctl -u beizuri-print.service -n 20 --no-pager
EOF

chmod +x "$SCRIPT_DIR/check_status.sh"
chown $ACTUAL_USER:$ACTUAL_USER "$SCRIPT_DIR/check_status.sh"

cat > "$SCRIPT_DIR/view_logs.sh" << 'EOF'
#!/bin/bash
echo "========================================"
echo "BeiZuri Print Server Logs"
echo "========================================"
echo ""
echo "Standard Output:"
tail -n 50 print_server.log 2>/dev/null || echo "No logs yet"
echo ""
echo "----------------------------------------"
echo "Error Log:"
tail -n 50 print_server_error.log 2>/dev/null || echo "No errors yet"
echo ""
echo "System Journal (last 50 lines):"
journalctl -u beizuri-print.service -n 50 --no-pager
EOF

chmod +x "$SCRIPT_DIR/view_logs.sh"
chown $ACTUAL_USER:$ACTUAL_USER "$SCRIPT_DIR/view_logs.sh"

cat > "$SCRIPT_DIR/stop_service.sh" << 'EOF'
#!/bin/bash
echo "Stopping BeiZuri Print Service..."
sudo systemctl stop beizuri-print.service
echo "Service stopped!"
systemctl status beizuri-print.service --no-pager
EOF

chmod +x "$SCRIPT_DIR/stop_service.sh"
chown $ACTUAL_USER:$ACTUAL_USER "$SCRIPT_DIR/stop_service.sh"

cat > "$SCRIPT_DIR/uninstall_service.sh" << 'EOF'
#!/bin/bash
echo "========================================"
echo "WARNING: Uninstall BeiZuri Print Service"
echo "========================================"
read -p "Are you sure you want to uninstall? (yes/no): " confirm
if [ "$confirm" != "yes" ]; then
    echo "Uninstall cancelled."
    exit 0
fi

echo "Stopping service..."
sudo systemctl stop beizuri-print.service

echo "Disabling service..."
sudo systemctl disable beizuri-print.service

echo "Removing service file..."
sudo rm /etc/systemd/system/beizuri-print.service

echo "Reloading systemd..."
sudo systemctl daemon-reload

echo "Service uninstalled!"
EOF

chmod +x "$SCRIPT_DIR/uninstall_service.sh"
chown $ACTUAL_USER:$ACTUAL_USER "$SCRIPT_DIR/uninstall_service.sh"

# Create log files with proper permissions
touch "$SCRIPT_DIR/print_server.log"
touch "$SCRIPT_DIR/print_server_error.log"
chown $ACTUAL_USER:$ACTUAL_USER "$SCRIPT_DIR/print_server.log"
chown $ACTUAL_USER:$ACTUAL_USER "$SCRIPT_DIR/print_server_error.log"

echo ""
echo "Enabling and starting service..."
systemctl daemon-reload
systemctl enable beizuri-print.service
systemctl start beizuri-print.service

# Wait a moment for service to start
sleep 2

echo ""
if systemctl is-active --quiet beizuri-print.service; then
    echo "========================================"
    echo "SUCCESS! Service installed and started!"
    echo "========================================"
    echo ""
    echo "The print server is now running as a system service."
    echo "It will:"
    echo "  - Start automatically on system boot"
    echo "  - Restart automatically if it crashes"
    echo "  - Run in the background always"
    echo ""
    echo "Service Details:"
    echo "  - Service Name: beizuri-print.service"
    echo "  - Status: Running"
    echo "  - Logs: $SCRIPT_DIR/print_server.log"
    echo ""
    echo "Test the printer at: http://localhost:8080/test"
    echo ""
    echo "Useful Commands:"
    echo "  ./restart_service.sh  - Restart the service"
    echo "  ./check_status.sh     - Check service status"
    echo "  ./view_logs.sh        - View service logs"
    echo "  ./stop_service.sh     - Stop the service"
    echo "  ./uninstall_service.sh - Remove service"
    echo ""
    echo "System Commands:"
    echo "  sudo systemctl status beizuri-print    - Check status"
    echo "  sudo systemctl restart beizuri-print   - Restart"
    echo "  sudo journalctl -u beizuri-print -f    - Follow logs"
    echo "========================================"
else
    echo "========================================"
    echo "ERROR: Service failed to start!"
    echo "========================================"
    echo ""
    echo "Check the logs with:"
    echo "  ./view_logs.sh"
    echo "  sudo journalctl -u beizuri-print -n 50"
    systemctl status beizuri-print.service --no-pager
    exit 1
fi

echo ""
echo "NOTE: You may need to log out and back in for USB"
echo "      permissions to take effect if the service"
echo "      can't access the printer."
echo ""