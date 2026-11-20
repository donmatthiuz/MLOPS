import React, { useEffect, useMemo, useState } from 'react'

const FUELS = [
  { id: 'super', label: 'Súper', tone: 'super' },
  { id: 'regular', label: 'Regular', tone: 'regular' },
  { id: 'diesel', label: 'Diésel', tone: 'diesel' },
]

const money = new Intl.NumberFormat('es-GT', {
  style: 'currency',
  currency: 'GTQ',
  maximumFractionDigits: 2,
})
const number = new Intl.NumberFormat('es-GT')

function day(value) {
  if (!value) return null
  const parsed = new Date(`${String(value).slice(0, 10)}T12:00:00`)
  return Number.isNaN(parsed.getTime()) ? null : parsed
}

function dateLabel(value, options = { day: 'numeric', month: 'short', year: 'numeric' }) {
  const parsed = day(value)
  return parsed ? new Intl.DateTimeFormat('es-GT', options).format(parsed) : 'Sin fecha'
}

function weekLabel(value) {
  const start = day(value)
  if (!start) return 'Semana no disponible'
  const end = new Date(start)
  end.setDate(end.getDate() + 6)
  return `${dateLabel(value, { day: 'numeric', month: 'short' })} – ${new Intl.DateTimeFormat('es-GT', { day: 'numeric', month: 'short', year: 'numeric' }).format(end)}`
}

function generatedLabel(value) {
  if (!value) return 'Sin fecha'
  const parsed = new Date(value)
  return Number.isNaN(parsed.getTime())
    ? 'Sin fecha'
    : new Intl.DateTimeFormat('es-GT', {
        dateStyle: 'medium',
        timeStyle: 'short',
        timeZone: 'America/Guatemala',
      }).format(parsed)
}

function price(value) {
  return value == null ? '—' : money.format(Number(value))
}

function percent(value) {
  return value == null ? '—' : `${new Intl.NumberFormat('es-GT', { maximumFractionDigits: 1 }).format(Number(value) * 100)} %`
}

function directionLabel(value) {
  return { sube: 'Sube', baja: 'Baja', se_mantiene: 'Se mantiene' }[value] || 'Sin dato'
}

function modelLabel(value) {
  return {
    linea_base: 'Línea base',
    linea_base_respaldo: 'Línea base de respaldo',
    regresion_logistica: 'Regresión logística',
    arbol_decision: 'Árbol de decisión',
  }[value] || value || 'Sin dato'
}

async function request(path, signal) {
  const response = await fetch(path, { signal, headers: { Accept: 'application/json' } })
  if (!response.ok) {
    let detail
    try {
      detail = (await response.json()).detail
    } catch {
      // The server may return a non-JSON error page.
    }
    const error = new Error(typeof detail === 'string' ? detail : `Error ${response.status}`)
    error.status = response.status
    throw error
  }
  return response.json()
}

function useRemote(path, refreshKey) {
  const [state, setState] = useState({ data: null, error: null, loading: true })

  useEffect(() => {
    const controller = new AbortController()
    setState((previous) => ({ ...previous, error: null, loading: true }))
    request(path, controller.signal)
      .then((data) => setState({ data, error: null, loading: false }))
      .catch((error) => {
        if (error.name !== 'AbortError') setState({ data: null, error, loading: false })
      })
    return () => controller.abort()
  }, [path, refreshKey])

  return state
}

