# Backtest de señales sobre velas de exchange

## Datos (Binance spot, sin API key)
- `GET https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=15m&startTime=<ms>&limit=1000`; paginar con `startTime = openTime_última_vela + 1` hasta que devuelva menos de 1000 filas.
- `GET /api/v3/ticker/24hr` → ordenar por `quoteVolume` para la watchlist dinámica.
- Formato de fila: `[openTime, open, high, low, close, volume, closeTime, quoteVolume, trades, ...]`.
- **La última fila es la vela en curso**: descartarla (`candles[:-1]`) para trabajar solo con velas cerradas.
- Excluir stablecoins (USDC, FDUSD, TUSD, BUSD, DAI, USDP, EUR, USD1…) y apalancados (sufijos `UP/DOWN/BULL/BEAR`); sin ese filtro el primer lugar por volumen es USDCUSDT.
- Caché en disco por `(symbol, interval, start_ms, end_ms)`, con `end_ms` en múltiplo de 86400000 para que sobreviva entre corridas. ~50 requests por par (1 año de 15m + 1h + 4h + 1d), ~20 s por par con 0.12 s de pausa.
- Reusar la lista de símbolos guardada en el JSON de la corrida anterior: si el universo cambia, la caché no pega y se repagan los minutos de red. Con caché caliente un análisis completo de 216 celdas corre en ~6 s.
- Diagnóstico rápido: si `curl` a `/api/v3/ping` responde 200, la red está bien y el problema es el código.

## Indicadores (Python puro)
- RSI Wilder(14): suavizar ganancias/pérdidas por periodo con la recurrencia Wilder; `rsi = 100 − 100/(1+ag/al)`; devolver `100` si `al == 0`.
- ATR Wilder(14): true range `max(h−l, |h−pc|, |l−pc|)`, primera media simple y después suavizado Wilder.
- EMA(n): sembrar con la SMA de las primeras n velas, luego `k = 2/(n+1)`. Como filtro de tendencia, calcularla sobre velas cerradas del TF superior y mapear por `closeTime <= t` con búsqueda binaria (si no, se mete lookahead).

## Señal (divergencia regular de RSI)
- Pivote: extremo de una ventana de ±k velas (k=3 está bien).
- Alcista: `low2 < low1` y `rsi(low2) > rsi(low1) + 2`; bajista: simétrica sobre máximos.
- Filtros de calidad medibles: ≥0.5% de diferencia de precio entre pivotes, pivotes a ≤60 velas de distancia, y volumen de la vela de entrada ≥1.2× SMA20(volumen). **El de volumen fue el único que mejoró el resultado de forma medible; medir cada filtro por separado.**
- Guardar también el índice del pivote anterior (`p1_idx`): varios filtros útiles (ancho de la divergencia) se calculan sobre la distancia entre pivotes y es incómodo reconstruirla después.
- Entrada: cierre de la vela `pivote + k` (la que confirma el pivote).
- Frescura en vivo: aceptar la señal si la vela que la confirma es una de las últimas 2 cerradas (tolera un tick perdido) y deduplicar igual por `(par, TF, openTime del pivote)`.

## Simulación y métricas
- TP = 1.5×ATR, SL = 1.0×ATR desde el cierre de entrada; cierre forzado a las N velas (15m/1h 100, 4h 60, 1d 30).
- Avanzar por `high`/`low`: si en la misma vela se tocan TP y SL, contar SL.
- **Guardar por operación `R_sin_comisiones = movimiento_bruto / (stop/precio)` y `risk_pct = stop/precio`.** Con eso cualquier comisión se recalcula sin re-simular: `R(comisión) = R0 − 2·comisión / risk_pct`. Barrer 0.001 (spot taker), 0.0005 (futuros taker) y 0.0002 (maker) en la misma corrida.
- Métricas por celda: n, win rate, IC95 de Wilson, esperanza en R, R total, profit factor, velas medias en posición, drag en R, señales por par por mes.
- Baseline: mismo universo y misma estructura, entradas ciegas cada ~25 velas alternando dirección; es el número que dice si la señal aporta algo.

