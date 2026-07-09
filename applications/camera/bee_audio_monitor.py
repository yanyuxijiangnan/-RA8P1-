#!/usr/bin/env python3
"""
Bee audio monitor — receive, visualize, and log bee sound analysis from the MCU.

Connects to the board via UART, receives binary audio analysis frames from
the bee_audio_sender module, and provides:
  - Real-time audio feature visualization (spectrum bands, frequency, RMS)
  - Bee state classification display with color-coded alerts
  - CSV logging for long-term monitoring
  - Offline mode: parse saved UART capture logs

Protocol (34 bytes per frame, matches bee_audio_sender.c):
  SYNC:    AA 55 AA 55     (4B)
  type:    0x02             (1B)
  state:   uint8            (1B)  0=Normal, 1=Swarm, 2=Queen, 3=Hornet, 4=Abnormal
  conf:    uint8            (1B)  confidence 0-100
  domFq:   uint16_be        (2B)  dominant frequency Hz
  rms:     uint16_be        (2B)  RMS * 100
  lowE:    uint32_be        (4B)  low band energy * 1e6
  midE:    uint32_be        (4B)  mid band energy * 1e6
  highE:   uint32_be        (4B)  high band energy * 1e6
  centr:   uint16_be        (2B)  spectral centroid Hz
  flat:    uint16_be        (2B)  flatness * 10000
  zcr:     uint16_be        (2B)  zero-crossing rate * 10000
  ts:      uint32_be        (4B)  timestamp (tick)
  chk:     uint8             (1B)  XOR checksum

Usage:
  python bee_audio_monitor.py COM3
  python bee_audio_monitor.py COM3 --no-gui
  python bee_audio_monitor.py --replay capture.log
"""

import argparse
import csv
import os
import struct
import sys
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Tuple


BEE_STATE_NAMES = {
    0: "正常嗡鸣",
    1: "分蜂前奏",
    2: "蜂王缺失",
    3: "胡蜂入侵",
    4: "异常躁动",
}

STATE_COLORS = {
    0: (0, 200, 0),
    1: (255, 165, 0),
    2: (255, 0, 255),
    3: (255, 0, 0),
    4: (200, 200, 0),
}

import matplotlib
_matplotlib_available = False
try:
    matplotlib.use("TkAgg")
    from matplotlib import font_manager
    _cn_fonts = [f.name for f in font_manager.fontManager.ttflist
                 if f.name in ("Microsoft YaHei", "SimHei", "WenQuanYi Micro Hei", "Noto Sans CJK SC")]
    _cn_font = _cn_fonts[0] if _cn_fonts else None
    if _cn_font:
        matplotlib.rcParams["font.sans-serif"] = [_cn_font, "SimHei", "DejaVu Sans"]
        matplotlib.rcParams["axes.unicode_minus"] = False
    _matplotlib_available = True
except Exception:
    pass


@dataclass
class AudioFrame:
    """Decoded audio analysis frame from the MCU."""
    state: int
    confidence: float
    dominant_freq: float
    rms: float
    low_energy: float
    mid_energy: float
    high_energy: float
    spectral_centroid: float
    spectral_flatness: float
    zero_cross_rate: float
    timestamp_ms: int
    local_time: float = 0.0

    @property
    def state_name(self) -> str:
        return BEE_STATE_NAMES.get(self.state, "Unknown")

    @property
    def state_color(self) -> Tuple[int, int, int]:
        return STATE_COLORS.get(self.state, (128, 128, 128))

    @property
    def is_alert(self) -> bool:
        return self.state != 0 and self.confidence > 0.55



SYNC = bytes([0xAA, 0x55, 0xAA, 0x55])
FRAME_SIZE = 34


