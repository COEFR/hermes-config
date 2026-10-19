# Alertas de Polymarket con links y miniatura del mercado

Código y verificaciones que funcionaron para que cada aviso de ballenas/insider lleve **link a la predicción**, **link al perfil** y **la miniatura del mercado** (lo que Dylan llama «la imagen de la apuesta»). Un gráfico de probabilidad **no** es lo pedido: lo rechazó explícitamente.

## 1. URLs que existen (verificadas con curl)

| qué | URL | resultado |
|---|---|---|
| Mercado | `https://polymarket.com/event/<eventSlug>` | 200 |
| Perfil de la wallet | `https://polymarket.com/profile/<proxyWallet>` | 200 (funciona con wallets proxy) |
| Miniatura del trade | campo `icon` de `data-api.polymarket.com/trades` | URL a PNG/JPG (256×256 o 1024×1024) |
| Miniatura del mercado | `https://gamma-api.polymarket.com/markets?condition_ids=<conditionId>` | 200, campo `image`/`icon` (puede venir vacío) |
| Miniatura del evento | `https://gamma-api.polymarket.com/events?slug=<eventSlug>` | 200, campo `image`/`icon` |
| Histórico de precios | `https://clob.polymarket.com/prices-history?market=<asset>&interval=1d&fidelity=60` | 200, `{"history":[{"t":epoch,"p":0..1}]}` — solo para análisis |
| `data-api.polymarket.com/prices-history` | — | 404, no usar |
| `clob.polymarket.com/trades` | — | 401, pide auth |

Campos del trade que hacen falta: `eventSlug`, `slug`, `proxyWallet`, `icon`, `conditionId` (o `market`), `asset` (token id), `title`, `price`, `outcome`, `size`, `timestamp`.

## 2. Descargar la miniatura (sin Pillow)

```python
UA = {"User-Agent": "Mozilla/5.0"}

def descargar(url, salida):
    if not url:
        return None
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=25) as r:
        datos = r.read()
    if len(datos) < 500:                 # vacío o placeholder mínimo
        return None
    cab = datos[:12]
    if cab.startswith(b"\x89PNG"):   ext = "png"
    elif cab.startswith(b"\xff\xd8"): ext = "jpg"
    elif cab[:4] == b"RIFF":         ext = "webp"
    elif cab[:3] == b"GIF":          ext = "gif"
    else: return None                    # no es una imagen
    ruta = str(Path(salida).with_suffix("." + ext))
    Path(ruta).write_bytes(datos)
    return ruta
```

Cadena de respaldo en `para_trade`: `trade["icon"]` → `gamma/markets?condition_ids=` → `gamma/events?slug=`.
Probado con un trade real **sin `icon`**: la cadena resolvió la imagen igual. Sin arte en ninguna de las tres, la alerta sale sin imagen (no inventar una genérica).

## 3. Mandar texto + imagen en un solo mensaje (Discord, sin `requests`)

```python
def _multipart(payload, imagen):
    b = "----poly" + uuid.uuid4().hex
    partes = [f'--{b}\r\nContent-Disposition: form-data; name="payload_json"\r\n\r\n{json.dumps(payload)}\r\n'.encode()]
    with open(imagen, "rb") as fh:
        partes.append(f'--{b}\r\nContent-Disposition: form-data; name="files[0]"; filename="miniatura.png"\r\nContent-Type: image/png\r\n\r\n'.encode() + fh.read() + b"\r\n")
    partes.append(f"--{b}--\r\n".encode())
    return b"".join(partes), f"multipart/form-data; boundary={b}"

payload = {"content": texto[:1900], "flags": 4}    # flags 4 = sin vista previa
```

Con `requests`: `data={"payload_json": json.dumps(payload)}` + `files={"files[0]": ("miniatura.png", open(img, "rb"), "image/png")}`. Si se manda `json=` cuando hay imagen, el adjunto no viaja.

## 4. Verificación (obligatoria)

1. Mandar un **ejemplo real** por la función de envío (`🧪 EJEMPLO` en la primera línea) cuando las alertas reales son esporádicas: es la única forma de probar el formato hoy.
2. Releer el canal: `GET /channels/{id}/messages?limit=1` y comprobar `attachments >= 1`, `embeds == 0`, que el contenido traiga `polymarket.com/event` y `polymarket.com/profile`, y que el adjunto sea la **miniatura** (`width`/`height` 256×256 o 1024×1024), no un PNG de 900×420 dibujado.
3. El HTTP 200 del POST no prueba nada de eso.
4. Para el cuerpo del mensaje, usar la misma función que arma la alerta real (`format_discord_message(..., links)`) en vez de escribir el texto a mano en la prueba.
