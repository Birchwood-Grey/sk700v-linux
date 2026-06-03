# Sudokoo SK700V — Display Protocol

Reverse-engineered notes for the Sudokoo SK700V CPU cooler's LCD (quad-segment:
FREQ / LOAD / POWER / CPU TEMP). The device is undocumented and ships with a
Windows-only app ("MasterCraft", a rebranded DeepCool tool). This document is the
result of independent reverse engineering; it is not official.

## Device

- USB HID, Vendor ID 381c, Product ID 0003
- On Linux it appears as a hidraw node (e.g. /dev/hidraw10); the number can change.
  Match by VID 381C in /sys/class/hidraw/hidraw*/device/uevent.
- All communication is HID output reports on report ID 0x10, 64 bytes,
  zero-padded after the meaningful bytes.

## Data frame (display values)

20 meaningful bytes, padded to 64. This is the frame that shows live stats:

| Byte  | Meaning           | Encoding |
|-------|-------------------|----------|
| 0     | report ID         | 0x10 |
| 1     | command           | 0x68 |
| 2-5   | frame type        | 01 09 0d 01  (the 0d selects the sensor-data frame) |
| 6     | show flag         | 0x02 = display values; 0x00 = init/clear (boot animation) |
| 7     | power high byte   | power = byte7 * 256 + byte8  (big-endian u16, watts) |
| 8     | power low byte    | |
| 9     | flag/config       | non-power; observed 0x0a in some frames; effect unconfirmed |
| 10    | unit flag         | 0 = label "C", 1 = label "F" (relabel only — see note) |
| 11    | constant          | 0x42 (required; not a checksum) |
| 12    | CPU temp          | two-slope scale (see below); caps at 127 |
| 13-14 | unused            | confirmed inert (0x00) |
| 15    | load              | percent, raw 1:1 (0-100) |
| 16-17 | frequency         | MHz, big-endian u16 (e.g. 10 68 = 4200 = 4.20 GHz) |
| 18    | checksum          | sum(bytes[1..17]) % 256 |
| 19    | terminator        | 0x16 |
| 20-63 | padding           | 0x00, inert |

The frame must be streamed continuously (~1-3 Hz) or the panel blanks. Sending a few
0x00-flag frames once at startup wakes/initialises the display.

### Temperature scale (byte 12)

The displayed temperature number maps to byte 12 via a two-slope curve
(verified by sweeping byte values and reading the panel):

    displayed <= 63 :  byte = 4 * (displayed - 32)      (display = byte/4 + 32)
    displayed >= 63 :  byte = 2 * displayed             (display = byte/2)

The field hardware-caps at 127 (byte 255 -> 127) in every tested frame mode
(0x0c and 0x0d). Celsius covers the full realistic range; Fahrenheit is limited
to 127 F because the unit flag only changes the label, not the scale.

### Unit flag (byte 10)

Byte 10 changes only the label ("C" vs "F"); it does NOT convert the value.
To display Fahrenheit correctly, the host must convert C -> F itself and encode
the Fahrenheit number into byte 12 (subject to the 127 cap above).

## Init / clear frame

Sent a few times at startup. Same header with the show flag = 0x00:

    10 68 01 09 0d 01 00 00 64 32 00 42 70 00 00 28 0e 10 0e 16

Setting the show flag to 0x00 triggers the display's boot animation.

## Other observed commands (not fully decoded)

- Report 0x05 (10 68 05 01 01 <value> <checksum> 16): seen in firmware with values
  1, 13, 14, 27, 31. Replaying these verbatim produced no visible change. Purpose
  unknown — not brightness, as far as tested.
- 16-byte 10 68 01 09 0c ... frames and the bytecode symbols setDisplayAreaStatus /
  setThermometerAreaStatus likely control display modes/areas. Unexplored.
- The Windows app's writer referenced GPU fields (gpuTemperature, gpuUsage, gpuPower,
  gpuClock) — the device may have a GPU display mode. Unexplored.

## Open questions

- High-range Fahrenheit (>127 F): achievable in any mode? Would need a capture of the
  official app running in F under load.
- Brightness control: which command, if any?

## Met