def decode_frame(data: bytes) -> Optional[AudioFrame]:
    """Decode a 34-byte binary audio frame. Returns None on checksum error."""
    if len(data) < FRAME_SIZE:
        return None
    if data[0:4] != SYNC:
        return None
    if data[4] != 0x02:
        return None

    chk = 0
    for b in data[4:FRAME_SIZE - 1]:
        chk ^= b
    if chk != data[FRAME_SIZE - 1]:
        return None

    pos = 5
    state = data[pos]; pos += 1
    conf = data[pos] / 100.0; pos += 1
    dom_freq = float((data[pos] << 8) | data[pos + 1]); pos += 2
    rms = ((data[pos] << 8) | data[pos + 1]) / 100.0; pos += 2
    low_e  = float((data[pos] << 24) | (data[pos + 1] << 16) |
                    (data[pos + 2] << 8) | data[pos + 3]) / 1_000_000.0; pos += 4
    mid_e  = float((data[pos] << 24) | (data[pos + 1] << 16) |
                    (data[pos + 2] << 8) | data[pos + 3]) / 1_000_000.0; pos += 4
    high_e = float((data[pos] << 24) | (data[pos + 1] << 16) |
                    (data[pos + 2] << 8) | data[pos + 3]) / 1_000_000.0; pos += 4
    centroid = float((data[pos] << 8) | data[pos + 1]); pos += 2
    flatness = ((data[pos] << 8) | data[pos + 1]) / 10000.0; pos += 2
    zcr = ((data[pos] << 8) | data[pos + 1]) / 10000.0; pos += 2
    ts = (data[pos] << 24) | (data[pos + 1] << 16) | (data[pos + 2] << 8) | data[pos + 3]

    return AudioFrame(
        state=state,
        confidence=conf,
        dominant_freq=dom_freq,
        rms=rms,
        low_energy=low_e,
        mid_energy=mid_e,
        high_energy=high_e,
        spectral_centroid=centroid,
        spectral_flatness=flatness,
        zero_cross_rate=zcr,
        timestamp_ms=ts,
        local_time=time.time(),
    )


def extract_frames_from_buffer(buf: bytes) -> Tuple[List[AudioFrame], bytes]:
    """Scan buffer for audio frames, return decoded frames + remaining tail."""
    frames = []
    while True:
        idx = buf.find(SYNC)
        if idx < 0:
            break
        if idx > 0:
            buf = buf[idx:]
        if len(buf) < FRAME_SIZE:
            break
        frame = decode_frame(buf[:FRAME_SIZE])
        if frame:
            frames.append(frame)
            buf = buf[FRAME_SIZE:]
        else:
            buf = buf[1:]
    return frames, buf


import re

LOG_PATTERN = re.compile(
    r"BEE:\s*state=(\w+)\s+conf=([\d.]+)\s+domFreq=([\d.]+)Hz\s+"
    r"lowE=([\d.]+)\s+midE=([\d.]+)\s+highE=([\d.]+)\s+flat=([\d.]+)"
)

_EN_STATE_NAMES = {
    0: "Normal", 1: "Swarm Prelude", 2: "Queen Missing",
    3: "Hornet Invasion", 4: "Abnormal",
}
STATE_NAME_TO_ID = {v.lower(): k for k, v in _EN_STATE_NAMES.items()}
for k, v in BEE_STATE_NAMES.items():
    STATE_NAME_TO_ID[v.lower()] = k


def parse_log_line(line: str) -> Optional[AudioFrame]:
    """Try to parse a text-format LOG_I line."""
    m = LOG_PATTERN.search(line)
    if not m:
        return None
    state_name, conf, dom_freq, low_e, mid_e, high_e, flat_val = m.groups()
    state = STATE_NAME_TO_ID.get(state_name.lower(), 0)
    return AudioFrame(
        state=state,
        confidence=float(conf),
        dominant_freq=float(dom_freq),
        rms=0.0,
        low_energy=float(low_e),
        mid_energy=float(mid_e),
        high_energy=float(high_e),
        spectral_centroid=0.0,
        spectral_flatness=float(flat_val),
        zero_cross_rate=0.0,
        timestamp_ms=0,
        local_time=time.time(),
    )



def live_read(
    port: str,
    baud: int = 115200,
    callback=None,
    stop_event=None,
):
    """Generator that yields AudioFrame objects from live UART stream."""
    try:
        import serial
    except ImportError:
        print("[audio] pyserial required: pip install pyserial")
        sys.exit(1)

    try:
        ser = serial.Serial(port, baud, timeout=0.3)
    except Exception as e:
        print(f"[audio] 错误: 无法打开串口 {port}: {e}")
        sys.exit(1)

    buf = b""
    print(f"[audio] 已连接 {port} @ {baud} 波特率. 等待音频帧...")

    try:
        while stop_event is None or not stop_event.is_set():
            w = ser.in_waiting
            if w == 0:
                time.sleep(0.05)
                continue
            chunk = ser.read(min(w, 8192))
            if not chunk:
                continue
            buf += chunk
            if len(buf) > 65536:
                buf = buf[-32768:]

            frames, buf = extract_frames_from_buffer(buf)
            for frame in frames:
                if callback:
                    callback(frame)
                yield frame

            if b"\n" in buf:
                lines = buf.decode("utf-8", errors="replace").split("\n")
                buf = lines.pop().encode("utf-8", errors="replace")
                for line in lines:
                    frame = parse_log_line(line)
                    if frame:
                        if callback:
                            callback(frame)
                        yield frame

    except KeyboardInterrupt:
        print("\n[audio] 用户停止.")
    finally:
        ser.close()



