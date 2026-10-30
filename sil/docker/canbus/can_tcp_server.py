#!/usr/bin/env python3
"""
TCP CAN Bus Server (relay) with optional network perturbation
=============================================================
Default behaviour is unchanged: any frame sent by one client is broadcast to all
others. Wire format: 16 bytes per frame [4B ID | 1B DLC | 3B pad | 8B data].

Research extension (CEP / delayed and out-of-order events): the frames that flow
from perception to the ECU (0x100, 0x101, 0x120 by default) can be delayed,
re-ordered and passed through an ordering policy before they reach the other
clients. The configuration lives in /app/perturb.json (the directory is a bind
mount, so the host can rewrite it between runs without restarting anything):

    {
      "run_id": "h1a_050ms_r03",     # name of the log file (logs/<run_id>.csv); "" = no log
      "ids": [256, 257, 288],         # frame IDs to perturb (decimal); default 0x100/0x101/0x120
      "delay_ms": 50,                 # fixed network delay added to every perturbed frame
      "jitter_ms": 0,                 # gaussian jitter (std) added to the delay
      "p_disorder": 0.0,              # fraction of perturbed frames that get an extra delay
      "disorder_ms": [40, 200],       # uniform range of that extra delay (creates out-of-order arrival)
      "loss": 0.0,                    # fraction of perturbed frames dropped
      "policy": "arrival",            # "arrival" | "watermark" | "kslack" (ordering before the ECU)
      "watermark_ms": 150,            # watermark: hold each frame until ingress + L, drop later ones
      "seed": 1                       # RNG seed for this run
    }

Every frame is logged (when run_id is set) as: t_in, t_out, id, dlc, data_hex, dropped
where t_in is the relay ingress time (perf_counter, seconds) and t_out the moment it
was forwarded (empty if dropped). ECU → harness frames (0x080, 0x200, 0x300) are never
perturbed and are logged with t_out = t_in.

Usage: python3 can_tcp_server.py [port]
"""

import heapq
import json
import os
import random
import socket
import struct
import sys
import threading
import time

FRAME_SIZE = 16
DEFAULT_PORT = 29536
APP_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(APP_DIR, "perturb.json")
LOG_DIR = os.path.join(APP_DIR, "logs")

clients = []
lock = threading.Lock()
frame_count = 0

DEFAULT_CFG = dict(run_id="", ids=[0x100, 0x101, 0x120], delay_ms=0.0, jitter_ms=0.0, p_disorder=0.0,
                   disorder_ms=[40, 200], loss=0.0, policy="arrival", watermark_ms=150.0, seed=1)


