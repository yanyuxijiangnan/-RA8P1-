#!/usr/bin/env python3
"""
Bee (蜜蜂) detection and counting from camera-captured images.

Detection strategies:
  1. Color segmentation — isolate yellow/brown bee-colored regions in HSV
  2. Background subtraction — detect moving bees when background is available
  3. Contour analysis — filter by area, convexity, and aspect ratio

Usage:
  python bee_detector.py <image.bmp>
  python bee_detector.py <image_dir>
  python bee_detector.py --realtime COM3

As a library:
  from bee_detector import BeeDetector, count_bees
  count, annotated = count_bees("path/to/image.bmp")
"""

import argparse
import os
import sys
from dataclasses import dataclass
from typing import List, Optional, Tuple

import cv2
import numpy as np



@dataclass
class BeeConfig:
    """Tunable parameters for bee detection."""

    image_width: int = 320
    image_height: int = 240

    bee_h_low: int = 12
    bee_h_high: int = 50
    bee_s_low: int = 50
    bee_s_high: int = 255
    bee_v_low: int = 40
    bee_v_high: int = 240

    bg_history: int = 50
    bg_var_thresh: int = 25
    bg_learning_rate: float = 0.01

    morph_kernel_size: int = 3
    morph_close_iters: int = 2
    morph_open_iters: int = 1

    min_blob_area: int = 15
    max_blob_area: int = 600
    min_convexity: float = 0.5
    max_aspect_ratio: float = 3.0

    swarm_bee_count: int = 30

    debug: bool = False



class BeeDetector:
    """Detect and count bees in an image using color + contour analysis."""

    def __init__(self, config: Optional[BeeConfig] = None):
        self.cfg = config or BeeConfig()
        self._mog2 = cv2.createBackgroundSubtractorMOG2(
            history=self.cfg.bg_history,
            varThreshold=self.cfg.bg_var_thresh,
            detectShadows=False,
        )
        self._bg_initialized = False


    def _bee_color_mask(self, hsv: np.ndarray) -> np.ndarray:
        low = np.array([self.cfg.bee_h_low, self.cfg.bee_s_low, self.cfg.bee_v_low])
        high = np.array([self.cfg.bee_h_high, self.cfg.bee_s_high, self.cfg.bee_v_high])
        return cv2.inRange(hsv, low, high)


    def _motion_mask(self, gray: np.ndarray) -> np.ndarray:
        fg = self._mog2.apply(gray, learningRate=self.cfg.bg_learning_rate)
        if not self._bg_initialized:
            fg = cv2.morphologyEx(fg, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
        return fg

    def reset_background(self):
        """Reset the background model (e.g. after camera repositioning)."""
        self._mog2 = cv2.createBackgroundSubtractorMOG2(
            history=self.cfg.bg_history,
            varThreshold=self.cfg.bg_var_thresh,
            detectShadows=False,
        )
        self._bg_initialized = False


    def _clean_mask(self, mask: np.ndarray) -> np.ndarray:
        k = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE,
            (self.cfg.morph_kernel_size, self.cfg.morph_kernel_size),
        )
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k, iterations=self.cfg.morph_close_iters)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, k, iterations=self.cfg.morph_open_iters)
        return mask


    def _filter_contours(self, mask: np.ndarray) -> List[np.ndarray]:
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        kept = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < self.cfg.min_blob_area or area > self.cfg.max_blob_area:
                continue

            hull = cv2.convexHull(cnt)
            hull_area = cv2.contourArea(hull)
            if hull_area < 1:
                continue
            convexity = area / hull_area
            if convexity < self.cfg.min_convexity:
                continue

            x, y, w, h = cv2.boundingRect(cnt)
            if w < 1 or h < 1:
                continue
            ar = max(w / h, h / w)
            if ar > self.cfg.max_aspect_ratio:
                continue

            kept.append(cnt)
        return kept


    def detect(
        self,
        image: np.ndarray,
        use_color: bool = True,
        use_motion: bool = True,
    ) -> Tuple[int, List[Tuple[int, int, int, int]]]:
        """
        Run bee detection on a BGR image.

        Args:
            image: BGR image (numpy array).
            use_color: Enable color-based bee segmentation.
            use_motion: Enable background-subtraction motion detection.

        Returns:
            (count, list of (x, y, w, h) bounding boxes).
        """
        bboxes = []

        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        combined_mask = np.zeros(image.shape[:2], dtype=np.uint8)

        if use_color:
            color_mask = self._bee_color_mask(hsv)
            color_clean = self._clean_mask(color_mask)
            combined_mask = cv2.bitwise_or(combined_mask, color_clean)

        if use_motion:
            motion_mask = self._motion_mask(gray)
            motion_clean = self._clean_mask(motion_mask)
            combined_mask = cv2.bitwise_or(combined_mask, motion_clean)

            if not self._bg_initialized and np.count_nonzero(motion_mask) < gray.size // 2:
                self._bg_initialized = True

        if not use_color and not use_motion:
            color_mask = self._bee_color_mask(hsv)
            color_clean = self._clean_mask(color_mask)
            combined_mask = color_clean

        valid_contours = self._filter_contours(combined_mask)
        for cnt in valid_contours:
            x, y, w, h = cv2.boundingRect(cnt)
            bboxes.append((x, y, w, h))

        return len(bboxes), bboxes


    def annotate(
        self,
        image: np.ndarray,
        bboxes: List[Tuple[int, int, int, int]],
    ) -> np.ndarray:
        """Draw bounding boxes and count overlay on a copy of the image."""
        out = image.copy()
        count = len(bboxes)

        for idx, (x, y, w, h) in enumerate(bboxes):
            cv2.rectangle(out, (x, y), (x + w, y + h), (0, 255, 0), 2)
            cv2.putText(
                out, str(idx + 1), (x, y - 4),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1,
            )

        label = f"Bee Count: {count}"
        if count >= self.cfg.swarm_bee_count:
            label += " [SWARM!]"

        cv2.putText(
            out, label, (10, 26),
            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2,
        )

        return out