class CsvLogger:
    """Persist audio frames to CSV file."""

    def __init__(self, path: str):
        self._path = path
        self._file = open(path, "w", newline="", encoding="utf-8")
        self._writer = csv.writer(self._file)
        self._writer.writerow([
            "time", "state", "confidence", "dom_freq_hz", "rms",
            "low_energy", "mid_energy", "high_energy",
            "centroid_hz", "flatness", "zcr", "timestamp_ms",
        ])
        self._count = 0

    def write(self, frame: AudioFrame):
        self._writer.writerow([
            datetime.now().isoformat(timespec="seconds"),
            frame.state_name,
            f"{frame.confidence:.3f}",
            f"{frame.dominant_freq:.0f}",
            f"{frame.rms:.2f}",
            f"{frame.low_energy:.6f}",
            f"{frame.mid_energy:.6f}",
            f"{frame.high_energy:.6f}",
            f"{frame.spectral_centroid:.0f}",
            f"{frame.spectral_flatness:.4f}",
            f"{frame.zero_cross_rate:.4f}",
            frame.timestamp_ms,
        ])
        self._count += 1
        self._file.flush()

    def close(self):
        self._file.close()
        print(f"[audio] 已记录 {self._count} 帧到 {self._path}")



class LiveDisplay:
    """蜂群音频实时可视化 (matplotlib)."""

    def __init__(self, history_sec: int = 60):
        self._history = history_sec
        self._frames: deque = deque(maxlen=2000)

        import matplotlib.pyplot as plt
        self._plt = plt
        self._fig, self._axes = self._plt.subplots(3, 1, figsize=(12, 9))
        self._fig.canvas.manager.set_window_title("蜂群音频监测")
        self._running = True

        self._fig.canvas.mpl_connect("close_event", self._on_close)

        self._init_plots()

    def _on_close(self, event):
        self._running = False

    @property
    def running(self) -> bool:
        return self._running

    def _init_plots(self):
        self._ax_freq, self._ax_bands, self._ax_state = self._axes

        self._ax_freq.set_ylabel("频率 (Hz)")
        self._ax_freq.set_title("蜂群音频 — 频率变化趋势")
        self._ax_freq.set_ylim(0, 2000)
        self._ax_freq.grid(True, alpha=0.3)
        self._ln_dom, = self._ax_freq.plot([], [], "b-", linewidth=1.5, label="主导频率")
        self._ln_cent, = self._ax_freq.plot([], [], "g--", linewidth=1.0, label="频谱质心")
        self._ax_freq.legend(loc="upper right", fontsize=8)

        self._ax_freq.axhspan(150, 280, alpha=0.08, color="green", label="_低频段")
        self._ax_freq.axhspan(300, 500, alpha=0.08, color="orange", label="_中频段")
        self._ax_freq.axhspan(600, 1500, alpha=0.08, color="red", label="_高频段")
        self._ax_freq.text(5, 220, "正常嗡鸣段", fontsize=7, color="green", alpha=0.6)
        self._ax_freq.text(5, 410, "分蜂频段", fontsize=7, color="orange", alpha=0.6)
        self._ax_freq.text(5, 1000, "胡蜂频段", fontsize=7, color="red", alpha=0.6)

        self._ax_bands.set_ylabel("能量 (x1e-6)")
        self._ax_bands.set_title("频段能量分布 (最新帧)")
        self._ax_bands.set_ylim(0, 10)
        self._ax_bands.grid(True, alpha=0.3, axis="y")
        self._bar_labels = ["低频\n150-280Hz", "中频\n300-500Hz", "高频\n600-1500Hz"]
        self._bar_colors = ["green", "orange", "red"]
        self._bars = self._ax_bands.bar(self._bar_labels, [0, 0, 0], color=self._bar_colors, alpha=0.7)

        self._ax_state.set_ylabel("蜂群状态")
        self._ax_state.set_xlabel("时间 (秒前)")
        self._ax_state.set_title("蜂群状态识别")
        self._ax_state.set_ylim(-0.5, 4.5)
        self._ax_state.set_yticks(range(5))
        self._ax_state.set_yticklabels([BEE_STATE_NAMES[i] for i in range(5)], fontsize=9)
        self._ax_state.grid(True, alpha=0.3)
        self._ln_state, = self._ax_state.plot([], [], "ko-", markersize=4, linewidth=1.5)
        self._state_text = self._ax_state.text(
            0.98, 0.95, "", transform=self._ax_state.transAxes,
            fontsize=12, fontweight="bold", ha="right", va="top",
            bbox=dict(boxstyle="round", facecolor="white", alpha=0.8),
        )

        self._fig.tight_layout()
        self._plt.ion()
        self._plt.show(block=False)

    def add_frame(self, frame: AudioFrame):
        self._frames.append(frame)
        self._redraw()

    def _redraw(self):
        if not self._running:
            return

        frames = list(self._frames)
        if len(frames) < 1:
            return

        now = time.time()
        times = [now - f.local_time for f in frames]

        dom_freqs = [f.dominant_freq for f in frames]
        centroids = [f.spectral_centroid for f in frames]
        self._ln_dom.set_data(times, dom_freqs)
        self._ln_cent.set_data(times, centroids)
        self._ax_freq.set_xlim(max(times) + 1 if times else 60, max(0, min(times) - 1))
        self._ax_freq.relim()
        self._ax_freq.autoscale_view(scalex=True)

        latest = frames[-1]
        max_e = max(latest.low_energy, latest.mid_energy, latest.high_energy, 1e-9) * 1.2
        for bar, val in zip(self._bars, [latest.low_energy, latest.mid_energy, latest.high_energy]):
            bar.set_height(val * 1e6)
        self._ax_bands.set_ylim(0, max(max_e * 1e6, 1))

        states = [f.state for f in frames]
        self._ln_state.set_data(times, states)
        self._ax_state.set_xlim(max(times) + 1 if times else 60, max(0, min(times) - 1))

        color = latest.state_color
        cname = "#{:02x}{:02x}{:02x}".format(*color)
        alert = "  !!告警!!" if latest.is_alert else ""
        self._state_text.set_text(
            f"{latest.state_name}{alert}  |  "
            f"置信度: {latest.confidence:.0%}  |  "
            f"主频: {latest.dominant_freq:.0f} Hz  |  "
            f"声压: {latest.rms:.1f}"
        )
        self._state_text.set_color(cname)

        try:
            self._fig.canvas.draw()
            self._fig.canvas.flush_events()
        except Exception:
            pass

    def close(self):
        self._running = False
        try:
            self._plt.close("all")
        except Exception:
            pass



