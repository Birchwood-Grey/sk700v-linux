#!/usr/bin/env bash
# SK700V Linux installer: Python package + udev rules + systemd user service.
set -e

echo "==> Installing the sk700v Python package (user)..."
pip install --user -e .

echo "==> Installing udev rules (needs sudo)..."
sudo cp udev/99-sk700v.rules /etc/udev/rules.d/
sudo cp udev/99-rapl-power.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules
sudo udevadm trigger --subsystem-match=hidraw || true
sudo chmod -R a+r /sys/devices/virtual/powercap/intel-rapl || true

echo "==> Installing systemd user service..."
mkdir -p ~/.config/systemd/user
cp systemd/sk700v.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now sk700v.service

echo ""
echo "Done. The SK700V monitor is running in the background."
echo "  sk700v status                  # check it"
echo "  sk700v unit F                  # switch units (then restart)"
echo "  systemctl --user restart sk700v"
echo ""
echo "If your cooler was just plugged in, a reboot ensures udev permissions stick."
