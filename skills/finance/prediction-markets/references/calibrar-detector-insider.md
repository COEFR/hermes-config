# Calibrar un detector de «insider» en Polymarket (edad × tamaño × puntaje)

Receta para elegir los umbrales con la distribución delante en vez de inventarlos, y para comprobar que un canal
selectivo no está mudo por construcción.

## Endpoints que hacen falta

| qué | URL | notas |
|---|---|---|
| trades recientes | `https://data-api.polymarket.com/trades?limit=500` | público, cachea ~2 min; monto = `size × price` |
| **primera actividad** (edad real) | `https://data-api.polymarket.com/activity?user=<wallet>&limit=1&sortBy=TIMESTAMP&sortDirection=ASC` | devuelve la operación más vieja de la wallet → `edad_dias` |
| historial y volumen | `.../activity?user=<wallet>&limit=500` · `.../value?user=<wallet>` | el conteo se corta en el `limit`: descriptivo, no edad |

## Script de calibración (una corrida, sin tocar el bot)

```python
trades = traer("https://data-api.polymarket.com/trades?limit=500")
vistos, filas = set(), []
for t in trades:
    usd = float(t["size"]) * float(t["price"])
    w = t["proxyWallet"]
    if usd < 150 or w in vistos:
        continue
    vistos.add(w)
    p = perfil(w)                      # edad ASC + conteo + value, con reintentos
    filas.append((p.get("edad_dias"), usd, p.get("n"), t.get("title")))
print(len(filas), "wallets con apuesta ≥ $150")
```

Con reintentos ante 429 (2-3 s de espera, 2-3 intentos) y ~0,3 s entre perfiles.

## Medido (500 trades)

- 20-21 wallets distintas con apuesta ≥$150.
- **17 con más de 200 operaciones**, 3 entre 100 y 200, **ninguna con ≤100** → el criterio «pocas operaciones» no
  filtra: descarta el canal entero.
- Solo **3 con edad ≤30 días** (8, 11 y 26 días), con apuestas de $162 a $550.
- Con `edad ≤30 d + USD ≥250 + puntaje ≥3` salen **2 candidatos por 300 trades**, ambos con 3/6 → ~2-4 avisos/hora.

## Esquema de puntaje que funcionó (6 puntos)

`edad ≤3 d` → +2 · `edad ≤30 d` → +1 · `conteo ≤10` → +1 · `USD ≥2000` → +2 · `USD ≥MIN` → +1 ·
`precio extremo (≤0,15 o ≥0,85)` → +1 · `valor de la cartera ≥10k` → +1. Avisar con **≥3**; el umbral 4 vacía el canal.

## Cómo probar sin inundar ni engañarse

1. Borrar `vistos.json`/`stats.json` del clon antes de cada prueba: el estado hace que la segunda corrida devuelva 0 y
   parece que el filtro es demasiado estricto.
2. Correr con `MIN_USD=150` y `MIN_USD=250` sobre la misma ventana y comparar cuántos pasan — es la curva de costo
   que se le muestra al usuario, no una opinión.
3. Si sale 0 en todas las variantes, sospechar del **fetch del perfil** (429 → `edad=None` → descarte silencioso) antes
   de bajar más el umbral.
4. Verificar el aviso real releyendo el canal: `attachments ≥ 1`, `embeds == 0` y la línea de la wallet.
