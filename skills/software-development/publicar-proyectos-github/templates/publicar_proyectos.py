#!/usr/bin/env python3
"""Publica/actualiza los proyectos del usuario en GitHub con lo que hay AHORA en el equipo.

Dar a cada proyecto un repo git propio (para que de acá en más se actualice con un push normal) y subir
el estado actual. Antes de subir, candado de secretos: si un archivo a publicar contiene una clave, ese
proyecto se aborta y no se publica nada de él.

Uso:  python3 publicar_proyectos.py            (todos)
      python3 publicar_proyectos.py <carpeta>  (uno solo)

Ajustar PROYECTOS, USUARIO y VAR_TOKEN. El token se lee de ~/.hermes/.env: NUNCA va dentro del script.
"""
import os
import re
import subprocess
import sys

BASE = os.path.expanduser("~/.hermes/data")
USUARIO = "COEFR"
ENV = os.path.expanduser("~/.hermes/.env")
VAR_TOKEN = "GITHUB_TOKEN_DOLAR"          # la variable del .env que tiene el PAT

# (carpeta local, repo en GitHub, descripción, ¿público?)
PROYECTOS = [
    ("proyecto1", "repo-1", "Qué hace el proyecto", False),
]

GITIGNORE = """# generado por publicar_proyectos.py — lo que NO debe subirse
.env
.env.*
*.token
.token*
token*
logs/
*.log
__pycache__/
*.pyc
node_modules/
cache/
*.tmp
.DS_Store
# llaves y material privado (GitHub bloquea el push si se cuelan)
migracion/
*llave*
id_rsa*
id_ed25519*
*.pem
*.key
*.crt
*.ppk
"""

EXTRA = {  # datos de estado que no van al repo (por proyecto)
    # "memecoins": "*.json\n*.jsonl\n*.db\n",
}

# El valor tiene que PARECER una clave (charset de clave + 24): así no marca líneas legítimas como
# `if l.startswith("HELIUS_API_KEY=")`, que fue un falso positivo real.
PATRONES = [
    (re.compile(r"ghp_[A-Za-z0-9]{20,}"), "token de GitHub"),
    (re.compile(r"github_pat_[A-Za-z0-9_]{20,}"), "token fino de GitHub"),
    (re.compile(r"\d{8,12}:AA[A-Za-z0-9_-]{30,}"), "token de bot de Telegram"),
    (re.compile(r"BEGIN (OPENSSH|RSA|EC|PGP) PRIVATE KEY"), "llave privada"),
    (re.compile(r"(?i)(api[_-]?key|secret|passwd|password|token)\s*[:=]\s*['\"]([A-Za-z0-9+/_-]{24,})['\"]"),
     "clave embebida"),
]


def token():
    with open(ENV) as fh:
        for linea in fh:
            if linea.startswith(VAR_TOKEN + "="):
                return linea.split("=", 1)[1].strip()
    raise SystemExit(f"falta {VAR_TOKEN} en {ENV}")


def sh(cmd, cwd, timeout=180):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    return r.returncode, (r.stdout + r.stderr).strip()


def archivos_a_subir(p):
    rc, out = sh(["git", "ls-files", "--cached", "--others", "--exclude-standard"], p)
    return [f for f in out.splitlines() if f and not f.startswith(".git/")]


def main():
    elegido = sys.argv[1] if len(sys.argv) > 1 else None
    TOK = token()
    url_tok = f"https://x-access-token:{TOK}@github.com/{USUARIO}/{{repo}}.git"

    for carpeta, repo, desc, publico in PROYECTOS:
        if elegido and carpeta != elegido:
            continue
        p = os.path.join(BASE, carpeta)
        print(f"\n══ {carpeta} → {USUARIO}/{repo} ({'PÚBLICO' if publico else 'privado'})")

        nuevo = not os.path.isdir(os.path.join(p, ".git"))
        if nuevo:
            rc, out = sh(["git", "init", "-q", "-b", "main"], p)
            if rc != 0:
                print(f"   ⛔ no se pudo iniciar git: {out[-120:]}")
                continue
        with open(os.path.join(p, ".gitignore"), "w") as fh:
            fh.write(GITIGNORE + EXTRA.get(carpeta, ""))
        # que las reglas nuevas valgan también sobre lo que ya estaba en el índice
        sh(["git", "rm", "-r", "--cached", "-q", "--ignore-unmatch", "."], p)
        sh(["git", "add", "-A"], p)

        # candado: ninguna clave entre los archivos a subir
        sospechosos = []
        for f in archivos_a_subir(p):
            ruta = os.path.join(p, f)
            try:
                if os.path.getsize(ruta) > 4_000_000:
                    continue
                with open(ruta, encoding="utf-8", errors="ignore") as fh:
                    texto = fh.read()
            except OSError:
                continue
            for rx, que in PATRONES:
                if rx.search(texto):
                    sospechosos.append(f"{f} ({que})")
        if sospechosos:
            print("   ⛔ ABORTADO: hay claves en archivos que se subirían:")
            for s in sospechosos[:5]:
                print("      -", s)
            continue

        n = len(archivos_a_subir(p))
        sh(["git", "-c", "user.name=" + USUARIO,
            "-c", f"user.email={USUARIO.lower()}@users.noreply.github.com",
            "commit", "-q", "--allow-empty", "-m", f"{carpeta}: estado actual ({n} archivos)"], p)
        rc, out = sh(["git", "push", url_tok.format(repo=repo), "main:main", "-f"], p)
        if rc == 0:
            print(f"   ✅ publicado ({n} archivos)")
            if nuevo:
                sh(["git", "remote", "remove", "origin"], p)
                sh(["git", "remote", "add", "origin", f"https://github.com/{USUARIO}/{repo}.git"], p)
        else:
            print(f"   ⛔ falló el push: {out[-300:]}")

    print("\n=== listo ===")


if __name__ == "__main__":
    main()