class Perturbacao:
    """Network delay/disorder/loss + ordering policy, applied to frames of the configured IDs."""

    def __init__(self):
        self.cfg = dict(DEFAULT_CFG)
        self.mtime = None
        self.rng = random.Random(1)
        self.heap = []                 # (t_due, seq, t_in, data, src)
        self.seq = 0
        self.cv = threading.Condition()
        self.log = None
        self.log_path = None
        self.log_lock = threading.Lock()
        # ordering policy state
        self.buf = []                  # frames that already "arrived" (t_due passed) but are held by the policy
        self.max_t = -1.0
        self.liberado = -1.0
        self.K = 0.0
        self.dropped = 0
        self.forwarded = 0
        threading.Thread(target=self._dispatcher, daemon=True).start()
        threading.Thread(target=self._config_watcher, daemon=True).start()

    # ---------------------------------------------------------------- config / log
    def _config_watcher(self):
        while True:
            try:
                st = os.stat(CONFIG_PATH)
                if st.st_mtime != self.mtime:
                    self.mtime = st.st_mtime
                    with open(CONFIG_PATH) as f:
                        novo = dict(DEFAULT_CFG)
                        novo.update(json.load(f))
                    self._apply(novo)
            except FileNotFoundError:
                if self.cfg != DEFAULT_CFG:
                    self._apply(dict(DEFAULT_CFG))
                self.mtime = None
            except Exception as e:
                print(f"[CAN BUS] perturb.json error: {e}", flush=True)
            time.sleep(0.2)

    def _apply(self, novo):
        with self.cv:
            self.cfg = novo
            self.rng = random.Random(int(novo.get("seed", 1)))
            self.heap, self.buf, self.max_t, self.K, self.liberado = [], [], -1.0, 0.0, -1.0
            self.dropped = self.forwarded = 0
            with self.log_lock:
                if self.log:
                    self.log.close()
                    self.log = None
                if novo.get("run_id"):
                    os.makedirs(LOG_DIR, exist_ok=True)
                    self.log_path = os.path.join(LOG_DIR, f"{novo['run_id']}.csv")
                    self.log = open(self.log_path, "w", buffering=1)
                    self.log.write("t_in,t_out,id,dlc,data,dropped\n")
            self.cv.notify_all()
        print(f"[CAN BUS] perturbation config: {json.dumps(novo)}", flush=True)

    def _logar(self, t_in, t_out, data, dropped=0):
        # Logging must never break frame delivery: the log file is swapped by the
        # config watcher between runs, so writes are serialized and errors swallowed.
        with self.log_lock:
            if not self.log:
                return
            try:
                can_id = struct.unpack('<I', data[0:4])[0]
                self.log.write(f"{t_in:.6f},{'' if t_out is None else f'{t_out:.6f}'},{can_id},{data[4]},{data[8:16].hex()},{dropped}\n")
            except Exception:
                pass

    # ---------------------------------------------------------------- ingress
    def ingress(self, data, src):
        """Called by the client thread for every frame. Returns True if the relay handled delivery."""
        t_in = time.perf_counter()
        can_id = struct.unpack('<I', data[0:4])[0]
        cfg = self.cfg
        if can_id not in cfg["ids"] or (cfg["delay_ms"] == 0 and cfg["p_disorder"] == 0 and cfg["loss"] == 0
                                        and cfg["policy"] == "arrival" and cfg["jitter_ms"] == 0):
            broadcast(data, src)
            self._logar(t_in, t_in, data)
            return
        if cfg["loss"] > 0 and self.rng.random() < cfg["loss"]:
            self._logar(t_in, None, data, 1)
            with self.cv:
                self.dropped += 1
            return
        delay = cfg["delay_ms"] / 1000.0
        if cfg["jitter_ms"]:
            delay += self.rng.gauss(0, cfg["jitter_ms"] / 1000.0)
        if cfg["p_disorder"] > 0 and self.rng.random() < cfg["p_disorder"]:
            lo, hi = cfg["disorder_ms"]
            delay += self.rng.uniform(lo, hi) / 1000.0
        with self.cv:
            self.seq += 1
            heapq.heappush(self.heap, (t_in + max(0.0, delay), self.seq, t_in, data, src))
            self.cv.notify()

    # ---------------------------------------------------------------- dispatcher (network arrival + policy)
    def _dispatcher(self):
        while True:
            with self.cv:
                while not self.heap and not self.buf:
                    self.cv.wait()
                now = time.perf_counter()
                chegados = []
                while self.heap and self.heap[0][0] <= now:
                    chegados.append(heapq.heappop(self.heap))
                prontos = self._policy(chegados, now)
                prox = self.heap[0][0] if self.heap else None
                espera_policy = self._proxima_liberacao(now)
                if espera_policy is not None:
                    prox = min(prox, espera_policy) if prox is not None else espera_policy
            for (t_in, data, src) in prontos:
                broadcast(data, src)
                self._logar(t_in, time.perf_counter(), data)
            with self.cv:
                self.forwarded += len(prontos)
                if prox is not None:
                    dt = prox - time.perf_counter()
                    if dt > 0:
                        self.cv.wait(timeout=min(dt, 0.05))
                elif not self.heap and not self.buf:
                    pass

    def _policy(self, chegados, now):
        """chegados: frames whose network arrival time has passed. Returns frames to forward now, in order."""
        pol = self.cfg["policy"]
        if pol == "arrival":
            return [(t_in, data, src) for (_, _, t_in, data, src) in chegados]
        if pol == "watermark":
            L = self.cfg["watermark_ms"] / 1000.0
            for (_, _, t_in, data, src) in chegados:
                if t_in + L < now:                      # arrived after its release time: late -> drop
                    self._logar(t_in, None, data, 1)
                    self.dropped += 1
                else:
                    self.buf.append((t_in, data, src))
            prontos = sorted([f for f in self.buf if f[0] + L <= now], key=lambda f: f[0])
            self.buf = [f for f in self.buf if f[0] + L > now]
            return prontos
        if pol == "kslack":
            for (_, _, t_in, data, src) in chegados:
                if t_in > self.max_t:
                    self.max_t = t_in
                    self.buf.append((t_in, data, src))
                    continue
                # tardio: chegou depois da folga atual, ou é mais antigo que algo já liberado
                # (entregá-lo quebraria a ordem; o K-slack descarta)
                tarde = t_in < self.max_t - self.K or t_in < self.liberado
                self.K = max(self.K, self.max_t - t_in)     # a folga aprende com ele para os próximos
                if tarde:
                    self._logar(t_in, None, data, 1)
                    self.dropped += 1
                else:
                    self.buf.append((t_in, data, src))
            # libera o que já está coberto pela folga; sem frames novos, o relógio avança sozinho
            marca = max(self.max_t - self.K, now - self.K - 0.02)
            prontos = sorted([f for f in self.buf if f[0] <= marca], key=lambda f: f[0])
            self.buf = [f for f in self.buf if f[0] > marca]
            if prontos:
                self.liberado = max(self.liberado, prontos[-1][0])
            return prontos
        return [(t_in, data, src) for (_, _, t_in, data, src) in chegados]

    def _proxima_liberacao(self, now):
        if not self.buf:
            return None
        if self.cfg["policy"] == "watermark":
            L = self.cfg["watermark_ms"] / 1000.0
            return min(f[0] + L for f in self.buf)
        return now + 0.01          # kslack releases only when new frames arrive; poll