def headless_monitor(port: str, baud: int, csv_path: str, duration_s: int = 0):
    """无 GUI 模式，仅 CSV 记录."""
    logger = CsvLogger(csv_path)
    start = time.time()
    frame_count = 0
    last_print = start

    def on_frame(frame: AudioFrame):
        nonlocal frame_count, last_print
        logger.write(frame)
        frame_count += 1
        now = time.time()
        if now - last_print >= 5.0:
            alert = " ***" if frame.is_alert else ""
            print(f"[audio] {frame_count:4d} 帧 | "
                  f"状态={frame.state_name} 置信度={frame.confidence:.0%} "
                  f"频率={frame.dominant_freq:6.0f}Hz 声压={frame.rms:.2f}{alert}")
            last_print = now

    try:
        for frame in live_read(port, baud, callback=on_frame):
            if duration_s > 0 and (time.time() - start) >= duration_s:
                break
    except KeyboardInterrupt:
        pass
    finally:
        logger.close()
        print(f"[audio] 完成. 共记录 {frame_count} 帧.")



def main():
    parser = argparse.ArgumentParser(
        description="蜂群音频监测 — 实时蜜蜂声音分析",
    )
    parser.add_argument(
        "port", nargs="?", default=None,
        help="串口 (例如 COM3, /dev/ttyUSB0)",
    )
    parser.add_argument(
        "-b", "--baud", type=int, default=115200,
        help="波特率 (默认: 115200)",
    )
    parser.add_argument(
        "-o", "--output", default=None,
        help="CSV 输出路径 (默认: bee_audio_<时间戳>.csv)",
    )
    parser.add_argument(
        "--no-gui", action="store_true", default=False,
        help="无头模式: 仅 CSV 记录，不显示可视化",
    )
    parser.add_argument(
        "-d", "--duration", type=int, default=0,
        help="运行 N 秒后停止 (0 = 持续运行)",
    )
    parser.add_argument(
        "--replay", default=None,
        help="回放保存的串口日志文件",
    )
    parser.add_argument(
        "--demo",
        action="store_true", default=False,
        help="演示模式: 用模拟数据展示 GUI (无需硬件)",
    )
    args = parser.parse_args()

    if args.demo:
        _run_demo_gui(args.output)
        return

    if args.replay:
        _run_replay_gui(args.replay, args.output)
        return

    if args.port is None:
        parser.print_help()
        print("\n快速启动 (无需硬件):")
        print("  python bee_audio_monitor.py --demo")
        sys.exit(1)

    csv_path = args.output or f"bee_audio_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

    if args.no_gui:
        headless_monitor(args.port, args.baud, csv_path, args.duration)
        return

    display = LiveDisplay(history_sec=60)
    logger = CsvLogger(csv_path)

    def on_frame(frame: AudioFrame):
        logger.write(frame)
        display.add_frame(frame)

    try:
        for frame in live_read(args.port, args.baud, callback=on_frame):
            if not display.running:
                break
            if args.duration > 0:
                pass
    except KeyboardInterrupt:
        pass
    finally:
        display.close()
        logger.close()


