# Umbrales y fuentes: cómo se juzga una wallet (comunidad + papers)

Todo lo de abajo está medido o citado; nada es "opinión de foro" sin fuente. Sirve para justificar los
cortes del clasificador cuando el usuario pregunte por qué una wallet es INSIDER y otra CANDIDATA.

## Muestra y significancia

- **30 posiciones cerradas** es el mínimo para mirar un win rate; por debajo, el número es ruido.
- Para distinguir un edge chico (55% vs 50%) con 95% de confianza: **~380 operaciones**. Con 20
  variantes probadas, el umbral de significancia sube a t ≈ 3,02 (ajuste por comparaciones múltiples).
- **t-stat > 1.645** (una cola) como piso para declarar que el resultado no es azar.

## Win rate y payoff

- Rango sano: **50-70%**. **≥85-90% es bandera roja**, no premio: en memecoins suele significar acceso
  insider o sniping con bot, no habilidad.
- El **ROI importa más que el win rate**, y hay que leerlo junto al payoff (ganancia media vs pérdida
  media). Caso documentado: 73% de win rate en 6 meses puede terminar en **−18%**.
- **Concentración**: si **>50% del PnL viene de UN solo trade**, es lotería, no habilidad.
- **Hold time**: <10 s = sniper/arb bot · <2 min = scalper automatizado (**no copiable**) · ≥20 min =
  decisión humana (rango copiable).

## Fondeo y comportamiento

- **FRESH_FUNDED**: si el historial arranca con el fondeo, el track record no puede ser más viejo que
  eso → no hay nada que evaluar.
- Fondeo desde el **dev/LP/deployer** del token, o desde un patrón de reparto (una wallet que fondea
  decenas de hijas) = insider/farm.
- Fondeo desde un CEX con pocos saltos = normal (no lo convierte en insider).
- **Bot vs humano**: un humano opera en ráfagas y duerme; una wallet que toca **60 tokens al día**
  está escaneando, no eligiendo. Operar a toda hora con ritmo constante = programa.

## Clustering: señales ordenadas por fuerza

1. **Co-firma** (misma tx) — la más fuerte.
2. **Autoridad compartida** (misma mint/freeze authority).
3. **Mismo pagador de fees** (bundle Jito).
4. **Fondeo repetido** desde la misma fuente.
5. **Ritmo de operación** (mismos horarios/intervalos).
6. **Timing** (mismo slot, montos idénticos) — la más débil, es la que más falsos positivos da.

Regla dura: **≥2 señales independientes**. Y nunca agrupar a través de stop-nodes (CEX, bridge, pool,
airdrop, hub con 1.000+ firmas).

## Tasas base (contexto obligatorio al informar)

- **0,4%** de las wallets de pump.fun superó los 10.000 USD.
- **20,8%** de los tokens hace 2x; **2,6%** hace 10x (91-97% de los que hacen 10x tocan su pico el
  mismo día del lanzamiento).
- **6,16%** de los traders de memecoins en Solana fue rentable a 90 días (mediana ≈ −120 USD).
- Los "+1538%" que se publicitan suelen medirse desde el piso de lanzamiento: inflan **3-5x**.

## Herramientas citadas por la comunidad (para qué sirve cada una)

- **Helius Wallet API** `funded-by` y **Solscan Pro** `account/funded_by` (batch hasta 50): fondeo en un
  paso, sin caminar hop por hop. Birdeye tiene equivalente.
- **Solana Tracker**: detección de sniper/bundler (`excludeZeroBuys`), útil para filtrar el ruido de
  los lanzamientos.
- **RugCheck**: `insiderNetworks`, `creatorTokens`, `topHolders`, `knownAccounts`. Da el **conteo** de
  la red de insiders, no las direcciones.
- **Bubblemaps**: grafo visual de transferencias, bueno para explicar un clúster a un humano.
- PnL de GMGN/Cielo/Axiom: requieren key y **no** se pueden presentar como propios.