PERT = None


def broadcast(data, src):
    with lock:
        for c in clients:
            if c is not src:
                try:
                    c.sendall(data)
                except Exception:
                    pass


def handle_client(conn, addr):
    global frame_count
    print(f"[CAN BUS] Client connected: {addr}", flush=True)
    with lock:
        clients.append(conn)
    try:
        while True:
            data = b''
            while len(data) < FRAME_SIZE:
                chunk = conn.recv(FRAME_SIZE - len(data))
                if not chunk:
                    return
                data += chunk
            frame_count += 1
            PERT.ingress(data, conn)
            if frame_count % 1000 == 0:
                can_id = struct.unpack('<I', data[0:4])[0]
                print(f"[CAN BUS] {frame_count} frames | last: 0x{can_id:03X} | fwd={PERT.forwarded} drop={PERT.dropped}", flush=True)
    except Exception as e:
        print(f"[CAN BUS] Client {addr} error: {e}", flush=True)
    finally:
        with lock:
            if conn in clients:
                clients.remove(conn)
        conn.close()
        print(f"[CAN BUS] Client disconnected: {addr}", flush=True)


def main():
    global PERT
    port = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PORT
    PERT = Perturbacao()
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(('0.0.0.0', port))
    server.listen(10)
    print(f"[CAN BUS] TCP CAN bus server on port {port} (perturbation config: {CONFIG_PATH})", flush=True)
    print("[CAN BUS] Frame format: 16 bytes [4B ID | 1B DLC | 3B pad | 8B data]", flush=True)
    while True:
        conn, addr = server.accept()
        t = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
        t.start()


if __name__ == '__main__':
    main()
