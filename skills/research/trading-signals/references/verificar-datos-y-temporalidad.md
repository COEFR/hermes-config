# Verificar datos y temporalidades (cuando dice «no se ve igual que TradingView»)

Se dispara con: «verificá que los datos estén correctos», «acabo de comparar con TradingView y no se ve así», «verificá la temporalidad, si es correcta».
El orden **no** es negociable: **primero los datos, después el dibujo**. Ajustar el gráfico sin haber probado la fuente es trabajar a ciegas — en el caso real los datos eran idénticos a Binance (0 diferencias) y el parecido se arregló entero del lado del dibujo.
Implementación de referencia en el proyecto: `verifica_datos.py` y `verifica_temporalidad.py`.

## 1. Los datos: dos endpoints de la misma casa + otra casa
- **Mismo exchange, dos endpoints**: `/api/v3/klines` contra `/api/v3/uiKlines` → tienen que dar **diferencias exactas = 0** en varios pares y temporalidades. Esto valida la descarga **y el mapeo OHLC**: si el orden de los campos estuviera cambiado, el cierre no coincidiría.
- **Otro mercado** (Bybit/OKX) para fijar la tolerancia: el mismo par difiere **0,07%–0,85%** entre venues, y eso es normal, no un error.
- Lo que sí se le puede afirmar al usuario: la fuente es **Binance spot**, la misma que TradingView usa para `BINANCE:PAR`. Y por eso **hay que preguntarle cuál está mirando**: el perpetuo (`.P`) y otros exchanges tienen precios distintos — es la causa más común de «no se ve igual».
- Para que compare a ojo, darle las **últimas velas en texto** (O/H/L/C con hora **UTC**) y pedir una captura si sigue sin cuadrar.

## 2. La temporalidad: seis comprobaciones
1. **Constantes**: `15m=900000 ms · 1h=3600000 · 4h=14400000 · 1d=86400000` y su equivalente en minutos (el `MINUTOS_VELAS` del tracker) coinciden con el `interval` que se pide a Binance.
2. **Espaciado exacto**: sobre 200 velas, la diferencia entre aperturas consecutivas es siempre la duración del TF — sin huecos.
3. **Alineación a los límites del TF en UTC**: 15m en :00/:15/:30/:45 · 1h en :00 · **4h en 00/04/08/12/16/20** · **1d a las 00:00**. Una sesión diaria distinta es el error clásico de mirar otro mercado.
4. **Orden cronológico** y **la última vela pedida es la viva**: de ahí que el bot analice `candles[:-1]` y el PNG dibuje solo velas cerradas.
5. **En señales reales** (no solo en las velas): el `entry_ts` cae exacto en un límite de SU temporalidad, existe entre las velas pedidas, y **el precio de entrada es exactamente el `close` de esa vela** — esto valida el mapeo OHLC de punta a punta.
6. **Sin lookahead**: la entrada está `PIVOT_K` velas después del pivote (3 en esta implementación), nunca en el pivote.
- **Decir la muestra que se probó**: si en ese momento no había señales en alguna TF, aclararlo (los chequeos 1–4 cubren las cuatro temporalidades; los «de señal» solo las que existían).
- **Un caso por vez no alcanza**: muestrear varias señales reales de varias TF y pares; con una sola, un `entry_ts` mal puesto en el resto pasa inadvertido.

## 3. Que quede como comando, no como episodio
- `salud.py --datos` corre las dos verificaciones dentro de la auditoría y **suma sus fallos al exit code**: una sola orden responde «¿está todo bien?».
- El resumen tiene que leer la **línea informativa** de cada script (la de «diferencias exactas: 0» o «RESULTADO»), no la última de su stdout, o el reporte muestra una frase decorativa y parece que no verificó nada.
- **Cuidado con el nombre del flag nuevo**: en un script largo, `args` como Namespace de argparse choca con un `args` que ya se usa como variable de bucle más abajo → `py_compile` pasa y el script revienta **solo en la rama nueva** (`AttributeError: 'str' object has no attribute 'datos'`). Renombrar (p. ej. `cli`) y volver a correr el camino nuevo.
- Reportar las tres cosas juntas: **qué se comprobó, con qué resultado numérico, y qué no se pudo comprobar**.
