# Brokr — UI Reference

Mapa de todos los bloques y secciones de la interfaz, con su intención y comportamiento.

---

## Estructura general

La UI es una SPA de una sola página (`/`). Tiene **dos vistas principales** (DeGiro e Indexa Capital) que se alternan con tabs. Todos los datos monetarios pueden ocultarse con el modo privacidad.

---

## Elementos globales (siempre presentes)

### Barra de navegación superior
Contiene el logo, los tabs de vista (**DeGiro** / **Indexa Capital**), y los botones de acción principales. Los botones de acción varían según la vista activa:
- **Sync from DeGiro** — abre el modal de sesión para inyectar un nuevo JSESSIONID.
- **Update Prices** — fuerza re-enriquecimiento con yfinance sin re-sincronizar DeGiro. Solo aparece cuando hay portfolio cargado.
- **Export for Hermes** — copia al portapapeles (o descarga como `.txt`) el contexto estructurado para el agente de IA.
- **Privacy** (ojo) — activa/desactiva el modo privacidad. Cuando está activo, todos los valores monetarios del dashboard muestran `***` o quedan en blanco.

### Modal de sesión (`#cred-modal`)
Diálogo que aparece al pulsar "Sync from DeGiro" o cuando la sesión ha expirado. Contiene un campo para pegar el `JSESSIONID` copiado desde las cookies del navegador en `trader.degiro.nl`. Al confirmar, el backend crea la sesión y arranca la carga del portfolio.

### Indicador de frescura (`freshness-timestamp`)
Texto pequeño junto al logo que muestra cuándo se actualizaron los datos por última vez ("Updated 5 min ago"). Se actualiza cada 30 segundos sin recargar datos.

### Badge de datos obsoletos (`#stale-badge`)
Aparece cuando los datos del portfolio son de un día anterior al actual. Avisa al usuario de que los precios pueden no estar al día. Desaparece automáticamente cuando se carga datos frescos.

### Overlay de carga (`#loading-overlay`)
Pantalla completa con spinner que bloquea la UI durante la carga inicial del portfolio raw (fase 1, ~2-3s).

### Banner de enriquecimiento (`#enrichment-modal`)
Modal no bloqueante que aparece mientras el backend está descargando datos de yfinance en segundo plano (fase 2, ~9s). Desaparece solo cuando termina. Puede cerrarse manualmente sin cancelar el proceso.

### Toast notifications (`#toast-container`)
Notificaciones flotantes en la esquina superior derecha. Se auto-descartan a los 4 segundos. Máximo 3 visibles simultáneamente. Variantes: `success` (verde), `error` (rojo), `info` (gris). El toast de progreso de "Updating prices…" es especial: permanece hasta que termina el enriquecimiento y luego cambia a confirmación.

### Empty state (`#empty-state`)
Pantalla que se muestra cuando no hay portfolio cargado aún (primera vez o sesión expirada). Contiene un botón "Connect to DeGiro" que abre el modal de sesión.

---

## Vista DeGiro (`#degiro-view`)

### KPI Cards — Resumen financiero
Cinco tarjetas en la parte superior que dan un vistazo rápido del estado de la cartera:

| Tarjeta | Qué muestra |
|---------|-------------|
| **Portfolio** | Valor total incluyendo cash. Subtexto: variación diaria (€ y %) con badge verde/rojo. Línea secundaria: P&L total acumulado. |
| **Invested** | Valor de las posiciones abiertas (sin cash). Subtexto: número de posiciones. |
| **Cash** | Efectivo disponible en cuenta. Si el cash cae por debajo del 1% del portfolio, la tarjeta se resalta en dorado como aviso. |
| **Unrealized P&L** | Ganancia/pérdida no realizada total vs coste de adquisición. Badge con porcentaje. |
| **Positions** | Número total de posiciones. Subtexto: desglose `N ETFs · M stocks`. |

### Barra de asignación ETF / Stock
Barra visual debajo de las KPI cards. Muestra la distribución actual entre ETFs (teal) y stocks (naranja), con el valor en EUR y el porcentaje de cada bloque. El objetivo por defecto es 70% ETF / 30% STOCK (configurable vía variables de entorno).

### Métricas de concentración
Tres tarjetas compactas que miden el riesgo de concentración de la cartera:

