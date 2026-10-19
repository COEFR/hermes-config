#!/usr/bin/env python3
"""
Prueba end-to-end de la red de seguridad del gateway (se lanza con temporizador,
DESPUES de que la respuesta del turno en curso ya salio, para no cortarla).

  1. SIGKILL al proceso del gateway  -> debe volver solo en ~5 s (systemd Restart=always).
  2. `systemctl --user stop`         -> systemd NO lo reinicia (parada intencional),
                                        entonces el vigilante externo debe levantarlo y avisar.

Deja el resultado en ~/.hermes/logs/gateway-selftest.log
"""
import os
import subprocess
import time

HERMES = os.path.expanduser("~/.hermes")
LOG = os.path.join(HERMES, "logs", "gateway-selftest.log")
UNIT = "hermes-gateway"
ENV = dict(os.environ)
ENV.update({"XDG_RUNTIME_DIR": f"/run/user/{os.getuid()}",
            "DBUS_SESSION_BUS_ADDRESS": f"unix:path=/run/user/{os.getuid()}/bus"})
PY = "/usr/bin/python3"


def log(msg):
    with open(LOG, "a") as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}\n")


def sc(*args, t=40):
    p = subprocess.run(["systemctl", "--user", *args], capture_output=True, text=True,
                       timeout=t, env=ENV)
    return (p.stdout or "").strip(), (p.stderr or "").strip(), p.returncode


def prop(name):
    out, _, _ = sc("show", UNIT, "-p", name, "--value")
    return out


def main():
    log("=== PRUEBA 1: SIGKILL (¿vuelve solo?) ===")
    pid0, n0 = prop("MainPID"), prop("NRestarts")
    log(f"antes: pid={pid0} NRestarts={n0} active={sc('is-active', UNIT)[0]}")
    try:
        os.kill(int(pid0), 9)
        log(f"kill -9 {pid0} enviado")
    except Exception as e:
        log(f"!! no pude matar el pid {pid0}: {e}")
    t0, ok = time.time(), False
    while time.time() - t0 < 60:
        time.sleep(3)
        act = sc("is-active", UNIT)[0]
        if act == "active" and prop("MainPID") not in ("", pid0):
            ok = True
            break
    log(f"resultado 1: {'RECUPERADO' if ok else 'NO VOLVIÓ'} en {round(time.time()-t0,1)} s "
        f"| pid nuevo={prop('MainPID')} NRestarts={prop('NRestarts')}")

    log("=== PRUEBA 2: parada intencional (systemd no reinicia -> debe actuar el vigilante) ===")
    sc("stop", UNIT)
    time.sleep(12)
    act = sc("is-active", UNIT)[0]
    log(f"tras stop: active={act} (se espera 'inactive': systemd no reinicia paradas intencionales)")
    log("--- salida del vigilante ---")
    p = subprocess.run([PY, os.path.join(HERMES, "scripts", "gateway-watchdog.py")],
                       capture_output=True, text=True, timeout=180, env=ENV)
    for line in (p.stdout or "").splitlines():
        log("  vigilante: " + line)
    time.sleep(10)
    act = sc("is-active", UNIT)[0]
    log(f"resultado 2: active={act} pid={prop('MainPID')} NRestarts={prop('NRestarts')} "
        f"-> {'RECUPERADO POR EL VIGILANTE' if act == 'active' else 'SIGUE CAÍDO'}")
    log("=== fin de la prueba; si ves 'RECUPERADO' en ambos, la red de seguridad funciona ===")


if __name__ == "__main__":
    main()
