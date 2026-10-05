import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { api, ApiError, login as loginRequest, type CurrentUser, type ReferenceItem, type UserItem } from './api'

const referenceTabs = [
  { resource: 'control-types', label: 'Виды контроля' },
  { resource: 'inspection-kinds', label: 'Виды проверок' },
  { resource: 'departments', label: 'Подразделения' },
  { resource: 'violation-groups', label: 'Группы нарушений' },
]

const navigation = ['Дашборд', 'Проверки', 'Нарушения', 'Контроль сроков', 'Аналитика', 'Оценка эффективности ПК', 'Отчёты и экспорт', 'Справочники', 'Пользователи и роли', 'История изменений']

type View = 'dashboard' | 'references' | 'users'

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
    if (item === 'Справочники') setView('references')
    else if (item === 'Пользователи и роли') setView('users')
    else setView('dashboard')
  }

  return <div className="app-shell"><aside className="sidebar" aria-label="Основная навигация"><div className="brand"><span className="brand-mark">ПК</span><div><strong>Производственный контроль</strong><small>Единая система учёта</small></div></div><nav>{navigation.map((item, index) => { const active = (item === 'Дашборд' && view === 'dashboard') || (item === 'Справочники' && view === 'references') || (item === 'Пользователи и роли' && view === 'users'); return <button className={active ? 'nav-item active' : 'nav-item'} key={item} type="button" onClick={() => selectNavigation(item)}><span className="nav-icon" aria-hidden="true">{index + 1}</span>{item}</button> })}</nav><div className="sidebar-footer"><span className="status-dot" /> Система работает<small>База данных: локальная</small><small>Версия 0.2.0</small></div></aside><main className="workspace"><header className="topbar"><label className="search"><span>⌕</span><input placeholder="Поиск будет доступен после создания реестра" disabled /></label><div className="user-panel"><div><strong>{displayName}</strong><small>{user.roles.join(', ')}</small></div><button className="logout" onClick={() => { sessionStorage.removeItem('pk-control-token'); setToken(''); setUser(null) }}>Выйти</button></div></header><section className="content">{view === 'references' ? <ReferenceWorkspace token={token} user={user} /> : view === 'users' ? <UsersWorkspace token={token} /> : <Dashboard />}</section></main></div>
}

export default App
