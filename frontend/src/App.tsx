import { useEffect, useMemo, useState, type FormEvent, type ReactNode } from 'react'
import { api, ApiError, login as loginRequest, setUnauthorizedHandler, type AnalyticsFilterParams, type AnalyticsResponse, type AnalyticsSummary, type AssessmentComputeResponse, type AssessmentCriterionResult, type AssessmentPeriodType, type AssessmentResultDetail, type AssessmentResultItem, type CurrentUser, type DeadlineChangeItem, type DeadlineControlItem, type DeadlineControlResponse, type ImportPreviewRow, type InspectionItem, type MeasureInput, type MeasureItem, type ObjectItem, type PersonItem, type ReferenceItem, type UserItem, type ViolationItem, type ViolationTypeItem } from './api'

const blankMeasure = (): MeasureInput => ({ department_id: '', object_id: '', person_id: '', elimination_measure: '', due_date: '' })

const referenceTabs = [
  { resource: 'control-types', label: 'Виды контроля' },
  { resource: 'inspection-kinds', label: 'Виды проверок' },
  { resource: 'departments', label: 'Подразделения' },
  { resource: 'violation-groups', label: 'Группы нарушений' },
]

const navigation = ['Дашборд', 'Проверки', 'Нарушения', 'Импорт', 'Контроль сроков', 'Оценка эффективности ПК', 'Отчёты и экспорт', 'Справочники', 'Пользователи и роли', 'История изменений']

type View = 'dashboard' | 'inspections' | 'violations' | 'imports' | 'deadlines' | 'assessment' | 'references' | 'users'

function LoginScreen({ onLogin, notice }: { onLogin: (token: string, user: CurrentUser) => void; notice?: string }) {
  const [loginValue, setLoginValue] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setLoading(true)
    setError('')
    try {
      const token = await loginRequest(loginValue, password)
      const user = await api.me(token)
      onLogin(token, user)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Не удалось войти')
    } finally {
      setLoading(false)
    }
  }

  return <main className="login-page"><section className="login-card"><div className="login-mark">ПК</div><p className="eyebrow">PK CONTROL</p><h1>Производственный контроль</h1><p className="muted">Войдите, чтобы работать со справочниками и данными системы.</p>{notice && <p className="login-note">{notice}</p>}<form onSubmit={submit}><label>Логин<input autoComplete="username" value={loginValue} onChange={(event) => setLoginValue(event.target.value)} required /></label><label>Пароль<input type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} required /></label>{error && <p className="form-error">{error}</p>}<button className="primary-button" disabled={loading}>{loading ? 'Выполняется вход…' : 'Войти'}</button></form><p className="login-hint">Первого администратора создаёт системный администратор после настройки сервера.</p></section></main>
}


const controlTypeColors: Record<string, string> = { PC_III: '#176fca', PC_II: '#2abf88', ROSTECHNADZOR: '#e8930c', GAZNADZOR: '#8b5cf6' }
function controlTypeColor(code: string) { return controlTypeColors[code] ?? '#687d91' }
type AnalyticsFilterState = { dateFrom: string; dateTo: string; controlType: string; department: string; object: string; severity: string; status: string }
const emptyAnalyticsFilters = (): AnalyticsFilterState => ({ dateFrom: '', dateTo: '', controlType: '', department: '', object: '', severity: '', status: '' })
function analyticsParams(filters: AnalyticsFilterState): AnalyticsFilterParams { return { date_from: filters.dateFrom || undefined, date_to: filters.dateTo || undefined, control_type_id: filters.controlType || undefined, department_id: filters.department || undefined, object_id: filters.object || undefined, severity: filters.severity || undefined, status: filters.status || undefined } }

function DonutChart({ parts, centerLabel }: { parts: { label: string; value: number; color: string }[]; centerLabel: string }) {
  const total = parts.reduce((sum, part) => sum + part.value, 0)
  const radius = 60
  const circumference = 2 * Math.PI * radius
  let offset = 0
  return <div className="donut-wrap"><svg viewBox="0 0 160 160" role="img" aria-label={`${centerLabel}: ${total}`}><g transform="rotate(-90 80 80)"><circle cx="80" cy="80" r={radius} fill="none" stroke="#e8edf4" strokeWidth="22" />{parts.filter((part) => part.value > 0).map((part) => { const length = (part.value / total) * circumference; const segment = <circle key={part.label} cx="80" cy="80" r={radius} fill="none" stroke={part.color} strokeWidth="22" strokeDasharray={`${length} ${circumference - length}`} strokeDashoffset={-offset} />; offset += length; return segment })}</g><text x="80" y="77" textAnchor="middle" className="donut-total">{total}</text><text x="80" y="95" textAnchor="middle" className="donut-label">{centerLabel}</text></svg>{parts.length > 0 && <ul className="donut-legend">{parts.map((part) => <li key={part.label}><span className="legend-dot" style={{ background: part.color }} />{part.label}<strong>{part.value}</strong></li>)}</ul>}{total === 0 && <p className="empty">Нет данных.</p>}</div>
}

function HBarList({ items }: { items: { id: string; name: string; value: number; color?: string }[] }) {
  if (items.length === 0) return <p className="empty">Нет данных.</p>
  const max = Math.max(...items.map((item) => item.value))
  return <div className="hbar-list">{items.map((item) => <div className="hbar-row" key={item.id}><span className="hbar-name" title={item.name}>{item.name}</span><span className="hbar-track"><span className="hbar-fill" style={{ width: `${Math.max(3, Math.round((item.value / max) * 100))}%`, ...(item.color ? { background: item.color } : {}) }} /></span><span className="hbar-value">{item.value}</span></div>)}</div>
}

function useAnalytics(token: string, filters: AnalyticsFilterState) {
  const [data, setData] = useState<AnalyticsResponse | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError('')
    api.analytics(token, analyticsParams(filters)).then((result) => { if (!cancelled) setData(result) }).catch((reason: unknown) => { if (!cancelled) setError(reason instanceof Error ? reason.message : 'Не удалось загрузить аналитику') }).finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [token, filters])
  return { data, error, loading }
}

function AnalyticsKpis({ summary, onOpenStatus }: { summary: AnalyticsSummary; onOpenStatus: (status: string) => void }) {
  return <section className="kpis wide" aria-label="Показатели по нарушениям"><button className="kpi" type="button" onClick={() => onOpenStatus('')}><span>Всего нарушений</span><strong>{summary.total}</strong><small>аннулированные и ПК II исключены</small></button><button className="kpi" type="button" onClick={() => onOpenStatus('eliminated')}><span>Устранено</span><strong>{summary.eliminated}</strong><small>в срок и с просрочкой</small></button><button className="kpi" type="button" onClick={() => onOpenStatus('not_eliminated')}><span>Не устранено</span><strong>{summary.not_eliminated}</strong><small>открытые мероприятия</small></button><button className="kpi" type="button" onClick={() => onOpenStatus('overdue')}><span>Просрочено</span><strong>{summary.overdue}</strong><small>срок истёк</small></button><button className="kpi" type="button" onClick={() => onOpenStatus('due_soon')}><span>Срок ≤ 7 дней</span><strong>{summary.due_soon}</strong><small>приближается срок</small></button><button className="kpi" type="button" onClick={() => onOpenStatus('eliminated_late')}><span>Устранено с просрочкой</span><strong>{summary.eliminated_late}</strong><small>после истечения срока</small></button><button className="kpi" type="button" onClick={() => onOpenStatus('heavy')}><span>Критичные</span><strong>{summary.heavy}</strong><small>тяжесть 8–9</small></button></section>
}

function Dashboard({ token, onOpenDeadlines }: { token: string; onOpenDeadlines: (controlTypeId?: string, status?: string) => void }) {
  const [filters, setFilters] = useState<AnalyticsFilterState>(emptyAnalyticsFilters)
  const [departments, setDepartments] = useState<ReferenceItem[]>([])
  const [objects, setObjects] = useState<ObjectItem[]>([])
  const { data, error, loading } = useAnalytics(token, filters)
  useEffect(() => { api.references(token, 'departments').then(setDepartments).catch(() => setDepartments([])); api.objects(token).then(setObjects).catch(() => setObjects([])) }, [token])
  const grandTotal = data?.summary.total ?? 0
  const departmentSum = (data?.by_department ?? []).reduce((sum, item) => sum + item.total, 0)
  const objectSum = (data?.by_object ?? []).reduce((sum, item) => sum + item.total, 0)
  const multiScope = departmentSum > grandTotal || objectSum > grandTotal
  const periodNote = data?.period_from || data?.period_to ? `Период: ${data?.period_from ?? '…'} — ${data?.period_to ?? '…'}` : 'Период: все даты'
  const heavyDeptNote = (data?.by_department ?? []).filter((item) => item.heavy > 0).map((item) => `${item.name} — ${item.heavy}`).join(' · ')
  const heavyObjectNote = (data?.by_object ?? []).filter((item) => item.heavy > 0).map((item) => `${item.name} — ${item.heavy}`).join(' · ')
  const typeCards = data?.by_control_type ?? []
  const overdueDepts = [...(data?.by_department ?? [])].filter((item) => item.overdue > 0).sort((a, b) => b.overdue - a.overdue || a.name.localeCompare(b.name, 'ru')).map((item) => ({ id: item.department_id, name: item.name, value: item.overdue, color: '#b32929' }))
  return <>
    <div className="title-row"><div><p className="eyebrow">PK CONTROL</p><h1>Дашборд</h1></div><span className="period">{periodNote}</span></div>
    <section className="panel form-panel dashboard-filters"><div className="filter-chips">
      <label className="filter-chip">Период с<input type="date" value={filters.dateFrom} onChange={(event) => setFilters({ ...filters, dateFrom: event.target.value })} />—<input type="date" value={filters.dateTo} onChange={(event) => setFilters({ ...filters, dateTo: event.target.value })} /></label>
      <label className="filter-chip">Подразделение<select value={filters.department} onChange={(event) => setFilters({ ...filters, department: event.target.value })}><option value="">все</option>{departments.filter((item) => item.is_active).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
      <label className="filter-chip">Объект<select value={filters.object} onChange={(event) => setFilters({ ...filters, object: event.target.value })}><option value="">все</option>{objects.filter((item) => item.is_active).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
      <label className="filter-chip">Тяжесть<select value={filters.severity} onChange={(event) => setFilters({ ...filters, severity: event.target.value })}><option value="">любая</option>{[1, 2, 3, 4, 5, 6, 7, 8, 9].map((value) => <option key={value} value={String(value)}>{value}</option>)}</select></label>
      <button className="filter-chip reset" type="button" onClick={() => setFilters(emptyAnalyticsFilters())}>Сброс</button>
    </div></section>
    {error && <p className="form-error">{error}</p>}
    {loading ? <p className="empty">Загрузка…</p> : data ? <>
      <AnalyticsKpis summary={data.summary} onOpenStatus={(status) => onOpenDeadlines('all', status)} />
      <section className="analytics-cards" aria-label="Нарушения по видам контроля">{typeCards.map((item) => <div className="chart-card analytics-type-card" key={item.control_type_id} role="button" tabIndex={0} style={{ borderTopColor: controlTypeColor(item.code) }} onClick={() => onOpenDeadlines(item.control_type_id)} onKeyDown={(event) => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); onOpenDeadlines(item.control_type_id) } }}>
        <span className="analytics-type-head"><strong style={{ color: controlTypeColor(item.code) }}>{controlTypeLabel(item.code, item.name)}</strong><span className="analytics-type-share">{grandTotal > 0 ? Math.round((item.total / grandTotal) * 100) : 0}% от всех</span></span>
        <DonutChart parts={[{ label: 'Устранено', value: item.eliminated, color: '#2abf88' }, { label: 'Не устранено', value: item.not_eliminated, color: '#176fca' }, { label: 'Просрочено', value: item.overdue, color: '#b32929' }]} centerLabel="нарушений" />
        <span className="type-card-stats quad"><span className="stat ok"><strong>{item.eliminated}</strong> устранено</span><span className="stat"><strong>{item.not_eliminated}</strong> не устранено</span><span className="stat overdue"><strong>{item.overdue}</strong> просрочено</span><span className="stat heavy"><strong>{item.heavy}</strong> критичных</span></span>
        <span className="mini-progress">{([['Устранено', '#2abf88', item.eliminated], ['Не устранено', '#176fca', item.not_eliminated], ['Просрочено', '#b32929', item.overdue]] as const).filter((part) => part[2] > 0).map((part) => <span key={part[0]} style={{ background: part[1], flexGrow: part[2] }} title={`${part[0]}: ${part[2]}`} />)}</span>
        <span className="analytics-type-hint">Нажмите, чтобы открыть «Контроль сроков» по этому виду</span>
      </div>)}</section>
      {multiScope && <p className="muted-note">Суммы по подразделениям ({departmentSum}) и по объектам ({objectSum}) больше общего числа нарушений ({data.summary.total}): одно нарушение может иметь несколько ответственных подразделений и затрагивать несколько объектов — в каждом разрезе оно учитывается по своим мероприятиям.</p>}
      <section className="dashboard-bottom">
        <article className="chart-card"><h2>По подразделениям</h2><div className="chart-body"><HBarList items={data.by_department.map((item) => ({ id: item.department_id, name: item.name, value: item.total }))} /></div>{heavyDeptNote && <p className="chart-note">Критичные: {heavyDeptNote}.</p>}</article>
        <article className="chart-card"><h2>По объектам</h2><div className="chart-body"><HBarList items={data.by_object.map((item) => ({ id: item.object_id, name: item.name, value: item.total }))} /></div>{heavyObjectNote && <p className="chart-note">Критичные: {heavyObjectNote}.</p>}</article>
        <article className="chart-card clickable-card" role="button" tabIndex={0} onClick={() => onOpenDeadlines('all', 'overdue')} onKeyDown={(event) => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); onOpenDeadlines('all', 'overdue') } }}><h2>Топ подразделений · просрочено</h2><div className="chart-body"><HBarList items={overdueDepts} /></div><p className="chart-note">Нажмите на блок, чтобы открыть «Контроль сроков» с просроченными нарушениями.</p></article>
      </section>
    </> : null}
  </>
}

