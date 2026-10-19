# Alertas de Polymarket con links y gráfico

Código y verificaciones que funcionaron para que cada aviso de ballenas/insider lleve **link a la predicción**, **link al perfil** y **PNG del mercado**.

## 1. URLs que existen (verificadas con curl)

| qué | URL | resultado |
|---|---|---|
| Mercado | `https://polymarket.com/event/<eventSlug>` | 200 |
| Perfil de la wallet | `https://polymarket.com/profile/<proxyWallet>` | 200 (funciona con wallets proxy) |
| Histórico de precios | `https://clob.polymarket.com/prices-history?market=<asset>&interval=1d&fidelity=60` | 200, `{"history":[{"t":epoch,"p":0..1}]}` |
| `data-api.polymarket.com/prices-history` | — | 404, no usar |
| `clob.polymarket.com/trades` | — | 401, pide auth |

Campos del trade que hacen falta: `eventSlug`, `slug`, `proxyWallet`, `asset` (token id), `title`, `price`, `outcome`, `size`, `timestamp`.

## 2. Gráfico con Pillow

```python
def dibujar(puntos, titulo, precio=None, salida="grafico.png", ancho=900, alto=420):
    if len(puntos) < 3:
        return None                      # sin datos: la alerta sale igual, sin imagen
    img = Image.new("RGB", (ancho, alto), (19, 23, 34)); d = ImageDraw.Draw(img)
    izq, der, arriba, abajo = 60, ancho - 20, 70, alto - 45
    ys = [p for _, p in puntos]; ymin, ymax = min(ys), max(ys)
    if ymax - ymin < 0.02:               # mercados planos: forzar escala mínima
        m = (ymax + ymin) / 2; ymin, ymax = m - 0.01, m + 0.01
    x0, x1 = puntos[0][0], puntos[-1][0] or 1
    px = lambda t: izq + (t - x0) / max(1, x1 - x0) * (der - izq)
    py = lambda v: abajo - (v - ymin) / (ymax - ymin) * (abajo - arriba)
    for i in range(4):                   # grilla + eje en %
        v = ymin + (ymax - ymin) * i / 3
        d.line([(izq, py(v)), (der, py(v))], fill=(35, 40, 52)); d.text((8, py(v) - 6), f"{v*100:4.0f}%", fill=(209, 212, 220))
    d.line([(px(t), py(v)) for t, v in puntos], fill=(245, 179, 1), width=3, joint="curve")
    if precio is not None:               # línea roja donde apostó
        d.line([(izq, py(precio)), (der, py(precio))], fill=(239, 83, 80))
        d.ellipse([der - 7, py(precio) - 7, der + 7, py(precio) + 7], outline=(239, 83, 80), width=3)
    d.text((izq, 16), (titulo or "")[:95], fill=(209, 212, 220))
    d.text((izq, 36), f"probabilidad · últimas 24 h · mín {ymin*100:.0f}% / máx {ymax*100:.0f}%", fill=(120, 124, 134))
    img.save(salida, "PNG"); return salida
```

`charts/` al `.gitignore` y Pillow como dependencia del workflow (`pip install "pillow>=10,<13"`). Para probar en local con el venv del repo: `uv pip install --python .venv/bin/python "pillow>=10,<13"` (el venv viejo no la trae aunque el workflow sí).

## 3. Mandar texto + imagen en un solo mensaje (Discord, sin `requests`)

```python
def _multipart(payload, imagen):
    b = "----poly" + uuid.uuid4().hex
    partes = [f'--{b}\r\nContent-Disposition: form-data; name="payload_json"\r\n\r\n{json.dumps(payload)}\r\n'.encode()]
    with open(imagen, "rb") as fh:
        partes.append(f'--{b}\r\nContent-Disposition: form-data; name="files[0]"; filename="grafico.png"\r\nContent-Type: image/png\r\n\r\n'.encode() + fh.read() + b"\r\n")
    partes.append(f"--{b}--\r\n".encode())
    return b"".join(partes), f"multipart/form-data; boundary={b}"

payload = {"content": texto[:1900], "flags": 4}    # flags 4 = sin vista previa
```

Con `requests`: `data={"payload_json": json.dumps(payload)}` + `files={"files[0]": ("grafico.png", open(png, "rb"), "image/png")}`. Si se manda `json=` cuando hay PNG, la imagen no viaja.

## 4. Verificación (obligatoria)

1. Mandar un **ejemplo real** por la función de envío (`🧪 EJEMPLO` en la primera línea) cuando las alertas reales son esporádicas: es la única forma de probar el formato hoy.
2. Releer el canal: `GET /channels/{id}/messages?limit=1` y comprobar `attachments >= 1`, `embeds == 0` y que el contenido traiga `polymarket.com/event` y `polymarket.com/profile`.
3. El HTTP 200 del POST no prueba nada de eso.
4. Para el cuerpo del mensaje, usar la misma función que arma la alerta real (`format_discord_message(..., links)`) en vez de escribir el texto a mano en la prueba.