function Icon({ name, size = 20, className = '' }) {
  const shared = {
    width: size,
    height: size,
    viewBox: '0 0 24 24',
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth: 1.8,
    strokeLinecap: 'round',
    strokeLinejoin: 'round',
    'aria-hidden': true,
    className,
  }
  if (name === 'fuel') return <svg {...shared}><path d="M4 21V5a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v16M3 21h15M4 10h13M8 6h5" /><path d="M17 7h1a3 3 0 0 1 3 3v8a2 2 0 0 1-4 0" /></svg>
  if (name === 'refresh') return <svg {...shared}><path d="M20 7v5h-5M4 17v-5h5" /><path d="M5.6 9a7 7 0 0 1 12.2-2L20 12M4 12l2.2 5a7 7 0 0 0 12.2-2" /></svg>
  if (name === 'chart') return <svg {...shared}><path d="M3 3v18h18M6 16l5-5 4 3 5-7" /></svg>
  if (name === 'spark') return <svg {...shared}><path d="m12 2 1.7 6.3L20 10l-6.3 1.7L12 18l-1.7-6.3L4 10l6.3-1.7L12 2ZM19 17l.6 1.4L21 19l-1.4.6L19 21l-.6-1.4L17 19l1.4-.6L19 17Z" /></svg>
  if (name === 'up') return <svg {...shared}><path d="m5 15 7-7 7 7M12 8v11" /></svg>
  if (name === 'down') return <svg {...shared}><path d="m5 9 7 7 7-7M12 5v11" /></svg>
  if (name === 'flat') return <svg {...shared}><path d="M4 12h16m-5-5 5 5-5 5" /></svg>
  if (name === 'info') return <svg {...shared}><circle cx="12" cy="12" r="9" /><path d="M12 11v5m0-8h.01" /></svg>
  return null
}

function Loading({ height = 140 }) {
  return <div className="loading-block" style={{ minHeight: height }} role="status" aria-label="Cargando datos"><span>Cargando datos…</span></div>
}

function EmptyState({ title, message, kind = 'empty' }) {
  return <div className={`empty-state empty-state--${kind}`} role={kind === 'error' ? 'alert' : 'status'}>
    <span className="empty-state__icon"><Icon name="info" size={22} /></span>
    <div><strong>{title}</strong><p>{message}</p></div>
  </div>
}

function errorMessage(error) {
  if (error?.status === 503) return 'La capa Oro no está disponible. Revisa el acceso a S3 y vuelve a intentar.'
  return 'No se pudo cargar esta sección. Intenta actualizar los datos.'
}

function PriceCard({ fuel, row, selected, loading, onClick }) {
  return <button type="button" className={`price-card price-card--${fuel.tone} ${selected ? 'price-card--selected' : ''}`} onClick={onClick} aria-pressed={selected}>
    <span className="price-card__top"><span className="fuel-mark" /><span>{fuel.label}</span><span className="price-card__detail">Ver detalle</span></span>
    <span className="price-card__value">{loading ? '···' : price(row?.precio_promedio)}<small>/ galón</small></span>
    <span className="price-card__week">{row ? `Última semana: ${weekLabel(row.semana)}` : 'Sin lecturas disponibles'}</span>
    <span className="price-card__range"><span>Mín. {price(row?.precio_minimo)}</span><span>Máx. {price(row?.precio_maximo)}</span></span>
  </button>
}

