import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { api, ApiError, login as loginRequest, type CurrentUser, type DeadlineChangeItem, type DeadlineControlItem, type DeadlineControlResponse, type ImportPreviewRow, type InspectionItem, type MeasureInput, type MeasureItem, type ObjectItem, type PersonItem, type ReferenceItem, type UserItem, type ViolationItem, type ViolationTypeItem } from './api'

const blankMeasure = (): MeasureInput => ({ department_id: '', object_id: '', person_id: '', elimination_measure: '', due_date: '' })

const referenceTabs = [
  { resource: 'control-types', label: 'Виды контроля' },
  { resource: 'inspection-kinds', label: 'Виды проверок' },
  { resource: 'departments', label: 'Подразделения' },
  { resource: 'violation-groups', label: 'Группы нарушений' },
]

const navigation = ['Дашборд', 'Проверки', 'Нарушения', 'Импорт', 'Контроль сроков', 'Аналитика', 'Оценка эффективности ПК', 'Отчёты и экспорт', 'Справочники', 'Пользователи и роли', 'История изменений']

type View = 'dashboard' | 'inspections' | 'violations' | 'imports' | 'deadlines' | 'references' | 'users'

function LoginScreen({ onLogin }: { onLogin: (token: string, user: CurrentUser) => void }) {
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

  return <main className="login-page"><section className="login-card"><div className="login-mark">ПК</div><p className="eyebrow">PK CONTROL</p><h1>Производственный контроль</h1><p className="muted">Войдите, чтобы работать со справочниками и данными системы.</p><form onSubmit={submit}><label>Логин<input autoComplete="username" value={loginValue} onChange={(event) => setLoginValue(event.target.value)} required /></label><label>Пароль<input type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} required /></label>{error && <p className="form-error">{error}</p>}<button className="primary-button" disabled={loading}>{loading ? 'Выполняется вход…' : 'Войти'}</button></form><p className="login-hint">Первого администратора создаёт системный администратор после настройки сервера.</p></section></main>
}


