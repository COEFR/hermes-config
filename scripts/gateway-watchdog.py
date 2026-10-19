#!/usr/bin/env python3
"""
Vigilante del gateway de Hermes. Corre por cron del SISTEMA cada 3 min.

Motivo: el 2026-09-20 el gateway murio a las 10:24 (SIGKILL por el tear-down de la
sesion SSH que lo habia lanzado) y el chat quedo mudo ~10 min sin que nadie avisara.
systemd ya lo reinicia si el proceso muere, pero NO cubre el caso "proceso vivo y
Telegram desconectado" (red caida, polling trabado). Eso lo cubre este script.

Que comprueba:
  1. La unidad systemd del gateway esta activa.
  2. El latido del gateway (`state/gateway.heartbeat`) es reciente (< 180 s) -> el loop vive.
  3. No hay una racha de fallos de Telegram posteriores al ultimo "Connected" -> el
     adaptador sigue conectado.

Si algo falla: reinicia la unidad, lo registra y AVISA POR TELEGRAM (con la Bot API
directa, que no depende del gateway caido). Anti-rebote: maximo 1 reinicio cada 10 min.
"""
import json
import os
import re
import subprocess
import time
import urllib.parse
import urllib.request

HERMES = os.path.expanduser("~/.hermes")
LOG = os.path.join(HERMES, "logs", "watchdog.log")
STATE = os.path.join(HERMES, "state", "watchdog.json")
HEARTBEAT = os.path.join(HERMES, "state", "gateway.heartbeat")
UNIT = "hermes-gateway"
MAX_HEARTBEAT_AGE = 180        # s
TG_FAIL_LIMIT = 3              # fallos de Telegram seguidos tras el ultimo "Connected"
MIN_RESTART_GAP = 600          # s entre reinicios (anti-rebote)
UNIT_ENV = {
    "XDG_RUNTIME_DIR": f"/run/user/{os.getuid()}",
    "DBUS_SESSION_BUS_ADDRESS": f"unix:path=/run/user/{os.getuid()}/bus",
}


def log(msg):
    print(msg)
    try:
        if os.path.exists(LOG) and os.path.getsize(LOG) > 1_000_000:
            os.replace(LOG, LOG + ".1")
        with open(LOG, "a") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}\n")
    except Exception:
        pass


def systemctl(*args, timeout=30):
    env = dict(os.environ)
    env.update(UNIT_ENV)
    try:
        p = subprocess.run(["systemctl", "--user", *args], capture_output=True,
                           text=True, timeout=timeout, env=env)
        return p.returncode, (p.stdout or "").strip(), (p.stderr or "").strip()
    except Exception as e:
        return 127, "", str(e)


def send_telegram(text):
    env = {}
    p = os.path.join(HERMES, ".env")
    if os.path.exists(p):
        for line in open(p):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    token = env.get("TELEGRAM_BOT_TOKEN")
    chat = env.get("TELEGRAM_HOME_CHANNEL")
    if not token or not chat:
        log("  !! sin credenciales de Telegram: no puedo avisar")
        return False
    data = urllib.parse.urlencode({"chat_id": chat, "text": text[:4090],
                                   "parse_mode": "HTML"}).encode()
    try:
        with urllib.request.urlopen(
                urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage", data=data),
                timeout=20) as r:
            return bool(json.loads(r.read().decode()).get("ok"))
    except Exception as e:
        log(f"  !! fallo al avisar por Telegram: {e}")
        return False


def heartbeat_age():
    try:
        return time.time() - os.path.getmtime(HEARTBEAT)
    except Exception:
        return None