function TrendChart({ rows, fuel }) {
  const ordered = useMemo(() => [...rows]
    .filter((row) => row.precio_promedio != null && Number.isFinite(Number(row.precio_promedio)))
    .sort((a, b) => String(a.semana).localeCompare(String(b.semana)))
    .slice(-12), [rows])
  if (ordered.length < 2) return <EmptyState title="Aún no hay tendencia" message="Se necesitan al menos dos semanas para trazar la evolución del precio." />

  const values = ordered.map((row) => Number(row.precio_promedio)).filter(Number.isFinite)
  if (values.length < 2) return <EmptyState title="Aún no hay tendencia" message="No hay suficientes precios válidos para dibujar la gráfica." />
  const low = Math.min(...values)
  const high = Math.max(...values)
  const spread = Math.max(high - low, 1)
  const minimum = low - spread * 0.16
  const maximum = high + spread * 0.16
  const x = (index) => 58 + (index / (ordered.length - 1)) * 684
  const y = (value) => 217 - ((Number(value) - minimum) / (maximum - minimum)) * 172
  const path = ordered.map((row, index) => `${index === 0 ? 'M' : 'L'} ${x(index)} ${y(row.precio_promedio)}`).join(' ')
  const fill = `${path} L ${x(ordered.length - 1)} 218 L ${x(0)} 218 Z`
  const latest = ordered.at(-1)
  const previous = ordered.at(-2)
  const difference = Number(latest.precio_promedio) - Number(previous.precio_promedio)

  return <div className="chart-wrap">
    <div className="chart-summary"><span>Últimas {ordered.length} semanas con datos</span><strong>{difference === 0 ? 'Sin cambio' : `${difference > 0 ? '+' : '−'}${price(Math.abs(difference))}`} <small>vs. semana anterior disponible</small></strong></div>
    <svg className="trend-chart" viewBox="0 0 800 260" preserveAspectRatio="xMidYMid meet" aria-hidden="true">
      <defs><linearGradient id="chart-fill" x1="0" x2="0" y1="0" y2="1"><stop offset="0%" stopColor="#246aa8" stopOpacity=".22" /><stop offset="100%" stopColor="#246aa8" stopOpacity="0" /></linearGradient></defs>
      {[0, 1, 2, 3].map((step) => {
        const value = minimum + ((maximum - minimum) * (3 - step)) / 3
        const lineY = 45 + (step * 172) / 3
        return <g key={step}><line x1="58" x2="742" y1={lineY} y2={lineY} stroke="#dce5ed" strokeDasharray="4 5" /><text x="48" y={lineY + 4} textAnchor="end" className="chart-axis">Q {value.toFixed(1)}</text></g>
      })}
      <path d={fill} fill="url(#chart-fill)" />
      <path d={path} fill="none" stroke="#246aa8" strokeWidth="3.5" strokeLinejoin="round" strokeLinecap="round" />
      {ordered.map((row, index) => <circle key={`${row.semana}-${index}`} cx={x(index)} cy={y(row.precio_promedio)} r={index === ordered.length - 1 ? 6 : 3.5} fill="#fff" stroke="#246aa8" strokeWidth="2.5" />)}
      {[0, Math.floor((ordered.length - 1) / 2), ordered.length - 1].filter((index, position, all) => all.indexOf(index) === position).map((index) => <text key={index} x={x(index)} y="248" textAnchor={index === 0 ? 'start' : index === ordered.length - 1 ? 'end' : 'middle'} className="chart-axis">{dateLabel(ordered[index].semana, { day: 'numeric', month: 'short' })}</text>)}
    </svg>
    <p className="chart-caption">Precio promedio semanal de {fuel.label.toLowerCase()}, en quetzales por galón. Los valores exactos aparecen en la tabla de abajo.</p>
  </div>
}

function Forecast({ resource, fuel, observedWeek }) {
  if (resource.loading) return <Loading height={220} />
  if (resource.error?.status === 404) return <EmptyState title="Sin pronóstico todavía" message={`Oro aún no ha generado una predicción para ${fuel.label.toLowerCase()}.`} />
  if (resource.error) return <EmptyState title="Pronóstico no disponible" message={errorMessage(resource.error)} kind="error" />
  const forecast = resource.data
  if (!forecast) return <EmptyState title="Sin pronóstico todavía" message="No hay una predicción disponible para este combustible." />
  const direction = forecast.prediccion || 'sin_dato'
  const icon = direction === 'sube' ? 'up' : direction === 'baja' ? 'down' : 'flat'
  return <div className="forecast-body">
    <div className={`forecast-direction forecast-direction--${direction}`}><span className="forecast-direction__icon"><Icon name={icon} size={30} /></span><div><span>Dirección estimada</span><strong>{directionLabel(direction)}</strong></div></div>
    <p className="forecast-week">Para la semana del <strong>{weekLabel(forecast.semana)}</strong></p>
    <div className="forecast-meta"><span>Modelo utilizado<strong>{modelLabel(forecast.modelo)}</strong></span><span>Probabilidad<strong>{forecast.probabilidad == null ? 'No disponible' : percent(forecast.probabilidad)}</strong></span></div>
    {forecast.probabilidad == null && <p className="inline-note"><Icon name="info" size={16} /> La línea base no calcula probabilidades.</p>}
    {observedWeek && <p className="forecast-context">Último precio observado: semana del {weekLabel(observedWeek)}. El pronóstico se basa en los datos disponibles de ese combustible.</p>}
  </div>
}