function Dashboard() {
  return <><div className="title-row"><div><p className="eyebrow">PK CONTROL</p><h1>Дашборд</h1></div><span className="period">Этап 2 · Справочники и доступ</span></div><div className="notice"><strong>Справочники и роли готовы к настройке.</strong><span>Проверки и реестр нарушений будут добавлены следующим этапом.</span></div><section className="kpis" aria-label="Ключевые показатели">{['Проверок', 'Нарушений', 'Устранено', 'Не устранено', 'Просрочено', 'Срок ≤ 7 дней'].map((label) => <article className="kpi" key={label}><span>{label}</span><strong>—</strong><small>Данные появятся после миграции журнала</small></article>)}</section></>
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

    <section className="panel"><div className="panel-header"><div><h2>{inspectionMode ? 'Журнал проверок' : 'Реестр нарушений'}</h2><p>{inspectionMode ? 'Номер документа нормализуется и уникален в рамках вида контроля.' : 'Статус и просрочка вычисляются сервером по календарным дням.'}</p></div><span className="counter">{inspectionMode ? items.length : shownViolations.length}</span></div>{error ? <p className="form-error">{error}</p> : inspectionMode ? <table><thead><tr><th>Дата</th><th>Номер документа</th><th>Вид проверки</th><th>Структурное подразделение</th><th>Объект</th><th>Состояние</th></tr></thead><tbody>{(items as InspectionItem[]).map((item) => <tr className="clickable-row" key={item.id} onClick={() => selectInspection(item)}><td>{item.inspection_date}</td><td className="code">{item.document_number}</td><td>{inspectionKindName(item.inspection_kind_id)}</td><td>{item.department_id ? departmentName(item.department_id) : '—'}</td><td>{item.object_id ? objectName(item.object_id) : '—'}</td><td><span className="chip muted-chip">{item.state}</span></td></tr>)}</tbody></table> : <><div className="registry-toolbar"><div className="deadline-filters"><label>Формулировка<input placeholder="Содержит текст…" value={violationFilters.formulation} onChange={(event) => setViolationFilters({ ...violationFilters, formulation: event.target.value })} /></label><label>Акт-предписание<select value={violationFilters.act} onChange={(event) => setViolationFilters({ ...violationFilters, act: event.target.value })}><option value="">Все акты</option>{violationActOptions.map((value) => <option key={value} value={value}>{value}</option>)}</select></label><label>Ответственный<select value={violationFilters.person} onChange={(event) => setViolationFilters({ ...violationFilters, person: event.target.value })}><option value="">Все ответственные</option>{violationPersonOptions.map(([id, label]) => <option key={id} value={id}>{label}</option>)}</select></label><label>Тяжесть<select value={violationFilters.severity} onChange={(event) => setViolationFilters({ ...violationFilters, severity: event.target.value })}><option value="">Любая</option>{violationSeverityOptions.map((value) => <option key={value} value={String(value)}>{value}</option>)}</select></label><label>Срок с<input type="date" value={violationFilters.dueFrom} onChange={(event) => setViolationFilters({ ...violationFilters, dueFrom: event.target.value })} /></label><label>Срок по<input type="date" value={violationFilters.dueTo} onChange={(event) => setViolationFilters({ ...violationFilters, dueTo: event.target.value })} /></label><label>Статус<select value={violationFilters.status} onChange={(event) => setViolationFilters({ ...violationFilters, status: event.target.value })}><option value="">Все</option><option value="overdue">Просрочено</option><option value="not_eliminated">Не устранено</option><option value="eliminated">Устранено</option></select></label></div></div><table><thead><tr><th>Формулировка</th><th>Акт-предписание</th><th>Ответственные</th><th>Тяжесть</th><th>Срок</th><th>Статус</th></tr></thead><tbody>{shownViolations.map((item) => <tr className="clickable-row" key={item.id} onClick={() => openViolation(item)}><td>{item.formulation}</td><td className="code">{violationActNumber(item.inspection_id)}</td><td>{measurePersons(item).length > 0 ? measurePersons(item).join(', ') : '—'}</td><td>{item.severity}</td><td>{earliestDueDate(item) ?? '—'}</td><td><span className={item.status === 'overdue' ? 'chip danger' : item.status === 'eliminated' ? 'chip success' : 'chip muted-chip'}>{item.status === 'overdue' ? 'Просрочено' : item.status === 'eliminated' ? 'Устранено' : 'Не устранено'}</span></td></tr>)}</tbody></table></>}{!error && items.length === 0 && <p className="empty">Записей пока нет.</p>}{!error && !inspectionMode && items.length > 0 && shownViolations.length === 0 && <p className="empty">Нарушений по выбранным условиям нет.</p>}</section>
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

function DeadlineWorkspace({ token }: { token: string }) {
  const [data, setData] = useState<DeadlineControlResponse | null>(null)
  const [violations, setViolations] = useState<ViolationItem[]>([])
  const [inspections, setInspections] = useState<InspectionItem[]>([])
  const [departments, setDepartments] = useState<ReferenceItem[]>([])
  const [objects, setObjects] = useState<ObjectItem[]>([])
  const [persons, setPersons] = useState<PersonItem[]>([])
  const [selectedType, setSelectedType] = useState<string | null>(null)
  const [statusFilter, setStatusFilter] = useState('')
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
  const activeType = types.find((item) => item.control_type_id === selectedType) ?? types[0] ?? null
  const typeItems = activeType ? items.filter((item) => item.control_type_id === activeType.control_type_id) : []
  const upcoming = typeItems
    .filter((item) => item.status !== 'eliminated' && (item.status === 'overdue' || item.due_soon))
    .sort((a, b) => (a.due_date ?? '9999-12-31').localeCompare(b.due_date ?? '9999-12-31') || a.person_name.localeCompare(b.person_name, 'ru'))
  const registryItems = typeItems
    .filter((item) => statusFilter === '' || (statusFilter === 'eliminated' ? item.status === 'eliminated' : statusFilter === 'due_soon' ? item.due_soon : item.status === statusFilter))
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
      <div className="type-cards">{types.map((item) => <button className={activeType && item.control_type_id === activeType.control_type_id ? 'type-card active' : 'type-card'} key={item.control_type_id} type="button" onClick={() => { setSelectedType(item.control_type_id); resetColumnFilters() }}><span className="type-card-head"><strong>{controlTypeLabel(item.code, item.name)}</strong>{activeType && item.control_type_id === activeType.control_type_id && <span className="type-card-badge">Выбрано</span>}</span><span className="type-card-total">{item.total}</span><span className="type-card-caption">всего нарушений</span><span className="type-card-stats"><span className="stat overdue"><strong>{item.overdue}</strong> просрочено</span><span className="stat soon"><strong>{item.due_soon}</strong> срок ≤ 7 дней</span><span className="stat"><strong>{item.not_eliminated}</strong> не устранено</span></span></button>)}</div>
      {activeType && <section className="panel"><div className="panel-header"><div><h2>Ближайшие сроки · {controlTypeLabel(activeType.code, activeType.name)}</h2></div><span className="counter">{upcoming.length}</span></div>{upcoming.length === 0 ? <p className="empty">Просроченных и приближающихся сроков нет.</p> : <ul className="due-list">{upcoming.map((item) => <li key={item.measure_id}><button className="due-item" type="button" onClick={() => setSelectedViolationId(item.violation_id)}><span className="due-date">{item.due_date ? formatDueTitle(item.due_date) : 'Срок не задан'}</span><span className="due-main"><strong>{item.elimination_measure}</strong><small>{item.department_name} · {item.object_name} · Акт {item.document_number}</small></span><span className={item.status === 'overdue' ? 'due-badge overdue' : 'due-badge soon'}>{item.status === 'overdue' ? `Просрочено · ${item.days_overdue} ${pluralDays(item.days_overdue)}` : item.days_left === 0 ? 'Срок сегодня' : `Осталось ${item.days_left} ${pluralDays(item.days_left ?? 0)}`}</span></button></li>)}</ul>}</section>}
      {activeType && <section className="panel"><div className="panel-header"><div><h2>Реестр нарушений · {controlTypeLabel(activeType.code, activeType.name)}</h2></div><span className="counter">{registryItems.length}</span></div>
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

function App() {
  const [token, setToken] = useState(() => sessionStorage.getItem('pk-control-token') ?? '')
  const [user, setUser] = useState<CurrentUser | null>(null)
  const [view, setView] = useState<View>('dashboard')

  useEffect(() => { if (token && !user) api.me(token).then(setUser).catch(() => { sessionStorage.removeItem('pk-control-token'); setToken('') }) }, [token, user])
  const displayName = useMemo(() => user?.display_name ?? 'Пользователь', [user])
  if (!token || !user) return <LoginScreen onLogin={(nextToken, nextUser) => { sessionStorage.setItem('pk-control-token', nextToken); setToken(nextToken); setUser(nextUser) }} />

  function selectNavigation(item: string) {
    if (item === 'Проверки') setView('inspections')
    else if (item === 'Нарушения') setView('violations')
    else if (item === 'Импорт') setView('imports')
    else if (item === 'Контроль сроков') setView('deadlines')
    else if (item === 'Справочники') setView('references')
    else if (item === 'Пользователи и роли') setView('users')
    else setView('dashboard')
  }

  return <div className="app-shell"><aside className="sidebar" aria-label="Основная навигация"><div className="brand"><span className="brand-mark">ПК</span><div><strong>Производственный контроль</strong><small>Единая система учёта</small></div></div><nav>{navigation.map((item, index) => { const active = (item === 'Дашборд' && view === 'dashboard') || (item === 'Проверки' && view === 'inspections') || (item === 'Нарушения' && view === 'violations') || (item === 'Импорт' && view === 'imports') || (item === 'Контроль сроков' && view === 'deadlines') || (item === 'Справочники' && view === 'references') || (item === 'Пользователи и роли' && view === 'users'); return <button className={active ? 'nav-item active' : 'nav-item'} key={item} type="button" onClick={() => selectNavigation(item)}><span className="nav-icon" aria-hidden="true">{index + 1}</span>{item}</button> })}</nav><div className="sidebar-footer"><span className="status-dot" /> Система работает<small>База данных: локальная</small><small>Версия 0.2.0</small></div></aside><main className="workspace"><header className="topbar"><label className="search"><span>⌕</span><input placeholder="Поиск будет доступен после создания реестра" disabled /></label><div className="user-panel"><div><strong>{displayName}</strong><small>{user.roles.join(', ')}</small></div><button className="logout" onClick={() => { sessionStorage.removeItem('pk-control-token'); setToken(''); setUser(null) }}>Выйти</button></div></header><section className="content">{view === 'inspections' ? <RegistryWorkspace key="inspections" token={token} kind="inspections" /> : view === 'violations' ? <RegistryWorkspace key="violations" token={token} kind="violations" /> : view === 'imports' ? <ImportWorkspace token={token} /> : view === 'deadlines' ? <DeadlineWorkspace token={token} /> : view === 'references' ? <ReferenceWorkspace token={token} user={user} /> : view === 'users' ? <UsersWorkspace token={token} /> : <Dashboard />}</section></main></div>
}

export default App
