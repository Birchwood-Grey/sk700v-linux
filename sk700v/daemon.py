"""The SK700V monitor daemon: read sensors, stream display frames, auto-reconnect."""
import time
import signal
from . import protocol, sensors, config

_running = True


def _stop(*_):
    global _running
    _running = False


def run():
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)

    cfg = config.load()
    unit, interval = cfg["unit"], cfg["interval"]
    tpath = sensors.find_temp_path()
    rpath = sensors.find_rapl()
    pl2 = sensors.find_pl2()
    print(f"SK700V monitor  (unit={unit}, interval={interval}s)")
    print(f"  temp : {tpath or 'NOT FOUND'}")
    print(f"  power: {rpath or 'NOT FOUND (needs RAPL permission - see README)'}")

    warned_power = False
    freq_smooth = 0.0
    prev_t = sensors.read_cpu_times()
    prev_e = sensors.read_energy_uj(rpath)
    prev_clk = time.monotonic()

    while _running:
        dev = sensors.find_hidraw()
        if not dev:
            print("Waiting for SK700V (device not found)...")
            for _ in range(20):
                if not _running:
                    return
                time.sleep(0.25)
            continue
        try:
            with open(dev, 'wb') as d:
                print(f"Connected: {dev}. Streaming. Ctrl+C to stop.")
                for _ in range(3):
                    d.write(protocol.INIT_FRAME); d.flush(); time.sleep(0.3)
                frame = protocol.build_data_frame(
                    sensors.read_temp_c(tpath) or 40, 0, 0,
                    sensors.read_freq_peak_mhz(), unit)
                last_update = 0.0
                while _running:
                    d.write(frame); d.flush(); time.sleep(0.25)   # keepalive stream
                    if time.monotonic() - last_update >= interval:
                        last_update = time.monotonic()
                        now = time.monotonic(); dt = now - prev_clk; prev_clk = now
                        cur_t = sensors.read_cpu_times()
                        dtot, didle = cur_t[0] - prev_t[0], cur_t[1] - prev_t[1]
                        prev_t = cur_t
                        load = 0 if dtot <= 0 else protocol.clamp(round(100*(dtot-didle)/dtot), 0, 100)
                        cur_e = sensors.read_energy_uj(rpath)
                        if prev_e is not None and cur_e is not None and cur_e >= prev_e and dt > 0:
                            power = round((cur_e - prev_e) / dt / 1e6)
                        else:
                            power = 0
                            if rpath and cur_e is None and not warned_power:
                                print("\n[note] power unreadable (RAPL perms) - shows 0. See README.\n")
                                warned_power = True
                        prev_e = cur_e
                        temp = sensors.read_temp_c(tpath)
                        fpeak = sensors.read_freq_peak_mhz()
                        freq_smooth = fpeak if freq_smooth == 0 else 0.6*freq_smooth + 0.4*fpeak
                        ppct = protocol.clamp(round(power / pl2 * 100), 0, 100) if (pl2 and pl2 > 0) else 0
                        frame = protocol.build_data_frame(
                            temp if temp is not None else 40, load, power,
                            round(freq_smooth), unit, power_pct=ppct)
                        shown = round(temp*9/5+32) if (unit == "F" and temp is not None) else temp
                        print(f"\rTEMP {shown}{unit}  LOAD {load}%  POWER {power}W  "
                              f"FREQ {freq_smooth/1000:.2f}GHz   ", end='', flush=True)
        except OSError:
            print("\nDevice disconnected - reconnecting...")
            time.sleep(1.0)
    print("\nStopped.")