function Metrics({ resource }) {
  if (resource.loading) return <Loading height={180} />
  if (resource.error?.status === 404) return <EmptyState title="Sin métricas todavía" message="Las métricas aparecerán cuando se ejecute la capa Oro." />
  if (resource.error) return <EmptyState title="Métricas no disponibles" message={errorMessage(resource.error)} kind="error" />
  const metrics = resource.data
  if (!metrics) return <EmptyState title="Sin métricas todavía" message="No hay resultados del modelo para mostrar." />
  return <div className="metrics-content">
    <div className="metrics-top"><div><span className="section-kicker">ÚLTIMA EJECUCIÓN</span><h3>{modelLabel(metrics.modelo_elegido)}</h3></div><span className="metrics-date">{generatedLabel(metrics._generado_en)}</span></div>
    <div className="metrics-grid"><div><span>Exactitud del modelo</span><strong>{percent(metrics.accuracy_modelo)}</strong></div><div><span>Exactitud de la línea base</span><strong>{percent(metrics.accuracy_linea_base)}</strong></div><div><span>F1 macro</span><strong>{percent(metrics.f1_macro_modelo)}</strong></div><div><span>Ejemplos evaluados</span><strong>{metrics.n_ejemplos == null ? '—' : number.format(metrics.n_ejemplos)}</strong></div></div>
    {metrics.modo_pocos_datos && <p className="inline-note"><Icon name="info" size={16} /> Aún hay pocos datos para entrenar un clasificador; se utiliza la línea base.</p>}
    {metrics.motivo && <p className="metrics-reason">{metrics.motivo}</p>}
  </div>
}

