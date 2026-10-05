import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { api, ApiError, login as loginRequest, type CurrentUser, type InspectionItem, type ReferenceItem, type ScopeItem, type UserItem, type ViolationItem, type ViolationTypeItem } from './api'

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
  const [error, setError] = useState('')
  const [showForm, setShowForm] = useState(false)
  const [saving, setSaving] = useState(false)
  const [form, setForm] = useState({ control_type_id: '', inspection_kind_id: '', document_number: '', inspection_date: new Date().toISOString().slice(0, 10), comment: '' })
  const [selected, setSelected] = useState<InspectionItem | null>(null)
  const [editForm, setEditForm] = useState({ inspection_kind_id: '', document_number: '', inspection_date: '', comment: '' })
  const [violationTypes, setViolationTypes] = useState<ViolationTypeItem[]>([])
  const [availableInspections, setAvailableInspections] = useState<InspectionItem[]>([])
  const [scopes, setScopes] = useState<ScopeItem[]>([])
  const [violationForm, setViolationForm] = useState({ inspection_id: '', inspection_scope_id: '', violation_type_id: '', formulation: '', violated_requirement: '', due_date: '', due_date_basis: '', due_date_source_text: '', document_received_date: '' })
  const inspectionMode = kind === 'inspections'
  function load() { (inspectionMode ? api.inspections(token) : api.violations(token)).then((data) => setItems(data)).catch((reason: unknown) => setError(reason instanceof Error ? reason.message : 'Не удалось загрузить реестр')) }
  useEffect(() => { setError(''); load() }, [kind, token])
  useEffect(() => { if (inspectionMode) { api.references(token, 'control-types').then(setControlTypes); api.references(token, 'inspection-kinds').then(setInspectionKinds) } else { api.inspections(token).then(setAvailableInspections); api.violationTypes(token).then(setViolationTypes) } }, [inspectionMode, token])
  useEffect(() => { if (violationForm.inspection_id) api.scopes(token, violationForm.inspection_id).then(setScopes).catch(() => setScopes([])); else setScopes([]) }, [token, violationForm.inspection_id])
  async function submit(event: FormEvent<HTMLFormElement>) { event.preventDefault(); setSaving(true); setError(''); try { await api.createInspection(token, { ...form, comment: form.comment || undefined }); setShowForm(false); setForm({ ...form, document_number: '', comment: '' }); load() } catch (reason) { setError(reason instanceof Error ? reason.message : 'Не удалось создать проверку') } finally { setSaving(false) } }
  function selectInspection(item: InspectionItem) { setSelected(item); setEditForm({ inspection_kind_id: item.inspection_kind_id, document_number: item.document_number, inspection_date: item.inspection_date, comment: item.comment ?? '' }) }
  async function saveInspection(event: FormEvent<HTMLFormElement>) { event.preventDefault(); if (!selected) return; setSaving(true); setError(''); try { const updated = await api.updateInspection(token, selected.id, { ...editForm, comment: editForm.comment || undefined }); setSelected(updated); setItems((current) => (current as InspectionItem[]).map((item) => item.id === updated.id ? updated : item)) } catch (reason) { setError(reason instanceof Error ? reason.message : 'Не удалось сохранить изменения') } finally { setSaving(false) } }
  async function submitViolation(event: FormEvent<HTMLFormElement>) { event.preventDefault(); setSaving(true); setError(''); try { await api.createViolation(token, violationForm.inspection_id, { inspection_scope_id: violationForm.inspection_scope_id, violation_type_id: violationForm.violation_type_id, formulation: violationForm.formulation, violated_requirement: violationForm.violated_requirement, due_date: violationForm.due_date || undefined, due_date_basis: violationForm.due_date_basis || undefined, due_date_source_text: violationForm.due_date_source_text || undefined, document_received_date: violationForm.document_received_date || undefined }); setShowForm(false); load() } catch (reason) { setError(reason instanceof Error ? reason.message : 'Не удалось создать нарушение') } finally { setSaving(false) } }
  return <><div className="title-row"><div><p className="eyebrow">РЕЕСТР</p><h1>{inspectionMode ? 'Проверки' : 'Нарушения'}</h1></div><button className="primary-button" onClick={() => setShowForm(!showForm)}>{showForm ? 'Закрыть форму' : inspectionMode ? 'Создать проверку' : 'Создать нарушение'}</button></div>{showForm && (inspectionMode ? <section className="panel form-panel"><h2>Новая проверка</h2><form className="entry-form" onSubmit={submit}><label>Вид контроля<select value={form.control_type_id} onChange={(event) => setForm({ ...form, control_type_id: event.target.value })} required><option value="">Выберите вид контроля</option>{controlTypes.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><label>Вид проверки<select value={form.inspection_kind_id} onChange={(event) => setForm({ ...form, inspection_kind_id: event.target.value })} required><option value="">Выберите вид проверки</option>{inspectionKinds.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><label>Номер документа<input value={form.document_number} onChange={(event) => setForm({ ...form, document_number: event.target.value })} required /></label><label>Дата проверки<input type="date" value={form.inspection_date} onChange={(event) => setForm({ ...form, inspection_date: event.target.value })} required /></label><label className="wide">Комментарий<textarea value={form.comment} onChange={(event) => setForm({ ...form, comment: event.target.value })} /></label><button className="primary-button" disabled={saving}>{saving ? 'Сохранение…' : 'Создать проверку'}</button></form></section> : <section className="panel form-panel"><h2>Новое нарушение</h2><form className="entry-form" onSubmit={submitViolation}><label>Проверка<select value={violationForm.inspection_id} onChange={(event) => setViolationForm({ ...violationForm, inspection_id: event.target.value, inspection_scope_id: '' })} required><option value="">Выберите проверку</option>{availableInspections.map((item) => <option key={item.id} value={item.id}>{item.inspection_date} · {item.document_number}</option>)}</select></label><label>Область проверки<select value={violationForm.inspection_scope_id} onChange={(event) => setViolationForm({ ...violationForm, inspection_scope_id: event.target.value })} required disabled={!violationForm.inspection_id}><option value="">{scopes.length ? 'Выберите область' : 'Нет областей проверки'}</option>{scopes.map((item) => <option key={item.id} value={item.id}>{item.comment || `Подразделение ${item.department_id.slice(0, 8)}`}</option>)}</select></label><label>Тип нарушения<select value={violationForm.violation_type_id} onChange={(event) => setViolationForm({ ...violationForm, violation_type_id: event.target.value })} required><option value="">Выберите тип</option>{violationTypes.map((item) => <option key={item.id} value={item.id}>{item.code} · {item.name}</option>)}</select></label><label>Срок устранения<input type="date" value={violationForm.due_date} onChange={(event) => setViolationForm({ ...violationForm, due_date: event.target.value })} /></label><label className="wide">Формулировка<textarea value={violationForm.formulation} onChange={(event) => setViolationForm({ ...violationForm, formulation: event.target.value })} required /></label><label className="wide">Нарушенное требование<textarea value={violationForm.violated_requirement} onChange={(event) => setViolationForm({ ...violationForm, violated_requirement: event.target.value })} required /></label><label>Основание срока<input value={violationForm.due_date_basis} onChange={(event) => setViolationForm({ ...violationForm, due_date_basis: event.target.value })} /></label><label>Дата получения документа<input type="date" value={violationForm.document_received_date} onChange={(event) => setViolationForm({ ...violationForm, document_received_date: event.target.value })} /></label><label className="wide">Источник срока<textarea value={violationForm.due_date_source_text} onChange={(event) => setViolationForm({ ...violationForm, due_date_source_text: event.target.value })} /></label><button className="primary-button" disabled={saving}>{saving ? 'Сохранение…' : 'Создать нарушение'}</button></form></section>)}{selected && <section className="panel form-panel"><div className="panel-header"><div><h2>Карточка проверки</h2><p>Состояние: {selected.state}</p></div><button className="logout" onClick={() => setSelected(null)}>Закрыть</button></div><form className="entry-form" onSubmit={saveInspection}><label>Вид проверки<select value={editForm.inspection_kind_id} onChange={(event) => setEditForm({ ...editForm, inspection_kind_id: event.target.value })} required>{inspectionKinds.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><label>Номер документа<input value={editForm.document_number} onChange={(event) => setEditForm({ ...editForm, document_number: event.target.value })} required /></label><label>Дата проверки<input type="date" value={editForm.inspection_date} onChange={(event) => setEditForm({ ...editForm, inspection_date: event.target.value })} required /></label><label className="wide">Комментарий<textarea value={editForm.comment} onChange={(event) => setEditForm({ ...editForm, comment: event.target.value })} /></label><button className="primary-button" disabled={saving}>{saving ? 'Сохранение…' : 'Сохранить изменения'}</button></form></section>}<section className="panel"><div className="panel-header"><div><h2>{inspectionMode ? 'Журнал проверок' : 'Реестр нарушений'}</h2><p>{inspectionMode ? 'Номер документа нормализуется и уникален в рамках вида контроля.' : 'Статус и просрочка вычисляются сервером по календарным дням.'}</p></div><span className="counter">{items.length}</span></div>{error ? <p className="form-error">{error}</p> : inspectionMode ? <table><thead><tr><th>Дата</th><th>Номер документа</th><th>Состояние</th></tr></thead><tbody>{(items as InspectionItem[]).map((item) => <tr className="clickable-row" key={item.id} onClick={() => selectInspection(item)}><td>{item.inspection_date}</td><td className="code">{item.document_number}</td><td><span className="chip muted-chip">{item.state}</span></td></tr>)}</tbody></table> : <table><thead><tr><th>Формулировка</th><th>Тяжесть</th><th>Срок</th><th>Статус</th></tr></thead><tbody>{(items as ViolationItem[]).map((item) => <tr key={item.id}><td>{item.formulation}</td><td>{item.severity}</td><td>{item.due_date ?? '—'}</td><td><span className={item.status === 'overdue' ? 'chip danger' : item.status === 'eliminated' ? 'chip success' : 'chip muted-chip'}>{item.status === 'overdue' ? 'Просрочено' : item.status === 'eliminated' ? 'Устранено' : 'Не устранено'}</span></td></tr>)}</tbody></table>}{!error && items.length === 0 && <p className="empty">Записей пока нет.</p>}</section></>
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

  return <div className="app-shell"><aside className="sidebar" aria-label="Основная навигация"><div className="brand"><span className="brand-mark">ПК</span><div><strong>Производственный контроль</strong><small>Единая система учёта</small></div></div><nav>{navigation.map((item, index) => { const active = (item === 'Дашборд' && view === 'dashboard') || (item === 'Проверки' && view === 'inspections') || (item === 'Нарушения' && view === 'violations') || (item === 'Справочники' && view === 'references') || (item === 'Пользователи и роли' && view === 'users'); return <button className={active ? 'nav-item active' : 'nav-item'} key={item} type="button" onClick={() => selectNavigation(item)}><span className="nav-icon" aria-hidden="true">{index + 1}</span>{item}</button> })}</nav><div className="sidebar-footer"><span className="status-dot" /> Система работает<small>База данных: локальная</small><small>Версия 0.2.0</small></div></aside><main className="workspace"><header className="topbar"><label className="search"><span>⌕</span><input placeholder="Поиск будет доступен после создания реестра" disabled /></label><div className="user-panel"><div><strong>{displayName}</strong><small>{user.roles.join(', ')}</small></div><button className="logout" onClick={() => { sessionStorage.removeItem('pk-control-token'); setToken(''); setUser(null) }}>Выйти</button></div></header><section className="content">{view === 'inspections' ? <RegistryWorkspace token={token} kind="inspections" /> : view === 'violations' ? <RegistryWorkspace token={token} kind="violations" /> : view === 'references' ? <ReferenceWorkspace token={token} user={user} /> : view === 'users' ? <UsersWorkspace token={token} /> : <Dashboard />}</section></main></div>
}

export default App