def replay_file(path: str):
    """回放二进制串口日志文件 (纯文本模式)."""
    with open(path, "rb") as f:
        data = f.read()

    frames, _ = extract_frames_from_buffer(data)
    print(f"[audio] 回放: 在 {path} 中找到 {len(frames)} 个音频帧")

    if not frames:
        text = data.decode("utf-8", errors="replace")
        for line in text.split("\n"):
            frame = parse_log_line(line)
            if frame:
                frames.append(frame)
        print(f"[audio] 文本解析: 找到 {len(frames)} 帧")

    for i, f in enumerate(frames):
        alert = " *** 告警 ***" if f.is_alert else ""
        print(f"  [{i:3d}] {f.state_name} 置信度={f.confidence:.0%} "
              f"主频={f.dominant_freq:6.0f}Hz 声压={f.rms:.2f} "
              f"低E={f.low_energy:.6f} 中E={f.mid_energy:.6f} 高E={f.high_energy:.6f}"
              f"{alert}")

    from collections import Counter
    state_counts = Counter(f.state_name for f in frames)
    print(f"\n[audio] 统计摘要 ({len(frames)} 帧):")
    for name, count in state_counts.most_common():
        pct = count / len(frames) * 100
        print(f"  {name}: {count:4d} ({pct:.1f}%)")

    if frames:
        alerts = [f for f in frames if f.is_alert]
        if alerts:
            print(f"\n  告警: 检测到 {len(alerts)} 帧异常!")



def _simulate_frame(state: int) -> AudioFrame:
    """Generate one realistic AudioFrame for the given state (uses same
    parameter ranges as simulate_audio.py)."""
    import random

    state_params = {
        0: {"name": "Normal",          "dom_freq": (200, 280), "low_r": 0.50, "mid_r": 0.28, "high_r": 0.12, "rms": (30, 80)},
        1: {"name": "Swarm Prelude",   "dom_freq": (300, 480), "low_r": 0.25, "mid_r": 0.45, "high_r": 0.18, "rms": (80, 150)},
        2: {"name": "Queen Missing",   "dom_freq": (150, 350), "low_r": 0.22, "mid_r": 0.30, "high_r": 0.25, "rms": (20, 60)},
        3: {"name": "Hornet Invasion", "dom_freq": (600, 1300),"low_r": 0.12, "mid_r": 0.22, "high_r": 0.48, "rms": (120, 250)},
        4: {"name": "Abnormal",         "dom_freq": (100, 500), "low_r": 0.18, "mid_r": 0.28, "high_r": 0.32, "rms": (50, 120)},
    }
    p = state_params[state]
    j = 0.15
    total_e = random.uniform(0.003, 0.045)
    low_r = max(0.02, p["low_r"] * (1 + random.uniform(-j, j)))
    mid_r = max(0.02, p["mid_r"] * (1 + random.uniform(-j, j)))
    high_r = max(0.02, p["high_r"] * (1 + random.uniform(-j, j)))

    dom_freq = random.uniform(*p["dom_freq"])
    centroid = dom_freq * random.uniform(1.0, 1.5)
    flatness = random.uniform(0.45, 0.75) if state == 2 else random.uniform(0.18, 0.40)
    zcr = random.uniform(0.25, 0.45) if state == 4 else random.uniform(0.06, 0.22)

    return AudioFrame(
        state=state,
        confidence=random.uniform(0.68, 0.94),
        dominant_freq=dom_freq,
        rms=random.uniform(*p["rms"]),
        low_energy=total_e * low_r,
        mid_energy=total_e * mid_r,
        high_energy=total_e * high_r,
        spectral_centroid=centroid,
        spectral_flatness=flatness,
        zero_cross_rate=zcr,
        timestamp_ms=0,
        local_time=time.time(),
    )


