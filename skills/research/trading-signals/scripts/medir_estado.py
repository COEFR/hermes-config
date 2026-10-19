#!/usr/bin/env python3
"""Mide un ESTADO de mercado (no una señal) contra la estructura del bot, sobre la caché de 3 años.

Sirve para contestar consultas del tipo «¿le tiro un short a X que está subiendo?» con números propios
en vez de con la intuición de que «sobrecomprado ⇒ cae».

Estado (todo conocido al cierre de la vela, sin lookahead):
    RSI(14) ≥ --rsi-min  Y  ADX(14) ≥ --adx-min  Y  (+DI > −DI si --alza 1)
Entrada al cierre de la vela que cumple el estado. Salida: stop --sl×ATR, objetivo --tp×ATR,
empate en la misma vela = stop, timeout --timeout velas, comisión --fee %/lado.
**Cooldown --cooldown velas por par**: sin él una misma parábola entra decenas de veces y el promedio miente.

Reporta: n, % al objetivo, % de movimiento medio por señal, umbral de equilibrio de esa estructura,
las tres ventanas de un año, los pares que más aportan y el retorno forward a 1/3/6/12 velas
(¿el precio siguió en la dirección del estado o se dio vuelta?).

Uso:
    python3 medir_estado.py --tf 4h --rsi-min 75 --adx-min 40
    python3 medir_estado.py --tf 4h --rsi-min 30 --adx-min 25 --alza 0 --lado long --timeout 30

Datos: caché del bot en `<trading-dir>/cache`; de cada par se usa la **serie más larga cacheada**
(no hardcodear el start_ms de la ventana: las claves cambian y el script devolvería «sin casos» sin error).
"""
import argparse
import datetime as dt
import glob
import json
import os
import sys


def simular(k, i, atr, lado, tp_mult, sl_mult, fee_pct, timeout):
    """Devuelve el % de movimiento neto de comisiones de una entrada al cierre de la vela i."""
    entry = float(k[i][4])
    if lado == "short":
        stop, tgt = entry + sl_mult * atr, entry - tp_mult * atr
    else:
        stop, tgt = entry - sl_mult * atr, entry + tp_mult * atr
    for j in range(i + 1, min(i + 1 + timeout, len(k))):
        hi, lo = float(k[j][2]), float(k[j][3])
        toca_stop = hi >= stop if lado == "short" else lo <= stop
        toca_tp = lo <= tgt if lado == "short" else hi >= tgt
        if toca_stop:                     # empate en la misma vela: conservador, gana el stop
            return -sl_mult * atr / entry * 100 - 2 * fee_pct
        if toca_tp:
            return tp_mult * atr / entry * 100 - 2 * fee_pct
    cierre = float(k[min(i + timeout, len(k) - 1)][4])
    bruto = (entry - cierre) / entry * 100 if lado == "short" else (cierre - entry) / entry * 100
    return bruto - 2 * fee_pct