function RegistryWorkspace({ token, kind }: { token: string; kind: 'inspections' | 'violations' }) {
  const [items, setItems] = useState<InspectionItem[] | ViolationItem[]>([])
  const [controlTypes, setControlTypes] = useState<ReferenceItem[]>([])
  const [inspectionKinds, setInspectionKinds] = useState<ReferenceItem[]>([])
  const [departments, setDepartments] = useState<ReferenceItem[]>([])
  const [objects, setObjects] = useState<ObjectItem[]>([])
  const [persons, setPersons] = useState<PersonItem[]>([])
  const [error, setError] = useState('')
  const [showForm, setShowForm] = useState(false)
  const [saving, setSaving] = useState(false)
  const [form, setForm] = useState({ control_type_id: '', inspection_kind_id: '', department_id: '', object_id: '', document_number: '', inspection_date: new Date().toISOString().slice(0, 10), comment: '' })
  const [selected, setSelected] = useState<InspectionItem | null>(null)
  const [editForm, setEditForm] = useState({ inspection_kind_id: '', department_id: '', object_id: '', document_number: '', inspection_date: '', comment: '' })
  const [violationTypes, setViolationTypes] = useState<ViolationTypeItem[]>([])
  const [availableInspections, setAvailableInspections] = useState<InspectionItem[]>([])
  const [violationForm, setViolationForm] = useState({ inspection_id: '', violation_type_id: '', formulation: '', violated_requirement: '', document_received_date: '', measures: [blankMeasure()] })
  const [selectedViolation, setSelectedViolation] = useState<ViolationItem | null>(null)
  const [violationFilters, setViolationFilters] = useState({ formulation: '', act: '', person: '', severity: '', dueFrom: '', dueTo: '', status: '' })
  const inspectionMode = kind === 'inspections'

  const departmentName = (id: string) => departments.find((item) => item.id === id)?.name ?? '—'
  const objectName = (id: string) => objects.find((item) => item.id === id)?.name ?? '—'
  const inspectionKindName = (id: string | null) => id ? inspectionKinds.find((item) => item.id === id)?.name ?? '—' : '—'
  const requiresInspectionKind = (controlTypeId: string) => { if (!controlTypeId) return false; return !['PC_II', 'ROSTECHNADZOR', 'GAZNADZOR'].includes(controlTypes.find((item) => item.id === controlTypeId)?.code ?? '') }
  const personLabel = (id: string) => { const person = persons.find((item) => item.id === id); return person ? `${person.full_name}${person.position ? ` · ${person.position}` : ''}` : '—' }
  const isLocationRequired = (controlTypeId: string, kindId: string) => Boolean(controlTypeId && kindId) && ['PLANNED', 'UNSCHEDULED'].includes(inspectionKinds.find((item) => item.id === kindId)?.code ?? '') && (controlTypes.find((item) => item.id === controlTypeId)?.code ?? '') === 'PC_III'
  const earliestDueDate = (v: ViolationItem) => { const dates = v.measures.map((m) => m.due_date).filter(Boolean) as string[]; return dates.length ? dates.sort()[0] : null }
  const measurePersons = (v: ViolationItem) => v.measures.map((m) => personLabel(m.person_id)).filter((n) => n !== '—')
  const createDeadlineControl = availableInspections.find((item) => item.id === violationForm.inspection_id)?.has_deadline_control ?? true
  const violationActNumber = (id: string) => availableInspections.find((item) => item.id === id)?.document_number ?? '—'
  const allViolations = inspectionMode ? [] : items as ViolationItem[]
  const shownViolations = allViolations.filter((item) => { const query = violationFilters.formulation.trim().toLowerCase(); if (query && !item.formulation.toLowerCase().includes(query)) return false; if (violationFilters.act && violationActNumber(item.inspection_id) !== violationFilters.act) return false; if (violationFilters.person && !item.measures.some((measure) => measure.person_id === violationFilters.person)) return false; if (violationFilters.severity && item.severity !== Number(violationFilters.severity)) return false; if (violationFilters.status && (item.status ?? 'not_eliminated') !== violationFilters.status) return false; return inDateRange(earliestDueDate(item), violationFilters.dueFrom, violationFilters.dueTo) })
  const violationActOptions = [...new Set(allViolations.map((item) => violationActNumber(item.inspection_id)).filter((value) => value !== '—'))].sort((a, b) => a.localeCompare(b, 'ru'))
  const violationPersonOptions = [...new Map(allViolations.flatMap((item) => item.measures.map((measure) => [measure.person_id, personLabel(measure.person_id)]))).entries()].filter(([, label]) => label !== '—').sort((a, b) => a[1].localeCompare(b[1], 'ru'))
  const violationSeverityOptions = [...new Set(allViolations.map((item) => item.severity))].sort((a, b) => a - b)
  function resetViolationFilters() { setViolationFilters({ formulation: '', act: '', person: '', severity: '', dueFrom: '', dueTo: '', status: '' }) }

  function load() { (inspectionMode ? api.inspections(token) : api.violations(token)).then((data) => setItems(data)).catch((reason: unknown) => setError(reason instanceof Error ? reason.message : 'Не удалось загрузить реестр')) }
  useEffect(() => { setError(''); setSelected(null); setSelectedViolation(null); setShowForm(false); load() }, [kind, token])
  useEffect(() => {
    api.references(token, 'departments').then(setDepartments).catch(() => setDepartments([]))
    api.objects(token).then(setObjects).catch(() => setObjects([]))
    api.persons(token).then(setPersons).catch(() => setPersons([]))
    if (inspectionMode) { api.references(token, 'control-types').then(setControlTypes); api.references(token, 'inspection-kinds').then(setInspectionKinds) } else { api.inspections(token).then(setAvailableInspections); api.violationTypes(token).then(setViolationTypes) }
  }, [inspectionMode, token])
  async function submit(event: FormEvent<HTMLFormElement>) { event.preventDefault(); setSaving(true); setError(''); try { const location = isLocationRequired(form.control_type_id, form.inspection_kind_id) ? { department_id: form.department_id, object_id: form.object_id } : {}; await api.createInspection(token, { control_type_id: form.control_type_id, ...(requiresInspectionKind(form.control_type_id) ? { inspection_kind_id: form.inspection_kind_id } : {}), document_number: form.document_number, inspection_date: form.inspection_date, ...location, comment: form.comment || undefined }); setShowForm(false); setForm({ ...form, department_id: '', object_id: '', document_number: '', comment: '' }); load() } catch (reason) { setError(reason instanceof Error ? reason.message : 'Не удалось создать проверку') } finally { setSaving(false) } }
  function selectInspection(item: InspectionItem) { setSelected(item); setEditForm({ inspection_kind_id: item.inspection_kind_id ?? '', department_id: item.department_id ?? '', object_id: item.object_id ?? '', document_number: item.document_number, inspection_date: item.inspection_date, comment: item.comment ?? '' }) }
  async function saveInspection(event: FormEvent<HTMLFormElement>) { event.preventDefault(); if (!selected) return; setSaving(true); setError(''); try { const location = isLocationRequired(selected?.control_type_id ?? '', editForm.inspection_kind_id) ? { department_id: editForm.department_id, object_id: editForm.object_id } : { department_id: null, object_id: null }; const updated = await api.updateInspection(token, selected.id, { inspection_kind_id: requiresInspectionKind(selected.control_type_id) ? editForm.inspection_kind_id : null, document_number: editForm.document_number, inspection_date: editForm.inspection_date, ...location, comment: editForm.comment || undefined }); setSelected(updated); setItems((current) => (current as InspectionItem[]).map((item) => item.id === updated.id ? updated : item)) } catch (reason) { setError(reason instanceof Error ? reason.message : 'Не удалось сохранить изменения') } finally { setSaving(false) } }
  function updateMeasure(index: number, patch: Partial<MeasureInput>) { setViolationForm((current) => ({ ...current, measures: current.measures.map((item, itemIndex) => itemIndex === index ? { ...item, ...patch } : item) })) }
  async function submitViolation(event: FormEvent<HTMLFormElement>) { event.preventDefault(); setSaving(true); setError(''); try { const deadlineAware = availableInspections.find((item) => item.id === violationForm.inspection_id)?.has_deadline_control ?? true; await api.createViolation(token, violationForm.inspection_id, { violation_type_id: violationForm.violation_type_id, formulation: violationForm.formulation, violated_requirement: violationForm.violated_requirement, document_received_date: deadlineAware ? violationForm.document_received_date || undefined : undefined, measures: violationForm.measures.map((item) => ({ ...item, due_date: deadlineAware ? item.due_date || undefined : undefined })) }); setShowForm(false); setViolationForm({ inspection_id: '', violation_type_id: '', formulation: '', violated_requirement: '', document_received_date: '', measures: [blankMeasure()] }); load() } catch (reason) { setError(reason instanceof Error ? reason.message : 'Не удалось создать нарушение') } finally { setSaving(false) } }

  function openViolation(item: ViolationItem) { setError(''); setSelectedViolation(item) }
  function closeViolation() { setSelectedViolation(null) }
  function handleViolationUpdated(updated: ViolationItem) { setItems((current) => (current as ViolationItem[]).map((item) => item.id === updated.id ? updated : item)); setSelectedViolation(updated) }

  return <>
    <div className="title-row"><div><p className="eyebrow">РЕЕСТР</p><h1>{inspectionMode ? 'Проверки' : 'Нарушения'}</h1></div><button className="primary-button" onClick={() => setShowForm(!showForm)}>{showForm ? 'Закрыть форму' : inspectionMode ? 'Создать проверку' : 'Создать нарушение'}</button></div>

    {showForm && (inspectionMode ? <section className="panel form-panel"><h2>Новая проверка</h2><form className="entry-form" onSubmit={submit}><label>Вид контроля<select value={form.control_type_id} onChange={(event) => { const nextId = event.target.value; const keepKind = requiresInspectionKind(nextId); const keepLocation = keepKind && isLocationRequired(nextId, form.inspection_kind_id); setForm({ ...form, control_type_id: nextId, inspection_kind_id: keepKind ? form.inspection_kind_id : '', department_id: keepLocation ? form.department_id : '', object_id: keepLocation ? form.object_id : '' }) }} required><option value="">Выберите вид контроля</option>{controlTypes.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>{requiresInspectionKind(form.control_type_id) && <><label>Вид проверки<select value={form.inspection_kind_id} onChange={(event) => setForm({ ...form, inspection_kind_id: event.target.value, department_id: isLocationRequired(form.control_type_id, event.target.value) ? form.department_id : '', object_id: isLocationRequired(form.control_type_id, event.target.value) ? form.object_id : '' })} required><option value="">Выберите вид проверки</option>{inspectionKinds.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label></>}{isLocationRequired(form.control_type_id, form.inspection_kind_id) && <><label>Структурное подразделение<select value={form.department_id} onChange={(event) => setForm({ ...form, department_id: event.target.value, object_id: '' })} required><option value="">Выберите подразделение</option>{departments.filter((item) => item.is_active).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><label>Объект<select value={form.object_id} onChange={(event) => setForm({ ...form, object_id: event.target.value })} required><option value="">Выберите объект</option>{objects.filter((item) => item.is_active && (!item.owner_department_id || item.owner_department_id === form.department_id)).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label></>}<label>Номер документа<input value={form.document_number} onChange={(event) => setForm({ ...form, document_number: event.target.value })} required /></label><label>Дата проверки<input type="date" value={form.inspection_date} onChange={(event) => setForm({ ...form, inspection_date: event.target.value })} required /></label><label className="wide">Комментарий<textarea value={form.comment} onChange={(event) => setForm({ ...form, comment: event.target.value })} /></label><button className="primary-button" disabled={saving}>{saving ? 'Сохранение…' : 'Создать проверку'}</button></form></section> : <section className="panel form-panel"><h2>Новое нарушение</h2><form className="entry-form" onSubmit={submitViolation}><label>Проверка<select value={violationForm.inspection_id} onChange={(event) => setViolationForm({ ...violationForm, inspection_id: event.target.value })} required><option value="">Выберите проверку</option>{availableInspections.map((item) => <option key={item.id} value={item.id}>{item.inspection_date} · {item.document_number}</option>)}</select></label><label>Тип нарушения<select value={violationForm.violation_type_id} onChange={(event) => setViolationForm({ ...violationForm, violation_type_id: event.target.value })} required><option value="">Выберите тип</option>{violationTypes.filter((item) => item.is_active).map((item) => <option key={item.id} value={item.id}>{item.code} · {item.name}</option>)}</select></label>{createDeadlineControl ? <label>Дата получения документа<input type="date" value={violationForm.document_received_date} onChange={(event) => setViolationForm({ ...violationForm, document_received_date: event.target.value })} /></label> : <p className="cell-note wide">Для выбранного вида контроля (ПК II) контроль сроков не применяется — поля даты документа и сроков скрыты.</p>}<label className="wide">Формулировка нарушения<textarea value={violationForm.formulation} onChange={(event) => setViolationForm({ ...violationForm, formulation: event.target.value })} required /></label><label className="wide">Нарушенное требование<textarea value={violationForm.violated_requirement} onChange={(event) => setViolationForm({ ...violationForm, violated_requirement: event.target.value })} required /></label><div className="wide measures-block"><div className="measures-header"><h3>Меры по устранению и ответственные</h3><button type="button" className="tab" onClick={() => setViolationForm({ ...violationForm, measures: [...violationForm.measures, blankMeasure()] })}>Добавить меру</button></div>{violationForm.measures.map((measure, index) => <section className="measure-form" key={index}><strong>Мера {index + 1}</strong><label>Подразделение<select value={measure.department_id} onChange={(event) => updateMeasure(index, { department_id: event.target.value })} required><option value="">Выберите подразделение</option>{departments.filter((item) => item.is_active).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><label>Объект<select value={measure.object_id} onChange={(event) => updateMeasure(index, { object_id: event.target.value })} required><option value="">Выберите объект</option>{objects.filter((item) => item.is_active && (!item.owner_department_id || item.owner_department_id === measure.department_id)).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><label>Ответственный<select value={measure.person_id} onChange={(event) => updateMeasure(index, { person_id: event.target.value })} required><option value="">Выберите сотрудника</option>{persons.filter((item) => item.is_active && (!item.department_id || item.department_id === measure.department_id)).map((item) => <option key={item.id} value={item.id}>{item.full_name}{item.position ? ` · ${item.position}` : ''}</option>)}</select></label>{createDeadlineControl && <label>Срок устранения<input type="date" value={measure.due_date ?? ''} onChange={(event) => updateMeasure(index, { due_date: event.target.value })} /></label>}<label className="wide">Мероприятие по устранению<textarea value={measure.elimination_measure} onChange={(event) => updateMeasure(index, { elimination_measure: event.target.value })} required /></label>{violationForm.measures.length > 1 && <button type="button" className="logout" onClick={() => setViolationForm({ ...violationForm, measures: violationForm.measures.filter((_, itemIndex) => itemIndex !== index) })}>Удалить меру</button>}</section>)}</div><button className="primary-button" disabled={saving}>{saving ? 'Сохранение…' : 'Создать нарушение'}</button></form></section>)}

    {selected && inspectionMode && <section className="panel form-panel"><div className="panel-header"><div><h2>Карточка проверки</h2><p>Состояние: {selected.state}</p></div><button className="logout" onClick={() => setSelected(null)}>Закрыть</button></div><form className="entry-form" onSubmit={saveInspection}>{requiresInspectionKind(selected.control_type_id) && <><label>Вид проверки<select value={editForm.inspection_kind_id} onChange={(event) => setEditForm({ ...editForm, inspection_kind_id: event.target.value, department_id: isLocationRequired(selected?.control_type_id ?? '', event.target.value) ? editForm.department_id : '', object_id: isLocationRequired(selected?.control_type_id ?? '', event.target.value) ? editForm.object_id : '' })} required>{inspectionKinds.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label></>}{isLocationRequired(selected?.control_type_id ?? '', editForm.inspection_kind_id) && <><label>Структурное подразделение<select value={editForm.department_id} onChange={(event) => setEditForm({ ...editForm, department_id: event.target.value, object_id: '' })} required><option value="">Выберите подразделение</option>{departments.filter((item) => item.is_active).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><label>Объект<select value={editForm.object_id} onChange={(event) => setEditForm({ ...editForm, object_id: event.target.value })} required><option value="">Выберите объект</option>{objects.filter((item) => item.is_active && (!item.owner_department_id || item.owner_department_id === editForm.department_id)).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label></>}<label>Номер документа<input value={editForm.document_number} onChange={(event) => setEditForm({ ...editForm, document_number: event.target.value })} required /></label><label>Дата проверки<input type="date" value={editForm.inspection_date} onChange={(event) => setEditForm({ ...editForm, inspection_date: event.target.value })} required /></label><label className="wide">Комментарий<textarea value={editForm.comment} onChange={(event) => setEditForm({ ...editForm, comment: event.target.value })} /></label><button className="primary-button" disabled={saving}>{saving ? 'Сохранение…' : 'Сохранить изменения'}</button></form></section>}

    {selectedViolation && !inspectionMode && <ViolationCardModal token={token} violation={selectedViolation} inspections={availableInspections} departments={departments} objects={objects} persons={persons} onClose={closeViolation} onUpdated={handleViolationUpdated} />}

    <section className="panel"><div className="panel-header"><div><h2>{inspectionMode ? 'Журнал проверок' : 'Реестр нарушений'}</h2><p>{inspectionMode ? 'Номер документа нормализуется и уникален в рамках вида контроля.' : 'Статус и просрочка вычисляются сервером по календарным дням.'}</p></div><div className="header-actions">{!inspectionMode && <button className="logout small-button" type="button" onClick={resetViolationFilters}>Сброс фильтров</button>}<span className="counter">{inspectionMode ? items.length : shownViolations.length}</span></div></div>{error ? <p className="form-error">{error}</p> : inspectionMode ? <table><thead><tr><th>Дата</th><th>Номер документа</th><th>Вид проверки</th><th>Структурное подразделение</th><th>Объект</th><th>Состояние</th></tr></thead><tbody>{(items as InspectionItem[]).map((item) => <tr className="clickable-row" key={item.id} onClick={() => selectInspection(item)}><td>{item.inspection_date}</td><td className="code">{item.document_number}</td><td>{inspectionKindName(item.inspection_kind_id)}</td><td>{item.department_id ? departmentName(item.department_id) : '—'}</td><td>{item.object_id ? objectName(item.object_id) : '—'}</td><td><span className="chip muted-chip">{item.state}</span></td></tr>)}</tbody></table> : <><div className="registry-toolbar"><div className="deadline-filters"><label>Формулировка<input placeholder="Содержит текст…" value={violationFilters.formulation} onChange={(event) => setViolationFilters({ ...violationFilters, formulation: event.target.value })} /></label><label>Акт-предписание<select value={violationFilters.act} onChange={(event) => setViolationFilters({ ...violationFilters, act: event.target.value })}><option value="">Все акты</option>{violationActOptions.map((value) => <option key={value} value={value}>{value}</option>)}</select></label><label>Ответственный<select value={violationFilters.person} onChange={(event) => setViolationFilters({ ...violationFilters, person: event.target.value })}><option value="">Все ответственные</option>{violationPersonOptions.map(([id, label]) => <option key={id} value={id}>{label}</option>)}</select></label><label>Тяжесть<select value={violationFilters.severity} onChange={(event) => setViolationFilters({ ...violationFilters, severity: event.target.value })}><option value="">Любая</option>{violationSeverityOptions.map((value) => <option key={value} value={String(value)}>{value}</option>)}</select></label><label>Срок с<input type="date" value={violationFilters.dueFrom} onChange={(event) => setViolationFilters({ ...violationFilters, dueFrom: event.target.value })} /></label><label>Срок по<input type="date" value={violationFilters.dueTo} onChange={(event) => setViolationFilters({ ...violationFilters, dueTo: event.target.value })} /></label><label>Статус<select value={violationFilters.status} onChange={(event) => setViolationFilters({ ...violationFilters, status: event.target.value })}><option value="">Все</option><option value="overdue">Просрочено</option><option value="not_eliminated">Не устранено</option><option value="eliminated">Устранено</option></select></label></div></div><table><thead><tr><th>Формулировка</th><th>Акт-предписание</th><th>Ответственные</th><th>Тяжесть</th><th>Срок</th><th>Статус</th></tr></thead><tbody>{shownViolations.map((item) => <tr className="clickable-row" key={item.id} onClick={() => openViolation(item)}><td>{item.formulation}</td><td className="code">{violationActNumber(item.inspection_id)}</td><td>{measurePersons(item).length > 0 ? measurePersons(item).join(', ') : '—'}</td><td>{item.severity}</td><td>{earliestDueDate(item) ?? '—'}</td><td><span className={item.status === 'overdue' ? 'chip danger' : item.status === 'eliminated' ? 'chip success' : 'chip muted-chip'}>{item.status === 'overdue' ? 'Просрочено' : item.status === 'eliminated' ? 'Устранено' : 'Не устранено'}</span></td></tr>)}</tbody></table></>}{!error && items.length === 0 && <p className="empty">Записей пока нет.</p>}{!error && !inspectionMode && items.length > 0 && shownViolations.length === 0 && <p className="empty">Нарушений по выбранным условиям нет.</p>}</section>
  </>
}

type ViolationCardModalProps = {
  token: string
  violation: ViolationItem
  inspections: InspectionItem[]
  departments: ReferenceItem[]
  objects: ObjectItem[]
  persons: PersonItem[]
  onClose: () => void
  onUpdated: (violation: ViolationItem) => void
}

function ViolationCardModal({ token, violation, inspections, departments, objects, persons, onClose, onUpdated }: ViolationCardModalProps) {
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [eliminationForm, setEliminationForm] = useState<{ measureId: string; date: string; during: boolean } | null>(null)
  const [deadlineForm, setDeadlineForm] = useState<{ measureId: string; date: string; reason: string } | null>(null)
  const [deadlineHistory, setDeadlineHistory] = useState<Record<string, DeadlineChangeItem[]>>({})
  const [openHistoryId, setOpenHistoryId] = useState<string | null>(null)

  const inspection = inspections.find((item) => item.id === violation.inspection_id) ?? null
  const inspectionDate = inspection?.inspection_date ?? null
  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) { if (event.key === 'Escape') onClose() }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [onClose])

  const departmentName = (id: string) => departments.find((item) => item.id === id)?.name ?? '—'
  const objectName = (id: string) => objects.find((item) => item.id === id)?.name ?? '—'
  const personLabel = (id: string) => { const person = persons.find((item) => item.id === id); return person ? `${person.full_name}${person.position ? ` · ${person.position}` : ''}` : '—' }
  const hasHistory = (measure: MeasureItem) => Boolean(measure.original_due_date && measure.due_date && measure.original_due_date !== measure.due_date) || (deadlineHistory[measure.id]?.length ?? 0) > 0
  const measureChipClass = (measure: MeasureItem) => measure.eliminated_late || measure.status === 'overdue' ? 'chip danger' : measure.status === 'eliminated' ? 'chip success' : 'chip muted-chip'
  const measureChipLabel = (measure: MeasureItem) => measure.eliminated_late ? `Устранено с просрочкой${measure.days_overdue_at_elimination ? ` · ${measure.days_overdue_at_elimination} дн.` : ''}` : measure.status === 'overdue' ? 'Просрочено' : measure.status === 'eliminated' ? 'Устранено' : 'Не устранено'

  function openElimination(measureId: string) { setDeadlineForm(null); setEliminationForm({ measureId, date: new Date().toISOString().slice(0, 10), during: false }) }
  function openDeadline(measureId: string, dueDate: string | null) { setEliminationForm(null); setDeadlineForm({ measureId, date: dueDate ?? '', reason: '' }) }
  async function refreshViolation(): Promise<ViolationItem | null> { const fresh = await api.violations(token); const updated = fresh.find((item) => item.id === violation.id) ?? null; if (updated) onUpdated(updated); return updated }
  async function submitElimination(event: FormEvent<HTMLFormElement>) { event.preventDefault(); if (!eliminationForm) return; setSaving(true); setError(''); setNotice(''); try { const during = eliminationForm.during && Boolean(inspectionDate); await api.eliminateMeasure(token, eliminationForm.measureId, { elimination_date: during ? (inspectionDate as string) : eliminationForm.date, eliminated_during_inspection: during }); await refreshViolation(); setNotice(during ? 'Устранение зафиксировано в ходе проверки.' : 'Устранение зафиксировано.'); setEliminationForm(null) } catch (reason) { setError(reason instanceof Error ? reason.message : 'Не удалось зафиксировать устранение') } finally { setSaving(false) } }
  async function submitDeadline(event: FormEvent<HTMLFormElement>) { event.preventDefault(); if (!deadlineForm) return; setSaving(true); setError(''); setNotice(''); try { await api.changeMeasureDeadline(token, deadlineForm.measureId, { new_due_date: deadlineForm.date, reason: deadlineForm.reason }); const history = await api.deadlineChanges(token, deadlineForm.measureId); setDeadlineHistory((current) => ({ ...current, [deadlineForm.measureId]: history })); setOpenHistoryId(deadlineForm.measureId); await refreshViolation(); setNotice('Срок перенесён, изменение сохранено в истории.'); setDeadlineForm(null) } catch (reason) { setError(reason instanceof Error ? reason.message : 'Не удалось перенести срок') } finally { setSaving(false) } }
  async function toggleHistory(measureId: string) { if (openHistoryId === measureId) { setOpenHistoryId(null); return } setOpenHistoryId(measureId); if (deadlineHistory[measureId]) return; try { const history = await api.deadlineChanges(token, measureId); setDeadlineHistory((current) => ({ ...current, [measureId]: history })) } catch (reason) { setError(reason instanceof Error ? reason.message : 'Не удалось загрузить историю переносов') } }

  return <div className="modal-overlay" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose() }}><section className="modal-card" role="dialog" aria-modal="true" aria-label="Карточка нарушения">
    <div className="panel-header"><div><h2>Карточка нарушения</h2><p>Статус: <span className={violation.status === 'overdue' ? 'chip danger' : violation.status === 'eliminated' ? 'chip success' : 'chip muted-chip'}>{violation.status === 'overdue' ? 'Просрочено' : violation.status === 'eliminated' ? 'Устранено' : 'Не устранено'}</span> {!violation.has_deadline_control && <span className="chip muted-chip">ПК II — контроль сроков не применяется</span>}</p></div><button className="logout" onClick={onClose}>Закрыть</button></div>
    {notice && <p className="form-success">{notice}</p>}
    {error && <p className="form-error">{error}</p>}
    <div className="violation-details">
      <div className="detail-row"><span className="detail-label">Акт-предписание</span><span className="code">{inspection?.document_number ?? '—'}</span></div>
      <div className="detail-row"><span className="detail-label">Дата проверки</span><span>{inspection?.inspection_date ?? '—'}</span></div>
      <div className="detail-row"><span className="detail-label">Формулировка</span><span>{violation.formulation}</span></div>
      <div className="detail-row"><span className="detail-label">Нарушенное требование</span><span>{violation.violated_requirement}</span></div>
      <div className="detail-row"><span className="detail-label">Тяжесть</span><span>{violation.severity}</span></div>
      {violation.document_received_date && <div className="detail-row"><span className="detail-label">Дата получения документа</span><span>{violation.document_received_date}</span></div>}
    </div>
    <div className="scope-block">
      <h3>Меры по устранению ({violation.measures.length})</h3>
      {!violation.has_deadline_control && <p className="cell-note">Для этого вида контроля контроль сроков не применяется — сроки и переносы недоступны.</p>}
      <ul className="measure-list">{violation.measures.map((measure) => <li key={measure.id} className="measure-card"><div className="measure-card-header"><strong>{personLabel(measure.person_id)}</strong><div className="measure-chips">{measure.eliminated_during_inspection && <span className="chip success">В ходе проверки</span>}<span className={measureChipClass(measure)}>{measureChipLabel(measure)}</span></div></div><div className="measure-card-body"><span><strong>Подразделение:</strong> {departmentName(measure.department_id)}</span><span><strong>Объект:</strong> {objectName(measure.object_id)}</span><span><strong>Мероприятие:</strong> {measure.elimination_measure}</span><span><strong>Срок:</strong> {measure.due_date ?? '—'}{measure.original_due_date && measure.due_date && measure.original_due_date !== measure.due_date ? ` (первоначально ${measure.original_due_date})` : ''}</span>{measure.elimination_date && <span><strong>Дата устранения:</strong> {measure.elimination_date}{measure.eliminated_late ? ` — с просрочкой на ${measure.days_overdue_at_elimination ?? 0} дн.` : ''}</span>}</div>
      <div className="measure-actions">{measure.status !== 'eliminated' && eliminationForm?.measureId !== measure.id && <button className="primary-button small-button" type="button" disabled={saving} onClick={() => openElimination(measure.id)}>Зафиксировать устранение</button>}{measure.status !== 'eliminated' && violation.has_deadline_control && eliminationForm?.measureId !== measure.id && deadlineForm?.measureId !== measure.id && <button className="tab" type="button" disabled={saving} onClick={() => openDeadline(measure.id, measure.due_date)}>Перенести срок</button>}{hasHistory(measure) && <button className="tab" type="button" onClick={() => toggleHistory(measure.id)}>{openHistoryId === measure.id ? 'Скрыть историю' : 'История переносов'}</button>}</div>
      {eliminationForm?.measureId === measure.id && <form className="inline-action-form" onSubmit={submitElimination}><label>Дата устранения<input type="date" value={eliminationForm.during && inspectionDate ? inspectionDate : eliminationForm.date} disabled={eliminationForm.during} onChange={(event) => setEliminationForm({ ...eliminationForm, date: event.target.value })} required /></label><label className="checkbox-label"><input type="checkbox" checked={eliminationForm.during} onChange={(event) => setEliminationForm({ ...eliminationForm, during: event.target.checked })} /> Устранено в ходе проверки{inspectionDate ? ` (${inspectionDate})` : ''}</label><div className="measure-actions"><button className="primary-button small-button" disabled={saving}>{saving ? 'Сохранение…' : 'Подтвердить устранение'}</button><button type="button" className="logout" onClick={() => setEliminationForm(null)}>Отмена</button></div></form>}
      {deadlineForm?.measureId === measure.id && <form className="inline-action-form" onSubmit={submitDeadline}><label>Новый срок устранения<input type="date" value={deadlineForm.date} onChange={(event) => setDeadlineForm({ ...deadlineForm, date: event.target.value })} required /></label><label className="wide">Причина переноса<textarea value={deadlineForm.reason} onChange={(event) => setDeadlineForm({ ...deadlineForm, reason: event.target.value })} required /></label><div className="measure-actions"><button className="primary-button small-button" disabled={saving}>{saving ? 'Сохранение…' : 'Перенести срок'}</button><button type="button" className="logout" onClick={() => setDeadlineForm(null)}>Отмена</button></div></form>}
      {openHistoryId === measure.id && <div className="deadline-history">{(deadlineHistory[measure.id] ?? []).length > 0 ? <ul>{(deadlineHistory[measure.id] ?? []).map((change) => <li key={change.id}><strong>{change.old_due_date} → {change.new_due_date}</strong><span>{change.reason}</span><small>Изменено: {new Date(change.changed_at).toLocaleString('ru-RU')}</small></li>)}</ul> : <p className="cell-note">Переносов не зафиксировано.</p>}</div>}
      </li>)}</ul>
    </div>
  </section></div>
}

const deadlineStatusChips = [
  { value: '', label: 'Все' },
  { value: 'overdue', label: 'Просроченные' },
  { value: 'due_soon', label: 'Срок ≤ 7 дней' },
  { value: 'not_eliminated', label: 'Не устранено' },
  { value: 'eliminated', label: 'Устранено' },
  { value: 'eliminated_late', label: 'Устранено с просрочкой' },
  { value: 'heavy', label: 'Критичные' },
]

function controlTypeLabel(code: string, name: string) { if (code === 'PC_III') return 'ПК III уровня'; if (code === 'PC_II') return 'ПК II'; if (code === 'ROSTECHNADZOR') return 'Ростехнадзор'; if (code === 'GAZNADZOR') return 'Газнадзор'; return name }
function pluralDays(count: number) { const mod10 = count % 10; const mod100 = count % 100; if (mod10 === 1 && mod100 !== 11) return 'день'; if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return 'дня'; return 'дней' }
function formatDueTitle(iso: string) { return new Date(`${iso}T00:00:00`).toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' }).replace(' г.', '').toUpperCase() }
function deadlineRank(item: DeadlineControlItem) { if (item.status === 'overdue') return 0; if (item.due_soon) return 1; if (item.status === 'not_eliminated') return 2; return 3 }

function deadlineChipClass(item: DeadlineControlItem) { return item.eliminated_late || item.status === 'overdue' ? 'chip danger' : item.due_soon ? 'chip warning' : item.status === 'eliminated' ? 'chip success' : 'chip muted-chip' }
function deadlineChipLabel(item: DeadlineControlItem) { return item.eliminated_late ? 'Устранено с просрочкой' : item.status === 'overdue' ? 'Просрочено' : item.due_soon ? 'Срок ≤ 7 дней' : item.status === 'eliminated' ? 'Устранено' : 'Не устранено' }
function deviationCell(item: DeadlineControlItem) { if (item.status === 'overdue') return <span className="danger-note">Просрочено на {item.days_overdue} дн.</span>; if (item.elimination_date) return <span>{item.elimination_date}{item.eliminated_late ? <small className="danger-note"> с просрочкой {item.days_overdue_at_elimination ?? 0} дн.</small> : null}</span>; if (item.days_left !== null) return <span className={item.due_soon ? 'soon-note' : undefined}>Осталось {item.days_left} дн.</span>; return <span>—</span> }
function deviationKind(item: DeadlineControlItem) { if (item.status === 'overdue') return 'overdue'; if (item.elimination_date) return 'eliminated'; if (item.days_left !== null) return 'left'; return 'none' }
function inDateRange(value: string | null, from: string, to: string) { if (!from && !to) return true; if (!value) return false; if (from && value < from) return false; if (to && value > to) return false; return true }

function DeadlineWorkspace({ token, initialTypeId, initialStatus }: { token: string; initialTypeId?: string | null; initialStatus?: string | null }) {
  const [data, setData] = useState<DeadlineControlResponse | null>(null)
  const [violations, setViolations] = useState<ViolationItem[]>([])
  const [inspections, setInspections] = useState<InspectionItem[]>([])
  const [departments, setDepartments] = useState<ReferenceItem[]>([])
  const [objects, setObjects] = useState<ObjectItem[]>([])
  const [persons, setPersons] = useState<PersonItem[]>([])
  const [selectedType, setSelectedType] = useState<string | null>(initialTypeId ?? null)
  const [statusFilter, setStatusFilter] = useState(initialStatus ?? '')
  const [departmentFilter, setDepartmentFilter] = useState('')
  const [objectFilter, setObjectFilter] = useState('')
  const [severityFilter, setSeverityFilter] = useState('')
  const [actFilter, setActFilter] = useState('')
  const [personFilter, setPersonFilter] = useState('')
  const [formulationFilter, setFormulationFilter] = useState('')
  const [inspectionDateFrom, setInspectionDateFrom] = useState('')
  const [inspectionDateTo, setInspectionDateTo] = useState('')
  const [dueDateFrom, setDueDateFrom] = useState('')
  const [dueDateTo, setDueDateTo] = useState('')
  const [deviationFilter, setDeviationFilter] = useState('')
  const [selectedViolationId, setSelectedViolationId] = useState<string | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setError(''); setLoading(true)
    api.deadlineControl(token, {}).then(setData).catch((reason: unknown) => setError(reason instanceof Error ? reason.message : 'Не удалось загрузить контроль сроков')).finally(() => setLoading(false))
    api.violations(token).then(setViolations).catch(() => setViolations([]))
    api.inspections(token).then(setInspections).catch(() => setInspections([]))
    api.references(token, 'departments').then(setDepartments).catch(() => setDepartments([]))
    api.objects(token).then(setObjects).catch(() => setObjects([]))
    api.persons(token).then(setPersons).catch(() => setPersons([]))
  }, [token])

  const types = data?.types ?? []
  const items = data?.items ?? []
  const summary = data?.summary ?? null
  const showAllTypes = selectedType === 'all'
  const measureCounts = new Map<string, number>(); for (const entry of items) measureCounts.set(entry.control_type_id, (measureCounts.get(entry.control_type_id) ?? 0) + 1)
  const activeType = showAllTypes ? null : types.find((item) => item.control_type_id === selectedType) ?? types[0] ?? null
  const scopeLabel = showAllTypes ? 'все виды' : activeType ? controlTypeLabel(activeType.code, activeType.name) : ''
  const typeItems = showAllTypes ? items : activeType ? items.filter((item) => item.control_type_id === activeType.control_type_id) : []
  const upcoming = typeItems
    .filter((item) => item.status !== 'eliminated' && (item.status === 'overdue' || item.due_soon))
    .sort((a, b) => (a.due_date ?? '9999-12-31').localeCompare(b.due_date ?? '9999-12-31') || a.person_name.localeCompare(b.person_name, 'ru'))
  const registryItems = typeItems
    .filter((item) => statusFilter === '' || (statusFilter === 'eliminated' ? item.status === 'eliminated' : statusFilter === 'due_soon' ? item.due_soon : statusFilter === 'eliminated_late' ? item.eliminated_late : statusFilter === 'heavy' ? (violations.find((v) => v.id === item.violation_id)?.severity ?? 0) >= 8 : item.status === statusFilter))
    .filter((item) => !departmentFilter || item.department_id === departmentFilter)
    .filter((item) => !objectFilter || item.object_id === objectFilter)
    .filter((item) => !severityFilter || (violations.find((v) => v.id === item.violation_id)?.severity ?? 0) === Number(severityFilter))
    .filter((item) => !actFilter || item.inspection_id === actFilter)
    .filter((item) => inDateRange(item.inspection_date, inspectionDateFrom, inspectionDateTo))
    .filter((item) => !personFilter || item.person_id === personFilter)
    .filter((item) => { const query = formulationFilter.trim().toLowerCase(); return !query || item.violation_formulation.toLowerCase().includes(query) || item.elimination_measure.toLowerCase().includes(query) })
    .filter((item) => inDateRange(item.due_date, dueDateFrom, dueDateTo))
    .filter((item) => !deviationFilter || deviationKind(item) === deviationFilter)
    .sort((a, b) => deadlineRank(a) - deadlineRank(b) || (a.due_date ?? '9999-12-31').localeCompare(b.due_date ?? '9999-12-31') || a.person_name.localeCompare(b.person_name, 'ru'))
  const departmentOptions = [...new Map(typeItems.map((item) => [item.department_id, item.department_name])).entries()]
  const objectOptions = [...new Map(typeItems.map((item) => [item.object_id, item.object_name])).entries()]
  const severityValues = [...new Set(violations.filter((item) => typeItems.some((entry) => entry.violation_id === item.id)).map((item) => item.severity))].sort((a, b) => a - b)
  const actOptions = [...new Map(typeItems.map((item) => [item.inspection_id, item.document_number])).entries()].sort((a, b) => a[1].localeCompare(b[1], 'ru'))
  const deadlinePersonOptions = [...new Map(typeItems.map((item) => [item.person_id, item.person_position ? `${item.person_name} · ${item.person_position}` : item.person_name])).entries()].sort((a, b) => a[1].localeCompare(b[1], 'ru'))
  const selectedViolation = violations.find((item) => item.id === selectedViolationId) ?? null

  function handleViolationUpdated(updated: ViolationItem) { setViolations((current) => current.map((item) => item.id === updated.id ? updated : item)); api.deadlineControl(token, {}).then(setData).catch(() => undefined) }
  function resetColumnFilters() { setStatusFilter(''); setDepartmentFilter(''); setObjectFilter(''); setSeverityFilter(''); setActFilter(''); setPersonFilter(''); setFormulationFilter(''); setInspectionDateFrom(''); setInspectionDateTo(''); setDueDateFrom(''); setDueDateTo(''); setDeviationFilter('') }

  return <>
    <div className="title-row"><div><p className="eyebrow">КОНТРОЛЬ</p><h1>Контроль сроков</h1></div></div>
    {loading ? <p className="empty">Загрузка…</p> : error ? <p className="form-error">{error}</p> : <>
      <div className="type-cards">{summary && <button className={showAllTypes ? 'type-card active' : 'type-card'} type="button" onClick={() => { setSelectedType('all'); resetColumnFilters() }}><span className="type-card-head"><strong>Все виды</strong>{showAllTypes && <span className="type-card-badge">Выбрано</span>}</span><span className="type-card-total">{types.reduce((sum, item) => sum + item.total, 0)}</span><span className="type-card-caption">всего нарушений</span><span className="type-card-caption">мероприятий по устранению: {items.length}</span><span className="type-card-stats"><span className="stat overdue"><strong>{summary.overdue}</strong> просрочено</span><span className="stat soon"><strong>{summary.due_soon}</strong> срок ≤ 7 дней</span><span className="stat"><strong>{summary.not_eliminated}</strong> не устранено</span></span></button>}{types.map((item) => <button className={activeType && item.control_type_id === activeType.control_type_id ? 'type-card active' : 'type-card'} key={item.control_type_id} type="button" onClick={() => { setSelectedType(item.control_type_id); resetColumnFilters() }}><span className="type-card-head"><strong>{controlTypeLabel(item.code, item.name)}</strong>{activeType && item.control_type_id === activeType.control_type_id && <span className="type-card-badge">Выбрано</span>}</span><span className="type-card-total">{item.total}</span><span className="type-card-caption">всего нарушений</span><span className="type-card-caption">мероприятий по устранению: {measureCounts.get(item.control_type_id) ?? 0}</span><span className="type-card-stats"><span className="stat overdue"><strong>{item.overdue}</strong> просрочено</span><span className="stat soon"><strong>{item.due_soon}</strong> срок ≤ 7 дней</span><span className="stat"><strong>{item.not_eliminated}</strong> не устранено</span></span></button>)}</div>
      {(activeType || showAllTypes) && <section className="panel"><div className="panel-header"><div><h2>Ближайшие сроки · {scopeLabel}</h2></div><span className="counter">{upcoming.length}</span></div>{upcoming.length === 0 ? <p className="empty">Просроченных и приближающихся сроков нет.</p> : <ul className="due-list">{upcoming.map((item) => <li key={item.measure_id}><button className="due-item" type="button" onClick={() => setSelectedViolationId(item.violation_id)}><span className="due-date">{item.due_date ? formatDueTitle(item.due_date) : 'Срок не задан'}</span><span className="due-main"><strong>{item.violation_formulation}</strong><small>{item.department_name} · {item.object_name} · Акт {item.document_number}</small></span><span className={item.status === 'overdue' ? 'due-badge overdue' : 'due-badge soon'}>{item.status === 'overdue' ? `Просрочено · ${item.days_overdue} ${pluralDays(item.days_overdue)}` : item.days_left === 0 ? 'Срок сегодня' : `Осталось ${item.days_left} ${pluralDays(item.days_left ?? 0)}`}</span></button></li>)}</ul>}</section>}
      {(activeType || showAllTypes) && <section className="panel"><div className="panel-header"><div><h2>Реестр нарушений · {scopeLabel}</h2></div><div className="header-actions"><button className="logout small-button" type="button" onClick={resetColumnFilters}>Сброс фильтров</button><span className="counter">{registryItems.length}</span></div></div>
        <div className="registry-toolbar">
          <div className="tab-list">{deadlineStatusChips.map((chip) => <button className={statusFilter === chip.value ? 'tab active-tab' : 'tab'} key={chip.value || 'all'} type="button" onClick={() => setStatusFilter(chip.value)}>{chip.label}</button>)}</div>
          <div className="deadline-filters"><label>Акт-предписание<select value={actFilter} onChange={(event) => setActFilter(event.target.value)}><option value="">Все акты</option>{actOptions.map(([id, number]) => <option key={id} value={id}>{number}</option>)}</select></label><label>Дата проверки с<input type="date" value={inspectionDateFrom} onChange={(event) => setInspectionDateFrom(event.target.value)} /></label><label>Дата проверки по<input type="date" value={inspectionDateTo} onChange={(event) => setInspectionDateTo(event.target.value)} /></label><label>Ответственный<select value={personFilter} onChange={(event) => setPersonFilter(event.target.value)}><option value="">Все ответственные</option>{deadlinePersonOptions.map(([id, label]) => <option key={id} value={id}>{label}</option>)}</select></label><label>Подразделение<select value={departmentFilter} onChange={(event) => setDepartmentFilter(event.target.value)}><option value="">Все подразделения</option>{departmentOptions.map(([id, name]) => <option key={id} value={id}>{name}</option>)}</select></label><label>Объект<select value={objectFilter} onChange={(event) => setObjectFilter(event.target.value)}><option value="">Все объекты</option>{objectOptions.map(([id, name]) => <option key={id} value={id}>{name}</option>)}</select></label><label>Нарушение<input placeholder="Содержит текст…" value={formulationFilter} onChange={(event) => setFormulationFilter(event.target.value)} /></label><label>Срок с<input type="date" value={dueDateFrom} onChange={(event) => setDueDateFrom(event.target.value)} /></label><label>Срок по<input type="date" value={dueDateTo} onChange={(event) => setDueDateTo(event.target.value)} /></label><label>Степень<select value={severityFilter} onChange={(event) => setSeverityFilter(event.target.value)}><option value="">Любая</option>{severityValues.map((value) => <option key={value} value={String(value)}>{value}</option>)}</select></label><label>Отклонение<select value={deviationFilter} onChange={(event) => setDeviationFilter(event.target.value)}><option value="">Любое</option><option value="overdue">Просрочено</option><option value="left">Осталось дней</option><option value="eliminated">Дата устранения</option><option value="none">Без расчёта</option></select></label></div>
        </div>
        {registryItems.length === 0 ? <p className="empty">Мер по выбранным условиям нет.</p> : <table><thead><tr><th>Акт-предписание</th><th>Дата проверки</th><th>Ответственный</th><th>Подразделение</th><th>Объект</th><th>Нарушение</th><th>Срок устранения</th><th>Отклонение</th><th>Статус</th></tr></thead><tbody>{registryItems.map((item) => <tr className="clickable-row" key={item.measure_id} onClick={() => setSelectedViolationId(item.violation_id)}><td className="code">{item.document_number}</td><td>{item.inspection_date}</td><td>{item.person_name}{item.person_position ? <small className="cell-note">{item.person_position}</small> : null}</td><td>{item.department_name}</td><td>{item.object_name}</td><td>{item.violation_formulation}{item.elimination_measure ? <small className="cell-note">{item.elimination_measure}</small> : null}</td><td>{item.due_date ?? '—'}{item.original_due_date && item.due_date && item.original_due_date !== item.due_date ? <small className="cell-note">первоначально {item.original_due_date}</small> : null}</td><td>{deviationCell(item)}</td><td><span className={deadlineChipClass(item)}>{deadlineChipLabel(item)}</span></td></tr>)}</tbody></table>}
      </section>}
    </>}
    {selectedViolation && <ViolationCardModal token={token} violation={selectedViolation} inspections={inspections} departments={departments} objects={objects} persons={persons} onClose={() => setSelectedViolationId(null)} onUpdated={handleViolationUpdated} />}
  </>
}

function shorten(value: string, limit = 60) { return value.length > limit ? `${value.slice(0, limit)}…` : value }

function ImportWorkspace({ token }: { token: string }) {
  const [inspections, setInspections] = useState<InspectionItem[]>([])
  const [inspectionId, setInspectionId] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [headerRow, setHeaderRow] = useState('1')
  const [mapping, setMapping] = useState({ formulation: '', requirement: '', measure: '', responsible: '', dueDate: '' })
  const [preview, setPreview] = useState<Awaited<ReturnType<typeof api.previewImport>> | null>(null)
  const [violationTypes, setViolationTypes] = useState<ViolationTypeItem[]>([])
  const [departments, setDepartments] = useState<ReferenceItem[]>([])
  const [objects, setObjects] = useState<ObjectItem[]>([])
  const [persons, setPersons] = useState<PersonItem[]>([])
  const [assignment, setAssignment] = useState({ violationTypeId: '', departmentId: '', objectId: '', personId: '' })
  const [rowPersons, setRowPersons] = useState<Record<string, string>>({})
  const [message, setMessage] = useState('')
  const [messageTone, setMessageTone] = useState<'error' | 'success'>('error')

  useEffect(() => { api.inspections(token).then(setInspections).catch(() => setInspections([])); api.violationTypes(token).then(setViolationTypes); api.references(token, 'departments').then(setDepartments); api.objects(token).then(setObjects); api.persons(token).then(setPersons) }, [token])
  const ready = Boolean(inspectionId && file)
  function personOptions(value: string) { const filtered = persons.filter((item) => item.is_active && (!item.department_id || item.department_id === assignment.departmentId)); if (value && !filtered.some((item) => item.id === value)) { const extra = persons.find((item) => item.id === value); if (extra) return [...filtered, extra] } return filtered }
  function personForRow(row: ImportPreviewRow): string { const key = String(row.row_number); if (key in rowPersons) return rowPersons[key]; return row.responsible?.person_id ?? assignment.personId ?? '' }
  const missingPersonRows = preview ? preview.rows.filter((row) => !personForRow(row)) : []
  async function loadPreview() { if (!file || !inspectionId) return; setMessage(''); try { const result = await api.previewImport(token, inspectionId, file, { formulation: mapping.formulation, requirement: mapping.requirement, measure: mapping.measure, responsible: mapping.responsible, due_date: mapping.dueDate }, Number(headerRow)); setPreview(result); setRowPersons({}) } catch (reason) { setMessageTone('error'); setMessage(reason instanceof Error ? reason.message : 'Не удалось обработать файл') } }
  async function confirm() { if (!preview || preview.invalid_rows || missingPersonRows.length > 0 || !assignment.violationTypeId || !assignment.departmentId || !assignment.objectId) return; const resolvedMapping = preview.mapping; const rows = preview.rows.map((row) => ({ formulation: row.values[resolvedMapping.formulation], violated_requirement: row.values[resolvedMapping.requirement], violation_type_id: assignment.violationTypeId, measures: [{ department_id: assignment.departmentId, object_id: assignment.objectId, person_id: personForRow(row), elimination_measure: row.values[resolvedMapping.measure], due_date: row.due_date ?? undefined }] })); try { const result = await api.confirmImport(token, inspectionId, { rows }); setMessage(`Импортировано нарушений: ${result.created_violations}; мероприятий: ${result.created_measures}`); setMessageTone('success'); setPreview(null); setRowPersons({}) } catch (reason) { setMessageTone('error'); setMessage(reason instanceof Error ? reason.message : 'Не удалось подтвердить импорт') } }

  return <><div className="title-row"><div><p className="eyebrow">ЗАГРУЗКА ДАННЫХ</p><h1>Импорт нарушений</h1></div><span className="period">Excel и Word</span></div><section className="panel form-panel"><div className="import-steps"><span className="active-step">1. Файл</span><span>2. Сопоставление</span><span>3. Проверка</span><span>4. Подтверждение</span></div><form className="entry-form"><label>Проверка<select value={inspectionId} onChange={(event) => setInspectionId(event.target.value)} required><option value="">Выберите проверку</option>{inspections.map((item) => <option key={item.id} value={item.id}>{item.inspection_date} · {item.document_number}</option>)}</select></label><label>Строка с заголовками<input type="number" min="1" value={headerRow} onChange={(event) => setHeaderRow(event.target.value)} /></label><label className="wide upload-zone">Файл Excel или Word<input type="file" accept=".xlsx,.xls,.docx" onChange={(event) => setFile(event.target.files?.[0] ?? null)} />{file ? <strong>{file.name} · {(file.size / 1024).toFixed(1)} КБ</strong> : <span>Выберите файл .xlsx, .xls или .docx</span>}</label></form>{ready && <div className="import-mapping"><h3>Сопоставление колонок</h3><p>Укажите колонки исходного файла. После обработки система покажет строки, ошибки и предложенные значения.</p><div className="entry-form"><label>Формулировка нарушения<input value={mapping.formulation} placeholder="Например: Нарушение" onChange={(event) => setMapping({ ...mapping, formulation: event.target.value })} /></label><label>Нарушенное требование<input value={mapping.requirement} placeholder="Например: Требование" onChange={(event) => setMapping({ ...mapping, requirement: event.target.value })} /></label><label>Мероприятие<input value={mapping.measure} placeholder="Например: Мероприятие" onChange={(event) => setMapping({ ...mapping, measure: event.target.value })} /></label><label>Ответственный<input value={mapping.responsible} placeholder="Например: Ответственный" onChange={(event) => setMapping({ ...mapping, responsible: event.target.value })} /></label><label>Срок устранения<input value={mapping.dueDate} placeholder="Например: Срок" onChange={(event) => setMapping({ ...mapping, dueDate: event.target.value })} /></label></div><button className="primary-button" type="button" onClick={loadPreview}>Проверить и показать предварительный просмотр</button></div>}</section><section className="panel"><div className="panel-header"><div><h2>Предварительный просмотр</h2><p>До подтверждения новые нарушения и мероприятия не создаются.</p></div></div>{message && <p className={messageTone === 'success' ? 'form-success' : 'form-error'}>{message}</p>}{preview ? <><div className="import-mapping"><div className="entry-form"><label>Тип нарушения<select value={assignment.violationTypeId} onChange={(event) => setAssignment({ ...assignment, violationTypeId: event.target.value })}><option value="">Выберите тип</option>{violationTypes.filter((item) => item.is_active).map((item) => <option key={item.id} value={item.id}>{item.code} · {item.name}</option>)}</select></label><label>Подразделение<select value={assignment.departmentId} onChange={(event) => setAssignment({ ...assignment, departmentId: event.target.value, objectId: '', personId: '' })}><option value="">Выберите подразделение</option>{departments.filter((item) => item.is_active).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><label>Объект<select value={assignment.objectId} onChange={(event) => setAssignment({ ...assignment, objectId: event.target.value })}><option value="">Выберите объект</option>{objects.filter((item) => item.is_active && (!item.owner_department_id || item.owner_department_id === assignment.departmentId)).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><label>Ответственный по умолчанию<select value={assignment.personId} onChange={(event) => setAssignment({ ...assignment, personId: event.target.value })}><option value="">Не назначен</option>{personOptions(assignment.personId).map((item) => <option key={item.id} value={item.id}>{item.full_name}</option>)}</select></label></div><p>Подставляется в строки, где ответственный из файла не распознан. Если сотрудник из файла сопоставлен со справочником, назначается он.</p></div><p className="empty">Корректных строк: {preview.valid_rows}; с ошибками: {preview.invalid_rows}. Сопоставление колонок: формулировка «{preview.mapping.formulation}» · требование «{preview.mapping.requirement}» · мероприятие «{preview.mapping.measure}» · ответственный «{preview.mapping.responsible}».</p><table><thead><tr><th>№</th><th>Формулировка</th><th>Мероприятие</th><th>Срок</th><th>Ответственный</th><th>Ошибки</th></tr></thead><tbody>{preview.rows.map((row) => <tr key={row.row_number}><td>{row.row_number}</td><td>{shorten(row.values[preview.mapping.formulation] ?? '')}</td><td>{shorten(row.values[preview.mapping.measure] ?? '')}</td><td>{row.due_date ?? '—'}</td><td className="responsible-cell">{row.responsible && <span className={row.responsible.person_id ? 'chip success' : row.responsible.name ? 'chip danger' : 'chip muted-chip'} title={row.responsible.raw}>{row.responsible.person_id ? `Сопоставлен: ${row.responsible.person_name ?? ''}` : row.responsible.name ? `Не найден: ${row.responsible.name}` : row.responsible.position ? `Только должность: ${row.responsible.position}` : 'Имя не распознано'}</span>}<select value={personForRow(row)} onChange={(event) => setRowPersons({ ...rowPersons, [String(row.row_number)]: event.target.value })}><option value="">Не назначен</option>{personOptions(personForRow(row)).map((item) => <option key={item.id} value={item.id}>{item.full_name}{item.position ? ` · ${item.position}` : ''}</option>)}</select></td><td>{row.errors.length ? row.errors.join('; ') : '—'}</td></tr>)}</tbody></table>{missingPersonRows.length > 0 && <p className="form-error">Не назначен ответственный для строк: {missingPersonRows.map((row) => row.row_number).join(', ')}</p>}<div className="import-mapping"><button className="primary-button" type="button" disabled={Boolean(preview.invalid_rows) || missingPersonRows.length > 0 || !assignment.violationTypeId || !assignment.departmentId || !assignment.objectId} onClick={confirm}>Подтвердить импорт</button></div></> : <p className="empty">{ready ? 'Нажмите «Проверить», чтобы получить строки файла, нормализованные значения и построчные ошибки.' : 'Сначала выберите проверку и файл для импорта.'}</p>}</section></>
}

function ReferenceWorkspace({ token, user }: { token: string; user: CurrentUser }) {
  const [resource, setResource] = useState(referenceTabs[0].resource)
  const [items, setItems] = useState<ReferenceItem[]>([])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const isAdministrator = user.roles.includes('Administrator')

  useEffect(() => {
    setLoading(true)
    setError('')
    api.references(token, resource).then(setItems).catch((reason: unknown) => setError(reason instanceof Error ? reason.message : 'Не удалось загрузить справочник')).finally(() => setLoading(false))
  }, [resource, token])

  const title = referenceTabs.find((tab) => tab.resource === resource)?.label ?? 'Справочник'
  return <><div className="title-row"><div><p className="eyebrow">НАСТРОЙКИ</p><h1>Справочники</h1></div>{isAdministrator && <button className="primary-button" disabled>Добавить запись</button>}</div><div className="tab-list">{referenceTabs.map((tab) => <button className={resource === tab.resource ? 'tab active-tab' : 'tab'} key={tab.resource} onClick={() => setResource(tab.resource)}>{tab.label}</button>)}</div><section className="panel"><div className="panel-header"><div><h2>{title}</h2><p>Неактивные записи сохраняются в истории и не удаляются физически.</p></div><span className="counter">{items.length}</span></div>{loading ? <p className="empty">Загрузка…</p> : error ? <p className="form-error">{error}</p> : <table><thead><tr><th>Код</th><th>Наименование</th><th>Порядок</th><th>Статус</th></tr></thead><tbody>{items.map((item) => <tr key={item.id}><td className="code">{item.code}</td><td>{item.name}</td><td>{item.display_order}</td><td><span className={item.is_active ? 'chip success' : 'chip muted-chip'}>{item.is_active ? 'Активна' : 'Неактивна'}</span></td></tr>)}</tbody></table>}{!loading && !error && items.length === 0 && <p className="empty">Записей пока нет.</p>}</section></>
}

function UsersWorkspace({ token }: { token: string }) {
  const [users, setUsers] = useState<UserItem[]>([])
  const [error, setError] = useState('')
  useEffect(() => { api.users(token).then(setUsers).catch((reason: unknown) => setError(reason instanceof ApiError ? reason.message : 'Нет доступа к пользователям')) }, [token])
  return <><div className="title-row"><div><p className="eyebrow">АДМИНИСТРИРОВАНИЕ</p><h1>Пользователи и роли</h1></div><button className="primary-button" disabled>Создать пользователя</button></div><section className="panel"><div className="panel-header"><div><h2>Учетные записи</h2><p>Назначение ролей проверяется сервером; интерфейс не заменяет RBAC.</p></div></div>{error ? <p className="form-error">{error}</p> : <table><thead><tr><th>Логин</th><th>Отображаемое имя</th><th>Роли</th><th>Статус</th></tr></thead><tbody>{users.map((item) => <tr key={item.id}><td className="code">{item.login}</td><td>{item.display_name}</td><td>{item.roles.join(', ')}</td><td><span className={item.is_active ? 'chip success' : 'chip muted-chip'}>{item.is_active ? 'Активна' : 'Отключена'}</span></td></tr>)}</tbody></table>}{!error && users.length === 0 && <p className="empty">Пользователей пока нет.</p>}</section></>
}

type FactDraft = { values: Record<string, string>; notApplicable: boolean; comment: string }

const assessmentPeriodOptions: Array<{ value: AssessmentPeriodType; label: string; indexes: number[] }> = [
  { value: 'quarter', label: 'Квартал', indexes: [1, 2, 3, 4] },
  { value: 'half_year', label: 'Полугодие', indexes: [1, 2] },
  { value: 'nine_months', label: '9 месяцев', indexes: [1] },
  { value: 'year', label: 'Год', indexes: [1] },
]
const assessmentPeriodLabel = (type: AssessmentPeriodType) => assessmentPeriodOptions.find((option) => option.value === type)?.label ?? type
const assessmentIndexLabel = (type: AssessmentPeriodType, index: number) => (type === 'quarter' || type === 'half_year') ? (['', 'I', 'II', 'III', 'IV'][index] ?? String(index)) : ''
const assessmentPeriodTitle = (type: AssessmentPeriodType, year: number, index: number) => `${assessmentPeriodLabel(type)}${assessmentIndexLabel(type, index) ? ` ${assessmentIndexLabel(type, index)}` : ''} ${year}`
const assessmentInputTypeLabel: Record<string, string> = { manual: 'ручной ввод', auto: 'автоматически из журнала', mixed: 'журнал + ручной ввод' }
const assessmentSubjectLabel = (subject: 'department' | 'service') => subject === 'department' ? 'подразделение' : 'Служба ППБиБДД'
const formatDateTime = (value: string) => { try { return new Date(value).toLocaleString('ru-RU', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' }) } catch { return value } }
const formatScore = (score: number | null) => score === null ? '—' : score.toFixed(2).replace('.', ',')

function AssessmentVerdictChip({ verdict }: { verdict: string | null }) {
  if (verdict === 'satisfactory') return <span className="chip success">удовлетворительно</span>
  if (verdict === 'unsatisfactory') return <span className="chip danger">неудовлетворительно</span>
  return <span className="chip muted-chip">не рассчитан</span>
}

function AssessmentScoreBadge({ criterion }: { criterion: AssessmentCriterionResult }) {
  if (criterion.not_applicable) return <span className="score-badge score-na" title={criterion.reason}>Н/П</span>
  if (criterion.missing_input) return <span className="score-badge score-missing" title={criterion.reason}>нет данных</span>
  if (criterion.score === null) return <span className="score-badge score-missing">—</span>
  return <span className={`score-badge score-${criterion.score}`}>{criterion.score}</span>
}

function AssessmentWorkspace({ token, user }: { token: string; user: CurrentUser }) {
  const [periodType, setPeriodType] = useState<AssessmentPeriodType>('quarter')
  const [periodYear, setPeriodYear] = useState(new Date().getFullYear())
  const [periodIndex, setPeriodIndex] = useState(Math.floor(new Date().getMonth() / 3) + 1)
  const [departmentId, setDepartmentId] = useState('')
  const [departments, setDepartments] = useState<ReferenceItem[]>([])
  const [data, setData] = useState<AssessmentComputeResponse | null>(null)
  const [results, setResults] = useState<AssessmentResultItem[]>([])
  const [detail, setDetail] = useState<AssessmentResultDetail | null>(null)
  const [error, setError] = useState('')
  const [resultsError, setResultsError] = useState('')
  const [computing, setComputing] = useState(true)
  const [savingFact, setSavingFact] = useState(false)
  const [fixating, setFixating] = useState(false)
  const [fixationNote, setFixationNote] = useState('')
  const [editingId, setEditingId] = useState<string | null>(null)
  const [draft, setDraft] = useState<FactDraft | null>(null)
  const [factError, setFactError] = useState('')
  const canEditFacts = user.roles.includes('Administrator') || user.roles.includes('Specialist')
  const periodIndexes = assessmentPeriodOptions.find((option) => option.value === periodType)?.indexes ?? [1]
  const subjectName = departmentId ? departments.find((item) => item.id === departmentId)?.name ?? 'Подразделение' : 'Служба ППБиБДД'
  const selectionChanged = data !== null && (data.period_type !== periodType || data.period_year !== periodYear || data.period_index !== periodIndex || (data.department_id ?? '') !== departmentId)
  const sortedResults = [...results].sort((a, b) => b.created_at.localeCompare(a.created_at))
  const yearOptions = Array.from({ length: 5 }, (_, offset) => new Date().getFullYear() - 2 + offset)

  function closeEditor() { setEditingId(null); setDraft(null) }

  function resetSelectionState() { closeEditor() }

  function changePeriodType(value: AssessmentPeriodType) {
    const nextIndexes = assessmentPeriodOptions.find((option) => option.value === value)?.indexes ?? [1]
    setPeriodType(value)
    if (!nextIndexes.includes(periodIndex)) setPeriodIndex(Math.min(periodIndex, nextIndexes[nextIndexes.length - 1]))
    resetSelectionState()
  }

  async function runCompute() {
    setComputing(true); setError('')
    try {
      const response = await api.assessmentCompute(token, { period_type: periodType, period_year: periodYear, period_index: periodIndex, department_id: departmentId || null })
      setData(response); closeEditor()
    } catch (reason) { setData(null); setError(reason instanceof Error ? reason.message : 'Не удалось выполнить расчёт') } finally { setComputing(false) }
  }

  async function saveFact(criterion: AssessmentCriterionResult) {
    if (!draft) return
    setSavingFact(true); setFactError('')
    try {
      const values: Record<string, unknown> = {}
      for (const field of criterion.input_fields) {
        const raw = draft.values[field.key] ?? ''
        if (field.kind === 'bool') { if (raw === 'yes') values[field.key] = true; else if (raw === 'no') values[field.key] = false }
        else if (field.kind === 'number') { if (raw.trim() !== '') { const parsed = Number(raw); if (Number.isFinite(parsed)) values[field.key] = parsed } }
        else if (raw) values[field.key] = raw
      }
      await api.assessmentSaveFact(token, { criterion_id: criterion.criterion_id, period_type: periodType, period_year: periodYear, period_index: periodIndex, department_id: departmentId || null, values, not_applicable: draft.notApplicable, comment: draft.comment.trim() || null })
      closeEditor()
      await runCompute()
    } catch (reason) { setFactError(reason instanceof Error ? reason.message : 'Не удалось сохранить исходные данные') } finally { setSavingFact(false) }
  }

  async function fixateResult() {
    setFixating(true); setFixationNote(''); setError('')
    try {
      await api.assessmentSaveResult(token, { period_type: periodType, period_year: periodYear, period_index: periodIndex, department_id: departmentId || null })
      setFixationNote(`Результат за «${assessmentPeriodTitle(periodType, periodYear, periodIndex)} · ${subjectName}» зафиксирован.`)
      loadResults()
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Не удалось зафиксировать результат') } finally { setFixating(false) }
  }

  async function openDetail(item: AssessmentResultItem) {
    setDetail(null); setError('')
    try { setDetail(await api.assessmentResultDetail(token, item.id)) } catch (reason) { setError(reason instanceof Error ? reason.message : 'Не удалось загрузить зафиксированный результат') }
  }

  function loadResults() { api.assessmentResults(token).then(setResults).catch((reason: unknown) => setResultsError(reason instanceof Error ? reason.message : 'Не удалось загрузить результаты')) }

  function openEditor(criterion: AssessmentCriterionResult) {
    const values: Record<string, string> = {}
    for (const field of criterion.input_fields) {
      const raw = criterion.fact_values[field.key]
      if (typeof raw === 'boolean') values[field.key] = raw ? 'yes' : 'no'
      else if (raw !== null && raw !== undefined) values[field.key] = String(raw)
    }
    setDraft({ values, notApplicable: criterion.fact_not_applicable, comment: criterion.fact_comment ?? '' })
    setEditingId(criterion.criterion_id)
    setFactError('')
  }

  function toggleEditor(criterion: AssessmentCriterionResult) { if (editingId === criterion.criterion_id) closeEditor(); else openEditor(criterion) }

  function renderCriteriaRows(criteria: AssessmentCriterionResult[], editable: boolean): ReactNode[] {
    const rows: ReactNode[] = []
    let lastSection = ''
    for (const criterion of criteria) {
      if (criterion.section_code !== lastSection) {
        lastSection = criterion.section_code
        rows.push(<tr className="section-row" key={`section-${criterion.section_code}`}><td colSpan={6}>{criterion.section_code} · {criterion.section_title}</td></tr>)
      }
      const canEdit = editable && canEditFacts && criterion.input_fields.length > 0
      rows.push(<tr className={canEdit ? 'clickable-row' : undefined} key={criterion.criterion_id} onClick={canEdit ? () => toggleEditor(criterion) : undefined} title={canEdit ? 'Нажмите, чтобы ввести исходные данные' : undefined}>
        <td className="code">{criterion.criterion_code}</td>
        <td>{criterion.name}<small className="cell-note">{assessmentSubjectLabel(criterion.subject_type)} · {assessmentInputTypeLabel[criterion.input_type] ?? criterion.input_type}</small></td>
        <td className="fact-cell">{criterion.fact ?? '—'}{canEdit && editingId !== criterion.criterion_id && <button className="logout small-button" type="button" onClick={(event) => { event.stopPropagation(); openEditor(criterion) }}>Исходные данные</button>}</td>
        <td>{criterion.threshold ?? '—'}</td>
        <td><AssessmentScoreBadge criterion={criterion} /></td>
        <td className="reason-cell">{criterion.reason}</td>
      </tr>)
      if (editable && editingId === criterion.criterion_id && draft) {
        rows.push(<tr className="assessment-editor-row" key={`${criterion.criterion_id}-editor`}><td colSpan={6}><div className="entry-form assessment-fact-form">
          <strong>Исходные данные · {criterion.criterion_code}</strong>
          {criterion.input_fields.map((field) => <label key={field.key}>{field.label}{field.kind === 'date' ? <input type="date" value={draft.values[field.key] ?? ''} onChange={(event) => setDraft({ ...draft, values: { ...draft.values, [field.key]: event.target.value } })} /> : field.kind === 'bool' ? <select value={draft.values[field.key] ?? ''} onChange={(event) => setDraft({ ...draft, values: { ...draft.values, [field.key]: event.target.value } })}><option value="">— не указано —</option><option value="yes">Да</option><option value="no">Нет</option></select> : <input type="number" min={0} step={1} value={draft.values[field.key] ?? ''} onChange={(event) => setDraft({ ...draft, values: { ...draft.values, [field.key]: event.target.value } })} />}</label>)}
          <label className="checkbox-label"><input type="checkbox" checked={draft.notApplicable} onChange={(event) => setDraft({ ...draft, notApplicable: event.target.checked })} /> Неприменим в этом периоде (Н/П)</label>
          <label className="wide">Комментарий<textarea value={draft.comment} onChange={(event) => setDraft({ ...draft, comment: event.target.value })} placeholder="Пояснение к исходным данным" /></label>
          <div className="measure-actions wide"><button className="primary-button small-button" type="button" disabled={savingFact} onClick={() => void saveFact(criterion)}>{savingFact ? 'Сохранение…' : 'Сохранить и пересчитать'}</button><button className="logout small-button" type="button" disabled={savingFact} onClick={closeEditor}>Отмена</button></div>
          {factError && <p className="form-error wide">{factError}</p>}
        </div></td></tr>)
      }
    }
    return rows
  }

  useEffect(() => { api.references(token, 'departments').then(setDepartments).catch(() => setDepartments([])) }, [token])
  useEffect(() => { loadResults() }, [token])
  useEffect(() => { void runCompute() }, [])

  return <>
    <div className="title-row"><div><p className="eyebrow">ОЦЕНКА ЭФФЕКТИВНОСТИ</p><h1>Оценка эффективности ПК</h1></div><span className="period">{assessmentPeriodTitle(periodType, periodYear, periodIndex)} · {subjectName}</span></div>
    <section className="panel form-panel"><h2>Параметры оценки</h2><div className="entry-form assessment-params">
      <label>Период<select value={periodType} onChange={(event) => changePeriodType(event.target.value as AssessmentPeriodType)}>{assessmentPeriodOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select></label>
      <label>Год<select value={String(periodYear)} onChange={(event) => { setPeriodYear(Number(event.target.value)); resetSelectionState() }}>{yearOptions.map((year) => <option key={year} value={String(year)}>{year}</option>)}</select></label>
      <label>{periodType === 'quarter' ? 'Квартал' : periodType === 'half_year' ? 'Полугодие' : 'Подпериод'}<select value={String(periodIndex)} disabled={periodIndexes.length <= 1} onChange={(event) => { setPeriodIndex(Number(event.target.value)); resetSelectionState() }}>{periodIndexes.map((index) => <option key={index} value={String(index)}>{assessmentIndexLabel(periodType, index) || String(index)}</option>)}</select></label>
      <label>Объект оценки<select value={departmentId} onChange={(event) => { setDepartmentId(event.target.value); resetSelectionState() }}><option value="">Служба ППБиБДД (ПК III уровня)</option>{departments.filter((item) => item.is_active).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
      <div className="assessment-actions"><button className="primary-button" type="button" disabled={computing} onClick={() => void runCompute()}>{computing ? 'Выполняется расчёт…' : 'Рассчитать'}</button></div>
    </div></section>
    {error && <p className="form-error">{error}</p>}
    {computing ? <p className="empty">Выполняется расчёт…</p> : data ? <>
      <section className="kpis" aria-label="Сводка оценки">
        <div className="kpi"><span>Всего критериев</span><strong>{data.criteria.length}</strong><small>в справочнике оценки</small></div>
        <div className="kpi"><span>Учитывается</span><strong>{data.summary.applicable_count}</strong><small>входят в средний балл</small></div>
        <div className="kpi"><span>Неприменимо</span><strong>{data.summary.not_applicable_count}</strong><small>Н/П — вне расчёта</small></div>
        <div className="kpi"><span>Нет данных</span><strong>{data.summary.missing_input_count}</strong><small>нужны исходные данные</small></div>
        <div className="kpi"><span>Средний балл</span><strong>{formatScore(data.summary.average_score)}</strong><small>по учитываемым критериям</small></div>
        <div className="kpi"><span>Вердикт</span><span className="verdict-value"><AssessmentVerdictChip verdict={data.summary.verdict} /></span><small>порог — 1,00</small></div>
      </section>
      {selectionChanged && <p className="muted-note">Параметры изменены — нажмите «Рассчитать», чтобы обновить расчёт.</p>}
      {fixationNote && <p className="form-success">{fixationNote}</p>}
      <section className="panel">
        <div className="panel-header"><div><h2>Критерии оценки · {assessmentPeriodTitle(data.period_type, data.period_year, data.period_index)}</h2><p>Объект: {data.department_name ?? 'Служба ППБиБДД'} · баллы 0–2 и Н/П формируются автоматически из журнала и исходных данных.</p></div><div className="header-actions">{canEditFacts && <button className="primary-button" type="button" disabled={fixating} onClick={() => void fixateResult()}>{fixating ? 'Фиксация…' : 'Зафиксировать результат'}</button>}<span className="counter">{data.summary.applicable_count}</span></div></div>
        <table className="criteria-table"><thead><tr><th>Код</th><th>Критерий</th><th>Факт</th><th>Порог</th><th>Балл</th><th>Причина</th></tr></thead><tbody>{renderCriteriaRows(data.criteria, true)}</tbody></table>
      </section>
    </> : null}
    <section className="panel">
      <div className="panel-header"><div><h2>Зафиксированные результаты</h2><p>Нажмите на строку, чтобы посмотреть критерии на момент фиксации.</p></div><span className="counter">{sortedResults.length}</span></div>
      {resultsError ? <p className="form-error">{resultsError}</p> : sortedResults.length === 0 ? <p className="empty">Результаты ещё не зафиксированы.</p> : <table><thead><tr><th>Период</th><th>Объект оценки</th><th>Средний балл</th><th>Вердикт</th><th>Критерии</th><th>Создан</th></tr></thead><tbody>{sortedResults.map((item) => <tr key={item.id} className="clickable-row" onClick={() => void openDetail(item)}><td>{assessmentPeriodTitle(item.period_type, item.period_year, item.period_index)}</td><td>{item.department_name ?? 'Служба ППБиБДД'}</td><td>{formatScore(item.average_score)}</td><td><AssessmentVerdictChip verdict={item.verdict} /></td><td>{item.applicable_count} / {item.not_applicable_count} / {item.missing_input_count}<small className="cell-note">учитывается / Н/П / нет данных</small></td><td>{formatDateTime(item.created_at)}</td></tr>)}</tbody></table>}
    </section>
    {detail && <div className="modal-overlay" role="presentation" onClick={() => setDetail(null)}><section className="modal-card" role="dialog" aria-modal="true" aria-label="Зафиксированный результат оценки" onClick={(event) => event.stopPropagation()}>
      <div className="panel-header"><div><h2>{assessmentPeriodTitle(detail.period_type, detail.period_year, detail.period_index)} · {detail.department_name ?? 'Служба ППБиБДД'}</h2><p>Зафиксировано {formatDateTime(detail.created_at)}; обновлено {formatDateTime(detail.updated_at)}.</p></div><button className="logout" onClick={() => setDetail(null)}>Закрыть</button></div>
      <p className="muted-note">Средний балл <strong>{formatScore(detail.average_score)}</strong> · учитывается {detail.applicable_count} · Н/П {detail.not_applicable_count} · нет данных {detail.missing_input_count} · вердикт: <AssessmentVerdictChip verdict={detail.verdict} /></p>
      <table className="criteria-table"><thead><tr><th>Код</th><th>Критерий</th><th>Факт</th><th>Порог</th><th>Балл</th><th>Причина</th></tr></thead><tbody>{renderCriteriaRows(detail.criteria_payload, false)}</tbody></table>
    </section></div>}
  </>
}

function App() {
  const [token, setToken] = useState(() => sessionStorage.getItem('pk-control-token') ?? '')
  const [user, setUser] = useState<CurrentUser | null>(null)
  const [view, setView] = useState<View>('dashboard')
  const [deadlineInitialType, setDeadlineInitialType] = useState<string | null>(null)
  const [deadlineInitialStatus, setDeadlineInitialStatus] = useState<string | null>(null)
  const [deadlineVisitCount, setDeadlineVisitCount] = useState(0)
  const [sessionExpired, setSessionExpired] = useState(false)

  useEffect(() => {
    setUnauthorizedHandler(() => { sessionStorage.removeItem('pk-control-token'); setToken(''); setUser(null); setSessionExpired(true) })
    return () => { setUnauthorizedHandler(null) }
  }, [])
  useEffect(() => { if (token && !user) api.me(token).then(setUser).catch(() => { sessionStorage.removeItem('pk-control-token'); setToken('') }) }, [token, user])
  const displayName = useMemo(() => user?.display_name ?? 'Пользователь', [user])
  if (!token || !user) return <LoginScreen notice={sessionExpired ? 'Срок действия сессии истёк. Войдите снова.' : undefined} onLogin={(nextToken, nextUser) => { sessionStorage.setItem('pk-control-token', nextToken); setToken(nextToken); setUser(nextUser); setSessionExpired(false) }} />

  function openDeadlines(controlTypeId?: string, status?: string) { setDeadlineInitialType(controlTypeId ?? null); setDeadlineInitialStatus(status ?? null); setDeadlineVisitCount((count) => count + 1); setView('deadlines') }

  function selectNavigation(item: string) {
    if (item === 'Проверки') setView('inspections')
    else if (item === 'Нарушения') setView('violations')
    else if (item === 'Импорт') setView('imports')
    else if (item === 'Контроль сроков') openDeadlines()
    else if (item === 'Оценка эффективности ПК') setView('assessment')
    else if (item === 'Справочники') setView('references')
    else if (item === 'Пользователи и роли') setView('users')
    else setView('dashboard')
  }

  return <div className="app-shell"><aside className="sidebar" aria-label="Основная навигация"><div className="brand"><span className="brand-mark">ПК</span><div><strong>Производственный контроль</strong><small>Единая система учёта</small></div></div><nav>{navigation.map((item, index) => { const active = (item === 'Дашборд' && view === 'dashboard') || (item === 'Проверки' && view === 'inspections') || (item === 'Нарушения' && view === 'violations') || (item === 'Импорт' && view === 'imports') || (item === 'Контроль сроков' && view === 'deadlines') || (item === 'Оценка эффективности ПК' && view === 'assessment') || (item === 'Справочники' && view === 'references') || (item === 'Пользователи и роли' && view === 'users'); return <button className={active ? 'nav-item active' : 'nav-item'} key={item} type="button" onClick={() => selectNavigation(item)}><span className="nav-icon" aria-hidden="true">{index + 1}</span>{item}</button> })}</nav><div className="sidebar-footer"><span className="status-dot" /> Система работает<small>База данных: локальная</small><small>Версия 0.2.0</small></div></aside><main className="workspace"><header className="topbar"><label className="search"><span>⌕</span><input placeholder="Поиск будет доступен после создания реестра" disabled /></label><div className="user-panel"><div><strong>{displayName}</strong><small>{user.roles.join(', ')}</small></div><button className="logout" onClick={() => { sessionStorage.removeItem('pk-control-token'); setToken(''); setUser(null) }}>Выйти</button></div></header><section className="content">{view === 'inspections' ? <RegistryWorkspace key="inspections" token={token} kind="inspections" /> : view === 'violations' ? <RegistryWorkspace key="violations" token={token} kind="violations" /> : view === 'imports' ? <ImportWorkspace token={token} /> : view === 'deadlines' ? <DeadlineWorkspace key={`deadlines-${deadlineVisitCount}`} token={token} initialTypeId={deadlineInitialType} initialStatus={deadlineInitialStatus} /> : view === 'assessment' ? <AssessmentWorkspace token={token} user={user} /> : view === 'references' ? <ReferenceWorkspace token={token} user={user} /> : view === 'users' ? <UsersWorkspace token={token} /> : <Dashboard token={token} onOpenDeadlines={openDeadlines} />}</section></main></div>
}

export default App