## Cómo leer la tabla
- n≥300 por celda para creerle al número; n<100 → indicativo, con IC95 ancho, y decirlo.
- La esperanza en R y el profit factor discriminan mejor que el win rate: comparar siempre contra el umbral de equilibrio (SKILL.md).
- Comparar la celda ganadora contra el baseline del mismo TF, no contra cero.
- Contar y declarar cuántas celdas se probaron en total: con 216 combinaciones, la mejor brilla en parte por azar. La defensa no es el IC95 solo, es la consistencia (siguiente sección).

## Métrica de señal: % de movimiento por alerta
Para un bot que solo avisa, la cifra central es cuánto se mueve el precio por alerta. Se calcula por operación con lo ya guardado, sin re-simular:

`mov_bruto_% = R0 × risk_pct × 100`   ·   `mov_neto_% = mov_bruto_% − 2·comisión×100`

Por celda reportar: alertas/mes, % de aciertos, **% medio si acierta**, **% medio si falla** y el promedio por alerta. El desglose es lo que hace entendible el resultado de un golpe: "48% de aciertos, +5.7% cuando acierta y −2.9% cuando falla → +1.33% por alerta".

Traducción a dinero (diagnóstico interno, jamás como titular — ver reglas de reporte en SKILL.md): arriesgar un % fijo del capital por operación, compuesto y en orden cronológico, `eq *= 1 + riesgo·R_neto`; de ahí salen capital final, retorno y drawdown máximo. `riesgo=1%` es la referencia razonable. Sirve para responder "¿esto pierde o gana plata?" y para ordenar configuraciones entre sí.

## Robustez: cortar antes de creer
Dos cortes, siempre, sobre la celda o receta que se va a recomendar:
1. **Mitades temporales**: ordenar por tiempo y partir en dos; reportar el % por alerta de cada mitad. Si una mitad se cae a cero, el promedio alto es un tramo afortunado.
2. **Por par**: desglosar n y esperanza por símbolo. Si un solo par sostiene el resultado, no hay ventaja.

Agrupar por configuración antes de rankear: rankear celdas sin deduplicar hace que "las 3 mejores" sean la misma configuración con tres comisiones distintas y la robustez cubra un solo caso.

## Qué filtros y salidas suman (medido)
Divergencias de RSI, 15 pares líquidos USDT, 1 año, salida TP2×ATR/SL1×ATR, comisión 0.10%/lado. Base = señal + filtro de volumen. Valores = **% de movimiento por alerta**; comparar contra la fila de referencia del mismo TF:

| se agrega | 15m | 1h | 4h |
|---|---|---|---|
| referencia | −0.05% | −0.68% | +1.27% |
| **volatilidad ATR ≥ 1.5%** | **+1.09%** | −1.01% | **+1.45%** |
| ATR ≥ 2% | +2.11% (n=16) | −0.70% | +1.61% |
| RSI en extremo (<35 / >65) | −0.04% | −0.37% | +1.45% |
| BTC a favor (EMA200 4h) | +0.10% | −1.12% | +0.55% |
| vela de confirmación | +0.02% | −0.70% | +1.11% |
| divergencia ancha (≥20 velas) | −0.21% | s/m | s/m |
| salida trailing 2×ATR | −0.20% | −1.02% | **−0.75%** |
| salida break-even tras +1R | −0.39% | −0.97% | **−0.25%** |

Salida (misma señal de 4h, variando solo el objetivo): TP1.0 +0.50% · TP1.5 +0.87% · **TP2.0 +1.27%** · TP3.0 +1.08% por alerta. Con TP3 el acierto baja a 40% y aun así gana más que TP1.5: **la salida pesa tanto como la señal**.

### Las 11 salidas, con control de tres ventanas
Mismas señales de short (916), 3 años partidos en tres ventanas de 1 año, TP/SL en múltiplos del ATR(14) del TF, **% de movimiento por alerta**:

