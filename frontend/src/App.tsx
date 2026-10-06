import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { api, ApiError, login as loginRequest, type CurrentUser, type InspectionItem, type MeasureInput, type ObjectItem, type PersonItem, type ReferenceItem, type UserItem, type ViolationItem, type ViolationTypeItem } from './api'

const blankMeasure = (): MeasureInput => ({ department_id: '', object_id: '', person_id: '', elimination_measure: '', due_date: '' })

const referenceTabs = [
  { resource: 'control-types', label: 'Виды контроля' },
  { resource: 'inspection-kinds', label: 'Виды проверок' },
  { resource: 'departments', label: 'Подразделения' },
  { resource: 'violation-groups', label: 'Группы нарушений' },
]

const navigation = ['Дашборд', 'Проверки', 'Нарушения', 'Контроль сроков', 'Аналитика', 'Оценка эффективности ПК', 'Отчёты и экспорт', 'Справочники', 'Пользователи и роли', 'История изменений']

type View = 'dashboard' | 'inspections' | 'violations' | 'references' | 'users'

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
  const inspectionMode = kind === 'inspections'

  const departmentName = (id: string) => departments.find((item) => item.id === id)?.name ?? '—'
  const objectName = (id: string) => objects.find((item) => item.id === id)?.name ?? '—'
  const inspectionKindName = (id: string) => inspectionKinds.find((item) => item.id === id)?.name ?? '—'
  const personLabel = (id: string) => { const person = persons.find((item) => item.id === id); return person ? `${person.full_name}${person.position ? ` · ${person.position}` : ''}` : '—' }
  const isLocationRequired = (kindId: string) => ['PLANNED', 'UNSCHEDULED'].includes(inspectionKinds.find((item) => item.id === kindId)?.code ?? '')
  const earliestDueDate = (v: ViolationItem) => { const dates = v.measures.map((m) => m.due_date).filter(Boolean) as string[]; return dates.length ? dates.sort()[0] : null }
  const measurePersons = (v: ViolationItem) => v.measures.map((m) => personLabel(m.person_id)).filter((n) => n !== '—')

  function load() { (inspectionMode ? api.inspections(token) : api.violations(token)).then((data) => setItems(data)).catch((reason: unknown) => setError(reason instanceof Error ? reason.message : 'Не удалось загрузить реестр')) }
  useEffect(() => { setError(''); setSelected(null); setSelectedViolation(null); setShowForm(false); load() }, [kind, token])
  useEffect(() => {
    api.references(token, 'departments').then(setDepartments).catch(() => setDepartments([]))
    api.objects(token).then(setObjects).catch(() => setObjects([]))
    api.persons(token).then(setPersons).catch(() => setPersons([]))
    if (inspectionMode) { api.references(token, 'control-types').then(setControlTypes); api.references(token, 'inspection-kinds').then(setInspectionKinds) } else { api.inspections(token).then(setAvailableInspections); api.violationTypes(token).then(setViolationTypes) }
  }, [inspectionMode, token])
  async function submit(event: FormEvent<HTMLFormElement>) { event.preventDefault(); setSaving(true); setError(''); try { const location = isLocationRequired(form.inspection_kind_id) ? { department_id: form.department_id, object_id: form.object_id } : {}; await api.createInspection(token, { control_type_id: form.control_type_id, inspection_kind_id: form.inspection_kind_id, document_number: form.document_number, inspection_date: form.inspection_date, ...location, comment: form.comment || undefined }); setShowForm(false); setForm({ ...form, department_id: '', object_id: '', document_number: '', comment: '' }); load() } catch (reason) { setError(reason instanceof Error ? reason.message : 'Не удалось создать проверку') } finally { setSaving(false) } }
  function selectInspection(item: InspectionItem) { setSelected(item); setEditForm({ inspection_kind_id: item.inspection_kind_id, department_id: item.department_id ?? '', object_id: item.object_id ?? '', document_number: item.document_number, inspection_date: item.inspection_date, comment: item.comment ?? '' }) }
  async function saveInspection(event: FormEvent<HTMLFormElement>) { event.preventDefault(); if (!selected) return; setSaving(true); setError(''); try { const location = isLocationRequired(editForm.inspection_kind_id) ? { department_id: editForm.department_id, object_id: editForm.object_id } : { department_id: null, object_id: null }; const updated = await api.updateInspection(token, selected.id, { inspection_kind_id: editForm.inspection_kind_id, document_number: editForm.document_number, inspection_date: editForm.inspection_date, ...location, comment: editForm.comment || undefined }); setSelected(updated); setItems((current) => (current as InspectionItem[]).map((item) => item.id === updated.id ? updated : item)) } catch (reason) { setError(reason instanceof Error ? reason.message : 'Не удалось сохранить изменения') } finally { setSaving(false) } }
  function updateMeasure(index: number, patch: Partial<MeasureInput>) { setViolationForm((current) => ({ ...current, measures: current.measures.map((item, itemIndex) => itemIndex === index ? { ...item, ...patch } : item) })) }
  async function submitViolation(event: FormEvent<HTMLFormElement>) { event.preventDefault(); setSaving(true); setError(''); try { await api.createViolation(token, violationForm.inspection_id, { violation_type_id: violationForm.violation_type_id, formulation: violationForm.formulation, violated_requirement: violationForm.violated_requirement, document_received_date: violationForm.document_received_date || undefined, measures: violationForm.measures.map((item) => ({ ...item, due_date: item.due_date || undefined })) }); setShowForm(false); setViolationForm({ inspection_id: '', violation_type_id: '', formulation: '', violated_requirement: '', document_received_date: '', measures: [blankMeasure()] }); load() } catch (reason) { setError(reason instanceof Error ? reason.message : 'Не удалось создать нарушение') } finally { setSaving(false) } }

  async function eliminateMeasure(measureId: string) { if (!selectedViolation) return; setSaving(true); setError(''); try { await api.eliminateMeasure(token, measureId, { elimination_date: new Date().toISOString().slice(0, 10) }); const fresh = await api.violations(token); setItems(fresh); const updated = (fresh as ViolationItem[]).find((v) => v.id === selectedViolation.id); if (updated) setSelectedViolation(updated) } catch (reason) { setError(reason instanceof Error ? reason.message : 'Не удалось зафиксировать устранение') } finally { setSaving(false) } }

  return <>
    <div className="title-row"><div><p className="eyebrow">РЕЕСТР</p><h1>{inspectionMode ? 'Проверки' : 'Нарушения'}</h1></div><button className="primary-button" onClick={() => setShowForm(!showForm)}>{showForm ? 'Закрыть форму' : inspectionMode ? 'Создать проверку' : 'Создать нарушение'}</button></div>

    {showForm && (inspectionMode ? <section className="panel form-panel"><h2>Новая проверка</h2><form className="entry-form" onSubmit={submit}><label>Вид контроля<select value={form.control_type_id} onChange={(event) => setForm({ ...form, control_type_id: event.target.value })} required><option value="">Выберите вид контроля</option>{controlTypes.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><label>Вид проверки<select value={form.inspection_kind_id} onChange={(event) => setForm({ ...form, inspection_kind_id: event.target.value, department_id: isLocationRequired(event.target.value) ? form.department_id : '', object_id: isLocationRequired(event.target.value) ? form.object_id : '' })} required><option value="">Выберите вид проверки</option>{inspectionKinds.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>{isLocationRequired(form.inspection_kind_id) && <><label>Структурное подразделение<select value={form.department_id} onChange={(event) => setForm({ ...form, department_id: event.target.value, object_id: '' })} required><option value="">Выберите подразделение</option>{departments.filter((item) => item.is_active).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><label>Объект<select value={form.object_id} onChange={(event) => setForm({ ...form, object_id: event.target.value })} required><option value="">Выберите объект</option>{objects.filter((item) => item.is_active && (!item.owner_department_id || item.owner_department_id === form.department_id)).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label></>}<label>Номер документа<input value={form.document_number} onChange={(event) => setForm({ ...form, document_number: event.target.value })} required /></label><label>Дата проверки<input type="date" value={form.inspection_date} onChange={(event) => setForm({ ...form, inspection_date: event.target.value })} required /></label><label className="wide">Комментарий<textarea value={form.comment} onChange={(event) => setForm({ ...form, comment: event.target.value })} /></label><button className="primary-button" disabled={saving}>{saving ? 'Сохранение…' : 'Создать проверку'}</button></form></section> : <section className="panel form-panel"><h2>Новое нарушение</h2><form className="entry-form" onSubmit={submitViolation}><label>Проверка<select value={violationForm.inspection_id} onChange={(event) => setViolationForm({ ...violationForm, inspection_id: event.target.value })} required><option value="">Выберите проверку</option>{availableInspections.map((item) => <option key={item.id} value={item.id}>{item.inspection_date} · {item.document_number}</option>)}</select></label><label>Тип нарушения<select value={violationForm.violation_type_id} onChange={(event) => setViolationForm({ ...violationForm, violation_type_id: event.target.value })} required><option value="">Выберите тип</option>{violationTypes.filter((item) => item.is_active).map((item) => <option key={item.id} value={item.id}>{item.code} · {item.name}</option>)}</select></label><label>Дата получения документа<input type="date" value={violationForm.document_received_date} onChange={(event) => setViolationForm({ ...violationForm, document_received_date: event.target.value })} /></label><label className="wide">Формулировка нарушения<textarea value={violationForm.formulation} onChange={(event) => setViolationForm({ ...violationForm, formulation: event.target.value })} required /></label><label className="wide">Нарушенное требование<textarea value={violationForm.violated_requirement} onChange={(event) => setViolationForm({ ...violationForm, violated_requirement: event.target.value })} required /></label><div className="wide measures-block"><div className="measures-header"><h3>Меры по устранению и ответственные</h3><button type="button" className="tab" onClick={() => setViolationForm({ ...violationForm, measures: [...violationForm.measures, blankMeasure()] })}>Добавить меру</button></div>{violationForm.measures.map((measure, index) => <section className="measure-form" key={index}><strong>Мера {index + 1}</strong><label>Подразделение<select value={measure.department_id} onChange={(event) => updateMeasure(index, { department_id: event.target.value })} required><option value="">Выберите подразделение</option>{departments.filter((item) => item.is_active).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><label>Объект<select value={measure.object_id} onChange={(event) => updateMeasure(index, { object_id: event.target.value })} required><option value="">Выберите объект</option>{objects.filter((item) => item.is_active && (!item.owner_department_id || item.owner_department_id === measure.department_id)).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><label>Ответственный<select value={measure.person_id} onChange={(event) => updateMeasure(index, { person_id: event.target.value })} required><option value="">Выберите сотрудника</option>{persons.filter((item) => item.is_active && (!item.department_id || item.department_id === measure.department_id)).map((item) => <option key={item.id} value={item.id}>{item.full_name}{item.position ? ` · ${item.position}` : ''}</option>)}</select></label><label>Срок устранения<input type="date" value={measure.due_date ?? ''} onChange={(event) => updateMeasure(index, { due_date: event.target.value })} /></label><label className="wide">Мероприятие по устранению<textarea value={measure.elimination_measure} onChange={(event) => updateMeasure(index, { elimination_measure: event.target.value })} required /></label>{violationForm.measures.length > 1 && <button type="button" className="logout" onClick={() => setViolationForm({ ...violationForm, measures: violationForm.measures.filter((_, itemIndex) => itemIndex !== index) })}>Удалить меру</button>}</section>)}</div><button className="primary-button" disabled={saving}>{saving ? 'Сохранение…' : 'Создать нарушение'}</button></form></section>)}

    {selected && inspectionMode && <section className="panel form-panel"><div className="panel-header"><div><h2>Карточка проверки</h2><p>Состояние: {selected.state}</p></div><button className="logout" onClick={() => setSelected(null)}>Закрыть</button></div><form className="entry-form" onSubmit={saveInspection}><label>Вид проверки<select value={editForm.inspection_kind_id} onChange={(event) => setEditForm({ ...editForm, inspection_kind_id: event.target.value, department_id: isLocationRequired(event.target.value) ? editForm.department_id : '', object_id: isLocationRequired(event.target.value) ? editForm.object_id : '' })} required>{inspectionKinds.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>{isLocationRequired(editForm.inspection_kind_id) && <><label>Структурное подразделение<select value={editForm.department_id} onChange={(event) => setEditForm({ ...editForm, department_id: event.target.value, object_id: '' })} required><option value="">Выберите подразделение</option>{departments.filter((item) => item.is_active).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><label>Объект<select value={editForm.object_id} onChange={(event) => setEditForm({ ...editForm, object_id: event.target.value })} required><option value="">Выберите объект</option>{objects.filter((item) => item.is_active && (!item.owner_department_id || item.owner_department_id === editForm.department_id)).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label></>}<label>Номер документа<input value={editForm.document_number} onChange={(event) => setEditForm({ ...editForm, document_number: event.target.value })} required /></label><label>Дата проверки<input type="date" value={editForm.inspection_date} onChange={(event) => setEditForm({ ...editForm, inspection_date: event.target.value })} required /></label><label className="wide">Комментарий<textarea value={editForm.comment} onChange={(event) => setEditForm({ ...editForm, comment: event.target.value })} /></label><button className="primary-button" disabled={saving}>{saving ? 'Сохранение…' : 'Сохранить изменения'}</button></form></section>}

    {selectedViolation && !inspectionMode && <section className="panel form-panel"><div className="panel-header"><div><h2>Карточка нарушения</h2><p>Статус: <span className={selectedViolation.status === 'overdue' ? 'chip danger' : selectedViolation.status === 'eliminated' ? 'chip success' : 'chip muted-chip'}>{selectedViolation.status === 'overdue' ? 'Просрочено' : selectedViolation.status === 'eliminated' ? 'Устранено' : 'Не устранено'}</span></p></div><button className="logout" onClick={() => setSelectedViolation(null)}>Закрыть</button></div>
      <div className="violation-details"><div className="detail-row"><span className="detail-label">Формулировка</span><span>{selectedViolation.formulation}</span></div><div className="detail-row"><span className="detail-label">Нарушенное требование</span><span>{selectedViolation.violated_requirement}</span></div><div className="detail-row"><span className="detail-label">Тяжесть</span><span>{selectedViolation.severity}</span></div>{selectedViolation.document_received_date && <div className="detail-row"><span className="detail-label">Дата получения документа</span><span>{selectedViolation.document_received_date}</span></div>}</div>
      <div className="scope-block"><h3>Меры по устранению ({selectedViolation.measures.length})</h3><ul className="measure-list">{selectedViolation.measures.map((measure) => <li key={measure.id} className="measure-card"><div className="measure-card-header"><strong>{personLabel(measure.person_id)}</strong><span className={measure.status === 'overdue' ? 'chip danger' : measure.status === 'eliminated' ? 'chip success' : 'chip muted-chip'}>{measure.status === 'overdue' ? 'Просрочено' : measure.status === 'eliminated' ? 'Устранено' : 'Не устранено'}</span></div><div className="measure-card-body"><span><strong>Подразделение:</strong> {departmentName(measure.department_id)}</span><span><strong>Объект:</strong> {objectName(measure.object_id)}</span><span><strong>Мероприятие:</strong> {measure.elimination_measure}</span><span><strong>Срок:</strong> {measure.due_date ?? '—'}</span>{measure.elimination_date && <span><strong>Дата устранения:</strong> {measure.elimination_date}</span>}</div>{measure.status !== 'eliminated' && <button className="primary-button" style={{marginTop: '8px', fontSize: '12px', padding: '6px 10px'}} disabled={saving} onClick={() => eliminateMeasure(measure.id)}>{saving ? 'Сохранение…' : 'Зафиксировать устранение'}</button>}</li>)}</ul></div></section>}

    <section className="panel"><div className="panel-header"><div><h2>{inspectionMode ? 'Журнал проверок' : 'Реестр нарушений'}</h2><p>{inspectionMode ? 'Номер документа нормализуется и уникален в рамках вида контроля.' : 'Статус и просрочка вычисляются сервером по календарным дням.'}</p></div><span className="counter">{items.length}</span></div>{error ? <p className="form-error">{error}</p> : inspectionMode ? <table><thead><tr><th>Дата</th><th>Номер документа</th><th>Вид проверки</th><th>Структурное подразделение</th><th>Объект</th><th>Состояние</th></tr></thead><tbody>{(items as InspectionItem[]).map((item) => <tr className="clickable-row" key={item.id} onClick={() => selectInspection(item)}><td>{item.inspection_date}</td><td className="code">{item.document_number}</td><td>{inspectionKindName(item.inspection_kind_id)}</td><td>{item.department_id ? departmentName(item.department_id) : '—'}</td><td>{item.object_id ? objectName(item.object_id) : '—'}</td><td><span className="chip muted-chip">{item.state}</span></td></tr>)}</tbody></table> : <table><thead><tr><th>Формулировка</th><th>Ответственные</th><th>Тяжесть</th><th>Срок</th><th>Статус</th></tr></thead><tbody>{(items as ViolationItem[]).map((item) => <tr className="clickable-row" key={item.id} onClick={() => setSelectedViolation(item)}><td>{item.formulation}</td><td>{measurePersons(item).length > 0 ? measurePersons(item).join(', ') : '—'}</td><td>{item.severity}</td><td>{earliestDueDate(item) ?? '—'}</td><td><span className={item.status === 'overdue' ? 'chip danger' : item.status === 'eliminated' ? 'chip success' : 'chip muted-chip'}>{item.status === 'overdue' ? 'Просрочено' : item.status === 'eliminated' ? 'Устранено' : 'Не устранено'}</span></td></tr>)}</tbody></table>}{!error && items.length === 0 && <p className="empty">Записей пока нет.</p>}</section>
  </>
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
    else if (item === 'Справочники') setView('references')
    else if (item === 'Пользователи и роли') setView('users')
    else setView('dashboard')
  }

  return <div className="app-shell"><aside className="sidebar" aria-label="Основная навигация"><div className="brand"><span className="brand-mark">ПК</span><div><strong>Производственный контроль</strong><small>Единая система учёта</small></div></div><nav>{navigation.map((item, index) => { const active = (item === 'Дашборд' && view === 'dashboard') || (item === 'Проверки' && view === 'inspections') || (item === 'Нарушения' && view === 'violations') || (item === 'Справочники' && view === 'references') || (item === 'Пользователи и роли' && view === 'users'); return <button className={active ? 'nav-item active' : 'nav-item'} key={item} type="button" onClick={() => selectNavigation(item)}><span className="nav-icon" aria-hidden="true">{index + 1}</span>{item}</button> })}</nav><div className="sidebar-footer"><span className="status-dot" /> Система работает<small>База данных: локальная</small><small>Версия 0.2.0</small></div></aside><main className="workspace"><header className="topbar"><label className="search"><span>⌕</span><input placeholder="Поиск будет доступен после создания реестра" disabled /></label><div className="user-panel"><div><strong>{displayName}</strong><small>{user.roles.join(', ')}</small></div><button className="logout" onClick={() => { sessionStorage.removeItem('pk-control-token'); setToken(''); setUser(null) }}>Выйти</button></div></header><section className="content">{view === 'inspections' ? <RegistryWorkspace key="inspections" token={token} kind="inspections" /> : view === 'violations' ? <RegistryWorkspace key="violations" token={token} kind="violations" /> : view === 'references' ? <ReferenceWorkspace token={token} user={user} /> : view === 'users' ? <UsersWorkspace token={token} /> : <Dashboard />}</section></main></div>
}

export default App
