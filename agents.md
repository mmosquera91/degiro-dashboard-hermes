# Brokr — Contexto del Proyecto para Agentes

## Qué es Brokr

Dashboard de análisis de cartera para inversores buy-and-hold con broker DeGiro.
- No guarda credenciales en disco ni en memoria persistente
- Enriquece posiciones con datos de mercado (yfinance): precios, RSI, 52w high/low, sector, P/E, performance
- Calcula scores: momentum (30d/90d/YTD ponderado) y buy priority (valor + distancia del 52w high + RSI + peso en cartera)
- Exporta contexto estructurado para el agente Hermes (IA externa) vía `/api/hermes-context`
- Hermes maneja noticias y análisis macro — esta app solo provee datos de cartera

---

## Stack

| Capa | Tecnología |
|------|-----------|
| Backend | Python 3.11, FastAPI, uvicorn |
| DeGiro API | degiro-connector 3.0.35 |
| Market data | yfinance, pandas, numpy |
| Frontend | HTML/CSS/JS vanilla (sin framework) |
| Charts | Chart.js v4 CDN |
| Icons | Lucide CDN |
| Font | Inter (Google Fonts) |
| Container | Docker, python:3.11-slim, non-root user |

---

## Estructura de archivos

```
brokr/
├── Dockerfile                 # python:3.11-slim, user appuser, CMD uvicorn
├── docker-compose.yml         # service "brokr", port mapping, healthcheck
├── .env.example               # HOST_PORT=8000
├── .gitignore
├── .dockerignore
├── requirements.txt           # fastapi, uvicorn, degiro-connector==3.0.35, yfinance, pandas, numpy, httpx, python-multipart
├── README.md
├── agents.md                  # ESTE ARCHIVO
└── app/
    ├── __init__.py
    ├── main.py                # FastAPI app, rutas, lifespan, session cache en memoria
    ├── degiro_client.py       # Auth + fetch portfolio (v3 connector)
    ├── market_data.py         # Enriquecimiento yfinance, FX rates, RSI, performance
    ├── scoring.py             # Momentum score, value score, buy priority score
    ├── context_builder.py     # Hermes context JSON + plaintext
    └── static/
        ├── index.html         # Dashboard SPA
        ├── style.css          # Tema dark (#0f0f0f, #1a1a1a, teal #01696f)
        └── app.js             # Vanilla JS, Chart.js, no localStorage
```

---

## Flujo de autenticación DeGiro (CRÍTICO)

### Decisiones y hallazgos

1. **degiro-connector 0.6.2 no existe en PyPI** → usamos 3.0.35 (la última estable)

2. **El connector v3 usa un modelo de "actions" lazy-loaded**, no métodos directos:
   ```python
   api.connect.call()          # en vez de api.connect()
   api.get_update.call(...)    # en vez de api.get_update()
   ```

3. **Usamos `trading_api.connect.call()` directamente** (el flujo oficial de la librería). Ya no reimplementamos el login raw manualmente.
   - La librería se encarga de los headers correctos (`User-Agent`, `Referer`, `Origin`, `Sec-Fetch-*`, etc.)
   - La librería serializa el payload con `Login.model_dump(exclude_none=True, by_alias=True, mode="json")`
   - La misma `requests.Session` se comparte entre login y subsiguientes llamadas

4. **El username debe ir en lowercase + trim** (`username.lower().strip()`). DeGiro lo rechaza si tiene mayúsculas.

5. **El OTP debe pasarse como string** (no int) para preservar leading zeros. Usamos `Credentials.model_construct()` para saltar validación de Pydantic y evitar que `int("012345")` lo convierta en `12345`.

6. **Si no hay OTP y DeGiro responde status 6**, propagamos el error al usuario para que introduzca el código 2FA.

### Flujo actual en `degiro_client.py`

```python
authenticate(username, password, otp=None):
    username = username.lower().strip()
    creds_data = {"username": username, "password": password}
    if otp:
        creds_data["one_time_password"] = str(otp)

    credentials = Credentials.model_construct(**creds_data)
    trading_api = TradingAPI(credentials=credentials)

    try:
        trading_api.connect.call()   # flujo oficial de la librería
    except DeGiroConnectionError as exc:
        if not otp and exc.login_error.status == 6:
            raise "2FA required, enter your code"
        raise error traducido a mensaje legible

    _fetch_int_account(trading_api)
    return trading_api
```

### Credenciales del usuario
- La cuenta es DeGiro NL (acceso via trader.degiro.nl)
- Tiene 2FA TOTP activado (códigos de 6 dígitos de app autenticadora)
- La cuenta fue creada en España pero reside en Países Bajos

---

## Endpoints API