| estilo de salida | 1ª | 2ª | 3ª | ¿sobrevive? |
|---|---|---|---|---|
| fijo 1.5×ATR / stop 1×ATR | −0.11% | −0.18% | +0.01% | no |
| fijo 2×ATR / stop 1×ATR (base anterior del bot) | −0.14% | −0.07% | +0.12% | no |
| fijo 3×ATR / stop 1×ATR | −0.13% | −0.11% | −0.13% | no |
| fijo 2×ATR / stop 1.5×ATR | +0.06% | −0.04% | +0.20% | no |
| objetivo en el soporte / stop 1×ATR | −0.15% | +0.05% | +0.26% | no |
| **objetivo en el soporte / stop 1.5×ATR** | −0.05% | −0.03% | **+0.48%** | no (el menos malo) |
| break-even tras +1R, objetivo 3×ATR | −0.77% | −0.45% | −0.58% | no |
| parcial 50% en 1.5R + resto | −0.42% | −0.42% | −0.40% | no |
| salir cuando el RSI cruza 50 | −0.33% | −0.42% | −0.32% | no |
| salir a las 20 velas | −0.42% | −0.32% | +0.03% | no |

(el 11º, trailing 2×ATR, ya está tabulado arriba). Lectura: la **gestión de salida no rescata una entrada sin ventaja** — 0 de 11 — y todo lo que corta el recorrido antes de tiempo (break-even, parciales, salida por indicador, salida por tiempo) es **sistemáticamente lo peor**, por simetría con la comisión: cada entrada necesita recorrido para pagar el costo y absorber el ruido. Lo único que mejoró el comportamiento fue **ensanchar el stop a 1.5×ATR y apuntar al nivel estructural real** (el soporte) en vez de a un múltiplo fijo; al mostrar un objetivo estructural publicar siempre el **R:R** (puede quedar <1) en vez de limitarlo. El estudio vive en `salidas.py`: tabla por estilo × tres ventanas, sin rejilla de optimización (los estilos son discretos y se escriben a mano).

Recetas con corte en dos mitades del mismo año:

| receta | alertas/mes | aciertos | % por alerta | 1ª mitad | 2ª mitad |
|---|---|---|---|---|---|
| **15m+4h + vol + ATR≥1.5%** | 6.8 | 47.6% | **+1.33%** | +1.23% | +1.43% |
| 4h + vol + ATR≥1.5% | 4.6 | 50.9% | +1.45% | +1.13% | +1.75% |
| solo 4h + vol + ATR≥2% | 3.5 | 50.0% | +1.61% | +1.06% | +2.16% |
| 15m+4h + vol + ATR≥1.5% + RSI extremo | 2.1 | 60.0% | +2.21% | +0.24% | +3.52% |
| 1h + vol + ATR≥1.5% | 6.3 | 18.4% | **−1.01%** | −1.13% | −0.88% |

Lectura de estas mediciones (son dirección del efecto a reproducir con datos propios, no constantes universales):
- La **volatilidad mínima** es el añadido que da vuelta el resultado porque ataca la causa (comisión frente a stop ajustado), no el síntoma.
- El **1h no se arregla con ningún filtro**: se saca del bot.
- Los combos con n<30 que inflan el promedio (RSI en extremo) **no aguantan las dos mitades** → descartar.
- Sumar todas las temporalidades que el bot avisaría da ≈ **−0.1% por alerta**: la cartera completa se hunde por 15m y 1h aunque 4h gane. La decisión de alcance importa más que la elección de indicador.
- Sin slippage: asume entrada al cierre exacto de la vela. Decirlo en el reporte.

