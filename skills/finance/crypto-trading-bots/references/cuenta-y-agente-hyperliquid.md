# Cuenta y wallet de agente en Hyperliquid — verificar antes de prometer que se opera

Puesta en marcha de una cuenta nueva. Cuatro sondeos al endpoint `/info` (público, sin clave, sin firmar) que
separan los motivos por los que «el bot no puede operar». Cada uno atrapa una falla distinta: correrlos **todos**
antes de decir «listo» o «la cuenta está vacía».

```bash
A=0x...   # dirección de la CUENTA (no la del agente)
for T in clearinghouseState spotClearinghouseState extraAgents userNonFundingLedgerUpdates; do
  curl -s -X POST https://api.hyperliquid.xyz/info -H "Content-Type: application/json" \
    -d "{\"type\":\"$T\",\"user\":\"$A\"}"
done
```

| sondeo | qué responde |
|---|---|
| `clearinghouseState` | saldo y posiciones de **perpetuos**; `withdrawable`, `marginSummary` |
| `spotClearinghouseState` | saldos de **spot** — billetera distinta |
| `extraAgents` | qué wallets de agente están **autorizadas** sobre esa cuenta |
| `userNonFundingLedgerUpdates` | depósitos, transferencias internas y movimientos de vault recibidos |

- **Perpetuos y spot son dos billeteras separadas del mismo usuario.** Mirar sólo perpetuos y concluir «está
  vacía» es un falso negativo: los fondos pueden estar en spot.
- **`extraAgents` vacío = el agente NO está autorizado sobre ESA cuenta** → Hyperliquid rechaza toda orden aunque
  haya saldo. La autorización es **por cuenta**: un agente autorizado sobre la cuenta A no sirve para la cuenta B.
  Es el paso que más se olvida, porque autorizar el agente en el panel «API» da por hecho que aplica a la cuenta
  correcta, y la captura que muestra el usuario puede ser de otra.
- **`userNonFundingLedgerUpdates` vacío junto con saldo cero = esa cuenta nunca recibió nada.** Es la firma de
  «dirección equivocada», no de «depósito en camino»: no quedarse esperando, buscar en qué otra cuenta está la
  plata.
- Que la API **responda** con datos no prueba que sea la cuenta correcta: una cuenta existente, sin fondos y sin
  movimientos también contesta. Existir ≠ ser la que tiene el saldo.

## Varias direcciones en juego: verificar, no asumir

El usuario puede pasar sin distinguirlas la dirección del **agente**, la de su **cuenta** y a veces una tercera de
otra cuenta suya. Antes de configurar nada:

1. Preguntar **qué dirección ve en la pantalla principal** de la interfaz: esa es la cuenta.
2. Confirmar que el agente esté autorizado **sobre esa** cuenta (`extraAgents`).
3. Recién entonces conectar el bot.

Elegir mal la cuenta es el error que se paga con plata real, así que acá **sí** se pregunta y se verifica: la regla
de «no pedir permiso en cada paso» no aplica cuando lo que se decide es **a qué cuenta apunta el bot**. Si las
direcciones no coinciden, decirlo con los datos a la vista (saldo y movimientos de cada una) en vez de elegir una.

## Vaults: son fondos de copy-trading, no un depósito propio

En Hyperliquid un **vault** es un fondo donde **otra persona opera tu dinero** a cambio de comisión (copy-trading
gestionado). Cuando el usuario dice «cargué en vaults y no sé qué es eso», la explicación llana es:

- Esa plata **no aparece en el saldo de su cuenta** — está en el vault, y por eso el saldo sigue en cero.
- La está operando **un tercero**, no su bot.
- Se retira desde la sección de vaults de la interfaz (hay posición y botón de retiro): el monto se recupera.

Un depósito en vault **nunca** cuenta como fondos disponibles para el bot, y el usuario no debería confundirlo con
una recarga a su cuenta. Consultarlo con `userVaultEquities` para confirmar si hay posición ahí.

## El mínimo por orden: por qué un saldo chico no puede operar aunque «en teoría» alcance

Hyperliquid **rechaza toda orden por debajo de ~$10**, y freqtrade no lo muestra como número redondo: le suma el
margen y calcula su propio piso (con un mínimo de $10 dio **11,17 USDC**). La consecuencia es la que más
desconcierta: **con 5,89 USDC no entra ninguna orden**, ni bajando `stake_amount` a 2 — es un piso del exchange, no
una configuración del bot, y ninguna combinación de parámetros lo esquiva.

- **La firma está en el log** (la respuesta de la API sólo dice `Failed to enter position for <par>`, sin motivo):
  `Minimum stake amount > available balance. 11.17 > 5.30`.
- **Traducirlo antes de reportar**: saldo · mínimo por orden · cuánto falta · cuánto hace falta para operar
  cómodo (dos posiciones ≈ **$25-30**). Ese es el número que el usuario necesita, no la explicación del margen.
- **Es un buen resultado, no un fracaso**: el piso se descubre **antes** de cargar plata. Comparar saldo contra
  mínimo es parte de la verificación, y «faltan $5,28 para una operación» es la entrega.
- Con el saldo por debajo del mínimo el bot queda **conectado y sin poder operar**: no hay riesgo de que dispare
  nada raro, y así se lo puede tranquilizar.
