#!/usr/bin/env python3
"""Generate audio ML model weights for bee sound classification (10->32->16->5)."""

import numpy as np

rng = np.random.default_rng(42)
N_PER_CLASS = 2000

def make_normal(n):
    low  = rng.uniform(0.3, 1.5, n); mid  = rng.uniform(0.1, 0.5, n)
    high = rng.uniform(0.02, 0.15, n); vhigh= rng.uniform(0.001, 0.05, n)
    total= low+mid+high+vhigh + rng.uniform(0.001, 0.01, n)
    cent = rng.uniform(200, 280, n); flat = rng.uniform(0.10, 0.35, n)
    domf = rng.uniform(180, 280, n); domm = rng.uniform(0.1, 1.0, n)
    zcr  = rng.uniform(0.05, 0.20, n)
    return np.column_stack([low,mid,high,vhigh,total,cent,flat,domf,domm,zcr])

def make_swarm(n):
    low  = rng.uniform(0.15, 0.5, n); mid = low * rng.uniform(1.8, 4.0, n)
    high = rng.uniform(0.05, 0.3, n); vhigh= rng.uniform(0.005, 0.1, n)
    total= low+mid+high+vhigh + rng.uniform(0.001, 0.02, n)
    cent = rng.uniform(280, 450, n); flat = rng.uniform(0.15, 0.45, n)
    domf = rng.uniform(280, 480, n); domm = rng.uniform(0.1, 1.0, n)
    zcr  = rng.uniform(0.10, 0.30, n)
    return np.column_stack([low,mid,high,vhigh,total,cent,flat,domf,domm,zcr])

def make_queen_missing(n):
    low  = rng.uniform(0.05, 0.25, n); mid = rng.uniform(0.1, 0.5, n)
    high = rng.uniform(0.1, 0.6, n); vhigh= rng.uniform(0.05, 0.3, n)
    total= low+mid+high+vhigh + rng.uniform(0.001, 0.02, n)
    cent = rng.uniform(400, 800, n); flat = rng.uniform(0.55, 0.90, n)
    domf = rng.uniform(300, 900, n); domm = rng.uniform(0.05, 0.5, n)
    zcr  = rng.uniform(0.15, 0.40, n)
    return np.column_stack([low,mid,high,vhigh,total,cent,flat,domf,domm,zcr])

def make_hornet(n):
    low  = rng.uniform(0.03, 0.2, n); mid = rng.uniform(0.1, 0.4, n)
    high = low * rng.uniform(2.5, 6.0, n); vhigh= rng.uniform(0.02, 0.2, n)
    total= low+mid+high+vhigh + rng.uniform(0.001, 0.03, n)
    cent = rng.uniform(600, 1200, n); flat = rng.uniform(0.20, 0.60, n)
    domf = rng.uniform(600, 1400, n); domm = rng.uniform(0.05, 0.8, n)
    zcr  = rng.uniform(0.15, 0.35, n)
    return np.column_stack([low,mid,high,vhigh,total,cent,flat,domf,domm,zcr])

def make_abnormal(n):
    low  = rng.uniform(0.05, 0.3, n); mid = rng.uniform(0.1, 0.5, n)
    high = rng.uniform(0.1, 0.5, n); vhigh= rng.uniform(0.05, 0.4, n)
    total= low+mid+high+vhigh + rng.uniform(0.01, 0.1, n)
    cent = rng.uniform(500, 1500, n); flat = rng.uniform(0.30, 0.70, n)
    domf = rng.uniform(400, 2000, n); domm = rng.uniform(0.02, 0.5, n)
    zcr  = rng.uniform(0.25, 0.55, n)
    return np.column_stack([low,mid,high,vhigh,total,cent,flat,domf,domm,zcr])

def generate_all():
    X = np.vstack([make_normal(N_PER_CLASS), make_swarm(N_PER_CLASS),
                   make_queen_missing(N_PER_CLASS), make_hornet(N_PER_CLASS),
                   make_abnormal(N_PER_CLASS)])
    y = np.hstack([np.full(N_PER_CLASS, i) for i in range(5)])
    idx = rng.permutation(len(X))
    return X[idx], y[idx]

def softmax(x): e = np.exp(x - x.max(axis=-1, keepdims=True)); return e / e.sum(axis=-1, keepdims=True)
def relu(x): return np.maximum(x, 0.0)
def relu_deriv(x): return (x > 0).astype(np.float64)
def acc(p, y): return (p.argmax(axis=-1) == y).mean()