def count_bees(
    image_path: str,
    config: Optional[BeeConfig] = None,
    output_path: Optional[str] = None,
) -> Tuple[int, Optional[np.ndarray]]:
    """
    Count bees in an image file.

    Args:
        image_path: Path to BMP/JPEG/PNG image.
        config: Optional BeeConfig.
        output_path: If given, write annotated image to this path.

    Returns:
        (count, annotated_image) tuple.
    """
    img = cv2.imread(image_path)
    if img is None:
        raise FileNotFoundError(f"Cannot read image: {image_path}")

    detector = BeeDetector(config)
    count, bboxes = detector.detect(img, use_motion=False)

    annotated = None
    if bboxes:
        annotated = detector.annotate(img, bboxes)
        if output_path:
            cv2.imwrite(output_path, annotated)

    return count, annotated



def batch_process(
    input_dir: str,
    output_dir: Optional[str] = None,
    config: Optional[BeeConfig] = None,
    extensions: Tuple[str, ...] = (".bmp", ".jpg", ".jpeg", ".png"),
) -> List[Tuple[str, int]]:
    """Process all images in a directory."""
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    detector = BeeDetector(config)
    results = []

    files = sorted(
        f for f in os.listdir(input_dir)
        if f.lower().endswith(extensions)
    )

    if not files:
        print("[bee] No image files found.")
        return results

    for fname in files:
        fpath = os.path.join(input_dir, fname)
        img = cv2.imread(fpath)
        if img is None:
            print(f"[bee] WARN: cannot read {fname}, skipping")
            continue

        count, bboxes = detector.detect(img, use_motion=False)
        results.append((fname, count))
        print(f"  [{count:3d} bee(s)]  {fname}")

        if output_dir and bboxes:
            annotated = detector.annotate(img, bboxes)
            out_name = f"{os.path.splitext(fname)[0]}_bees.png"
            cv2.imwrite(os.path.join(output_dir, out_name), annotated)

        detector.reset_background()

    total = sum(r[1] for r in results)
    print(f"\n[bee] Total: {len(files)} image(s), {total} bee(s) detected")
    return results



