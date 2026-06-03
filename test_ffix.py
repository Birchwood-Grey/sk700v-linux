#!/usr/bin/env python3
import time, glob, sys
sys.path.insert(0, '.')
from sk700v import protocol, sensors
dev = sensors.find_hidraw() or '/dev/hidraw10'
print(f"Device: {dev}")
print("Sending FAKE 70C in Fahrenheit mode (= 158F). Old code capped at 127.")
print("Watch the CPU TEMP field — does it show ~158 F? Ctrl+C to stop.")
with open(dev, 'wb') as d:
    for _ in range(3): d.write(protocol.INIT_FRAME); d.flush(); time.sleep(0.3)
    frame = protocol.build_data_frame(70, 25, 45, 5200, unit="F", power_pct=40)
    print("frame:", ' '.join(f'{x:02x}' for x in frame[:20]))
    try:
        while True:
            d.write(frame); d.flush(); time.sleep(0.25)
    except KeyboardInterrupt:
        print("\nStopped.")