| Tarjeta | Qué muestra |
|---------|-------------|
| **Top Holding** | Peso (%) de la posición más grande. Subtexto: nombre del activo. |
| **Top 5 Weight** | Suma de pesos del top 5 de posiciones. Subtexto: lista de símbolos. |
| **HHI** | Índice Herfindahl-Hirschman (suma de cuadrados de pesos, escala 0–10 000). Etiqueta automática: `Diversified` (<1000) / `Concentrated` (1000–1800) / `High Risk` (>1800). |

### Gráficos de composición
Tres gráficos que describen la estructura de la cartera. Solo se re-renderizan cuando cambian los precios (hash de posiciones).

| Gráfico | Tipo | Qué muestra |
|---------|------|-------------|
| **Top 10 by Weight** | Barras horizontales | Las 10 posiciones con mayor peso. ETFs en teal, stocks en naranja. |
| **Sector Breakdown** | Donut | Distribución del valor en EUR por sector. Tooltips con EUR y %. |
| **Geographic Breakdown** | Donut | Distribución por país de cotización inferido por yfinance. |

### Tabla de posiciones
Tabla central del dashboard. Encima tiene tres **filter tabs**: `All`, `ETF`, `STOCK`. Las cabeceras de columna son clicables para ordenar (toggle asc/desc).

La tabla tiene **scroll vertical interno** con altura máxima (~520px escritorio / 420px móvil) — los encabezados quedan siempre visibles aunque la lista sea larga. Ordenada por nombre A→Z por defecto; clic en encabezado alterna asc/desc.

Columnas visibles:

| Columna | Descripción | Color |
|---------|-------------|-------|
| Name | Nombre del producto. Icono de alerta si enriquecimiento falló o falta FX. | — |
| Value (EUR) | Valor actual de la posición en EUR. | — |
| P&L % | Rentabilidad no realizada vs precio medio de compra. | Verde / Rojo |
| Price | Precio actual en la moneda original. | — |
| Qty | Cantidad de títulos. | — |
| Weight | Peso de la posición en el portfolio (%). | — |
| Type | ETF o STOCK. | — |
| Avg Buy | Precio medio de compra. | — |
| RSI | RSI de 14 periodos. | — |
| Momentum | Score `0.20×30d + 0.30×90d + 0.50×1Y`. | Verde fuerte (>30) / Verde suave (0–30) / Rojo suave (−25–0) / Rojo fuerte (<−25, quality gate) |
| Buy Priority | Score 0–1, `null` si falla quality gates. | Verde (≥0.6) / Ámbar (0.4–0.6) / Rojo (<0.4) |

**Fila de detalle** (expandible al hacer clic en una fila): muestra ISIN, divisa, sector, 52w high/low, distancia al 52w high, rendimientos a 30d/90d/YTD/1Y, P/E ratio, value score, y la razón de bloqueo si `buy_priority_score` es null.

### Buy Radar
Dos paneles side-by-side con los mejores candidatos de compra según `buy_priority_score`: uno para **ETFs** y otro para **Stocks**. Cada entrada muestra nombre, símbolo, la razón principal del score y la puntuación numérica. Si el candidato es de la watchlist (no poseído), lleva el badge `Watchlist`.

### Winners / Losers
Dos listas de 5 posiciones: las de **mayor rentabilidad** y las de **peor rentabilidad** por P&L %. Cada entrada muestra nombre, símbolo, porcentaje y valor absoluto en EUR.

### Benchmark — Portfolio vs S&P 500
Gráfico de líneas que compara la evolución del portfolio frente al S&P 500, ambos indexados a 100 desde el primer snapshot. El portfolio usa **Time-Weighted Return (TWR)** para neutralizar el efecto de depósitos y retiradas. Si solo hay un snapshot, muestra una tabla de comparación en lugar del gráfico. Si no hay snapshots, muestra un estado vacío.

### Attribution Table
Tabla que desglosa cuánto ha contribuido cada posición al retorno total del portfolio. Aparece bajo el título "Attribution Analysis (click to expand)".

Al expandir muestra una **leyenda fija** que explica cada métrica antes de la tabla:

