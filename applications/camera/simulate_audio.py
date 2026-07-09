#!/usr/bin/env python3
"""
MCU audio data simulator — generates realistic bee audio analysis frames
so you can verify the bee_audio_monitor.py without actual hardware.

Two modes:
  1. File mode: write binary frames to a file → verify with --replay
  2. Virtual COM mode: create a pseudo-serial port server → verify live GUI

Usage:
  python simulate_audio.py --file test_audio.bin --frames 100

  python bee_audio_monitor.py --replay test_audio.bin

  python simulate_audio.py --port COM4 --baud 115200

State progression simulation:
  Normal → Swarm Prelude → Normal → Queen Missing → Normal
  → Hornet Invasion → Normal → Abnormal → Normal ...
"""

import argparse
import math
import os
import random
import struct
import sys
import time
from typing import List, Optional


SYNC = bytes([0xAA, 0x55, 0xAA, 0x55])
FRAME_TYPE = 0x02
FRAME_SIZE = 34

BEE_STATES = {
    0: {"name": "Normal", "dom_freq": (200, 280), "low_ratio": 0.55, "mid_ratio": 0.25, "high_ratio": 0.10, "rms": (30, 80)},
    1: {"name": "Swarm Prelude", "dom_freq": (300, 480), "low_ratio": 0.25, "mid_ratio": 0.45, "high_ratio": 0.15, "rms": (80, 150)},
    2: {"name": "Queen Missing", "dom_freq": (150, 350), "low_ratio": 0.20, "mid_ratio": 0.30, "high_ratio": 0.25, "rms": (20, 60)},
    3: {"name": "Hornet Invasion", "dom_freq": (600, 1300), "low_ratio": 0.10, "mid_ratio": 0.20, "high_ratio": 0.50, "rms": (120, 250)},
    4: {"name": "Abnormal", "dom_freq": (100, 500), "low_ratio": 0.15, "mid_ratio": 0.25, "high_ratio": 0.35, "rms": (50, 120)},
}


def encode_frame(
    state: int,
    confidence: float,
    dom_freq: float,
    rms: float,
    low_e: float,
    mid_e: float,
    high_e: float,
    centroid: float,
    flatness: float,
    zcr: float,
    ts: int,
) -> bytes:
    """Encode an AudioFrame into the 34-byte binary protocol."""
    buf = bytearray(FRAME_SIZE)
    buf[0:4] = SYNC
    buf[4] = FRAME_TYPE
    buf[5] = state
    buf[6] = int(max(0.0, min(1.0, confidence)) * 100)
    _put_u16(buf, 7, int(dom_freq))
    _put_u16(buf, 9, int(rms * 100))
    _put_u32(buf, 11, int(low_e * 1_000_000))
    _put_u32(buf, 15, int(mid_e * 1_000_000))
    _put_u32(buf, 19, int(high_e * 1_000_000))
    _put_u16(buf, 23, int(centroid))
    _put_u16(buf, 25, int(flatness * 10000))
    _put_u16(buf, 27, int(zcr * 10000))
    _put_u32(buf, 29, ts)

    chk = 0
    for b in buf[4:FRAME_SIZE - 1]:
        chk ^= b
    buf[FRAME_SIZE - 1] = chk
    return bytes(buf)


def _put_u16(buf, off, val):
    buf[off] = (val >> 8) & 0xFF
    buf[off + 1] = val & 0xFF


def _put_u32(buf, off, val):
    buf[off] = (val >> 24) & 0xFF
    buf[off + 1] = (val >> 16) & 0xFF
    buf[off + 2] = (val >> 8) & 0xFF
    buf[off + 3] = val & 0xFF


