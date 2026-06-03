"""Read CPU sensors on Linux: temperature, load, package power, peak frequency."""
import glob


def find_hidraw():
    """Locate the SK700V's hidraw node by USB VID 381C (survives renumbering)."""
    for ue in glob.glob('/sys/class/hidraw/hidraw*/device/uevent'):
        try:
            if '381C' in open(ue).read().upper():
                return '/dev/' + ue.split('/')[4]
        except Exception:
            pass
    return None


def find_temp_path():
    """AMD k10temp / zenpower Tctl (temp1_input)."""
    for hw in glob.glob('/sys/class/hwmon/hwmon*'):
        try:
            name = open(hw + '/name').read().strip()
        except Exception:
            continue
        if name in ('k10temp', 'zenpower') and __import__('os').path.exists(hw + '/temp1_input'):
            return hw + '/temp1_input'
    return None


def find_rapl():
    """RAPL package energy counter (intel-rapl:0)."""
    for c in sorted(glob.glob('/sys/class/powercap/intel-rapl:*/energy_uj')):
        if c.split('/')[-2] == 'intel-rapl:0':
            return c
    cs = sorted(glob.glob('/sys/class/powercap/intel-rapl:*/energy_uj'))
    return cs[0] if cs else None


def read_temp_c(path):
    try:
        return round(int(open(path).read().strip()) / 1000)
    except Exception:
        return None


def read_cpu_times():
    v = list(map(int, open('/proc/stat').readline().split()[1:]))
    return sum(v), v[3] + (v[4] if len(v) > 4 else 0)


def read_energy_uj(path):
    if not path:
        return None
    try:
        return int(open(path).read().strip())
    except Exception:
        return None


def read_freq_peak_mhz():
    """Peak core clock across all cores (steadier + more meaningful than the mean)."""
    best = 0
    for f in glob.glob('/sys/devices/system/cpu/cpu[0-9]*/cpufreq/scaling_cur_freq'):
        try:
            best = max(best, int(open(f).read().strip()))
        except Exception:
            pass
    return round(best / 1000) if best else 0

def find_pl2():
    """RAPL PL2 (short-term power limit) for the package, in watts. None if unreadable."""
    for c in sorted(glob.glob('/sys/class/powercap/intel-rapl:*/constraint_1_power_limit_uw')):
        if c.split('/')[-2] == 'intel-rapl:0':
            try:
                return int(open(c).read().strip()) / 1e6
            except Exception:
                return None
    return None