def train():
    X, y = generate_all()
    n = len(X); split = int(n * 0.8)
    X_train, y_train = X[:split], y[:split]
    X_test,  y_test  = X[split:], y[split:]

    mean = X_train.mean(axis=0); std = X_train.std(axis=0) + 1e-8
    X_train = (X_train - mean) / std; X_test = (X_test - mean) / std

    I, H1, H2, O = 10, 32, 16, 5
    def init(fin, fout): return rng.normal(0, np.sqrt(2.0/fin), (fin, fout)).astype(np.float64)
    W1, b1 = init(I, H1), np.zeros(H1, np.float64)
    W2, b2 = init(H1, H2), np.zeros(H2, np.float64)
    W3, b3 = init(H2, O), np.zeros(O, np.float64)

    lr = 0.01
    for ep in range(200):
        idx = rng.permutation(split)
        total_loss = 0; batches = 0
        for s in range(0, split, 64):
            bx = X_train[idx[s:s+64]]; by = y_train[idx[s:s+64]]; bs = len(bx)
            z1 = bx@W1+b1; a1=relu(z1); z2=a1@W2+b2; a2=relu(z2); z3=a2@W3+b3; a3=softmax(z3)
            total_loss += -np.log(a3[np.arange(bs), by]+1e-10).mean(); batches += 1
            dz3=a3.copy(); dz3[np.arange(bs), by]-=1; dz3/=bs
            dW3=a2.T@dz3; db3=dz3.sum(0); da2=dz3@W3.T; dz2=da2*relu_deriv(z2)
            dW2=a1.T@dz2; db2=dz2.sum(0); da1=dz2@W2.T; dz1=da1*relu_deriv(z1)
            dW1=bx.T@dz1; db1=dz1.sum(0)
            for w,dw in [(W1,dW1),(W2,dW2),(W3,dW3)]: w-=lr*dw
            for b,db in [(b1,db1),(b2,db2),(b3,db3)]: b-=lr*db
        if ep%40==0 or ep==199:
            ta=acc(softmax(relu(relu(X_train@W1+b1)@W2+b2)@W3+b3), y_train)
            te=acc(softmax(relu(relu(X_test@W1+b1)@W2+b2)@W3+b3), y_test)
            print(f"Epoch {ep:3d}: loss={total_loss/batches:.4f}  train_acc={ta:.3f}  test_acc={te:.3f}")

    export(W1,b1,W2,b2,W3,b3,mean,std)
    print(f"Model exported: audio_model_data.h (965 params, test_acc={te:.3f})")

FMT = "{:.8e}f"
def export(W1,b1,W2,b2,W3,b3,mean,std):
    lines = ["/* Auto-generated by train_audio_model.py -- DO NOT EDIT */","",
             "#ifndef AUDIO_MODEL_DATA_H","#define AUDIO_MODEL_DATA_H","",
             "static const int audio_layer_dims[4] = {10, 32, 16, 5};",""]
    for idx,(W,B) in enumerate([(W1,b1),(W2,b2),(W3,b3)]):
        wf = W.astype(np.float32).flatten(); bf = B.astype(np.float32).flatten()
        for name,arr in [(f"audio_w{idx}",wf),(f"audio_b{idx}",bf)]:
            lines.append(f"static const float {name}[{len(arr)}] = {{")
            for j in range(0, len(arr), 8):
                lines.append("    " + ", ".join(FMT.format(x) for x in arr[j:j+8]) + ",")
            lines.append("};"); lines.append("")
    lines.append("static const float *audio_weights[3] = {audio_w0, audio_w1, audio_w2};")
    lines.append("static const float *audio_biases[3]  = {audio_b0, audio_b1, audio_b2};")
    lines.append('static const char  audio_activations[] = "rrs";'); lines.append("")
    lines.append(f"static const float audio_input_mean[10] = {{{','.join(FMT.format(x) for x in mean.astype(np.float32))}}};")
    lines.append(f"static const float audio_input_std[10]  = {{{','.join(FMT.format(x) for x in std.astype(np.float32))}}};")
    lines.append(""); lines.append("#endif /* AUDIO_MODEL_DATA_H */")
    dest = __file__.replace("tools\\training\\","applications\\audio_analysis\\").replace("tools/training/","applications/audio_analysis/").replace("train_audio_model.py","audio_model_data.h")
    open(dest,"w").write("\n".join(lines)+"\n")

if __name__ == "__main__":
    train()