def realtime_mode(port: str, baud: int = 115200, output_dir: str = "."):
    """
    Connect to the MCU camera UART and run bee detection on each frame.

    Binary protocol:
      SYNC:  AA 55 AA 55 (4 bytes)
      HDR:   width(2B) | height(2B) | format(1B) | data_size(4B)  = 9 bytes
      DATA:  RGB565 payload
      FOOT:  XOR checksum (1 byte)
    """
    import time
    import struct

    try:
        import serial
    except ImportError:
        print("[bee] pyserial required: pip install pyserial")
        sys.exit(1)

    SYNC = bytes([0xAA, 0x55, 0xAA, 0x55])
    detector = BeeDetector()
    os.makedirs(output_dir, exist_ok=True)

    print(f"[bee] Connecting to {port} @ {baud}...")
    try:
        ser = serial.Serial(port, baud, timeout=0.5)
    except Exception as e:
        print(f"[bee] ERROR: {e}")
        sys.exit(1)

    buf = b""
    total_frames = 0
    total_bees = 0
    last_report = time.time()

    print(f"[bee] Real-time bee detection active. Output -> {os.path.abspath(output_dir)}")
    print("[bee] Press Ctrl+C to stop.")

    try:
        while True:
            w = ser.in_waiting
            if w == 0:
                time.sleep(0.1)
                continue

            chunk = ser.read(min(w, 65536))
            if not chunk:
                continue
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
                w2 = (buf[pos] << 8) | buf[pos + 1]
                h2 = (buf[pos + 2] << 8) | buf[pos + 3]
                fmt = buf[pos + 4]
                dsz = (buf[pos + 5] << 24) | (buf[pos + 6] << 16) | \
                      (buf[pos + 7] << 8) | buf[pos + 8]
                pos += 9

                if w2 == 0 or h2 == 0 or dsz == 0 or \
                   w2 > 4096 or h2 > 4096 or dsz > 10 * 1024 * 1024:
                    buf = buf[1:]
                    continue

                need = dsz + 1
                if pos + need > len(buf):
                    break

                data = buf[pos:pos + dsz]
                chk = buf[pos + dsz]
                pos += need

                exp = 0
                for b_val in data:
                    exp ^= b_val
                if exp != chk:
                    buf = buf[1:]
                    continue

                bgr = _rgb565_to_bgr(data, w2, h2)
                if bgr is None:
                    buf = buf[pos:]
                    continue

                count, bboxes = detector.detect(bgr)
                total_frames += 1
                total_bees += count

                ts = time.strftime("%Y%m%d_%H%M%S")
                swarm_flag = " [SWARM!]" if count >= detector.cfg.swarm_bee_count else ""
                print(f"[bee] Frame #{total_frames}: {count} bee(s){swarm_flag}")

                if bboxes:
                    annotated = detector.annotate(bgr, bboxes)
                    fname = f"bee_{ts}_{w2}x{h2}.png"
                    cv2.imwrite(os.path.join(output_dir, fname), annotated)

                now = time.time()
                if now - last_report > 30.0:
                    avg = total_bees / max(total_frames, 1)
                    print(f"[bee] -- {total_frames} frames, avg {avg:.1f} bees/frame --")
                    last_report = now

                buf = buf[pos:]

    except KeyboardInterrupt:
        print(f"\n[bee] Stopped. {total_frames} frame(s), {total_bees} total bee detections.")
    finally:
        ser.close()


