#!/usr/bin/env python3
"""Debug receiver - count bytes and look for sync."""
import sys, os, struct, serial, time

SYNC = bytes([0xAA, 0x55, 0xAA, 0x55])

def save_bmp(path, data, w, h):
    row = ((w * 3 + 3) // 4) * 4
    pd = row * h
    with open(path, 'wb') as f:
        f.write(b'BM' + struct.pack('<I', 54+pd) + struct.pack('<HH', 0, 0) +
                struct.pack('<I', 54) + struct.pack('<I', 40) +
                struct.pack('<i', w) + struct.pack('<i', -h) +
                struct.pack('<H', 1) + struct.pack('<H', 24) +
                struct.pack('<I', 0) + struct.pack('<I', pd) +
                struct.pack('<i', 2835) + struct.pack('<i', 2835) +
                struct.pack('<I', 0) + struct.pack('<I', 0))
        pad = b'\x00' * (row - w * 3)
        for y in range(h - 1, -1, -1):
            for x in range(w):
                off = (y * w + x) * 2
                p = (data[off+1] << 8) | data[off]
                r = ((p >> 11) & 0x1F) << 3
                g = ((p >> 5) & 0x3F) << 2
                b = (p & 0x1F) << 3
                f.write(bytes([b, g, r]))
            f.write(pad)

def main():
    port = sys.argv[1] if len(sys.argv) >= 2 else "COM3"
    baud = int(sys.argv[2]) if len(sys.argv) >= 3 else 115200
    out = sys.argv[3] if len(sys.argv) >= 4 else os.path.join(
        os.path.expanduser("~"), "Desktop", "camera")
    os.makedirs(out, exist_ok=True)

    print(f"Camera RX {port} @ {baud} -> {os.path.abspath(out)}")

    try:
        ser = serial.Serial(port, baud, timeout=0.5)
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    buf = b""
    total_bytes = 0
    total_imgs = 0
    last_report = time.time()

    try:
        while True:
            w = ser.in_waiting
            if w == 0:
                now = time.time()
                if now - last_report > 2.0:
                    print(f"[{time.strftime('%H:%M:%S')}] recv={total_bytes}B, imgs={total_imgs}")
                    last_report = now
                time.sleep(0.2)
                continue

            chunk = ser.read(min(w, 65536))
            if not chunk:
                continue
            total_bytes += len(chunk)
            buf += chunk
            if len(buf) > 600000:
                buf = buf[-300000:]

            while True:
                idx = buf.find(SYNC)
                if idx < 0:
                    break
                if idx > 0:
                    buf = buf[idx:]

                if len(buf) < 13:
                    break
                pos = 4
                w2 = (buf[pos] << 8) | buf[pos+1]
                h2 = (buf[pos+2] << 8) | buf[pos+3]
                fmt = buf[pos+4]
                dsz = (buf[pos+5] << 24) | (buf[pos+6] << 16) | \
                      (buf[pos+7] << 8) | buf[pos+8]
                pos += 9
                if w2 == 0 or h2 == 0 or dsz == 0 or \
                   w2 > 4096 or h2 > 4096 or dsz > 10*1024*1024:
                    buf = buf[1:]
                    continue
                need = dsz + 1
                if pos + need > len(buf):
                    break
                data = buf[pos:pos+dsz]
                chk = buf[pos+dsz]
                pos += need
                exp = 0
                for b in data:
                    exp ^= b
                if exp != chk:
                    buf = buf[1:]
                    continue
                ts = time.strftime("%Y%m%d_%H%M%S")
                fp = os.path.join(out, f"cam_{ts}_{w2}x{h2}.bmp")
                if fmt == 0:
                    save_bmp(fp, data, w2, h2)
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -
                    -【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【【
                else:
                    with open(fp + ".raw", 'wb') as f:
                        f.write(data)
                total_imgs += 1
                print(f"  OK: {fp} ({dsz}B) [recv={total_bytes}B]")
                buf = buf[pos:]

    except KeyboardInterrupt:
        print(f"\nDone. {total_bytes}B recv, {total_imgs} image(s).")
    finally:
        ser.close()

if __name__ == "__main__":
    main()