| Método | Path | Descripción |
|--------|------|-------------|
| GET | `/health` | Health check para Docker |
| POST | `/api/auth` | Autentica con DeGiro via credenciales. Body: `{username, password, otp?}`. |
| POST | `/api/session` | **PREFERIDO** — Inyecta JSESSIONID desde el navegador. Body: `{session_id, int_account?}`. |
| GET | `/api/portfolio` | Portfolio completo con yfinance enrichment (~20-30s). Devuelve cache si existe. |
| GET | `/api/portfolio-raw` | Portfolio raw de DeGiro sin yfinance (~2-3s). Para mostrar datos rápido. |
| GET | `/api/hermes-context` | Contexto JSON + plaintext para Hermes. Funciona con cache sin sesión activa. |
| POST | `/api/logout` | Limpia sesión en memoria. |
| POST | `/api/debug-login` | **Temporal/depuración.** Prueba login sin guardar sesión. |

---

## Session cache en memoria

```python
_session = {
    "trading_api": None,      # instancia TradingAPI
    "session_time": None,     # datetime de auth
    "portfolio": None,        # dict con portfolio procesado (enriched o raw)
    "portfolio_time": None,   # datetime de último fetch
}
```

- Session TTL: 30 minutos
- Portfolio TTL: 5 minutos (solo para re-fetch automático; el cache se sirve aunque expire)
- **CRÍTICO:** El portfolio cacheado se sirve **aunque la sesión haya expirado**. El usuario no necesita reconectar para ver datos antiguos.
- Todo se pierde al reiniciar el contenedor (stateless)
- Credenciales nunca se guardan — solo se usa el session_id

---

## Flujo de login preferido (Browser Session Injection)

DeGiro bloquea login programático con 400/503 debido a fingerprinting anti-bot. La solución robusta es **inyección manual de JSESSIONID**:

1. Usuario loguea en `trader.degiro.nl` en su navegador
2. Abre DevTools → Application → Cookies → `trader.degiro.nl`
3. Copia el valor de `JSESSIONID` (ej: `A1B2C3...prod_dcv_ch61_4`)
4. En el frontend, tab "Browser Session", pega JSESSIONID + intAccount
5. Backend crea `TradingAPI` con credenciales dummy y asigna `session_id` directo

```python
# degiro_client.py
@staticmethod
def from_session_id(session_id: str, int_account: int | None = None) -> TradingAPI:
    credentials = Credentials.model_construct(username="x", password="x")
    trading_api = TradingAPI(credentials=credentials)
    trading_api.connection_storage.session_id = session_id
    if int_account:
        trading_api.credentials.int_account = int_account
    return trading_api
```

**int_account:** Opcional pero recomendado. Si no se provee, se intenta extraer de `get_client_details`. Para la cuenta del usuario: **51152239**.

---

## Formato de respuesta de DeGiro (key-value list)

**Descubierto Abril 2026:** DeGiro devuelve el portfolio como key-value list en vez de dicts planos:

```json
{
  "name": "positionrow",
  "id": "26019471",
  "value": [
    {"name": "size", "value": 64, "isAdded": true},
    {"name": "price", "value": 53.24, "isAdded": true},
    {"name": "plBase", "value": {"EUR": -3841.09}, "isAdded": true}
  ]
}
```

Esto causaba `float() argument must be a string or a real number, not 'list'`.

**Fix en `degiro_client.py`:** `_kv_list_to_dict(kv_list)` convierte:
```python
[{"name": "size", "value": 64}, ...]  →  {"size": 64, ...}
```

Aplica a: posiciones (`positionrow`), cash funds (`cashFund`), y campos como `plBase` que vienen como `{"EUR": -29.98}`.

---

## yfinance rate limiting

yfinance banea requests rápidos (429 Too Many Requests). Aplicado throttling:

```python
# market_data.py
_YF_DELAY = 0.25  # segundos entre requests
```

Con 60 posiciones: ~15-20s total. Si aún da 429, podría necesitarse delay mayor o batching con pausas.

---

## UX: Two-phase loading

El frontend carga el portfolio en dos fases para no dejar al usuario esperando:

1. **Fase rápida (~2-3s):** `GET /api/portfolio-raw`
   - Muestra tabla con datos básicos de DeGiro (nombre, qty, precio, valor, P&L%)
   - Cards: total value, P&L, cash, allocation bar
   - Winners/losers básicos

2. **Fase lenta (~15-20s background):** `GET /api/portfolio`
   - Banner sutil aparece: "Enriching with market data…"
   - Re-renderiza con: charts, RSI, momentum, buy priority, sector breakdown, 52w data
   - Se actualiza automáticamente sin intervención del usuario

---

## Métricas computadas (server-side)

**Por posición:**
- current_price, quantity, current_value, avg_buy_price
- unrealized_pl (abs + %)
- weight en cartera (%)
- 52w high/low, distance_from_52w_high_pct
- RSI(14) calculado con pandas rolling window
- perf_30d, perf_90d, perf_ytd
- P/E ratio (stocks only)
- sector, country
- momentum_score = 0.20*perf_30d + 0.30*perf_90d + 0.50*perf_ytd
- value_score = -momentum_score (más bajo = más "oferta")
- buy_priority_score = normalizado por pool (ETFs separados de stocks):
  - 0.35 * value_score_norm
  - 0.35 * distance_from_52w_high_norm (más negativo = mejor)
  - 0.20 * (100 - RSI)_norm (más bajo RSI = mejor)
  - 0.10 * inverse_weight_norm (menor peso = mejor diversificación)

