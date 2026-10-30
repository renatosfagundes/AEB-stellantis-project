"""Mede a distribuição de atraso que o relé aplica com desordem (sem Docker): 3 IDs como a percepção
(0x100 e 0x101 a 100 Hz, 0x120 a 50 Hz) durante 6 s, configuração do H1b com ordem de chegada.
Uso: py -3.12 teste_relay_lat.py
"""
import json
import socket
import struct
import subprocess
import sys
import threading
import time
from pathlib import Path

CANBUS = Path(__file__).resolve().parent.parent / "docker" / "canbus"
CFG = CANBUS / "perturb.json"
PORT = 29598


def main():
    original = CFG.read_text(encoding="utf-8")
    srv = subprocess.Popen([sys.executable, str(CANBUS / "can_tcp_server.py"), str(PORT)], stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    time.sleep(0.8)
    try:
        CFG.write_text(json.dumps(dict(run_id="", delay_ms=20, p_disorder=0.2, disorder_ms=[200, 600], policy="arrival", seed=3)), encoding="utf-8")
        time.sleep(0.6)
        tx = socket.create_connection(("127.0.0.1", PORT))
        rx = socket.create_connection(("127.0.0.1", PORT))
        rx.settimeout(0.2)
        chegou, stop = {}, threading.Event()

        def rxl():
            buf = b""
            while not stop.is_set():
                try:
                    buf += rx.recv(4096)
                except socket.timeout:
                    continue
                while len(buf) >= 16:
                    fr, buf = buf[:16], buf[16:]
                    cid, k = struct.unpack("<I", fr[:4])[0], struct.unpack("<I", fr[8:12])[0]
                    chegou[(cid, k)] = time.perf_counter()
        threading.Thread(target=rxl, daemon=True).start()
        envio, k, t0 = {}, 0, time.perf_counter()
        while time.perf_counter() - t0 < 6:
            for cid in (0x100, 0x101) + ((0x120,) if k % 2 == 0 else ()):
                envio[(cid, k)] = time.perf_counter()
                tx.sendall(struct.pack("<IBxxx", cid, 8) + struct.pack("<I", k) + b"\x00" * 4)
            k += 1
            time.sleep(0.01)
        time.sleep(1.5)
        stop.set()
        lat = sorted(1000 * (chegou[x] - envio[x]) for x in envio if x[0] == 0x120 and x in chegou)
        n = len(lat)
        extra = sum(1 for x in lat if x > 150)
        print(f"0x120: {n} entregues; média {sum(lat) / n:.0f} ms; p50 {lat[n // 2]:.0f}; p90 {lat[int(n * .9)]:.0f}; máx {lat[-1]:.0f}; "
              f"{100 * extra / n:.0f}% com atraso extra (esperado ~20%, média esperada ~100 ms)")
    finally:
        srv.terminate()
        CFG.write_text(original, encoding="utf-8")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