export default function App() {
  const [fuelId, setFuelId] = useState('super')
  const [refreshKey, setRefreshKey] = useState(0)
  const [fromInput, setFromInput] = useState('')
  const [toInput, setToInput] = useState('')
  const [filters, setFilters] = useState({ from: '', to: '' })
  const [filterError, setFilterError] = useState('')
  const [page, setPage] = useState(0)
  const fuel = FUELS.find((item) => item.id === fuelId)
  const parameters = new URLSearchParams({ combustible: fuelId, limit: '100' })
  if (filters.from) parameters.set('desde', filters.from)
  if (filters.to) parameters.set('hasta', filters.to)

  const health = useRemote('/health', refreshKey)
  const current = useRemote('/precios/actual', refreshKey)
  const forecast = useRemote(`/prediccion?combustible=${fuelId}`, refreshKey)
  const history = useRemote(`/precios?${parameters}`, refreshKey)
  const metrics = useRemote('/modelo/metricas', refreshKey)
  const currentRows = Array.isArray(current.data) ? current.data : []
  const currentByFuel = Object.fromEntries(currentRows.map((row) => [row.combustible, row]))
  const rows = Array.isArray(history.data) ? history.data : []
  const visibleRows = rows.slice(page * 10, page * 10 + 10)
  const maxPages = Math.max(1, Math.ceil(rows.length / 10))
  const latestWeek = currentRows.reduce((latest, row) => String(row.semana) > latest ? String(row.semana) : latest, '')

  function chooseFuel(id) {
    setFuelId(id)
    setPage(0)
  }

  function applyFilters(event) {
    event.preventDefault()
    if (fromInput && toInput && fromInput > toInput) {
      setFilterError('La fecha inicial no puede ser posterior a la final.')
      return
    }
    setFilterError('')
    setPage(0)
    setFilters({ from: fromInput, to: toInput })
  }

  function clearFilters() {
    setFromInput('')
    setToInput('')
    setFilterError('')
    setPage(0)
    setFilters({ from: '', to: '' })
  }

  return <>
    <a className="skip-link" href="#main-content">Ir al contenido principal</a>
    <header className="site-header"><div className="shell header-inner"><a className="brand" href="#inicio" aria-label="Gasolina GT, ir al inicio"><span className="brand-icon"><Icon name="fuel" size={22} /></span><span>Gasolina<span className="brand-accent">GT</span><small>OBSERVATORIO DE PRECIOS</small></span></a><nav aria-label="Navegación principal"><a href="#resumen">Resumen</a><a href="#historico">Histórico</a><a href="#modelo">Modelo</a></nav><a className="header-docs" href="/docs">Documentación API</a></div></header>

    <main id="main-content">
      <section className="hero" id="inicio"><div className="shell hero-inner"><div className="hero-content"><div className="eyebrow"><span className="eyebrow-line" /> DATOS DE COMBUSTIBLES · GUATEMALA</div><h1>Entiende cómo se mueve <em>el precio del combustible.</em></h1><p>Consulta precios semanales, sigue su evolución y conoce la dirección estimada para la próxima semana disponible.</p><div className="hero-actions"><a className="primary-link" href="#resumen">Explorar precios</a><a className="secondary-link" href="#historico">Ver histórico</a></div></div><div className="hero-aside"><div className="hero-aside__label">ESTADO DE LOS DATOS</div><div className={`status-pill ${health.loading ? 'status-pill--loading' : health.error ? 'status-pill--error' : 'status-pill--ok'}`} role="status"><span className="status-dot" />{health.loading ? 'Comprobando conexión' : health.error ? 'Oro no disponible' : 'Datos conectados'}</div><div className="hero-aside__divider" /><span>Última semana disponible</span><strong>{latestWeek ? weekLabel(latestWeek) : current.loading ? 'Cargando…' : 'Sin datos'}</strong><p>Los precios y pronósticos muestran su fecha de referencia; no representan valores en tiempo real.</p></div></div><div className="hero-grid" aria-hidden="true" /></section>

      <div className="shell dashboard">
        <div className="dashboard-heading" id="resumen"><div><span className="section-kicker">PANORAMA SEMANAL</span><h2>Precios por combustible</h2><p>Promedio por galón de la última semana disponible para cada tipo.</p></div><button type="button" className="refresh-button" onClick={() => setRefreshKey((key) => key + 1)} disabled={health.loading || current.loading || history.loading || forecast.loading || metrics.loading}><Icon name="refresh" size={18} /> Actualizar datos</button></div>

        {current.error && <EmptyState title="No se pudieron consultar los precios" message={errorMessage(current.error)} kind="error" />}
        <div className="price-grid">{FUELS.map((item) => <PriceCard key={item.id} fuel={item} row={currentByFuel[item.id]} selected={fuelId === item.id} loading={current.loading} onClick={() => chooseFuel(item.id)} />)}</div>

        <div className="content-grid"><section className="panel forecast-panel" aria-labelledby="forecast-heading"><div className="panel-heading"><span className="panel-icon panel-icon--amber"><Icon name="spark" /></span><div><span className="section-kicker">PRÓXIMA SEMANA DISPONIBLE</span><h2 id="forecast-heading">Pronóstico · {fuel.label}</h2></div></div><Forecast resource={forecast} fuel={fuel} observedWeek={currentByFuel[fuelId]?.semana} /></section><section className="panel context-panel" aria-labelledby="context-heading"><div className="panel-heading"><span className="panel-icon panel-icon--blue"><Icon name="chart" /></span><div><span className="section-kicker">CÓMO LEER LOS DATOS</span><h2 id="context-heading">Una referencia clara</h2></div></div><div className="context-list"><div><span className="context-number">01</span><p><strong>Precios por semana</strong>Las semanas van de martes a lunes, siguiendo los precios de referencia del MEM.</p></div><div><span className="context-number">02</span><p><strong>Variación calculada</strong>Compara el promedio con la semana calendario anterior, cuando existe.</p></div><div><span className="context-number">03</span><p><strong>Pronóstico con fecha</strong>La predicción se refiere a la semana indicada y depende de las fotos ya procesadas.</p></div></div></section></div>

        <section className="panel history-panel" id="historico" aria-labelledby="history-heading"><div className="history-heading"><div><span className="section-kicker">SERIE DE PRECIOS</span><h2 id="history-heading">Histórico semanal · {fuel.label}</h2><p>Explora el promedio, el rango y la dirección del cambio.</p></div><div className="fuel-tabs" role="group" aria-label="Elegir combustible">{FUELS.map((item) => <button key={item.id} type="button" className={fuelId === item.id ? 'active' : ''} onClick={() => chooseFuel(item.id)} aria-pressed={fuelId === item.id}>{item.label}</button>)}</div></div>
          <form className="filter-form" onSubmit={applyFilters}><div className="date-fields"><label>Desde<input type="date" value={fromInput} onChange={(event) => setFromInput(event.target.value)} aria-describedby={filterError ? 'filter-error' : undefined} /></label><label>Hasta<input type="date" value={toInput} onChange={(event) => setToInput(event.target.value)} aria-describedby={filterError ? 'filter-error' : undefined} /></label></div><div className="filter-actions"><button className="filter-submit" type="submit">Aplicar fechas</button><button className="filter-clear" type="button" onClick={clearFilters}>Limpiar</button></div>{filterError && <p id="filter-error" className="filter-error" role="alert">{filterError}</p>}</form>
          {history.loading ? <Loading height={315} /> : history.error ? <EmptyState title="Histórico no disponible" message={errorMessage(history.error)} kind="error" /> : rows.length === 0 ? <EmptyState title="Sin semanas en este período" message="Prueba con otro rango de fechas o espera a que Oro procese nuevas fotos." /> : <><TrendChart rows={rows} fuel={fuel} /><div className="table-heading"><h3>Detalle por semana</h3><span>{number.format(rows.length)} {rows.length === 1 ? 'semana' : 'semanas'} · hasta 100 resultados</span></div><div className="table-scroll"><table><thead><tr><th scope="col">Semana</th><th scope="col">Promedio</th><th scope="col">Mínimo</th><th scope="col">Máximo</th><th scope="col">Variación</th><th scope="col">Dirección</th></tr></thead><tbody>{visibleRows.map((row) => <tr key={`${row.semana}-${row.combustible}`}><td>{weekLabel(row.semana)}</td><td className="table-strong">{price(row.precio_promedio)}</td><td>{price(row.precio_minimo)}</td><td>{price(row.precio_maximo)}</td><td>{row.diferencia_q == null ? '—' : `${Number(row.diferencia_q) > 0 ? '+' : ''}${price(row.diferencia_q)}`}</td><td><span className={`direction-tag direction-tag--${row.direccion || 'none'}`}>{directionLabel(row.direccion)}</span></td></tr>)}</tbody></table></div>{maxPages > 1 && <div className="pagination"><button type="button" onClick={() => setPage((value) => Math.max(0, value - 1))} disabled={page === 0}>Anterior</button><span>Página {page + 1} de {maxPages}</span><button type="button" onClick={() => setPage((value) => Math.min(maxPages - 1, value + 1))} disabled={page >= maxPages - 1}>Siguiente</button></div>}</>}
        </section>

        <section className="model-section" id="modelo" aria-labelledby="model-heading"><div className="model-intro"><span className="section-kicker">TRANSPARENCIA DEL MODELO</span><h2 id="model-heading">Qué hay detrás del pronóstico</h2><p>La capa Oro compara el modelo con una línea base sencilla y registra las métricas de cada ejecución.</p><a href="/docs">Explorar los endpoints de la API <span aria-hidden="true">↗</span></a></div><div className="panel metrics-panel"><Metrics resource={metrics} /></div></section>
      </div>
    </main>

    <footer className="site-footer"><div className="shell footer-inner"><div className="footer-brand"><span className="brand-icon"><Icon name="fuel" size={19} /></span><span>GasolinaGT</span></div><p>Datos de la capa Oro · Equipo 07 · Guatemala</p><a href="/docs">API /docs</a></div></footer>
  </>
}
