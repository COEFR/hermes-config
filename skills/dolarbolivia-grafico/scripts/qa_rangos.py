# Barrido de rangos del gráfico: comprueba que CADA vista muestra la serie completa.
#
# Uso: /home/ubuntu/.hermes/hermes-agent/venv/bin/python qa_rangos.py [https://dolarbolivia.site/]
#
# Por qué existe: «velas invisibles / la serie termina en julio» se diagnostica mirando
# getVisibleLogicalRange(), no la captura. Si `to` no llega a n-1, la vista está cortada
# (barSpacing); si llega pero la serie es vieja, el problema es de datos.
#
# Ojo: leer el rango apenas carga devuelve el valor por defecto (~160 velas al final) y
# parece un bug. Hay que dejar que el ajuste del componente corra: ~2,5 s por vista.

import asyncio
import json
import subprocess
import sys
import urllib.request

import websockets

CHROME = "/home/ubuntu/.cache/ms-playwright/chromium-1243/chrome-linux64/chrome"
BASE = (sys.argv[1] if len(sys.argv) > 1 else "https://dolarbolivia.site/").rstrip("/") + "/"
PUERTO = 9433

COMBOS = [
    ("hoy", 5), ("ayer", 15), ("3d", 15), ("7d", 60),
    ("1m", 60), ("3m", 240), ("1y", 1440), ("todo", 10080),
]


async def main():
    proc = subprocess.Popen([
        CHROME, "--headless=new", "--no-sandbox", "--disable-gpu",
        f"--remote-debugging-port={PUERTO}", "--window-size=1600,3000",
        BASE + "?rango=1m&intervalo=60&qa_arranque=1",
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    paginas = []
    for _ in range(40):
        try:
            datos = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{PUERTO}/json", timeout=2).read())
            paginas = [p for p in datos if p.get("type") == "page" and p.get("url", "").startswith("http")]
            if paginas:
                break
        except Exception:
            pass
        await asyncio.sleep(0.5)
    if not paginas:
        print("no se abrió ninguna pestaña")
        return

    problemas = []
    async with websockets.connect(paginas[0]["webSocketDebuggerUrl"], max_size=40_000_000) as ws:
        contador = [0]

        async def enviar(metodo, params=None):
            contador[0] += 1
            i = contador[0]
            await ws.send(json.dumps({"id": i, "method": metodo, "params": params or {}}))
            while True:
                r = json.loads(await ws.recv())
                if r.get("id") == i:
                    return r

        async def ev(expr):
            r = await enviar("Runtime.evaluate", {"expression": expr, "awaitPromise": True, "returnByValue": True})
            return r.get("result", {}).get("result", {}).get("value")

        await enviar("Runtime.enable")
        await asyncio.sleep(2)

        for rango, intervalo in COMBOS:
            await enviar("Page.navigate", {"url": f"{BASE}?rango={rango}&intervalo={intervalo}&qa=1"})
            await asyncio.sleep(2.5)
            info, actual = None, None
            for _ in range(20):
                info = await ev("JSON.stringify(window.__grafico || null)")
                actual = await ev("JSON.stringify(window.__chart ? window.__chart.timeScale().getVisibleLogicalRange() : null)")
                if info and actual:
                    break
                await asyncio.sleep(0.5)
            if not info or not actual:
                print(f"SIN DATOS {rango}/{intervalo}: el componente no dibujó")
                problemas.append(f"{rango}/{intervalo}")
                continue
            g, v = json.loads(info), json.loads(actual)
            velas, tope = g.get("velas", 0), (g.get("velas", 1) - 1)
            ok = velas and abs(v.get("from", 9)) <= 1.5 and abs(v.get("to", 0) - tope) <= 1.5
            print(f"{'OK ' if ok else 'MAL'} {rango:>4}/{intervalo:<5} velas={velas:<5} "
                  f"ultima={g.get('ultima')} visible={v.get('from'):.0f}..{v.get('to'):.0f}")
            if not ok:
                problemas.append(f"{rango}/{intervalo}")

    proc.terminate()
    print("\nPROBLEMAS:", ", ".join(problemas) if problemas else "ninguno")


asyncio.run(main())