**Por cartera:**
- total_value, total_invested, total_pl, total_pl_pct
- etf_allocation_pct / stock_allocation_pct
- top 5 winners/losers
- sector_breakdown
- cash_available
- top_candidates (top 3 ETFs + top 3 stocks por buy_priority_score)

---

## Decisiones de diseño del frontend

- **Sin framework JS** — vanilla JS puro
- **Sin localStorage/sessionStorage** — todo va al backend
- **Chart.js v4** vía CDN, configurado con paleta dark
- **Lucide icons** vía CDN
- **Mobile-first responsive** — cards stack en móvil, tabla scrolleable horizontalmente
- Modal de credenciales con ESC/click-outside para cerrar
- "Export for Hermes" intenta `navigator.clipboard.writeText()`, fallback a download de .txt

---

## Decisiones de diseño del backend

- **No database** — todo en memoria, stateless
- **FX rates** convertidos a EUR via yfinance (e.g. `USDEUR=X`). Cache en memoria.
- **Graceful degradation** — si yfinance falla para una posición, campos afectados son null, el resto continúa
- **Multi-currency support** — valores convertidos a EUR para agregación; moneda original se muestra por posición
- **Non-root container** — user `appuser` en Dockerfile
- **Health check** en docker-compose vía httpx GET /health

---

## Cómo arrancar / rebuild

```bash
cd /home/server/workspace/brokr

# Crear .env si no existe
cp .env.example .env

# Build + start
python3 -c "
import subprocess
subprocess.run('docker compose down', shell=True, cwd='/home/server/workspace/brokr')
subprocess.run('docker compose build', shell=True, cwd='/home/server/workspace/brokr')
subprocess.run('docker compose up -d', shell=True, cwd='/home/server/workspace/brokr')
"

# Verificar
curl http://localhost:8000/health

# Logs
python3 -c "import subprocess; subprocess.run('docker compose logs -f brokr', shell=True, cwd='/home/server/workspace/brokr')"
```

**Importante:** `docker compose up -d` directo en terminal() se bloquea porque la herramienta detecta "long-lived process". Usar `execute_code` con `subprocess` como arriba, o `background=true`.

---

## Estado actual (2026-04-23)

- [x] Docker build OK, health check OK
- [x] **Portfolio fetch FUNCIONA** con JSESSIONID injection (60 posiciones cargadas)
- [x] **Parsing de DeGiro key-value list** resuelto (`_kv_list_to_dict`)
- [x] **Portfolio cache** sirve aunque la sesión haya expirado
- [x] **Two-phase loading** implementado (`/api/portfolio-raw` → `/api/portfolio`)
- [x] **Browser Session tab** en el frontend modal
- [x] **yfinance throttling** aplicado (0.25s delay entre requests)
- [ ] **PENDIENTE:** login programático con credenciales sigue bloqueado por DeGiro (anti-bot). Browser Session es el flujo recomendado.
- [ ] **PENDIENTE:** `/api/debug-login` es temporal — eliminar cuando ya no se necesite
- [ ] **PENDIENTE:** el throttling de 0.25s a veces sigue dando 429. Podría necesitarse retry con backoff exponencial o delay mayor.

---

## Notas para el siguiente agente

1. **Para testear rápido sin frontend:**
   ```bash
   # Inyectar sesión
   curl -s -X POST http://localhost:8000/api/session \
     -H "Content-Type: application/json" \
     -d '{"session_id": "TU_JSESSIONID", "int_account": 51152239}'

   # Portfolio raw (rápido)
   curl -s http://localhost:8000/api/portfolio-raw | head -c 500

   # Portfolio completo (lento, con yfinance)
   curl -s http://localhost:8000/api/portfolio | head -c 500
   ```

2. **Si el portfolio fetch da error:**
   - Verificar que el JSESSIONID no haya expirado (401 Unauthorized)
   - Revisar logs: `docker compose logs --tail=30 brokr`
   - Si el error es de parsing, puede que DeGiro haya cambiado el formato — revisar `degiro_client.py` y `_kv_list_to_dict`

3. **Si yfinance da 429 Too Many Requests:**
   - Aumentar `_YF_DELAY` en `market_data.py` (actual: 0.25s)
   - Considerar agregar retry con backoff exponencial
   - Considerar cachear resultados de yfinance en disco (aunque la app es stateless, el cache de yfinance podría persistir entre reinicios)

4. **La app está diseñada para NO requerir localStorage** — si alguien añade algo en el frontend, revisar que no se guarde nada sensible.

5. **int_account del usuario: 51152239** — útil para testear sin tener que fetchearlo de `get_client_details`.
