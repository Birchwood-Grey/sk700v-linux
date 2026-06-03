"""SK700V packet protocol: frame construction and encoding.

Data frame (HID report 0x10, 64 bytes zero-padded). Reverse-engineered byte map:
  [0..5] 10 68 01 09 0d 01   header
  [6]    0x02                 show flag (0x00 = init/clear)
  [7:8]  POWER  watts, big-endian u16  (power = b7*256 + b8)
  [10]   UNIT   0 = label "C", 1 = label "F"  (relabel only; caller converts value)
  [11]   0x42                 structural constant
  [12]   TEMP   two-slope scale: n<=63 -> 4*(n-32) ; n>=63 -> 2*n   (caps at 127)
  [15]   LOAD   percent, raw
  [16:17] FREQ  MHz, big-endian u16
  [18]   checksum = sum(bytes[1..17]) % 256
  [19]   0x16                 terminator

Note: the temperature field hardware-caps at 127 (byte 255 -> 127) in all known
frame modes, so Fahrenheit display is limited to 127 F max. Celsius is full-range.
"""

FRAME_LEN = 64
TEMP_DISPLAY_MAX = 127  # hardware ceiling of the temp field


def pad(frame):
    """Zero-pad a frame to the 64-byte HID report length."""
    return bytes(bytearray(frame) + bytearray(FRAME_LEN - len(frame)))


def clamp(v, lo, hi):
    return max(lo, min(hi, int(v)))


INIT_FRAME = pad([0x10, 0x68, 0x01, 0x09, 0x0d, 0x01, 0x00, 0x00, 0x64, 0x32,
                  0x00, 0x42, 0x70, 0x00, 0x00, 0x28, 0x0e, 0x10, 0x0e, 0x16])


def encode_temp_byte(display_number):
    """Encode a number for the two-slope temp field so the panel shows it."""
    n = round(display_number)
    if n < 32:
        n = 32
    b = (2 * n) if n >= 63 else (4 * (n - 32))
    return clamp(b, 0, 255)


def build_data_frame(celsius, load_pct, power_w, freq_mhz, unit="C"):
    """Build a display frame from live sensor values.

    celsius: real CPU temperature in C (we convert to F here if unit=='F').
    unit: 'C' or 'F' (sets the on-screen label and converts the value).
    """
    p = bytearray(20)
    p[0:6] = bytes([0x10, 0x68, 0x01, 0x09, 0x0d, 0x01])
    p[6] = 0x02
    p[11] = 0x42
    w = clamp(power_w, 0, 65535)
    p[7] = (w >> 8) & 0xff
    p[8] = w & 0xff
    if unit == "F":
        display = celsius * 9 / 5 + 32
        p[10] = 1
    else:
        display = celsius
        p[10] = 0
    p[12] = encode_temp_byte(display)
    p[15] = clamp(load_pct, 0, 100)
    m = clamp(freq_mhz, 0, 65535)
    p[16] = (m >> 8) & 0xff
    p[17] = m & 0xff
    p[18] = sum(p[1:18]) % 256
    p[19] = 0x16
    return pad(p)
