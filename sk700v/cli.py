"""Command-line interface: sk700v start | unit C|F | rate <sec> | status"""
import sys
from . import config, daemon, sensors


def cmd_status():
    cfg = config.load()
    dev = sensors.find_hidraw()
    print("SK700V status")
    print(f"  device : {dev or 'not connected'}")
    print(f"  unit   : {cfg['unit']}")
    print(f"  rate   : {cfg['interval']}s")
    print(f"  config : {config.CONFIG_PATH}")


def cmd_unit(arg):
    u = (arg or "").strip().upper()
    if u not in ("C", "F"):
        print("usage: sk700v unit C|F"); return 1
    config.save(unit=u)
    note = "  (note: Fahrenheit is hardware-capped at 127 F)" if u == "F" else ""
    print(f"Temperature unit set to {u}.{note}")
    print("Restart the monitor for it to take effect.")


def cmd_rate(arg):
    try:
        v = float(arg)
    except (TypeError, ValueError):
        print("usage: sk700v rate <seconds>  (0.25 - 10)"); return 1
    cfg = config.save(interval=max(0.25, min(10.0, v)))
    print(f"Update rate set to {cfg['interval']}s. Restart the monitor to apply.")


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    cmd = argv[0] if argv else "help"
    arg = argv[1] if len(argv) > 1 else None
    if cmd == "start":
        daemon.run()
    elif cmd == "status":
        cmd_status()
    elif cmd == "unit":
        return cmd_unit(arg)
    elif cmd == "rate":
        return cmd_rate(arg)
    else:
        print("SK700V cooler LCD monitor\n"
              "usage:\n"
              "  sk700v start        run the monitor (foreground)\n"
              "  sk700v status       show device + settings\n"
              "  sk700v unit C|F     set temperature unit\n"
              "  sk700v rate <sec>   set update interval (0.25-10)\n")
    return 0