def _rgb565_to_bgr(data: bytes, w: int, h: int) -> Optional[np.ndarray]:
    """Decode raw RGB565 bytes → BGR numpy array (OpenCV format)."""
    expected = w * h * 2
    if len(data) < expected:
        return None

    arr = np.frombuffer(data[:expected], dtype=np.uint16).reshape((h, w))

    r = ((arr >> 11) & 0x1F).astype(np.uint8) << 3
    g = ((arr >> 5) & 0x3F).astype(np.uint8) << 2
    b = (arr & 0x1F).astype(np.uint8) << 3

    return cv2.merge([b, g, r])


def _frame_to_bgr(data: bytes, w: int, h: int, fmt: int) -> Optional[np.ndarray]:
    """Decode frame data to BGR based on format code."""
    if fmt == 0:
        return _rgb565_to_bgr(data, w, h)
    print(f"[bee] WARN: unknown format {fmt}")
    return None



def main():
    parser = argparse.ArgumentParser(
        description="Bee (蜜蜂) detection and counting from camera images",
    )
    parser.add_argument(
        "input",
        help="Image file, directory, or COM port (with --realtime)",
        nargs="?",
        default=None,
    )
    parser.add_argument(
        "-o", "--output",
        help="Output file or directory for annotated images",
        default=None,
    )
    parser.add_argument(
        "--min-area",
        help=f"Minimum blob area in pixels (default: {BeeConfig.min_blob_area})",
        type=int,
        default=BeeConfig.min_blob_area,
    )
    parser.add_argument(
        "--max-area",
        help=f"Maximum blob area in pixels (default: {BeeConfig.max_blob_area})",
        type=int,
        default=BeeConfig.max_blob_area,
    )
    parser.add_argument(
        "--swarm-count",
        help=f"Bee count threshold for swarming alert (default: {BeeConfig.swarm_bee_count})",
        type=int,
        default=BeeConfig.swarm_bee_count,
    )
    parser.add_argument(
        "--realtime",
        help="Run in real-time mode, reading from camera UART",
        action="store_true",
        default=False,
    )
    parser.add_argument(
        "--baud",
        help="UART baud rate for real-time mode (default: 115200)",
        type=int,
        default=115200,
    )
    parser.add_argument(
        "--no-color",
        help="Disable color-based detection (motion-only)",
        action="store_true",
        default=False,
    )
    parser.add_argument(
        "--no-motion",
        help="Disable motion detection (color-only, always true for single images)",
        action="store_true",
        default=False,
    )
    parser.add_argument(
        "--debug",
        help="Enable debug mode (show intermediate masks)",
        action="store_true",
        default=False,
    )
    args = parser.parse_args()

    config = BeeConfig()
    config.min_blob_area = args.min_area
    config.max_blob_area = args.max_area
    config.swarm_bee_count = args.swarm_count
    config.debug = args.debug

    if args.realtime:
        port = args.input or "COM3"
        realtime_mode(port, args.baud, args.output or ".")
        return

    if args.input is None:
        parser.print_help()
        sys.exit(1)

    input_path = os.path.abspath(args.input)

    if os.path.isfile(input_path):
        count, annotated = count_bees(input_path, config)
        print(f"Bee count: {count}")

        if annotated is not None:
            if args.output:
                out_path = args.output
                if os.path.isdir(args.output):
                    base = os.path.splitext(os.path.basename(input_path))[0]
                    out_path = os.path.join(args.output, f"{base}_bees.png")
                cv2.imwrite(out_path, annotated)
                print(f"Annotated: {out_path}")
            else:
                cv2.imshow("Bee Detection", annotated)
                print("Press any key to close...")
                cv2.waitKey(0)
                cv2.destroyAllWindows()

        sys.exit(0)

    elif os.path.isdir(input_path):
        batch_process(input_path, args.output, config)

    else:
        print(f"[bee] ERROR: path not found: {input_path}")
        sys.exit(1)


if __name__ == "__main__":
    main()