def generate_frame(state: int, timestamp_ms: int, jitter: float = 0.15) -> bytes:
    """
    Generate a realistic audio analysis frame for the given bee state.

    Args:
        state: bee_sound_state_t (0-4)
        timestamp_ms: MCU tick timestamp
        jitter: random variation factor (0-1)
    """
    info = BEE_STATES[state]
    total_energy = random.uniform(0.002, 0.05)

    def _jitter(val):
        return val * (1.0 + random.uniform(-jitter, jitter))

    low_ratio = max(0.02, _jitter(info["low_ratio"]))
    mid_ratio = max(0.02, _jitter(info["mid_ratio"]))
    high_ratio = max(0.02, _jitter(info["high_ratio"]))
    vhigh_ratio = max(0.0, 1.0 - low_ratio - mid_ratio - high_ratio)

    low_e = total_energy * low_ratio
    mid_e = total_energy * mid_ratio
    high_e = total_energy * high_ratio

    dom_freq = random.uniform(*info["dom_freq"])
    rms = random.uniform(*info["rms"])
    centroid = dom_freq * random.uniform(1.0, 1.6)

    if state == 2:
        flatness = random.uniform(0.45, 0.75)
    else:
        flatness = random.uniform(0.15, 0.40)

    if state == 4:
        zcr = random.uniform(0.25, 0.45)
    else:
        zcr = random.uniform(0.05, 0.20)

    confidence = random.uniform(0.65, 0.95)

    return encode_frame(
        state=state,
        confidence=confidence,
        dom_freq=dom_freq,
        rms=rms,
        low_e=low_e,
        mid_e=mid_e,
        high_e=high_e,
        centroid=centroid,
        flatness=flatness,
        zcr=zcr,
        ts=timestamp_ms,
    )


