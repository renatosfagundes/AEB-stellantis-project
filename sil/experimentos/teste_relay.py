"""Teste local do relé com perturbação (sem Docker): sobe o servidor numa porta livre, liga dois
clientes, manda frames 0x120 a 50 Hz e confere atraso, desordem, descarte e log.
Uso: py -3.12 teste_relay.py
"""
import json
import os
import socket
import struct
import subprocess
import sys
import threading
import time
from pathlib import Path

AQUI = Path(__file__).resolve().parent
CANBUS = AQUI.parent / "docker" / "canbus"
CFG = CANBUS / "perturb.json"
PORT = 29599


def frame(can_id, payload=b"\x00" * 8):
    return struct.pack("<IBxxx", can_id, 8) + payload


def recv_loop(sock, out, stop):
    sock.settimeout(0.2)
    while not stop.is_set():
        try:
            data = b""
            while len(data) < 16:
                chunk = sock.recv(16 - len(data))
                if not chunk:
                    return
                data += chunk
            out.append((time.perf_counter(), struct.unpack("<I", data[:4])[0], struct.unpack("<H", data[8:10])[0]))
        except socket.timeout:
            continue


def cenario(cfg, n=100, periodo=0.02):
    CFG.write_text(json.dumps(cfg), encoding="utf-8")
    time.sleep(0.5)                                  # watcher lê a cada 0,2 s
    tx = socket.create_connection(("127.0.0.1", PORT))
    rx = socket.create_connection(("127.0.0.1", PORT))
    out, stop = [], threading.Event()
    threading.Thread(target=recv_loop, args=(rx, out, stop), daemon=True).start()
    time.sleep(0.2)
    t_envio = []
    for k in range(n):
        t_envio.append(time.perf_counter())
        tx.sendall(frame(0x120, struct.pack("<H", k) + b"\x00" * 6))
        time.sleep(periodo)
    time.sleep(1.5)
    stop.set()
    tx.close()
    rx.close()
    return t_envio, out


def main():
    original = CFG.read_text(encoding="utf-8") if CFG.exists() else None
    srv = subprocess.Popen([sys.executable, str(CANBUS / "can_tcp_server.py"), str(PORT)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    time.sleep(0.8)
    ok = True
    try:
        # 1) sem perturbação
        t0, out = cenario(dict(run_id="t_sem", delay_ms=0))
        lat = [out[i][0] - t0[out[i][2]] for i in range(len(out))]
        print(f"sem perturbação: {len(out)}/100 frames, latência média {1000 * sum(lat) / len(lat):.1f} ms")
        ok &= len(out) == 100 and max(lat) < 0.02
        # 2) atraso fixo de 100 ms
        t0, out = cenario(dict(run_id="t_100", delay_ms=100))
        lat = [out[i][0] - t0[out[i][2]] for i in range(len(out))]
        print(f"atraso 100 ms: {len(out)}/100 frames, latência média {1000 * sum(lat) / len(lat):.1f} ms, máx {1000 * max(lat):.1f}")
        ok &= len(out) == 100 and 0.095 < sum(lat) / len(lat) < 0.13
        # 3) desordem 20 % com +200..600 ms, ordem de chegada
        t0, out = cenario(dict(run_id="t_des", delay_ms=20, p_disorder=0.2, disorder_ms=[200, 600], seed=3))
        seqs = [o[2] for o in out]
        fora = sum(1 for i in range(1, len(seqs)) if seqs[i] < max(seqs[:i]))
        print(f"desordem 20 %: {len(out)}/100 frames, {fora} chegaram fora de ordem")
        ok &= len(out) == 100 and fora > 5
        # 4) watermark 150 ms: ordem restaurada, tardios descartados
        t0, out = cenario(dict(run_id="t_wm", delay_ms=20, p_disorder=0.2, disorder_ms=[200, 600], policy="watermark", watermark_ms=150, seed=3))
        seqs = [o[2] for o in out]
        fora = sum(1 for i in range(1, len(seqs)) if seqs[i] < max(seqs[:i]))
        print(f"watermark: {len(out)}/100 frames entregues (descartados {100 - len(out)}), {fora} fora de ordem")
        ok &= fora == 0 and 70 <= len(out) < 100
        # 5) k-slack: ordem restaurada sem descarte
        t0, out = cenario(dict(run_id="t_ks", delay_ms=20, p_disorder=0.2, disorder_ms=[200, 600], policy="kslack", seed=3))
        seqs = [o[2] for o in out]
        fora = sum(1 for i in range(1, len(seqs)) if seqs[i] < max(seqs[:i]))
        lat = [out[i][0] - t0[out[i][2]] for i in range(len(out))]
        print(f"k-slack: {len(out)}/100 frames, {fora} fora de ordem, latência média {1000 * sum(lat) / len(lat):.0f} ms")
        ok &= fora == 0 and len(out) >= 95
        log = (CANBUS / "logs" / "t_ks.csv").read_text().splitlines()
        print(f"log t_ks.csv: {len(log) - 1} linhas; cabeçalho: {log[0]}")
        ok &= len(log) - 1 >= 100
    finally:
        srv.terminate()
        if original is not None:
            CFG.write_text(original, encoding="utf-8")
        for f in (CANBUS / "logs").glob("t_*.csv"):
            f.unlink()
    print("TUDO OK" if ok else "FALHOU")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
