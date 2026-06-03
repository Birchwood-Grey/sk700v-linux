"""Load and save the user config at ~/.config/sk700v/config.ini."""
import os
import configparser

CONFIG_PATH = os.path.expanduser("~/.config/sk700v/config.ini")
DEFAULTS = {"unit": "C", "interval": "1.0"}


def load():
    cfg = configparser.ConfigParser()
    cfg["sk700v"] = dict(DEFAULTS)
    try:
        cfg.read(CONFIG_PATH)
    except Exception:
        pass
    s = cfg["sk700v"] if cfg.has_section("sk700v") else DEFAULTS
    unit = str(s.get("unit", "C")).strip().upper()
    if unit not in ("C", "F"):
        unit = "C"
    try:
        interval = max(0.25, min(10.0, float(s.get("interval", "1.0"))))
    except Exception:
        interval = 1.0
    return {"unit": unit, "interval": interval}


def save(unit=None, interval=None):
    cur = load()
    if unit is not None:
        cur["unit"] = unit
    if interval is not None:
        cur["interval"] = interval
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    cfg = configparser.ConfigParser()
    cfg["sk700v"] = {"unit": cur["unit"], "interval": str(cur["interval"])}
    with open(CONFIG_PATH, "w") as f:
        f.write("# SK700V monitor configuration\n")
        cfg.write(f)
    return cur