| Columna | Fórmula | Interpretación |
|---------|---------|----------------|
| **Absolute** | `perf_ytd × peso` | Cuánto sumó o restó al rendimiento total de la cartera este año. Positivo = aportó, negativo = drenó. |
| **Relative vs S&P 500** | `(perf_ytd − ref_ytd) × peso` | Cuánto aportó en exceso de la referencia histórica del S&P 500. Positivo = batió al mercado históricamente. |

**Cómo se calcula `ref_ytd`** (benchmark de referencia):
```
ref_ytd = promedio_mensual(^GSPC, 6 años) × meses_transcurridos_en_el_año
```
No depende de los snapshots del usuario — usa datos reales de mercado. Se cachea 24 horas.

Los encabezados de columna tienen tooltip con la fórmula al hacer hover.

Requiere posiciones enriquecidas con `perf_ytd`. Si no hay datos, muestra "No attribution data yet".

### Health Alerts
Lista de alertas automáticas calculadas en cada enriquecimiento (por `health_checks.py`). Cada alerta tiene tipo, mensaje y severidad (`info` / `warn` / `critical`). Si no hay alertas, muestra "All systems healthy".

### Rebalance Planner
Panel con un campo de entrada para indicar cuánto capital se quiere desplegar (en EUR). Al calcular, llama a `/api/rebalance-plan` y muestra:
- **Hold reserve**: euros retenidos y por qué.
- **Warnings**: condiciones que impiden una asignación óptima.
- **Projected allocation**: ETF/Stock % antes y después del despliegue.
- **Buy list**: lista ordenada de compras recomendadas con importe y razón.
- **Excluded**: posiciones que pasaron el scoring pero quedaron fuera del plan.
- **Watchlist candidates**: candidatos no poseídos (informativo, no afecta a la asignación).

### Snapshot Manager (`<details>`)
Desplegable en la parte inferior. Muestra una tabla de todos los snapshots históricos guardados (fecha, valor del portfolio, retorno del benchmark, si tiene datos completos). Botón **Save Snapshot Now** guarda el estado actual. Cada fila tiene un botón **Delete** con confirmación.

### Watchlist (`<details>`)
Panel expandible para gestionar tickers no poseídos que se quieren seguir. Se añaden por ISIN; el backend resuelve el símbolo y lo clasifica automáticamente como ETF o STOCK.

Columnas de la tabla: nombre, tipo (botón toggle ETF↔STOCK), buy priority score, RSI, distancia al 52w high, botón de eliminar.

Los tickers de la watchlist compiten en el mismo pool de scoring que las posiciones reales y pueden aparecer en el Buy Radar.

---

## Vista Indexa Capital (`#indexa-view`)

Vista separada para la cuenta en Indexa Capital (robo-advisor). Se carga de forma lazy la primera vez que se activa el tab. Requiere `INDEXA_API_TOKEN` en el `.env`; si no está configurado, muestra un estado vacío explicativo.

### KPI Cards — Indexa
Métricas del portfolio gestionado por Indexa:

| Tarjeta | Qué muestra |
|---------|-------------|
| **Total Value** | Valor actual del portfolio. Subtexto: número de fondos. |
| **Invested** | Capital principal aportado. |
| **Return (EUR)** | Ganancia/pérdida absoluta desde inicio. |
| **Return (%)** | Retorno TWR total. Subtexto: retornos de 1Y / 1M / 1W si están disponibles. |
| **Last Contribution** | Importe y fecha del último depósito. |
| **Annual Return** | Retorno anualizado desde inicio. |
| **Volatility** | Volatilidad histórica del portfolio (%). |
| **Sharpe Ratio** | Ratio de Sharpe. |
| **Max Drawdown** | Caída máxima (%). Subtexto: importe en EUR y fechas del periodo. |
| **Risk Profile** | Perfil de riesgo asignado por Indexa (escala /10) y retorno esperado. |

### Gráfico de asignación por fondos
Donut que muestra el peso de cada fondo dentro del portfolio Indexa.

### Gráfico de rendimiento histórico
Línea temporal del valor del portfolio (teal) y el capital invertido (naranja discontinuo). Selector de rango de tiempo: `1M` / `6M` / `1Y` / `5Y` / `All`.

### Tabla de fondos
Lista de todos los fondos de la cartera Indexa, ordenados por valor descendente. Columnas: nombre, ISIN, clase de activo, valor actual, coste, ganancia/pérdida, peso (%).