def telegram_failures(limit_lines=300, window_s=1800):
    """Fallos de Telegram posteriores al ultimo 'Connected'. Devuelve (n_fallos, n_lineas_leidas)."""
    path = os.path.join(HERMES, "logs", "errors.log")
    if not os.path.exists(path):
        return 0
    try:
        with open(path, "rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            f.seek(max(0, size - 200_000))
            lines = f.read().decode("utf-8", "replace").splitlines()[-limit_lines:]
    except Exception:
        return 0
    ts_re = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})")
    now = time.time()
    last_connected = -1
    for i, ln in enumerate(lines):
        if "Connected to Telegram" in ln:
            last_connected = i
    fails = 0
    for ln in lines[last_connected + 1:]:
        if "[Telegram]" not in ln:
            continue
        if not re.search(r"(failed|ConnectError|timed? ?out|Lost|refused|unreachable|retry)", ln, re.I):
            continue
        m = ts_re.match(ln)
        if m:
            try:
                if now - time.mktime(time.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")) > window_s:
                    continue
            except Exception:
                pass
        fails += 1
    return fails


def load_state():
    try:
        return json.load(open(STATE))
    except Exception:
        return {"last_restart": 0, "strikes": 0}


def save_state(st):
    try:
        json.dump(st, open(STATE, "w"), indent=1)
    except Exception:
        pass


def main():
    st = load_state()
    problems = []

    rc, active, err = systemctl("is-active", UNIT)
    active = active.strip()
    if rc != 0 or active != "active":
        problems.append(f"la unidad no está activa (is-active={active or err or 'sin respuesta'})")

    age = heartbeat_age()
    if age is None:
        problems.append("no existe el archivo de latido `state/gateway.heartbeat`")
    elif age > MAX_HEARTBEAT_AGE:
        problems.append(f"latido viejo: {int(age)} s sin latir (límite {MAX_HEARTBEAT_AGE} s)")

    fails = telegram_failures()
    if fails >= TG_FAIL_LIMIT:
        problems.append(f"{fails} fallos de Telegram después del último 'Connected'")

    if not problems:
        st["strikes"] = 0
        save_state(st)
        return 0

    log("PROBLEMA: " + " | ".join(problems))
    gap = time.time() - st.get("last_restart", 0)
    if gap < MIN_RESTART_GAP:
        log(f"  ya reinicié hace {int(gap)} s: no repito (anti-rebote)")
        return 0

    action = "restart" if active == "active" else "start"
    log(f"  -> systemctl --user {action} {UNIT}")
    rc, out, err = systemctl(action, UNIT)
    st["last_restart"] = time.time()
    st["strikes"] = st.get("strikes", 0) + 1
    save_state(st)
    time.sleep(8)

    rc2, active2, _ = systemctl("is-active", UNIT)
    recovered = active2.strip() == "active"
    if rc != 0 and not recovered:
        log(f"  !! el reinicio falló (rc={rc} {err}) — reintento con start")
        rc3, _, err3 = systemctl("start", UNIT)
        time.sleep(8)
        rc2, active2, _ = systemctl("is-active", UNIT)
        recovered = active2.strip() == "active"
        log(f"  fallback start rc={rc3} active={active2} {err3}")

    log(f"  resultado: {'RECUPERADO' if recovered else 'SIGUE CAÍDO'}")
    if recovered:
        send_telegram(
            "🔧 <b>Vigilante del gateway</b>\n"
            f"Detecté: {'; '.join(problems)}\n"
            f"Acción: <b>{action}</b> de la unidad → <b>recuperado</b> en ~{int(time.time() - st['last_restart'])} s.\n"
            "No hizo falta que hicieras nada.")
    else:
        send_telegram(
            "🚨 <b>Vigilante del gateway — no pude levantarlo</b>\n"
            f"Problemas: {'; '.join(problems)}\n"
            f"Intenté <b>{action}</b> y la unidad sigue sin estar activa.\n"
            "Los mensajes que me escribas ahora no van a llegar: hace falta entrar al "
            "VPS por SSH y correr <code>hermes gateway status</code> / "
            "<code>systemctl --user restart hermes-gateway</code>.")
    return 0


if __name__ == "__main__":
    main()