def _run_demo_gui(csv_path: Optional[str] = None):
    """演示模式: 模拟蜂群音频数据并显示 GUI (无需硬件)."""
    import random

    scenario = (
        [0] * 12 +
        [0, 0, 1, 1, 1, 1, 1, 1] +
        [0] * 6 +
        [0, 0, 2, 2, 2, 2, 2, 2] +
        [0] * 6 +
        [0, 0, 3, 3, 3, 3, 3, 3] +
        [0] * 6 +
        [0, 0, 4, 4, 4, 4, 4, 4] +
        [0] * 10
    )

    print("[demo] 正在启动 GUI 演示模式 (模拟蜂群音频数据)...")
    print("[demo] 无需硬件, 关闭 GUI 窗口即可退出.")
    print()

    display = LiveDisplay(history_sec=60)
    logger = None
    if csv_path:
        logger = CsvLogger(csv_path)

    frame_count = 0
    start_time = time.time()

    try:
        for state in scenario:
            if not display.running:
                break

            frame = _simulate_frame(state)
            frame.local_time = time.time()
            frame_count += 1

            display.add_frame(frame)
            if logger:
                logger.write(frame)

            if frame_count % 8 == 0 or frame.is_alert:
                alert = " *** 告警 ***" if frame.is_alert else ""
                print(f"[demo] 第 {frame_count:3d} 帧 | {frame.state_name} "
                      f"置信度={frame.confidence:.0%} 频率={frame.dominant_freq:.0f}Hz "
                      f"声压={frame.rms:.0f}{alert}")

            time.sleep(random.uniform(0.4, 0.9))

    except KeyboardInterrupt:
        pass
    finally:
        display.close()
        if logger:
            logger.close()

    elapsed = time.time() - start_time
    print(f"\n[demo] 完成. {frame_count} 帧, 耗时 {elapsed:.0f} 秒.")


def _run_replay_gui(path: str, csv_path: Optional[str] = None):
    """通过 GUI 回放保存的帧数据."""
    with open(path, "rb") as f:
        data = f.read()

    frames, _ = extract_frames_from_buffer(data)

    if not frames:
        text = data.decode("utf-8", errors="replace")
        for line in text.split("\n"):
            frame = parse_log_line(line)
            if frame:
                frames.append(frame)

    if not frames:
        print("[audio] 文件中未找到音频帧.")
        return

    print(f"[audio] GUI 回放: 从 {path} 加载了 {len(frames)} 帧")
    print("[audio] 关闭 GUI 窗口即可退出.\n")

    display = LiveDisplay(history_sec=120)
    logger = None
    if csv_path:
        logger = CsvLogger(csv_path)

    interval = max(0.15, min(2.0, 120.0 / len(frames)))

    try:
        for i, frame in enumerate(frames):
            if not display.running:
                break

            frame.local_time = time.time()
            display.add_frame(frame)
            if logger:
                logger.write(frame)

            alert = " *** 告警 ***" if frame.is_alert else ""
            print(f"[replay] {i+1:4d}/{len(frames)} | {frame.state_name} "
                  f"置信度={frame.confidence:.0%} 频率={frame.dominant_freq:.0f}Hz"
                  f"{alert}")

            time.sleep(interval)

    except KeyboardInterrupt:
        pass
    finally:
        display.close()
        if logger:
            logger.close()

    from collections import Counter
    state_counts = Counter(f.state_name for f in frames)
    print(f"\n[audio] 统计摘要 ({len(frames)} 帧):")
    for name, count in state_counts.most_common():
        pct = count / len(frames) * 100
        print(f"  {name}: {count:4d} ({pct:.1f}%)")

    alerts = [f for f in frames if f.is_alert]
    if alerts:
        print(f"\n  告警: 检测到 {len(alerts)} 帧异常!")


if __name__ == "__main__":
    main()
