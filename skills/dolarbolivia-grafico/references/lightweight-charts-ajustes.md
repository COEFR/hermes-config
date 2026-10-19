# Lightweight Charts: ajustes que costaron vueltas

Notas de la librería (v5, `createChart`, `CandlestickSeries`) aplicadas al gráfico de
`PriceChart.tsx`. Van acá porque son las que hacen que el gráfico «se vea mal» sin ser un
bug de datos.

## Opciones del widget

```ts
createChart(el, {
  layout: { background: { type: ColorType.Solid, color: '#131722' }, textColor: '#9aa4b2' },
  grid: { vertLines: { color: '#1f2430' }, horzLines: { color: '#1f2430' } },
  timeScale: {
    timeVisible: intervalo < 1440 && !nota,  // ver abajo
    secondsVisible: false,
    rightOffset: intervalo >= 1440 ? 1 : 4,
    barSpacing: 6,                            // provisional: se recalcula en ajustar()
  },
  crosshair: { mode: CrosshairMode.Normal },
});
```

- **`timeVisible`** decide si el eje escribe horas. Con velas diarias/semanales tiene que
  ser `false`: sus tiempos son 00:00 UTC y la librería dibuja en UTC, así que una vela
  diaria aparece rotulada «20:00» en Bolivia (UTC−4) y parece que la hora está mal.
- **`nota`**: cuando 1h/4h no tienen tramo suficiente, el componente cae al diario con un
  aviso; en ese caso tampoco van horas. El chequeo es sobre la **serie dibujada**, no sobre
  el botón elegido.
- **`rightOffset`**: con 0-1 la última vela queda pegada al borde derecho y el eje rotula
  fechas cercanas a hoy. Con 4-10 queda un hueco y la última **etiqueta** puede ser de
  meses atrás: el usuario lee eso como «la serie termina en julio».
- **El ancho de vela se calcula, no se hereda** (causa real de «velas invisibles» y de
  «la serie termina en julio»). La librería arranca en `barSpacing: 6` y `fitContent()` no
  lo baja lo suficiente: con 820 velas diarias en un panel de ~950 px la vista se corta y
  los últimos meses quedan fuera de pantalla, con el costado derecho vacío. Fijar el ancho
  según el panel y el rango explícito:

  ```ts
  const ajustar = () => {
    const ancho = caja.current?.clientWidth || 900;
    const porVela = Math.max(0.6, ancho / visibles.length);
    chart.timeScale().applyOptions({ barSpacing: porVela, rightOffset: 0 });
    chart.timeScale().setVisibleLogicalRange({ from: 0, to: visibles.length - 1 });
  };
  ajustar();
  requestAnimationFrame(ajustar);
  setTimeout(ajustar, 150);   // con autoSize el contenedor puede tardar en tener ancho
  ```

  Síntomas medidos de no hacerlo: `setVisibleLogicalRange({from:-2,to:n+1})` dejaba el
  rango interno en `0..595` con 118 velas en la serie, y un `fitContent()` con varias series
  lo dejaba en `0..594`. El chequeo es numérico: `getVisibleLogicalRange()` tiene que dar
  `0..n-1`, y `barSpacing × n ≈ ancho del panel`.

## Tiempos

- Velas intradía: `epoch + DESFASE`, con `DESFASE = -new Date().getTimezoneOffset() * 60`
  (Bolivia: `-14400`). Una sola vez, nunca dos.
- Velas diarias (`dia`) y semanales: **sin correr**. Son fechas (00:00 UTC) y con
  `timeVisible: false` el eje muestra la fecha correcta.
- `UTCTimestamp` numérico en todas las series; no mezclar con objetos `BusinessDay`.

## Agregación semanal (1S, `intervalo = 10080`)

No viene de la API: se arma desde `dia` (819 velas diarias 2024→hoy).

```ts
let semanas = [];
for (const d of diaria) {
  const dow = new Date(d.time * 1000).getUTCDay();        // 0=domingo
  const lunes = d.time - ((dow + 6) % 7) * 86400;         // lunes de esa semana
  const prev = semanas[semanas.length - 1];
  if (prev && prev.time === lunes) {
    prev.high = Math.max(prev.high, d.high);
    prev.low = Math.min(prev.low, d.low);
    prev.close = d.close;
    prev.venta = d.venta;
  } else {
    semanas.push({ time: lunes, open: d.open, high: d.high, low: d.low, close: d.close, venta: d.venta });
  }
}
```

- 819 diarias → **118 semanales**, la última el lunes de la semana en curso. Verificado.
- Al agregar una temporalidad nueva hay que **excluirla de la rama genérica de fallback**
  (`if (intervalo !== 1440 && diaria.length && !serieExt) → mostrar diario + nota`), o esa
  rama la captura antes y el botón nuevo muestra «se muestra 1D» en vez de sus velas.

## Completar el borde derecho (sin inventar el pasado)

- **1D**: si la última vela de `dia` es anterior a hoy, agregar la de hoy con las muestras
  propias del día (open de la primera, high/low máximos, close de la última) en el mismo
  instante que usa `dia` (00:00 UTC del día local).
- **15m/1h/4h**: los tramos `ext` llegan con retraso; tomar las muestras propias con
  `t > ultima.time`, agruparlas en el bucket en curso y agregar esa vela parcial.
- Los huecos **internos** no se rellenan: si no hay dato, no hay vela.

## Colores y legibilidad

- Vela alcista `#26a69a`, bajista `#ef5350`, fondo `#131722`. Nada de blanco: una vela
  blanca no existe en este gráfico, si el usuario la ve es el fondo o el crosshair.
- En la vista de 2 años el rango de precios (8→20 Bs) hace que 0,1 Bs sean ~3 px: las velas
  recientes quedan como guiones. Es escala, no un fallo de render.
