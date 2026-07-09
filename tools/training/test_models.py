#!/usr/bin/env python3
"""Test ML models by loading weights from generated C headers."""

import numpy as np
import re
import os

RNG = np.random.default_rng(123)

def parse_float_array(text, name):
    pattern = re.escape(name) + r'\s*\[[^\]]*\]\s*=\s*\{([^}]*)\}'
    m = re.search(pattern, text, re.DOTALL)
    if not m: raise ValueError(f"Cannot find '{name}'")
    vals = []
    for t in m.group(1).split(','):
        t = t.strip().rstrip('f')
        if t: vals.append(float(t))
    return np.array(vals, dtype=np.float32)

def parse_int_array(text, name):
    pattern = re.escape(name) + r'\s*\[[^\]]*\]\s*=\s*\{([^}]*)\}'
    m = re.search(pattern, text, re.DOTALL)
    if not m: raise ValueError(f"Cannot find '{name}'")
    return [int(x.strip()) for x in m.group(1).split(',') if x.strip()]

def parse_activations(text, name):
    m = re.search(re.escape(name) + r'\s*\[\]\s*=\s*"([^"]*)"', text)
    if not m: raise ValueError(f"Cannot find '{name}'")
    return m.group(1)

def dense(x, W, b):
    """x: (in,) or (N,in); W: (in,out); b: (out,)"""
    if x.ndim == 1:
        out = b.copy()
        for i in range(W.shape[0]): out += x[i] * W[i]
        return out
    return b + x @ W

def relu(x): return np.maximum(x, 0)

def softmax(x):
    e = np.exp(x - x.max(axis=-1, keepdims=True))
    return e / e.sum(axis=-1, keepdims=True)

def run_mlp(x, weights, biases, acts):
    h = x
    for W, b, a in zip(weights, biases, acts):
        h = dense(h, W, b)
        if a == 'r': h = relu(h)
        elif a == 's': h = softmax(h)
    return h

def load_model(header_path, prefix):
    if not os.path.exists(header_path):
        print(f"  [SKIP] {header_path} not found")
        return None
    text = open(header_path).read()
    dims = parse_int_array(text, f'{prefix}_layer_dims')
    acts = parse_activations(text, f'{prefix}_activations')
    weights, biases = [], []
    for i in range(len(dims)-1):
        w = parse_float_array(text, f'{prefix}_w{i}').reshape(dims[i], dims[i+1])
        b = parse_float_array(text, f'{prefix}_b{i}')
        weights.append(w); biases.append(b)
    mean = parse_float_array(text, f'{prefix}_input_mean')
    std  = parse_float_array(text, f'{prefix}_input_std')
    return dims, weights, biases, acts, mean, std

def test_audio():
    print("=" * 50)
    print("Testing Audio Model (10->32->16->5)")
    print("=" * 50)
    m = load_model("../applications/audio_analysis/audio_model_data.h", "audio")
    # ... (test logic same as before)
    # Path relative to tools/training/

def main():
    base = os.path.dirname(os.path.abspath(__file__))
    root = os.path.join(base, "..", "..")
    audio_h = os.path.join(root, "applications", "audio_analysis", "audio_model_data.h")
    vision_h = os.path.join(root, "src", "vision_model_data.h")

    print("\n=== Smart Bee Box ML Model Test Suite ===\n")

    for name, hdr, prefix in [
        ("Audio (10->32->16->5)", audio_h, "audio"),
        ("Vision (8->24->16->5)", vision_h, "vision"),
    ]:
        print("=" * 50)
        print(f"Testing {name}")
        print("=" * 50)
        m = load_model(hdr, prefix)
        if m is None: continue
        dims, weights, biases, acts, mean, std = m

        # Test 1: shape + softmax sum
        x = RNG.uniform(0, 1, dims[0]).astype(np.float32)
        xn = (x - mean) / (std + 1e-8)
        p = run_mlp(xn, weights, biases, acts)
        assert len(p)==dims[-1], f"Bad output dim: {len(p)}"
        assert abs(p.sum()-1)<0.001, f"Softmax sum={p.sum():.6f}"
        print(f"  [PASS] Shape={len(p)}, softmax sum={p.sum():.6f}")

        # Test 2: zeros -> no NaN
        zn = (-mean) / (std + 1e-8)
        pz = run_mlp(zn.astype(np.float32), weights, biases, acts)
        assert not np.any(np.isnan(pz)), "NaN detected!"
        print(f"  [PASS] Zeros -> no NaN")

        # Test 3: extreme -> no NaN/Inf
        xn2 = (np.ones(dims[0])*1e6 - mean) / (std + 1e-8)
        pe = run_mlp(xn2.astype(np.float32), weights, biases, acts)
        assert not np.any(np.isnan(pe)), "NaN on extreme!"
        print(f"  [PASS] Extreme values -> no NaN")

        # Test 4: batch inference
        batch = RNG.uniform(0, 1, (20, dims[0])).astype(np.float32)
        bn = (batch - mean) / (std + 1e-8)
        h = bn
        for W, b, a in zip(weights, biases, acts):
            h = h @ W + b
            if a == 'r': h = relu(h)
            elif a == 's': h = softmax(h)
        assert h.shape == (20, dims[-1]), f"Bad batch shape: {h.shape}"
        sums = h.sum(axis=1)
        assert np.allclose(sums, 1.0, atol=0.001), f"Batch softmax sums: {sums}"
        print(f"  [PASS] Batch (20 samples) -> all softmax sums ~1.0")

        print(f"  Model: {sum(w.size+b.size for w,b in zip(weights,biases))} parameters")
        print()

    print("=" * 50)
    print("All tests complete")
    print("=" * 50)

if __name__ == "__main__":
    main()
