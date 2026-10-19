#!/usr/bin/env python3
"""«¿Le tiro un short a X ahora mismo?» — evaluación en vivo de UN par.

Reusa el motor del bot (`<trading-dir>/signals.py` + `scoring.py`) para no reimplementar indicadores
ni quedar desalineado con lo que el bot alerta en producción.

Uso:
    python3 consultar_par.py AVAXUSDT
    python3 consultar_par.py AVAXUSDT --amplias 24 --lado short

Salida, por temporalidad y sobre velas CERRADAS:
  · estado: cierre, RSI(14), ADX(14) con +DI/−DI, ATR% del precio, volumen relativo a la SMA20, OBV(20)
  · señales FRESCAS (últimas 2 velas cerradas) = lo que el bot alertaría hoy
  · señales AMPLIAS (últimas N velas) = ¿hubo divergencia hace poco? Así «no hay nada» es verificable
  · contexto diario: EMA200 sembrada con SMA, distancia al máximo y al mínimo de 30 días
Solo lee datos públicos de Binance. No opera, no pide claves, no toca fondos.

Antes de responder, cruzar el estado con la tabla medida (`references/backtest-methodology.md`,
«Shortear un ESTADO, no una señal») — no opinar sobre sobrecompra ni sobre «ya está para caer».
"""
import argparse
import datetime as dt
import os
import sys


def f(x, d=2):
    return "—" if x is None else f"{x:.{d}f}"


def estado(S, tf, closed):
    closes = [float(c[4]) for c in closed]
    vols = [float(c[5]) for c in closed]
    rsi, atr = S.rsi_wilder(closes), S.atr_wilder(closed)
    adx, obv, vsma = S.adx_wilder(closed), S.obv_slope(closed), S.sma(vols, 20)
    i = len(closed) - 1
    a = adx[i] if i < len(adx) and adx[i] else (None, None, None)
    atr_pct = 100 * atr[i] / closes[i] if atr[i] else None
    vol_rel = vols[i] / vsma[i] if vsma[i] else None
    return {
        "vela": dt.datetime.fromtimestamp(closed[i][0] / 1000).strftime("%m-%d %H:%M"),
        "cierre": closes[i], "rsi": rsi[i], "adx": a[0], "pdi": a[1], "mdi": a[2],
        "atr_pct": atr_pct, "vol_rel": vol_rel,
        "obv": obv[i] if i < len(obv) else None,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("symbol")
    ap.add_argument("--trading-dir", default=os.path.expanduser("~/.hermes/data/trading"))
    ap.add_argument("--intervals", default="15m,1h,4h,1d")
    ap.add_argument("--amplias", type=int, default=24, help="velas cerradas hacia atrás = búsqueda amplia")
    ap.add_argument("--lado", default="short", choices=["short", "long", "both"])
    args = ap.parse_args()

    sys.path.insert(0, args.trading_dir)
    import signals as S

    sym = args.symbol.upper()
    if not sym.endswith("USDT"):
        sym += "USDT"
    S.SIDE = args.lado

    print(f"=== {sym} · {dt.datetime.now().strftime('%Y-%m-%d %H:%M')} · lado={args.lado}")
    try:
        tk = S.http_json(f"{S.BASE}/api/v3/ticker/24hr?symbol={sym}")
        print(f"    precio {tk['lastPrice']} ({float(tk['priceChangePercent']):+.1f}% en 24h)"
              f" · volumen 24h {float(tk['quoteVolume']) / 1e6:.1f} M USDT")
    except Exception as e:
        print(f"    !! ticker no disponible: {e}")

    for tf in args.intervals.split(","):
        try:
            k = S.klines(sym, tf, 400)
        except Exception as e:
            print(f"\n--- {tf}: error de descarga ({e})")
            continue
        closed = k[:-1]                      # la última vela está en curso
        st = estado(S, tf, closed)
        print(f"\n--- {tf} · vela cerrada {st['vela']} · cierre {f(st['cierre'], 4)}")
        print(f"    RSI {f(st['rsi'], 1)} · ADX {f(st['adx'], 1)} (+DI {f(st['pdi'], 1)} / −DI {f(st['mdi'], 1)})"
              f" · ATR {f(st['atr_pct'])}% del precio · vol {f(st['vol_rel'])}x · OBV {f(st['obv'], 3)}")

        for etiqueta, fresco in (("FRESCA", 2), ("amplia", max(2, args.amplias))):
            S.FRESH_BARS = fresco
            sigs = S.find_signals(sym, tf, k)
            for s in sigs:
                ts = dt.datetime.fromtimestamp(s["entry_ts"] / 1000).strftime("%m-%d %H:%M")
                print(f"    ★ {etiqueta} {ts} {s['tier'].upper()} p{s.get('score')} · "
                      f"RSI {s['rsi_prev']:.1f}→{s['rsi_now']:.1f} · ADX {f(s['adx'], 1)} · "
                      f"vol {f(s['vol_ratio'])}x · ATR {f(s['atr_pct'])}% · "
                      f"entrada {s['entry']:.4f} / stop {s['sl']:.4f} / obj {s['tp']:.4f} · "
                      f"riesgo {s['risk_pct']:.2f}% · R:R {f(s.get('rr'))}")
            if etiqueta == "amplia" and not sigs:
                print(f"    (sin divergencia en las últimas {fresco} velas cerradas)")

    # contexto diario: la tendencia de fondo decide si un contra-tendencia tiene sentido
    try:
        k1d = S.klines(sym, "1d", 400)
        closes = [float(c[4]) for c in k1d[:-1]]
        ema = None
        if len(closes) > 200:
            ema = sum(closes[:200]) / 200
            for x in closes[200:]:
                ema += (x - ema) * 2 / 201
        px = closes[-1]
        print(f"\n--- contexto diario: precio {px:.4f} · EMA200 {f(ema, 4)}"
              f" ({'por DEBAJO' if ema and px < ema else 'por ENCIMA' if ema else 's/d'})"
              f" · máx 30d {max(closes[-30:]):.4f} ({(px / max(closes[-30:]) - 1) * 100:+.1f}% desde el máx)"
              f" · mín 30d {min(closes[-30:]):.4f} ({(px / min(closes[-30:]) - 1) * 100:+.1f}% desde el mín)")
    except Exception as e:
        print(f"\n--- contexto diario: no disponible ({e})")


if __name__ == "__main__":
    main()
