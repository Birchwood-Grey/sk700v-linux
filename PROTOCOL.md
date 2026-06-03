# Sudokoo SK700V — Display Protocol

Reverse-engineered notes for the Sudokoo SK700V CPU cooler's LCD (quad-segment:
FREQ / LOAD / POWER / CPU TEMP). The device is undocumented and ships with a
Windows-only app ("MasterCraft", a rebranded DeepCool tool). This document is the
result of independent reverse engineering, cross-checked against community findings
(see Credits at the end); it is not official.

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
| 9     | power %           | 0-100, fills the progress bar under the wattage (independent of bytes 7-8) |
| 10    | unit flag         | 0 = "C", 1 = "F" (label, and the unit the temp float is in) |
| 11-14 | CPU temp          | IEEE-754 float32, big-endian, in the unit set by byte 10 |
| 15    | load              | percent, raw 1:1 (0-100) |
| 16-17 | frequency         | MHz, big-endian u16 (e.g. 10 68 = 4200 = 4.20 GHz) |
| 18    | checksum          | sum(bytes[1..17]) % 256 |
| 19    | terminator        | 0x16 |
| 20-63 | padding           | 0x00, inert |

The frame must be streamed continuously (~1-3 Hz) or the panel blanks. Sending a few
0x00-flag frames once at startup wakes/initialises the display.

### Temperature (bytes 11-14)

Temperature is a big-endian IEEE-754 single-precision float, in the unit set by byte 10:

    bytes[11..14] = struct.pack('>f', temperature_value)
    e.g. 54.0 C -> 42 58 00 00 ;  158.0 F -> 43 1e 00 00

Because it is a full 32-bit float, there is no display cap. (An earlier single-byte
analysis appeared to show a "two-slope scale" capping at 127 — that was an artifact of
holding the float's high byte at 0x42 and varying only the second byte. Encoding the
full float removes the limit; both Celsius and Fahrenheit are full-range.)

### Unit flag (byte 10)

Byte 10 sets the label ("C" vs "F"). The temperature float in bytes 11-14 must be
expressed in that same unit (the firmware does not convert), so the host converts
C -> F itself when Fahrenheit is selected.

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

## Method

Frame templates were recovered by disassembling the app's V8 bytecode; field meanings
and encodings were then mapped empirically by sending known byte values and reading the
panel. The temperature float layout and the power-percentage byte were cross-checked
against community findings (see Credits).

## Credits

Independent reverse engineering, cross-referenced with prior community work:
- gdedrouas/SK700V-display
- Nortank12/deepcool-digital-linux (and forks)

Contributions, corrections, and additional findings welcome.
