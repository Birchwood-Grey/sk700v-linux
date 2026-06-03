"""SK700V packet protocol: frame construction and encoding.

Data frame (HID report 0x10, 64 bytes zero-padded). Byte map (verified on hardware,
cross-checked against community findings):
  [0..5] 10 68 01 09 0d 01   header
  [6]    0x02                 show flag (0x00 = init/clear)
  [7:8]  POWER  watts, big-endian u16  (power = b7*256 + b8)
  [9]    POWER % progress bar (0-100), independent of the wattage value
  [10]   UNIT   0 = "C", 1 = "F"  (label + the unit the temp float is expressed in)
  [11:14] TEMP  IEEE-754 float32, big-endian, in the unit set by [10]
  [15]   LOAD   percent, raw
  [16:17] FREQ  MHz, big-endian u16
  [18]   checksum = sum(bytes[1..17]) % 256
  [19]   0x16                 terminator

Note: temperature is a full 32-bit float, so there is NO display cap (an earlier
single-byte decode appeared to cap at 127 only because the float's high byte was
held constant). Both Celsius and Fahrenheit are full-range.
"""
import struct

FRAME_LEN = 64


def pad(frame):
    return bytes(bytearray(frame) + bytearray(FRAME_LEN - len(frame)))


def clamp(v, lo, hi):
    return max(lo, min(hi, int(v)))


INIT_FRAME = pad([0x10, 0x68, 0x01, 0x09, 0x0d, 0x01, 0x00, 0x00, 0x64, 0x32,
                  0x00, 0x42, 0x70, 0x00, 0x00, 0x28, 0x0e, 0x10, 0x0e, 0x16])


def build_data_frame(celsius, load_pct, power_w, freq_mhz, unit="C", power_pct=0):
    """Build a display frame from live sensor values.

    celsius: real CPU temperature in C (converted to F here if unit=='F').
    unit: 'C' or 'F'.
    power_pct: 0-100 fill level for the progress bar under the wattage.
    """
    p = bytearray(20)
    p[0:6] = bytes([0x10, 0x68, 0x01, 0x09, 0x0d, 0x01])
    p[6] = 0x02
    w = clamp(power_w, 0, 65535)
    p[7] = (w >> 8) & 0xff
    p[8] = w & 0xff
    p[9] = clamp(power_pct, 0, 100)
    if unit == "F":
        display = celsius * 9 / 5 + 32
        p[10] = 1
    else:
        display = celsius
        p[10] = 0
    # temperature as big-endian IEEE-754 float32 in bytes [11..14]
    struct.pack_into('>f', p, 11, float(round(display)))
    p[15] = clamp(load_pct, 0, 100)
    m = clamp(freq_mhz, 0, 65535)
    p[16] = (m >> 8) & 0xff
    p[17] = m & 0xff
    p[18] = sum(p[1:18]) % 256
    p[19] = 0x16
    return pad(p)
