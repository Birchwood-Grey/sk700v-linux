# Operation Cold Light — Sudokoo SK700V LCD on Linux

## >>> STATUS: SOLVED (2026-06-02) — full TEMP/LOAD/POWER/FREQ monitor working on Linux. See "OPERATION COLD LIGHT COMPLETE" at end. <<<

## STATUS
- PARTIAL: Linux Python driver LIGHTS the panel (A/B keep-alive) but shows only a firmware PLACEHOLDER (32F). NO real host values are sent. Device = QUAD-SEGMENT LCD (temp/usage/watt/freq), Sudokoo firmware VID 381c. See ERRATA at end of file.
- NOT YET DECODED: FREQ / LOAD / POWER byte encoding (blocked — see below).

## DEVICE FACTS
- USB VID:PID = 381c:0003  (Sudokoo's own vendor ID, NOT DeepCool 3633)
- hidraw: /dev/hidraw10  (number can change on replug/reboot — see troubleshooting)
- USB path 1-9 / 1-9:1.0 ; Serial 0FC8E07905A6 ; HID name "SK SK700V"
- 64-byte interrupt packets, EP01 OUT (0x01), EP81 IN (0x81)
- MasterCraft is a rebranded DeepCool app (controls 15+ devices)

## THE WORKING PACKETS (the win)
Send A, sleep 0.1s, send B, sleep ~0.9s, loop forever. Stream must be continuous
or the screen blanks. Both are 64 bytes, zero-padded.

Packet A: 10 68 01 09 02 03 01 78 16  + 55 zero bytes
Packet B: 10 68 01 09 0d 01 02 00 00 0a 01 42 00 00 00 00 00 00 cf 16  + 44 zero bytes

Header 10 68 = report ID 0x10, command 0x68. Byte[4] is a sub-command/type
selector (A=0x02 "frame", B=0x0d "data"). Bytes [9]=0x0a, [11]=0x42, [18:19]=cf16
are firmware-validated constants: changing them blanks the screen, so they are NOT
free data fields. (0x42 is NOT a CRC — tested every algorithm in the crc npm pkg.)

## WHY FREQ/LOAD/POWER ISN'T DECODED YET
Every packet ever captured had those values = 0, because MasterCraft was running in
a Windows VM whose virtualized CPU reports no real sensor data. You cannot learn an
encoding from samples that are always zero. The values almost certainly DO get sent
on real hardware; we just never produced a nonzero sample.

Confirmed dead ends (don't repeat):
- VM + HWiNFO: VM can't read the real AMD chip; MasterCraft shows 0.
- Brute-forcing bytes: blocked by firmware-validated constant bytes.
- Decompiling index.jsc: V8 bytecode, no working decompiler for this version.
- Instrumenting node-hid: app's USB I/O does NOT go through node-hid.
- Instrumenting the usb module via asar override: override won't load; real I/O is
  in the native libusb / electron-edge-js (C#) layer, below file-edit reach.

## ARCHITECTURE DISCOVERED
- mastercraft_service.exe reads sensors (via HWiNFO64.dll SDK ordinals incl.
  608=HWi32Init) and serves them over a named pipe.
- Pipe: \\.\pipe\mastercraft_sensor_data ; handshake = SERVER_HELLO / CLIENT_HELLO /
  SETUP_DATA_CHANNEL / DATA_CHANNEL_READY ; data framed with magic header DE AD BE EF 5F ;
  GET_SENSOR_DATA / SENSOR_DATA exchange ; payload is double-encoded JSON.
- The Electron app (index.jsc) does the actual USB writes via libusb (usb module) /
  edge-js, NOT the service and NOT node-hid.

## THE PLAN WHEN A REAL WINDOWS PC IS AVAILABLE (the unlock)
1. Install MasterCraft + HWiNFO on the real Windows machine.
2. Plug in the SK700V. Start a USB capture (Wireshark/USBPcap on Windows, or usbmon
   from a Linux host if the device is passed through).
3. Run MasterCraft so the display shows REAL changing freq/load/power. Stress the CPU
   so values sweep across a known range.
4. Save the capture. The freq/load/power bytes fall out by diffing packets at known
   values — the same method that already worked for finding the two base packets.
5. Add those fields (plus AMD power path on Linux: /sys/class/powercap or zenpower,
   NOT the Intel intel-rapl path the reference projects use) to cooler.py.

## PUBLISHING
- github.com/Nortank12/deepcool-digital-linux — open an issue/PR; LCD protocol is
  undocumented there and maintainers don't own LCD units.
- r/linuxhardware post. Share: VID/PID 381c:0003, the two packets above, the named-pipe
  protocol, and the architecture notes.

## TROUBLESHOOTING (if the display stops after a reboot/replug)
- Confirm which hidraw is the cooler:
    for f in /sys/class/hidraw/hidraw*/device/uevent; do grep -q 381C "$f" && echo "$f"; done
- If it's not hidraw10, edit the path in ~/sk700v-controller/cooler.py.
- Permissions are handled by /etc/udev/rules.d/99-sk700v.rules (MODE 0666).

---
## SESSION 3 — protocol family identified (LCD "lq_series" dialect)
- Two dialects in this family. DIGITAL coolers (AG620/AK400/AK620): byte[1] is a
  type selector (0x13=temp, 0x4c=usage), value sent as DECIMAL DIGITS, each metric
  its own packet, init often 10 AA. LCD "lq_series" (MYSTIQUE, Assassin IV Vision,
  our SK700V): command byte[1]=0x68, sub-command at byte[4] (0x02 frame / 0x0d data).
- SK700V does NOT carry values in Packet A/B. Live-tested no-effect: digits in
  bytes[12-17]; byte[3] sweep 0x05-0x0a (the LCD format/leading-zero byte); byte[4]
  sweep. freq/load/power are SEPARATE packets MasterCraft only sends with REAL
  nonzero sensors (VM can't produce them).
- Method: strace -f -e trace=ioctl,write prints 64-byte writes in OCTAL.
- Refs: Nortank12/deepcool-digital-linux (maintainer owns NO LCD unit — we're ahead
  on SK700V), Algorithm0/deepcool-digital-info, daedlock/deepcool-lm (LCD 320x240,
  reverse-engineered), mymymy1303/qt-deepcool (MYSTIQUE: init EP0x01 cmd 0x0A
  payload EA 07 02 02 02 27 21).
- Routes without real Windows: (1) inject REAL live Linux sensor values as the
  feedback signal and brute-force the SK700V's own value packets using lq_series
  conventions; (2) software sensor spoofer feeding MasterCraft in the VM; (3) find a
  published MYSTIQUE-family capture to diff.

---
## SESSION 3 FINAL — why Packet A/B alone can't show freq/load/power
Found the MYSTIQUE 360 protocol doc (github.com/mymymy1303/qt-deepcool, PROTOCOL.md)
— closest LCD sibling to the SK700V. Key learnings:
- LCD-family DISPLAY packet carries ALL metrics together at fixed offsets, encoded as
  RAW SINGLE-BYTE INTEGERS (e.g. 34C = 0x22, 7% = 0x07), with frequency split as
  GHz-integer / GHz-decimal / MHz-little-endian. NOT floats, NOT decimal digits.
- Tested all three encodings (float, digits, raw int) across every non-constant byte
  of our Packet B, live on the display: NO field ever changed. => values are NOT in
  Packet B.
- MYSTIQUE requires a full INIT HANDSHAKE on EP 0x01 before it leaves "logo mode" and
  accepts display data on EP 0x02: cmds 0x12,0x02,0x03,0x04,0x07,0x08,0x05,0x0B,0x06,
  0x15,0x16,0x17, then mode-switch 0x0A payload EA 07 02 02 02 27 21, then status 0x10.
- CONCLUSION: SK700V's freq/load/power live in display packets we never captured, and
  are gated behind an init/mode-switch handshake we never captured. Our A+B worked only
  because MasterCraft had already initialized the device in a prior run.
- SK700V differs from MYSTIQUE: header 10 68 (vs AA 2E), 64-byte (vs 48), no HIDC
  footer, cf 16 near byte 18. So the MYSTIQUE byte map is NOT drop-in; it's a guide.

## THE ONE THING NEEDED (unchanged, now precisely scoped)
A USB capture of the Windows MasterCraft app talking to a REAL SK700V on REAL hardware,
so we capture (a) the full init handshake and (b) display packets with NONZERO values.
Everything else is solved. Without that capture, the init sequence cannot be
reconstructed by guessing (combinatorial, no feedback). This is the sole blocker.

## IF CONTRIBUTING / ASKING FOR HELP
Post our findings to github.com/Nortank12/deepcool-digital-linux (LCD discussion) — we
have more SK700V detail than anyone public. Provide: VID:PID 381c:0003, the two known
packets, this analysis. Someone with the same cooler + Windows could capture the
handshake in 10 min.

---
## SESSION 3 DECISIVE TEST — Packet B carries NO value fields (proven)
Ran a single-byte sweep of Packet B (each byte set to 0x50) watching the temperature
field, with continuous A+B streaming.
RESULT:
- Temperature NEVER changed from 32F (=0C firmware default) for ANY byte.
- Bytes [7]-[19] set to 0x50 => screen BLANKS (packet rejected). These are validated
  STRUCTURAL constants.
- Bytes [20]-[63] set to 0x50 => NO effect at all. These are inert padding the firmware
  ignores.
CONCLUSION (experimentally verified, not assumed):
- Packet B has zero renderable value fields. Every byte is either a validated structural
  constant or ignored padding. There is no offset in this packet where temp/freq/load/
  power could live.
- The 32F on screen is a FIRMWARE PLACEHOLDER for "monitoring mode active, no real data
  received." Packets A+B are HANDSHAKE/KEEP-ALIVE only — they keep the screen lit in
  monitoring layout; they do not carry the numbers.
- This explains why NOTHING we sent ever changed the display: we were editing a keep-
  alive packet that has no data fields. Not a wrong-offset problem — a wrong-packet
  problem, now proven.
- Per MYSTIQUE protocol, real values ride a separate display command that only works
  AFTER a multi-step init/mode-switch handshake. That handshake is the missing piece and
  is only obtainable by capturing the Windows app against REAL hardware.

## FINAL STATUS
Working temperature/keep-alive display on Linux: DONE and running.
Freq/load/power: blocked solely by the un-captured init handshake + data command.
This is a wrong-packet/missing-channel problem, proven by the byte-sweep above — not a
decoding problem we can brute-force. Sole unblock = real-hardware USB capture.

---
## SESSION 3 — every write-side avenue closed, read side silent (all proven)
Tests run this session and their results:
- Swept Packet A (bytes 4-30 -> 0x55): NO effect. Values are not in A.
- Swept Packet B with large values: [7]-[19] blank the screen (validated structural
  constants), [20]-[63] inert. With valid digits 0-9 (AK620 style): NO effect anywhere.
  => Packet B carries no renderable digit fields.
- Swept sub-command byte[4] across 0x01-0x20 watching for ANY reaction: none except the
  known states. No new command surfaced this way.
- AK620 dialect verbatim (0x10 0x13 temp / 0x10 0x4c util / 0x10 0xAA start): screen
  BLANKED and stayed off the whole time. => device PARSES these (acts on them) but treats
  them as a different/mode command, not "show data." Confirms a responsive command parser.
- Listened on the IN endpoint (0x81) while streaming A+B: device returned ZERO bytes.

## DEVICE INTERFACE LAYOUT (definitive, from lsusb -v)
- ONE hidraw node (/dev/hidraw10), ONE interface (bInterfaceNumber 0), TWO endpoints:
  0x81 IN (64B) and 0x01 OUT (64B). No second interface, no other hidraw node.
- => There is no alternate channel for replies. The single IN endpoint is silent under
  keep-alive traffic.

## CONCLUSION (evidence-backed, not speculation)
SK700V is a STATEFUL, SESSION-GATED segment LCD on a single 64B HID interface. It boots
locked, lights the panel from A+B keep-alive, and will not render host data (and will not
reply) until walked through an ordered UNLOCK HANDSHAKE we do not possess. Stateless
dialects (AK620) are parsed but rejected. The value/query commands are a different command
under the 0x68 scheme, never captured.

## THE SINGLE MISSING PIECE
A USB capture of Windows MasterCraft driving a REAL SK700V: the startup init/handshake
burst + the steady data packets with nonzero values. Everything upstream is solved. No
software-only, no-hardware route remains after this session's tests.

## RECOMMENDED NEXT ACTIONS (not more byte-sweeping)
1. POST to github.com/Nortank12/deepcool-digital-linux (LCD discussion): VID:PID
   381c:0003, packets A+B, single-interface layout, proof of gated channel. Recruit
   someone with the cooler + Windows to capture the handshake. We are first to document
   this device this far.
2. FALLBACK when willing: VM alarm-threshold capture (set MasterCraft temp alarm to
   70/80/90, tshark each, diff the changing byte) — now clearly worth the rebuild since
   every alternative is eliminated.

---
## SESSION 3 — COMPLETE CHANNEL ENUMERATION (from device's own HID descriptor)
Read the 126-byte report descriptor (od -t x1). Device declares usage page 0xFF00
(vendor-defined), ONE application collection, FIVE report IDs:
  - 0x02: 63-byte Feature + 63-byte Output
  - 0x03: 63-byte Feature + 63-byte Output
  - 0x04: 63-byte Feature + 63-byte Output
  - 0x05: bitfield Feature + Input (small)
  - 0x10: 63-byte Output + 63-byte Input   <-- the one our driver uses (Output only)
Also found a hiddev node for the device: /dev/usb/hiddev5 (1-9 path; dmesg "hiddev101"
is the minor number, not the filename).

EVERY channel the descriptor advertises has now been tested:
  - Output reports (0x10 etc): swept exhaustively earlier -> only A+B keep-alive works,
    no value fields render.
  - IN endpoint 0x81: listened while streaming A+B -> device returns ZERO bytes.
  - GET-feature (HIDIOCGFEATURE, _IOWR dir, 64B) on 0x02/0x03/0x04/0x05/0x10:
    all succeed, return 64 bytes, ALL ZERO.
  - SET-feature (HIDIOCSFEATURE, _IOWR dir=3, NOT write-only=1 -- that was a bug):
    calls succeed (ret 64) on 0x02/0x03/0x04/0x10, BUT device retains nothing
    (read-back still all zero) and the display never changes.
CONCLUSION: the device accepts feature writes at the USB layer but DISCARDS them in its
locked/idle state. Same gating as the output channel. There are NO undiscovered channels
-- the descriptor lists all report IDs and we have exercised every report type and both
endpoints. The blocker is a STATE the device won't enter, not a channel we haven't found.

## FINAL (complete) — the one missing piece is unchanged and now fully scoped
Only a capture of Windows MasterCraft driving REAL SK700V hardware can reveal the unlock
handshake. When captured, watch which REPORT IDs and which channel (feature vs output)
the app exercises during startup -- we now know the full inventory to compare against.

---
## SESSION 3 — KERNEL-VERIFIED CHANNEL MAP (from /sys/kernel/debug/hid/.../rdesc)
The kernel's authoritative descriptor decode (debugfs rdesc) confirms and refines the
hand-decode. One vendor application (usage page 0xFF00, app 00ff.0001), report IDs:
  - 0x02: Output + Feature, fields binary (Logical Max 1) -> FLAG/control report
  - 0x03: Output + Feature, fields binary (Logical Max 1) -> FLAG/control report
  - 0x04: Output + Feature, fields binary (Logical Max 1) -> FLAG/control report
  - 0x05: small bitfield (Report Size 1), Feature + Input
  - 0x10: Output (usage 00ff.0006) + Input (usage 00ff.0007), BOTH Logical Max 65280
          (0xFF00) = FULL-RANGE 0-255 byte fields, 63 bytes each.
KEY INSIGHT: report 0x10 is the ONLY full-range (data-carrying) report. Output 0x10 is
what our driver sends; INPUT 0x10 is the device's declared data-return channel. The
0x02/0x03/0x04 reports are binary-flag control reports (likely mode/unlock).
Most fields tagged 'Volatile' (can change on their own = sensor-data-like).

## INPUT 0x10 TESTED PROPERLY (blocking select() reads, 20s) -> SILENT
Earlier silent-listen used non-blocking polling; this used select() blocking reads.
Device emitted NO input report at all in the locked/idle state. The declared full-range
data-return channel is empty until the session is unlocked. Same gating as every other
channel.

## COMPLETE WALL-MAP (every declared channel tested, all gated)
output reports (swept) | feature GET (zeros) | feature SET (accepted, discarded) |
input report 0x10 (silent, blocking read) | raw IN endpoint (silent) | hiddev5 (init ok,
no data). Nothing in the descriptor is untested; no channels exist outside the descriptor.

## TARGETED DECODE PLAN FOR A FUTURE CAPTURE (profile upgrade from this session)
When MasterCraft traffic is captured on real hardware:
  - WATCH REPORT 0x10 for the value/data stream (it's the only full-range report).
  - WATCH REPORTS 0x02/0x03/0x04 (feature/flag) for the unlock/mode-switch sequence.
This is now a targeted decode, not a blind diff. We know which report carries data.

## SESSION 4 — DECOMPILER ROAD (re-extracted MasterCraft, all on Linux, no VM)
Re-downloaded MasterCraft-1.0.3-setup.exe (NSIS, 504MB) -> 7z extract -> $PLUGINSDIR/app-64.7z
-> 7z extract -> ~/mastercraft-app/ (full Electron app).

### Layers checked & ruled out:
- **fft-dll.dll** (the one custom .NET assembly, ~/mastercraft-app/.../resources/fft-dll.dll):
  decompiled w/ ilspycmd (8.2.0.7535, needs DOTNET_ROLL_FORWARD=LatestMajor on .NET8).
  55k lines = it's the NAudio AUDIO library. NOT device code. .NET layer RULED OUT.
- **Renderer JS** (~/asar-src/out/renderer/, extracted via npx @electron/asar):
  Plain readable JS, but it's only UI + display assets (greytemp-*.js = base64 PNG labels
  for FREQ/LOAD/POWER/TEMP) + IPC plumbing. Does NOT build packets. RULED OUT as protocol home.

### THE KEY FINDING — where the protocol actually lives:
- Renderer talks to main process via IPC. Confirmed channel names (the device "vocabulary"):
  **app/get-sensors-data** (almost certainly FREQ/LOAD/POWER fetch), app/get-fan-interface,
  app/get-device-list, app/get-systeminfo, app/update-firmware.
- Main process = **~/asar-src/out/main/index.jsc** = V8 BYTECODE (5.1MB). THIS holds the protocol.
- Strings SURVIVE in the bytecode. Confirmed via `strings index.jsc | grep`:
  - **node-hid** -> the device I/O library (known API: .write([bytes]), .sendFeatureReport([bytes]))
  - Sudokoo classes: **Sk700Controller**, Sk700AppService, SK700VMACH (Sk700Controller = packet builder)
  - handshake/connect methods: onConnect, onDisConnect, onReConnect, refreshDevice,
    registerConnectResetListener, initRpmFeedBack
  - NO raw packet bytes in strings -> they're computed in bytecode instructions.

### NEXT STEP (resume here):
- Install **View8** (free V8 bytecode disassembler) and disassemble index.jsc.
- Navigate to class **Sk700Controller**, find its node-hid .write/.sendFeatureReport calls,
  read the byte construction around onConnect (the handshake) and get-sensors-data (the value query).
- View8 needs the matching V8/Node version. index.jsc first bytes give the bytecode version tag
  (was about to check via xxd). Electron 29/30 era per the edge-js native dirs seen in unpacked modules.
- This is the hard path (instruction soup) but strings-survive means byte literals likely recoverable.

### FALLBACK (faster, reliable): VM USB-capture.
Now we know EXACTLY what to capture: traffic right after connect (the onConnect handshake) and
the response to app/get-sensors-data, on report 0x10. tshark -i usbmon1, set a known temp-alarm
value, diff the changing byte. Minutes of work vs hours of bytecode archaeology.

## ========================================================
## SESSION 5 — HANDOFF BRIEF FOR ANY NEW CHAT (READ FIRST)
## ========================================================
## A fresh chat does NOT have our history and WILL try to send Phil
## back down paths we already closed. Phil is a Linux/Python beginner
## and cannot always catch this. So: these doors are CLOSED. If a new
## chat proposes anything on this list, STOP and re-read this section.

### CLOSED DOORS — do NOT propose these, we already did them:
1. "Just try the DeepCool protocol / deepcool-digital-linux, it probably
   already works." — TESTED ON REAL HARDWARE in Session 3. We sent the
   DeepCool AK620 packets (10 13 / 10 4c / 10 AA) straight to the device.
   The screen BLANKED. The device parses these but refuses to show values.
   The SK700V is HANDSHAKE-GATED. A generic DeepCool packet will NOT work
   until we get past the unlock handshake. (Trying the prebuilt binary once
   is fine, but it is a long shot — do not frame it as "probably the answer.")
2. "Reverse-engineer the protocol from the .NET DLL (fft-dll.dll)." — DONE.
   It's the NAudio audio library. No device code. RULED OUT.
3. "Read the protocol from the renderer JavaScript." — DONE. Renderer is only
   UI + display images + IPC plumbing. No packet building. RULED OUT.
4. "Brute-force the packets / sweep bytes on the live device." — DONE in
   Session 3, every channel (output 0x10, feature get/set, input 0x10, raw
   IN endpoint, hiddev). All gated. Not a wrong-offset problem, a locked-state
   problem. Do NOT suggest more byte-sweeping.
5. "Dump strings from the bytecode to get the packet bytes." — DONE. Strings
   survive (node-hid, Sk700Controller, onConnect, app/get-sensors-data) but the
   actual packet BYTES are NOT in the strings — they're computed in the
   bytecode instructions. Strings alone will not give the handshake.

### THE ONE OPEN TASK (this is where to start):
Build a V8 bytecode disassembler for the CORRECT version and read the file
~/asar-src/out/main/index.jsc, specifically the class **Sk700Controller**.

KEY FACTS (already confirmed, don't re-derive):
- Exact version: Electron 23.3.13 -> Chromium 110.0.5481.208 -> V8 11.0.226.20.
  (An earlier guess of Electron 29/30 was WRONG and caused a d8 crash. Use 11.0.226.20.)
- index.jsc is a clean raw V8 cache, magic 0xC0DE05BC, ~5.05MB, NO packer wrapper.
  It IS decompilable — just needs a matching-version (11.0.226.20) tool.
- Prebuilt disassemblers do NOT cover 11.0.226.20, so this means BUILDING V8
  11.0.226.20 from source (depot_tools -> fetch v8 -> checkout 11.0.226.20 ->
  gclient sync -> gn gen with v8_monolithic + v8_enable_disassembler +
  v8_enable_object_print, pointer compression LEFT ON -> ninja v8_monolith ->
  compile v8dasm.cpp -> run on index.jsc). This is a multi-HOUR compile.
  Phil knows and accepted this. It is the "no VM" path.
- Inside Sk700Controller, find the node-hid .write() / .sendFeatureReport()
  calls. Read the bytes built around onConnect (the HANDSHAKE) and around
  app/get-sensors-data (the value query). Bytecode shows byte literals as
  e.g. LdaSmi [16], LdaSmi [104] — readable by hand even without full JS rebuild.

### WHAT WE'RE LOOKING FOR (the actual goal):
The ordered unlock HANDSHAKE the device needs at connect, plus the SK700V's
device-descriptor bytes (packet positions 2-7) and how FREQ/LOAD/POWER values
are encoded. Working temp display already ships (cooler.py). We only need
FREQ/LOAD/POWER, which are gated behind the handshake.

### THE FALLBACK (if View8/V8-build stops being worth it):
Windows VM with the SK700V passed through (qemu/virt-manager), run MasterCraft,
capture USB with tshark -i usbmon1. We now know to watch report 0x10, expect
a 0x68 header + 0x16 terminator + checksum (sum of bytes 1-15 mod 256). Diff a
known temp-alarm value to find the value offsets. Phil dreads the VM rebuild,
so it's the fallback, not the default.

## ===== SESSION 5 — V8 BUILD FULLY CONFIGURED (stop point) =====
## ALL SETUP DONE. Source fetched, checked out to 11.0.226.20, deps synced,
## gn gen succeeded (181 targets), disassembler+object_print flags confirmed ON.
## Python 3.14 is the system python; it only threw a harmless DeprecationWarning,
## the build works fine through it. Do NOT "fix" python unless something breaks.
##
## ONE COMMAND LEFT before the disassembler exists — THE BIG COMPILE (~30-90 min
## on the 9800X3D, runs loud, floods output, walk away while it runs):
##
##   export PATH="$HOME/depot_tools:$PATH"
##   cd ~/v8build/v8
##   ninja -C out.gn/x64.release v8_monolith
##
## When it finishes you'll have: ~/v8build/v8/out.gn/x64.release/  with libv8_monolith.a
## and a patched d8 that can dump bytecode.
##
## THEN (do this part in a FRESH CHAT with Claude, with room to read bytecode):
##  1. Build the dumper: get noelex/v8dasm (small v8dasm.cpp), compile it against
##     out.gn/x64.release/obj/libv8_monolith.a (+ V8 include dir). Claude will give
##     the exact g++ line — it needs -I include paths and to link the monolith .a.
##     (Alternative if v8dasm fights us: the patched d8 itself can dump via
##      d8 --print-bytecode, or xqy2006/jsc2js's loadjsc approach.)
##  2. Run it on the cooler's bytecode:
##       ./v8dasm ~/asar-src/out/main/index.jsc > ~/sk700v-controller/index.txt
##  3. In index.txt, find class **Sk700Controller**. Read the byte-array literals
##     (they show as LdaSmi [16], LdaSmi [104], then StaInArrayLiteral runs) in:
##       - onConnect  -> the UNLOCK HANDSHAKE (the prize; nobody else has this)
##       - the app/get-sensors-data handler -> the FREQ/LOAD/POWER value query
##     Paste those regions to Claude and we translate bytecode -> literal packets.
##
## GOAL REMINDER: temp display already ships (cooler.py). We need FREQ/LOAD/POWER,
## gated behind the handshake. The handshake is unsolved everywhere (even DeepCool's
## own MYSTIQUE LCD is uncracked) — this bytecode is the one place it exists in
## readable form. This is real RE, not a loop.

## ===== CORRECTION: "temp working" was INACCURATE (Phil flagged it) =====
## We do NOT have temperature working. What we actually have:
##   - Packets A+B (keep-alive) make the screen LIGHT UP (not black).
##   - The screen then shows 32F = 0C, which is a FIRMWARE PLACEHOLDER the
##     device generates on its own. We are NOT successfully sending it.
##   - ZERO values are confirmed sendable: not temp, not freq, not load, not power.
## So cooler.py only lights the panel; it does not display any real host data.
## The frozen 32F IS the locked-handshake state, made visible.
## The handshake (onConnect in Sk700Controller) is what unlocks the screen to
## accept ANY live value. Getting it should make temp + freq + load + power all
## sendable (same data channel, report 0x10). Do not assume temp is solved.

## ===== SESSION 5 — V8 MONOLITH BUILT ✓ + v8dasm reality check =====
## THE EXPENSIVE PART IS DONE:
##  - libv8_monolith.a BUILT (74MB) at ~/v8build/v8/out.gn/x64.release/obj/
##  - V8 source checked out at 11.0.226.20, gn configured w/ disassembler+object_print ON
##  - (the 9800X3D compiled all 1899 targets in ~2 MINUTES, not the feared hours)
##  - v8dasm cloned at ~/v8dasm (v8dasm.cpp + README.md)
##
## *** IMPORTANT: v8dasm is NOT a standalone compile. *** It works by PATCHING
## V8's source and REBUILDING, then a tiny loader triggers the patched code.
## Two complications for us:
##  (a) The README's patches are written for V8 8.7.220.25. We have 11.0.226.20.
##      The target functions likely changed names/APIs across versions, so each
##      patch must be hand-translated to OUR source. NEEDS Claude to read the
##      actual function bodies in our checkout and adapt. (This is the delicate part.)
##  (b) v8dasm.cpp is written for WINDOWS (#pragma comment(lib,...) / .lib files).
##      Must be ported to a Linux g++ command linking libv8_monolith.a + V8 includes.
##
## THE FOUR PATCHES (from v8dasm README — must be adapted to 11.0 source):
##  1. src/snapshot/code-serializer.cc, in CodeSerializer::Deserialize, after
##     maybe_result -> result succeeds, add:
##        result->GetBytecodeArray().Disassemble(std::cout); std::cout<<std::flush;
##  2. src/diagnostics/objects-printer.cc, in SharedFunctionInfo::SharedFunctionInfoPrint,
##     before final os<<"\n": if HasBytecodeArray() -> GetBytecodeArray().Disassemble(os).
##  3. src/diagnostics/objects.cc (or wherever HeapObjectShortPrint lives in 11.0),
##     OBJECT_BOILERPLATE_DESCRIPTION_TYPE case -> also print ObjectBoilerplateDescription.
##  4. same file, FIXED_ARRAY_TYPE case -> also print FixedArray elements.
##  (NOTE: file paths/function bodies may differ in 11.0 — VERIFY each before editing.)
##  Then: ninja -C out.gn/x64.release v8_monolith  (INCREMENTAL rebuild = fast)
##  Then: port v8dasm.cpp to Linux, g++ link against libv8_monolith.a + -I include dirs.
##  Then: ./v8dasm ~/asar-src/out/main/index.jsc > ~/sk700v-controller/index.txt
##  Then: find Sk700Controller; read byte literals (LdaSmi [16],[104], StaInArrayLiteral)
##        in onConnect (HANDSHAKE) + app/get-sensors-data handler.
##
## RESUME (fresh chat): "V8 11.0 monolith is built. Help me adapt the 4 v8dasm
## patches to my 11.0 source, rebuild, port v8dasm.cpp to Linux, and dump index.jsc."
## SESSION 6 — v8dasm BUILT ✓ (V8 11.0.226.20 disassembler, native Fedora 44, no VM)
Built v8_monolith from the 11.0.226.20 checkout earlier; this session = winning the link/compile
of the standalone v8dasm tool against it. The fight was entirely C++ runtime/ABI, not V8.

### THE WORKING BUILD (use this, ignore everything below it):
    cd ~/v8dasm && V8=~/v8build/v8
    g++ -std=c++17 \
      -I$V8/include -I$V8/out.gn/x64.release/gen/include \
      -DV8_COMPRESS_POINTERS -DV8_ENABLE_SANDBOX \
      v8dasm_linux.cpp \
      $V8/out.gn/x64.release/obj/libv8_monolith.a \
      -lpthread -ldl -lm -o v8dasm
    # -> link exit 0, ~29M binary. (warn_unused_result warning is cosmetic.)
    ./v8dasm ~/asar-src/out/main/index.jsc > ~/sk700v-controller/index.bytecode.txt

### KEY INSIGHT (why it kept failing):
- args.gn has **use_custom_libcxx = false** => the monolith was built against SYSTEM libstdc++,
  NOT Chromium's `Cr`-namespace libc++. So ALL the -D_LIBCPP_ABI_NAMESPACE=Cr / -nostdinc++ /
  V8-libc++ -isystem flags (inherited from an Electron-flavored recipe) were WRONG.
- The real wall was just: V8's pinned bundled clang can't parse Fedora 44's GCC-16 headers.
  Fix = compile with Fedora's own **g++ 16**, which speaks both the GCC-16 headers AND the same
  libstdc++ ABI the monolith used. No libc++ flags at all.

### DEAD ENDS (do NOT retry):
- $CLANG (V8's bundled clang) + Cr libc++ flags        -> undefined `std::Cr::*` (no libc++ in tree/build)
- find libc++.a / libc++ *.o in out.gn/x64.release     -> NONE exist (use_custom_libcxx=false)
- $CLANG -stdlib=libc++                                 -> 'iostream' not found (clang ships no libc++ headers here)
- $CLANG --gcc-toolchain=.../14                         -> dir doesn't exist; Fedora only has GCC 16
- sudo dnf install gcc-toolset-14                       -> no such package (that's a RHEL/CentOS thing)
- KEEP -DV8_COMPRESS_POINTERS -DV8_ENABLE_SANDBOX (V8 build flags; must match args.gn or runtime crash)

### NEXT STEP (resume here): READ THE DUMP
- Anchor on surviving string literals (names are stripped — kConsumeCodeCache replay):
  grep get-sensors-data / get-fan-interface / onConnect / initRpmFeedBack in index.bytecode.txt
- Packet bytes = runs of `LdaSmi [N]` -> `StaInArrayLiteral`. Known: 16=0x10 report id,
  104=0x68 status header, 22=0x16 terminator (matches DeepCool). 
- PRIZES v8dasm gives that deepcool-digital-linux can't: the bytes[2..7] device descriptor +
  the onConnect HANDSHAKE sequence.
- Decoder ring: src/devices/{ld,ls,ch,ak620_pro}.rs in Nortank12/deepcool-digital-linux.

## SESSION 6 (cont.) — v8dasm DUMPED ✓ ; live probe = screen silent ; handshake is the wall
### v8dasm recursion fixed → FULL dump obtained
- Patched src/snapshot/code-serializer.cc (CodeSerializer::Deserialize): after the
  ToHandle(&result) block, iterate SharedFunctionInfo::ScriptIterator(isolate, Script::cast(
  result->script())) and Disassemble() every SFI with HasBytecodeArray(). ninja v8_monolith,
  relink with the g++ line. Result: index.bytecode.txt = 171,982 lines (was 31).
### What the dump GAVE us:
- Confirmed channels/handlers (string literals survive): sk700/get-device-info,
  sk700/update-device-info, handleGetDeviceInfo, handleUpdateDeviceInfo (+ sk620 siblings).
- The WRITER function (SFI @0x1ba1001d10ea, block ~line 121224): reads cpuTemperature/usage/
  power/cpuClock(frequency)/fanRpm (+gpu mirror) + an "F" (Fahrenheit) flag, builds packets via
  CreateArrayLiteral [22] and [24], then TWO sends: device.write(...) then device.sendReport(...).
  => confirms 2-write pattern + sensor set + node-hid call path.
### What the dump CANNOT give (hard limit):
- onConnect (SFI 0x1ba100190bf1) and handleUpdateDeviceInfo (SFI 0x1ba10020c215/ce29) were
  serialized LAZY — no bytecode in cache, skipped by the walk. The handshake + per-value digit
  insertion are NOT recoverable statically without forcing those to compile (needs running the
  main process w/ fake node-hid+electron) OR a boilerplate-dump patch (ArrayBoilerplateDescription).
- The fixed bytes (10 68 .. cf 16) live inside CreateArrayLiteral TEMPLATES, not the instruction
  stream — that's why no LdaSmi[16]/StaInArrayLiteral digit-stuffing is visible.
### LIVE HARDWARE (device is present & writable):
- lsusb: 381c:0003 "SK SK700V" = /dev/hidraw10 (crw-rw-rw-, no sudo needed).
- USB descriptor: ONE HID interface, EP 0x01 OUT / 0x81 IN, 64-byte packets. hidraw10 IS correct target.
- find_dev.py parses HID_ID=0003:0000381C:00000003 correctly (orig matcher was too literal).
- Real CPU temp sensor = /sys/class/hwmon/hwmon3/temp1_input  [Tctl]  (~43-45C).
- PROBE RESULT: wrote 10 68 00 09 {02|0d} {tens}{ones} .. cf 16 to hidraw10. Writes succeed, NO
  error, but SCREEN UNCHANGED. Tried report-id variants (0x10-first, 0x00-prefix, RID+body): none
  flickered. `cat /dev/hidraw10` for 5s returned NOTHING (device emits no input/ack).
  => strongly implies device needs onConnect INIT HANDSHAKE before it accepts data frames.

### NEXT STEP (resume here) — GET THE HANDSHAKE VIA CAPTURE (handshake is sensor-INDEPENDENT!)
- The old VM-capture blocker (VM feeds zeros → no VALUE packets) does NOT apply to the handshake:
  MasterCraft sends init on connect regardless of sensor values. So capture just the FIRST burst.
- Plan: Windows VM + SK700V USB passthrough + Wireshark/USBPcap (or host usbmon if URBs visible).
  Capture the OUT transfers on connect BEFORE any 10 68 value frames = the onConnect sequence.
- Then: live probe on /dev/hidraw10 = replay handshake FIRST, then sweep value frame (slots/encoding
  for the digits — BCD pair 05 04="54" still the leading guess). Screen = the oracle.
- scripts: ~/sk700v-controller/sk700_probe.py , find_dev.py
- DECISION on the table: capture handshake (recommended, collapses hardest unknown) vs brute-force
  init+encoding blind (grim: too many simultaneous unknowns vs binary dark/not-dark signal).

## SESSION 7 PLAN — LAPTOP USB CAPTURE OF THE INIT HANDSHAKE + DATA COMMAND
Confirmed via search: NO old .pcap exists. We have only keep-alive Packet A/B (lit screen,
no values). The init/mode-switch handshake + the value command were NEVER captured. This
session captures them on a Windows LAPTOP driving the real SK700V (handshake is sensor-
independent; values need REAL nonzero sensors, which the laptop's CPU provides).

### CROSS-READ RESULT (A/B vs bytecode) — what the capture must resolve:
- A/B byte map: [0]10 reportID [1]68 cmd [2]01 const [3]09 LCDlayout [4]=TYPE(A=02 "frame",
  B=0d "data") ... [end]0x16 ; B has cf 16 trailer ([cf]=checksum/flag?).
- Values are NOT in A/B (output writes, proven). Bytecode writer calls BOTH write() AND
  sendReport(). => values almost certainly ride sendReport = a SEPARATE report channel
  (likely a FEATURE / SET_REPORT), not the interrupt-OUT keep-alive. THIS is why editing
  A/B never changed the display.
- The data command has its OWN [4] selector (NOT 0x02 or 0x0d) that we have never seen.
- CAPTURE CROSSHAIRS: (1) transport of value pkt = interrupt-OUT vs feature/SET_REPORT?
  (2) its [4] byte? (3) the init/unlock burst before steady state? (4) digit encoding?

### PHYSICAL SETUP (cooler stays mounted; only the USB data cable moves):
1. Power off PC, open side panel.
2. Unplug the screen's USB cable from JUSB4. LEAVE fan/pump power plugged in (cooling
   continues; CPU never uncooled). Desktop screen will go blank during capture - normal.
3. Cooler USB cable -> MZHOU adapter 9-pin male pins (keyed, one way) -> adapter USB-A ->
   laptop USB port.
### ENUMERATE-TEST GATE (do BEFORE any capture):
4. On laptop: Device Manager / listen for chime. Confirm new HID device appears
   (SK SK700V, VID 381c PID 0003). If nothing: reseat / check adapter. DO NOT proceed
   until it enumerates.
### SOFTWARE (laptop, Windows):
5. Install MasterCraft (same installer). Install Wireshark + enable USBPcap during setup.
   Reboot if prompted.
### CAPTURE:
6. Wireshark -> start capture on the USBPcap interface(s) (capture all if unsure which bus).
7. Launch MasterCraft. Let it connect + run ~30s showing real values. Toggle units (F/C)
   to capture that command too.
8. WRITE DOWN the displayed numbers at a marked moment: temp, clock, power, load, fan
   (these are the laptop's INTEL values - needed to match bytes). NOTE: decode-small-
   verify-large, ESPECIALLY power (laptop ~2-digit W vs your 9800X3D 3-digit W).
9. Stop. Save as ~/sk700v_connect.pcapng. Bring file back to Linux PC.
### READ THE CAPTURE (targets):
- INIT BURST = first OUT transfers right after attach / MasterCraft-open, before steady
  value frames. These are the handshake packets we DON'T already have (vs known A/B).
  Note report IDs + whether control/SET_REPORT (feature) or interrupt-OUT (EP 0x01).
- VALUE PKT = packet whose bytes change as sensors change. Find the written-down numbers
  in its bytes => encoding (watch for BCD digit pairs). Note its [4] selector + transport.
- Does cf (checksum?) change with payload?
### REPLAY (back on Linux, cable returned to JUSB4, /dev/hidraw10):
- Send captured init sequence IN ORDER, then a value pkt with live 9800X3D temp in the
  decoded slot. Watch screen.
- If temp shows: map freq/power/load/fan, wrap in a loop reading Linux sensors
  (Tctl = /sys/class/hwmon/hwmon3/temp1_input ; load from /proc/stat ; power via powercap/
  zenpower if available) and write a few times/sec. THEN verify your 3-digit power on screen.
### CONTINGENCIES:
- Init may be CALL-AND-RESPONSE (device replies on 0x81 IN, next pkt depends on reply) -
  capture shows the full exchange; replay must read + react, not just blast bytes.
- If values are FEATURE reports: on Linux hidraw use HIDIOCSFEATURE ioctl (not plain write).
  probe_setfeat.py / probe_feature.py are starting points.

## SESSION 7 PREP FINDINGS (pre-capture, 2026-06-01)
Reviewed all probe scripts + re-ran listener against live device. Two results that shape replay:

1. DEVICE IS SILENT to keep-alive. probe_read10.py (blocking reads + select, 20s, while
   streaming A+B) => "NO input report received." 
   => LIKELY FIRE-AND-FORGET (host talks, device renders, never replies). Replay can be a
      blind fixed sequence. CAVEAT: only proves silence to A/B, not to init packets. CONFIRM
      in capture: look for ANY IN transfers (device->host) during MasterCraft connect.
      - No INs during init  => truly fire-and-forget, replay blind. (simplest driver)
      - INs present         => call-and-response, replay must read+react.

2. DIGIT ENCODING = DECIMAL (supported). DivSmi [10] found at line ~121068, INSIDE the
   writer block (the SFI with cpuTemperature/power/write/sendReport in its const pool).
   => values split into base-10 digits (tens/ones) before going in the packet = BCD-pair
      theory backed. (DivSmi [100] hits elsewhere are likely UI %/scaling, not packet path.)

3. EARLIER PROBE NULLS ARE NOT REAL NEGATIVES. probe_datacmd.py (swept [4]=01,03,04,05,06,
   07,08,0b,0c,0e,0f,10,11,12) and probe_feat_live.py (feature reports rid 02/03/04/10) all
   ran while device was LOCKED (no unlock handshake first). Their "nothing happened" results
   are INCONCLUSIVE, not ruled out. After capture+unlock, RE-TEST the feature channel and the
   [4] command byte — they are still live candidates.

4. ASSETS READY FOR REPLAY:
   - cooler.py = working keep-alive (A+B @ ~1Hz) = foundation; final driver = this + unlock
     prepended once + value packet/feature in loop with live digits.
   - probe_feat_live.py = correct HIDIOCSFEATURE/GFEATURE tool (right _IOWR dir, write+readback)
     = ready if capture shows values ride SET_REPORT (matches bytecode 'sendReport' call).
   - Tried [4] list above = cross-check vs whatever [4] the capture reveals.

## CORRECTION TO TOP "DEVICE FACTS" (added 2026-06-01)
The early line "Decompiling index.jsc: no working decompiler for this version" is now
OBSOLETE. We BUILT one (v8dasm vs V8 11.0.226.20) and dumped 171,982 lines (Session 6).
The decompile's limit was NOT the tool — it was that onConnect + the value-insertion
function shipped LAZY (no bytecode in the cache). So the handshake is unrecoverable from
THIS .jsc, but not because decompiling failed. Capture remains the path.

## SESSION 7 PRE-CAPTURE TEST — lq_series packet tried live, REJECTED (2026-06-01)
Built the exact deepcool lq_series STATUS packet (header 10 68 01 08 0c 01 02, power BE u16,
temp BE f32, usage byte, freq BE u16, checksum=sum[1..16]%256, term 0x16) and streamed it
to /dev/hidraw10 with real live Tctl temp.
- test_lq.py (lq packet ALONE, no keep-alive): screen BLACK whole time. Writes succeeded,
  no errors. Device rejected it AND nothing held panel lit.
- test_lq_combo.py (A/B keep-alive + lq packet, headers 8,12 AND 9,13): phase 1 (A/B only)
  LIT the panel = baseline good. Phases 2+3 (lq packet added) = NO visible change at all.
RESULT: the lq_series data packet is IGNORED in the locked state, with both the reference
header (8,12) and our keep-alive's header (9,13). Confirms Session 3: device stays lit on
A/B but will not render host data until an unlock/mode-switch it has not received.
=> The free shortcut (be a plain lq_series device) is CLOSED. Capture remains required.
   Encoding (f32 temp etc.) was never reached - the lock is upstream of it. Cosmetic notes:
   RAPL energy_uj not readable as user (power unavailable w/o root/zenpower); cpu0 freq reads
   are single-core-twitchy (603<->5200) - both irrelevant until unlock is solved.

## ============================================================
## ERRATA & CURRENT TRUTH (2026-06-01) — supersedes any older claim it contradicts
## Format: [topic] stale claim -> correction.
## ============================================================

[DEVICE TYPE] Old top line "full-color LCD."
  -> SK700V is a QUAD-SEGMENT LCD: 4 fixed fields (temp / usage / wattage / frequency),
     confirmed by Sudokoo product page + Tom's Hardware + KitGuru. Monitoring = send VALUES,
     not pixels. (app uploadGif/uploadMedia hint a SEPARATE image path may exist, untested.)

[TEMP "WORKING"] Old top line "shows CPU temperature."
  -> FALSE (already flagged Session 5). Driver only LIGHTS the panel; shows firmware
     PLACEHOLDER 32F. Zero real values sent. Nothing works beyond lighting the panel.

[FIRMWARE ORIGIN] (new, key) SK700V = Sudokoo VID 381c:0003, NOT DeepCool 3633. MasterCraft
  is rebranded DeepCool sw, so SK700V speaks the DeepCool family grammar (10 68 header) but
  runs SUDOKOO firmware with its OWN device-specific unlock. => DeepCool/lq init does NOT
  transfer. The unlock lives only in MasterCraft onConnect.

[DECOMPILER] Old "confirmed dead end: no working decompiler for this V8 version."
  -> OBSOLETE. Built v8dasm (V8 11.0.226.20), dumped 171,982 lines (Session 6). Limit was
     LAZY functions (onConnect + device-command family have no bytecode in cache), NOT the tool.

[lq_series SHORTCUT] (new, this session) Tested the deepcool lq_series STATUS packet live
  (hdr 10 68 01 08 0c 01 02; power BE u16; temp BE f32; usage byte; freq BE u16;
  cksum=sum[1..16]%256; term 0x16). IGNORED in locked state with BOTH the reference header
  (8,12) and our keep-alive header (9,13). A/B still lit the panel; lq packet changed nothing.
  => SK700V is lq-FAMILY but needs its own unlock first. This shortcut is CLOSED.

[VALUE ENCODING] Old guess: BCD digit-pairs.
  -> Superseded. lq_series encodes temp = 4-byte BE FLOAT, usage = plain byte, power/freq =
     BE u16 (not BCD). This is the LEADING hypothesis for the SK700V value packet but
     UNCONFIRMED (we never got past the lock to test it). Old DivSmi[10] "digits" likely UI.

[VM CAPTURE] Sessions 3-5 called VM USB-capture the reliable fallback.
  -> Refined: a VM feeds MasterCraft ZERO sensors -> no VALUE packets (only keep-alive).
     Session 6's "unlock is sensor-INDEPENDENT" is partly right (the unlock fires on connect
     regardless), so a VM could yield the UNLOCK -- but not values. CHOSEN PATH = capture on a
     real Windows LAPTOP (real Intel sensors) so ONE capture gets BOTH unlock AND values.
     Reminder: decode-small-verify-large (laptop power 2-digit vs 9800X3D 3-digit).

[REPEATED "FINAL STATUS"] Several older sections each declare themselves final; they AGREE
  (capture the unlock) so not contradictory, but the Session 7 plan + this ERRATA are the
  current authority. In hand: channel map (0x10=data, 0x02/03/04=control/unlock flags),
  frame grammar, command vocabulary, value-layout hypothesis. Missing: the onConnect unlock.

[PUBLIC STATE] No public RE of the SK700V or Assassin IV VC Vision exists (2026-06-01) -
  reviews only. Nothing to borrow; the unlock must be captured.

## ============================================================
## *** SOLVED — OPERATION COLD LIGHT COMPLETE (2026-06-02) ***
## Full live CPU monitor working on Linux: TEMP / LOAD / POWER / FREQ all correct.
## ============================================================

HOW IT WAS CRACKED (the path that worked):
- Re-dumped index.jsc with v8dasm + a boilerplate-recursion patch (added FixedArray/
  ArrayBoilerplateDescription element printing to the code-serializer patch). This exposed
  the packet TEMPLATES that were eager (the unlock onConnect stayed lazy, but the templates
  were enough).
- Found the "show" flag: byte[6]=0x02 DISPLAYS data; byte[6]=0x00 = init/clear (triggers the
  boot animation). Our old keepalive A/B never sent a 0x02 data frame with values -> that's
  why the screen was lit-but-blank for 6 sessions. NO multi-step unlock handshake was needed;
  a correctly-formed 0x02 frame is accepted directly. (The capture/laptop plan was unnecessary.)
- Mapped every field live on the panel with a self-paced sweep (send known byte -> read screen).

THE SOLVED PROTOCOL (SK700V, quad-segment LCD, /dev/hidraw10, report 0x10, 64-byte frame):
  Data frame = 20 meaningful bytes, zero-padded to 64:
    [0..5] = 10 68 01 09 0d 01     header
    [6]    = 0x02                  SHOW flag (0x02 display / 0x00 init-clear)
    [7]    = 0x00
    [8]    = POWER  (raw watts, 1 byte, 1:1)
    [9],[10] = 0x00
    [11]   = 0x42                  structural constant
    [12]   = CPU TEMP, TWO-SLOPE scale (Celsius):
               C <= 63 :  byte = 4 * (C - 32)      (display C = byte/4 + 32)
               C >= 63 :  byte = 2 * C             (display C = byte/2)
    [13],[14] = 0x00
    [15]   = LOAD   (raw percent, 1 byte, 1:1)
    [16:17]= FREQ   MHz, BIG-ENDIAN u16  (e.g. 4200 -> 0x10 0x68 -> "4.20 GHz")
    [18]   = CHECKSUM = sum(bytes[1..17]) % 256
    [19]   = 0x16                  terminator
  Stream continuously (~1-3 Hz) or panel blanks. Send a few 0x00-flag frames once at start.

VERIFIED FIELD MAP (from live sweep, not assumed):
  byte8=71 ->POWER 71 ; byte15=71 ->LOAD 71 ; byte12=100 ->TEMP 57 (=100/4+32) ;
  byte16,17=0x1388 ->FREQ 5.00 ; 0x09C4 ->2.50 ; ALL-distinct frame read TEMP/LOAD/POWER/FREQ
  exactly as sent. Temp two-slope confirmed: bytes 40/80/120/160/180 -> 42/52/62/80/90 C.

ENCODING CORRECTIONS vs earlier guesses:
  - NOT BCD digit pairs, NOT 4-byte float (those were the lq_series-family hypothesis; the
    SK700V uses single raw bytes + one 2-byte BE freq + the temp two-slope). DivSmi[10] in the
    bytecode was UI formatting, not packet encoding.
  - byte[6] flag, not a handshake, was the whole blocker. "Handshake-gated" (Session 3) was
    WRONG in spirit: the device wasn't waiting for an unlock sequence, it was waiting for a
    frame with the show flag set. Our probes used the wrong flag/frame, never the right one.

LINUX SENSOR SOURCES (Fedora 44, Ryzen 9800X3D):
  TEMP  = k10temp Tctl (/sys/class/hwmon/hwmon*/temp1_input where name=k10temp)
  LOAD  = /proc/stat delta
  POWER = RAPL package energy: /sys/class/powercap/intel-rapl:0/energy_uj (delta/time).
          ROOT-LOCKED by default -> udev rule: SUBSYSTEM=="powercap", ACTION=="add",
          RUN+="/bin/chmod -R a+r /sys/devices/virtual/powercap/intel-rapl"
          (RUN may not fire on `udevadm trigger`; manual chmod works now, reboot/service for
          persistence. A systemd oneshot chmod is the bulletproof version - TODO.)
  FREQ  = max of cpu*/cpufreq/scaling_cur_freq (peak boost), lightly smoothed.

HEALTHY 9800X3D RANGES (for reference): base 4.7 / boost 5.2 GHz (5.25 seen, normal);
  Tjmax 89C (idle ~40-51, gaming 60-75, stress low-80s); PPT ~162W (idle ~40, gaming 70-120).

WORKING DRIVER: ~/sk700v-controller/sk700v_monitor.py  (all four fields live).
TODO (polish, not protocol): systemd auto-start service (+ fold in RAPL chmod), C/F toggle,
  update-rate config, README + protocol table, open-source on GitHub, post findings to
  Nortank12/deepcool-digital-linux LCD discussion (we're first to crack this device).