def serie_mas_larga(cache_dir, tf):
    """{símbolo: velas} quedándose con la serie más larga cacheada de cada par para esa TF."""
    out = {}
    for path in sorted(glob.glob(os.path.join(cache_dir, f"*_{tf}_*.json"))):
        sym = os.path.basename(path).split("_")[0]
        try:
            k = json.load(open(path))
        except Exception:
            continue
        if isinstance(k, list) and len(k) > 500 and len(k) > len(out.get(sym, [])):
            out[sym] = k
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trading-dir", default=os.path.expanduser("~/.hermes/data/trading"))
    ap.add_argument("--tf", default="4h")
    ap.add_argument("--rsi-min", type=float, default=75.0)
    ap.add_argument("--adx-min", type=float, default=40.0)
    ap.add_argument("--alza", type=int, default=1, help="1 = exigir +DI > −DI (subida fuerte)")
    ap.add_argument("--lado", default="short", choices=["short", "long"])
    ap.add_argument("--tp", type=float, default=2.0, help="objetivo en múltiplos de ATR")
    ap.add_argument("--sl", type=float, default=1.5, help="stop en múltiplos de ATR")
    ap.add_argument("--fee", type=float, default=0.05, help="comisión %% por lado (spot 0.10, futuros 0.05)")
    ap.add_argument("--timeout", type=int, default=50)
    ap.add_argument("--cooldown", type=int, default=6, help="velas mínimas entre casos del mismo par")
    args = ap.parse_args()

    sys.path.insert(0, args.trading_dir)
    import signals as S                      # reusar indicadores, no copiarlos

    series = serie_mas_larga(os.path.join(args.trading_dir, "cache"), args.tf)
    if not series:
        print(f"sin caché de {args.tf} en {args.trading_dir}/cache: correr antes un análisis del bot")
        return

    filas = []
    for sym, k in sorted(series.items()):
        closes = [float(c[4]) for c in k]
        rsi, atr, adx = S.rsi_wilder(closes), S.atr_wilder(k), S.adx_wilder(k)
        ultimo = -999
        for i in range(310, len(k) - 1):
            a = adx[i]
            if rsi[i] is None or atr[i] is None or not a or a[0] is None:
                continue
            if not (rsi[i] >= args.rsi_min and a[0] >= args.adx_min):
                continue
            if args.alza and not a[1] > a[2]:
                continue
            if i - ultimo < args.cooldown:
                continue
            ultimo = i
            riesgo = args.sl * atr[i] / closes[i]
            filas.append({
                "sym": sym, "ts": int(k[i][0]), "rsi": rsi[i], "adx": a[0],
                "atr_pct": 100 * atr[i] / closes[i], "riesgo_pct": 100 * riesgo,
                "mov_pct": simular(k, i, atr[i], args.lado, args.tp, args.sl, args.fee, args.timeout),
                "fwd": {n: (closes[i + n] / closes[i] - 1) * 100 for n in (1, 3, 6, 12) if i + n < len(k)},
            })

    if not filas:
        print("sin casos: revisar umbrales (o el par no tiene caché de esa TF)")
        return

    n = len(filas)
    mov = sum(x["mov_pct"] for x in filas) / n
    hit = 100 * sum(1 for x in filas if x["mov_pct"] > 0) / n
    riesgo = sum(x["riesgo_pct"] for x in filas) / n / 100
    drag = 2 * (args.fee / 100) / riesgo
    equil = 100 * (1 + drag) / ((args.tp / args.sl - drag) + (1 + drag))
    print(f"{args.lado} · {args.tf} · RSI≥{args.rsi_min:g} ADX≥{args.adx_min:g}"
          f"{' +DI>−DI' if args.alza else ''} · {len(series)} pares · stop {args.sl:g}×ATR / obj {args.tp:g}×ATR"
          f" · fee {args.fee:g}%/lado")
    print(f"n={n} · {hit:.1f}% al objetivo · {mov:+.2f}% de movimiento medio por señal"
          f" · stop medio {riesgo * 100:.2f}% → equilibrio ≈{equil:.1f}% al objetivo")
    fwd = {}
    for j in (1, 3, 6, 12):
        vals = [x["fwd"][j] for x in filas if j in x["fwd"]]
        if vals:
            fwd[j] = (sum(vals) / len(vals), 100 * sum(1 for v in vals if v < 0) / len(vals))
    print("forward: " + " · ".join(f"{j} velas {v[0]:+.2f}% ({v[1]:.0f}% a la baja)" for j, v in fwd.items()))

    t0 = min(x["ts"] for x in filas)
    año = 365 * 86_400_000
    for w in range(3):
        sub = [x for x in filas if t0 + w * año <= x["ts"] < t0 + (w + 1) * año]
        if not sub:
            continue
        ini = dt.datetime.fromtimestamp((t0 + w * año) / 1000).strftime("%Y-%m")
        m = sum(x["mov_pct"] for x in sub) / len(sub)
        h = 100 * sum(1 for x in sub if x["mov_pct"] > 0) / len(sub)
        print(f"   ventana {ini}: n={len(sub)} · {h:.0f}% al objetivo · {m:+.2f}%")

    pares = {}
    for x in filas:
        pares.setdefault(x["sym"], []).append(x["mov_pct"])
    top = sorted(((s, sum(v) / len(v), len(v)) for s, v in pares.items()), key=lambda t: -t[1])[:4]
    print("pares con mejor promedio: " + " · ".join(f"{s} {m:+.2f}% (n={q})" for s, m, q in top))
    print("Regla: si el signo no se mantiene en las TRES ventanas, no hay estado tradeable.")


if __name__ == "__main__":
    main()
