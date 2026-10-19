#!/usr/bin/env python3
"""Lee lo que el gráfico de DólarBolivia realmente dibujó, vía CDP.

El componente deja `window.__grafico = {intervalo, rango, velas, primera, ultima}` en
cada dibujo. Este script abre la página en Chromium headless, se conecta por
WebSocket al puerto de depuración y lo imprime. Sirve para zanjar dudas del tipo
«¿la última vela es de julio?» sin adivinar por la captura.

Uso:
    /home/ubuntu/.hermes/hermes-agent/venv/bin/python probe_grafico.py \
        "https://dolarbolivia.site/?rango=todo&intervalo=10080"

Requiere `websockets` (ya está en el venv de Hermes).
"""
import asyncio
import json
import subprocess
import sys
import urllib.request

import websockets

CHROME = "/home/ubuntu/.cache/ms-playwright/chromium-1243/chrome-linux64/chrome"


async def main(url: str, puerto: int = 9333) -> None:
    proc = subprocess.Popen(
        [CHROME, "--headless=new", "--no-sandbox", "--disable-gpu",
         f"--remote-debugging-port={puerto}", "--window-size=1600,4200", url],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        paginas = []
        for _ in range(40):
            try:
                datos = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{puerto}/json", timeout=2).read())
                paginas = [p for p in datos if p.get("type") == "page" and p.get("url", "").startswith("http")]
                if paginas:
                    break
            except Exception:
                pass
            await asyncio.sleep(0.5)
        if not paginas:
            print("no se encontró la pestaña")
            return

        async with websockets.connect(paginas[0]["webSocketDebuggerUrl"], max_size=20_000_000) as ws:
            async def ev(expr: str):
                await ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate",
                                          "params": {"expression": expr, "awaitPromise": True,
                                                     "returnByValue": True}}))
                while True:
                    r = json.loads(await ws.recv())
                    if r.get("id") == 1:
                        return r.get("result", {}).get("result", {}).get("value")

            valor = "null"
            for _ in range(30):
                valor = await ev("JSON.stringify(window.__grafico || null)")
                if valor and valor != "null":
                    break
                await asyncio.sleep(0.5)  # el JSON pesa ~1,5 MB: el primer render tarda
            print(valor)
    finally:
        proc.terminate()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    asyncio.run(main(sys.argv[1]))