def generate_scenario(frames_per_state: int = 20) -> bytes:
    """
    Generate a full scenario: each state appears for N frames,
    interleaved with Normal state transitions.
    """
    scenario = [
        (0, frames_per_state),
        (1, frames_per_state),
        (0, frames_per_state // 2),
        (2, frames_per_state),
        (0, frames_per_state // 2),
        (3, frames_per_state),
        (0, frames_per_state // 2),
        (4, frames_per_state),
        (0, frames_per_state),
    ]

    data = b""
    ts = 0
    for state, count in scenario:
        for _ in range(count):
            frame_bytes = generate_frame(state, ts)
            data += frame_bytes
            ts += 2000

    return data



def file_mode(path: str, frames: int):
    """Generate frames and save to a binary file for --replay testing."""
    data = generate_scenario(frames_per_state=max(10, frames // 40))
    with open(path, "wb") as f:
        f.write(data)
    print(f"[sim] Wrote {len(data) // FRAME_SIZE} frames to {path}")
    print(f"[sim] Verify with: python bee_audio_monitor.py --replay {path}")



def virtual_com_mode(port: Optional[str] = None, baud: int = 115200, interval_s: float = 2.0):
    """
    Serve simulated audio frames on a serial port.

    On Windows, use com0com (https://com0com.sourceforge.net/) to create
    a virtual COM port pair, then connect this simulator to one port and
    bee_audio_monitor.py to the other.

    On Linux/macOS, use socat:
      socat -d -d pty,raw,echo=0 pty,raw,echo=0
    Then use the two PTY paths.
    """
    try:
        import serial
    except ImportError:
        print("[sim] pyserial required: pip install pyserial")
        sys.exit(1)

    if port is None:
        print("[sim] ERROR: --port required for live mode")
        print("[sim] Set up a virtual COM pair first:")
        print("[sim]   Windows: install com0com, pair COM4<->COM5")
        print("[sim]   Linux:   socat -d -d pty,raw,echo=0 pty,raw,echo=0")
        sys.exit(1)

    try:
        ser = serial.Serial(port, baud, timeout=0.5)
    except Exception as e:
        print(f"[sim] ERROR opening {port}: {e}")
        sys.exit(1)

    print(f"[sim] Serving on {port} @ {baud} baud")
    print(f"[sim] Connect bee_audio_monitor.py to the OTHER port of the pair")
    print(f"[sim] Press Ctrl+C to stop")

    state_order = [0, 0, 1, 1, 0, 0, 2, 2, 0, 0, 3, 3, 0, 0, 4, 4, 0]
    ts = 0
    state_idx = 0

    try:
        while True:
            state = state_order[state_idx % len(state_order)]
            frame_bytes = generate_frame(state, ts)
            ser.write(frame_bytes)
            ser.flush()

            name = BEE_STATES[state]["name"]
            print(f"[sim] sent: state={name} ts={ts}", end="\r")
            ts += 2000
            state_idx += 1
            time.sleep(interval_s)
    except KeyboardInterrupt:
        print(f"\n[sim] Stopped. {state_idx} frames sent.")
    finally:
        ser.close()



def self_test():
    """Validate protocol encoding/decoding round-trip."""
    print("=" * 50)
    print("Self-test: Protocol validation")
    print("=" * 50)

    from bee_audio_monitor import decode_frame

    passed = 0
    failed = 0

    for state in range(5):
        for _ in range(10):
            frame_bytes = generate_frame(state, 0, jitter=0.1)
            decoded = decode_frame(frame_bytes)

            if decoded is None:
                print(f"  FAIL: state={state} decode returned None")
                failed += 1
                continue

            checks = [
                decoded.state == state,
                0.0 <= decoded.confidence <= 1.0,
                decoded.dominant_freq > 0,
                decoded.rms > 0,
                decoded.low_energy >= 0,
                decoded.mid_energy >= 0,
                decoded.high_energy >= 0,
                decoded.spectral_centroid > 0,
                0.0 <= decoded.spectral_flatness <= 1.0,
                0.0 <= decoded.zero_cross_rate <= 1.0,
            ]

            if all(checks):
                passed += 1
            else:
                print(f"  FAIL: state={state} values out of range")
                failed += 1

    print(f"\n  Result: {passed} passed, {failed} failed")
    print()

    print("Multi-frame extraction test:")
    data = b""
    for state in [0, 1, 2, 3, 4]:
        data += generate_frame(state, 0)
    noisy_data = generate_frame(0, 0) + b"\xFF\x00" + generate_frame(3, 0) + b"\x00" + generate_frame(2, 0)

    from bee_audio_monitor import extract_frames_from_buffer

    clean_frames, _ = extract_frames_from_buffer(data)
    print(f"  Clean buffer: {len(clean_frames)} frames extracted (expected 5)")

    noisy_frames, _ = extract_frames_from_buffer(noisy_data)
    print(f"  Noisy buffer: {len(noisy_frames)} frames extracted (expected 3)")

    all_ok = passed == 50 and len(clean_frames) == 5 and len(noisy_frames) == 3
    print(f"\nOverall: {'ALL OK' if all_ok else 'SOME FAILED'}")
    return all_ok



def preview_scenario(data: bytes):
    """Show what's in a generated scenario file."""
    from bee_audio_monitor import extract_frames_from_buffer
    from collections import Counter

    frames, _ = extract_frames_from_buffer(data)
    counts = Counter(f.state_name for f in frames)
    print("Scenario preview:")
    for name, count in counts.most_common():
        print(f"  {name:16s}: {count:4d} frames")
    print(f"  {'Total':16s}: {len(frames):4d} frames")

    print("\nState transitions:")
    prev = None
    for f in frames:
        if f.state_name != prev:
            print(f"  -> {f.state_name} (domFreq={f.dominant_freq:.0f}Hz, rms={f.rms:.0f})")
            prev = f.state_name



def main():
    parser = argparse.ArgumentParser(
        description="MCU Audio Simulator — test bee_audio_monitor.py without hardware",
    )
    parser.add_argument(
        "--file", default=None,
        help="Output binary file path (file mode)",
    )
    parser.add_argument(
        "--frames", type=int, default=200,
        help="Approx total frames to generate (default: 200)",
    )
    parser.add_argument(
        "--port", default=None,
        help="Virtual COM port for live streaming (requires com0com/socat pair)",
    )
    parser.add_argument(
        "--baud", type=int, default=115200,
        help="Baud rate for COM mode (default: 115200)",
    )
    parser.add_argument(
        "--interval", type=float, default=2.0,
        help="Seconds between frames in COM mode (default: 2.0)",
    )
    parser.add_argument(
        "--selftest", action="store_true", default=False,
        help="Run protocol encoding/decoding self-test",
    )
    parser.add_argument(
        "--preview", default=None,
        help="Preview a generated binary file without replaying",
    )
    args = parser.parse_args()

    if args.selftest:
        ok = self_test()
        sys.exit(0 if ok else 1)

    if args.preview:
        if not os.path.exists(args.preview):
            print(f"[sim] File not found: {args.preview}")
            sys.exit(1)
        with open(args.preview, "rb") as f:
            data = f.read()
        preview_scenario(data)
        sys.exit(0)

    if args.file:
        file_mode(args.file, args.frames)
        with open(args.file, "rb") as f:
            data = f.read()
        preview_scenario(data)
        return

    if args.port:
        virtual_com_mode(args.port, args.baud, args.interval)
        return

    print("No mode specified. Running quick self-test + generating example file.\n")
    self_test()
    print()

    example_path = "test_audio_example.bin"
    file_mode(example_path, 200)
    print()
    with open(example_path, "rb") as f:
        data = f.read()
    preview_scenario(data)
    print(f"\n[sim] Try: python bee_audio_monitor.py --replay {example_path}")


if __name__ == "__main__":
    main()