## ADX(14) y OBV: implementación y validación
- **ADX Wilder** con +DI/−DI: TR, +DM y −DM por vela; suavizar los tres con Wilder; `+DI = 100·sm(+DM)/ATR`, `−DI` simétrico; `DX = 100·|+DI−−DI|/(+DI+−DI)`; ADX = media Wilder de DX (la primera es la SMA de `periodo` DX). Reproduce los valores de referencia: tendencia monótona ⇒ ADX ≈ 100 con un solo DI distinto de cero; mercado lateral ⇒ ~20.
- **OBV por pendiente**: OBV incremental (`+vol` si la vela cierra arriba, `−vol` si cierra abajo) y normalizar la suma de las últimas 20 velas por el volumen de ese mismo tramo. Queda en ~±0,1–0,5: negativo = distribución (confirma un short), positivo = acumulación.
- Validar el indicador antes de usarlo y decirlo en el reporte: serie sintética de subida sostenida (ADX alto, −DI = 0) contra serie lateral (ADX bajo), y comparar la copia en vivo contra la del backtest. En BTC 4h real el ADX mediano ronda 21 con máximos ~40; si da 5 o 90 constantes, hay bug.
- No mostrar el ADX crudo: acompañarlo de su lectura (`≥25` tendencia definida, `≥40` fuerte, `<20` lateral) y de **+DI vs −DI** (quién domina). Un ADX alto en un short contra-tendencia significa lo contrario de lo que parece.

## Solo shorts (divergencia bajista) con ADX y volumen
Mismo arnés restringido a señales bajistas: 1.316 señales en el año. % de movimiento por alerta, TP2×ATR/SL1×ATR, comisión 0.10%/lado:

| filtros | 15m | 1h | 4h |
|---|---|---|---|
| solo divergencia bajista | −0.11% (66/mes) | −0.42% (32/mes) | −0.53% (10.6/mes) |
| + volumen ≥1.2× | +0.13% (12.9/mes) | −0.67% (6.8/mes) | **+2.00%** (1.7/mes) |
| + ADX ≥ 25 | −0.19% (50/mes) | −0.25% (22.7/mes) | −0.02% (6.6/mes) |
| + volumen y ADX ≥ 25 | −0.02% (8.5/mes) | +0.27% (2.9/mes) | **+4.30%** (1.0/mes) |
| + vol + ADX ≥ 25 + −DI > +DI | −0.76% (1.2/mes) | s/m | s/m |
| + vol + ADX ≥ 25 + ATR ≥ 1.5% | +1.84% (1.0/mes) | +0.76% (1.2/mes) | +4.79% (0.9/mes) |

- El **ADX aislado resta**; **volumen + ADX ≥25** es la mejor combinación (4h: 58,3% al objetivo, mitades +5,02%/+3,57%), pero deja la 4h en ~1 alerta/mes y n=12: es una muestra, no una certeza, y hay que decirlo así.
- Exigir **−DI > +DI empeora** y el patrón se explica solo: las divergencias bajistas reales ocurren casi siempre con **+DI > −DI**, o sea shorts contra-tendencia dentro de una subida fuerte. Mostrar la dominancia como contexto, nunca filtrar por ella.
- En shorts el **15m no aporta** (todas sus filas ≈0 o negativas) y el 1h apenas suma (+0,27%, mitades −0,17%/+0,67%): la 4h sostiene el resultado.

## La configuración tal como sale del bot (medir esto, no la celda)
La cifra que se le muestra al usuario es la de la config **ensamblada**: lista real de temporalidades y cooldown de 4 h por par aplicado sobre las señales ordenadas por tiempo (sin cooldown el total se infla con repeticiones del mismo par en la misma tendencia):

| temporalidades | alertas/mes | n | al objetivo | si acierta | si falla | % por alerta | 1ª mitad | 2ª mitad |
|---|---|---|---|---|---|---|---|---|
| 1h+4h+1d (el bot) | 4.1 | 49 | 44.9% | +6.77% | −2.30% | **+1.77%** | +1.82% | +1.71% |
| solo 4h | 1.0 | 12 | 58.3% | +9.07% | −2.38% | +4.30% | +5.02% | +3.57% |
| solo 1h | 2.9 | 35 | 40.0% | +3.80% | −2.09% | +0.27% | −0.17% | +0.67% |
| 4h+1d | 1.2 | 14 | 57.1% | +11.96% | −3.06% | +5.52% | +8.90% | +2.14% |

Lectura: la cartera **sí puede quedar consistente en las dos mitades** aunque su temporalidad más frecuente (1h) no lo sea, porque la 4h la sostiene; y una TF floja **solo agrega frecuencia, no valor**. Al recomendar alcance, decir cuál sostiene el resultado y cuál solo suma avisos.

## Palancas de frecuencia: qué cuesta cada alerta extra
Pedido típico: «12 alertas al mes es muy poco». Antes de tocar nada, medir en una sola corrida cada palanca con el **cooldown aplicado** (las filas por TF sin cooldown sobreestiman la frecuencia). Shorts, 15 pares, 1 año, TP2×ATR/SL1×ATR, 0.10%/lado, todas las TF del bot:

| configuración | alertas/mes | n | al objetivo | % por alerta |
|---|---|---|---|---|
| base: volumen ≥1.2× + ADX ≥25 | 12.4 | 149 | 36.2% | **+0.50%** |
| ADX ≥20 con volumen | 15.8 | 190 | 33.7% | +0.24% |
| sin ADX (solo volumen) | 20.9 | 251 | 35.5% | +0.12% |
| sin volumen (solo ADX ≥25) | 74.2 | 891 | 32.0% | −0.16% |
| sin ningún filtro | 101.7 | 1221 | 32.2% | −0.22% |
| base con umbrales relajados (0.2% precio, 1 pt RSI) | 22.2 | — | 34.6% | +0.13% |
| sin filtros con umbrales relajados | 195.2 | — | 33.7% | −0.17% |

- **El universo no es una palanca de frecuencia**: de top 20 a top 100 pares el conteo pasó de 11 a 12 alertas en la misma ventana ampliada (verificado: 100 pares escaneados, 4 errores de descarga). Los pares de la cola casi nunca cumplen ADX≥25. Medirlo antes de recomendar ampliar la watchlist.
- Toda palanca de frecuencia paga con valor por alerta (12 → 102 alertas/mes va de +0.50% a −0.22%). La decisión es del usuario, con la curva delante.

### Techo de disponibilidad (cuántas señales existen)
Misma familia de señales (divergencia bajista, 20 pares, 3 años) **sin cooldown**, contada por nivel de exigencia:

| exigencia | señales | por mes | por día |
|---|---|---|---|
| todas las divergencias bajistas | 4.550 | 126 | 4,2 |
| + volumen ≥1.2× | 916 | 25 | 0,8 |
| + volumen y ADX ≥20 | 693 | 19 | 0,6 |
| + volumen y ADX ≥25 | 527 | 15 | 0,5 |

Por temporalidad (crudas → con volumen → con volumen+ADX ≥20): 15m 2.755→569→441 (12/mes) · 1h 1.264→237→173 (4,8/mes) · 4h 455→92→62 (1,7/mes) · 1d 76→18→17 (0,5/mes). Relajando los umbrales de divergencia (0.2% de precio y 1 punto de RSI) el techo sube a ~195/mes.

Es el techo teórico (sin cooldown); lo que el bot entrega es la fila de la tabla de palancas, ya con cooldown aplicado. Usar el techo para contestar «¿cuántas hay?» y la tabla de palancas para «¿cuánto cuesta cada una?».

## Dos niveles de alerta (premium / normal), medidos en exclusiva
Particionar el conjunto ya filtrado por volumen según el ADX, en vez de aflojar los filtros. Menos de 20 señales por celda no se reporta. Cooldown 4 h:

| TF | nivel | alertas/mes | n | al objetivo | % por alerta | 1ª mitad | 2ª mitad |
|---|---|---|---|---|---|---|---|
| 15m | PREMIUM (vol + ADX ≥25) | 8.4 | 101 | 32.7% | −0.04% | −0.16% | +0.08% |
| 15m | NORMAL (vol, ADX <25) | 4.4 | 53 | **54.7%** | **+0.42%** | +0.32% | +0.53% |
| 1h | PREMIUM | 2.9 | 35 | 40.0% | +0.27% | −0.17% | +0.67% |
| 1h | NORMAL | 3.9 | 47 | 8.5% | **−1.37%** | −0.92% | −1.68% |
| 4h | PREMIUM | 1.0 | 12 | 58.3% | **+4.30%** | +5.02% | +3.57% |
| 4h | NORMAL | 0.7 | 8 | 25.0% | −1.44% | −2.12% | −0.76% |

- Los niveles se calculan con predicados **exclusivos** (`vol_ok and adx < umbral`); no se obtienen restando promedios de las filas «solo volumen» y «volumen + ADX», que se solapan.
- El signo del ADX **depende de la temporalidad**: ayuda en 4h (donde la divergencia es un fade contra-tendencia dentro de una subida fuerte) y estorba en 15m, donde el nivel sin tendencia definida es el que rinde. Nunca trasladar la conclusión de un filtro de una TF a otra: medirlo por TF.
- Config del bot resultante: premium en todas las TF + normal solo en 15m ⇒ ≈17 alertas/mes (12.4 premium + 4.4 normal); con el normal en todas serían ≈21/mes, pero 4.6 de esas tienen valor medido negativo. Guardar la partición en el JSON del estudio (`tiers`) para que el bot etiquete cada alerta con **su** histórico.

## Shortear un ESTADO, no una señal: sobrecompra dentro de una subida fuerte
Cuando la pregunta es de una línea («¿le tiro un short a X ahora mismo?») y el activo viene de subir fuerte, el caso a medir no es la divergencia del bot sino el **estado** del mercado. Estado definido al cierre de la vela: **RSI(14) ≥ umbral · ADX(14) ≥ umbral · +DI > −DI**. Entrada corta al cierre, stop 1,5×ATR, objetivo 2×ATR, comisión 0,05%/lado, timeout 50 velas, **cooldown 6 velas por par** (sin él la misma parábola se cuenta veinte veces). Caché de 3 años del propio bot, 15 pares. Script: `scripts/medir_estado.py`.

| estado | n | al objetivo | % por señal | ventanas de 1 año |
|---|---|---|---|---|
| 4h RSI≥75 + ADX≥40 | 409 | 35,5% | **−0,84%** | −0,97% / −0,65% / −0,89% |
| 4h RSI≥70 + ADX≥40 | 635 | 37,2% | −0,66% | −0,76% / −0,68% / −0,52% |
| 4h RSI≥70 + ADX≥25 | 1.305 | 36,9% | −0,60% | −0,86% / −0,38% / −0,58% |
| 1h RSI≥75 + ADX≥40 | 1.620 | 37,2% | −0,41% | −0,30% / −0,47% / −0,45% |
| solo AVAX, 4h RSI≥75 + ADX≥40 | 21 | 38,0% | −0,24% | — |

- Equilibrio de esa estructura (2×ATR / 1,5×ATR, 0,05%/lado): ≈**43% al objetivo**. Ninguna variante llega, y las cuatro son negativas **en las tres ventanas** → no es azar de un tramo ni de un par (AVAX solo queda en moneda al aire).
- Retorno **forward** tras el estado (4h RSI≥75 + ADX≥40): **+0,34% / +1,42% / +2,13% / +3,76%** a 1/3/6/12 velas, y solo 46–47% de las veces cerró abajo → tras una subida vertical el precio **sigue subiendo** en promedio. Medir el forward es lo que separa «está sobrecomprado» de «se va a dar vuelta».
- Lectura para el usuario: «sobrecomprado» describe el estado, no la dirección. El único short documentado de esta familia es la **divergencia bajista** (dos máximos con el RSI más bajo en el segundo) — y esa, medida, tampoco tiene ventaja fuera de muestra (`Regla -1`).
- Generalización: cualquier atajo del tipo «entrar contra un estado extremo» se mide con este mismo script (flags de RSI, ADX, lado y estructura) antes de recomendarlo; los tres cortes obligatorios son n, las tres ventanas y el forward.
