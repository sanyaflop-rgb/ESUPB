const navigation = [
  'Дашборд',
  'Проверки',
  'Нарушения',
  'Контроль сроков',
  'Аналитика',
  'Оценка эффективности ПК',
  'Отчёты и экспорт',
  'Справочники',
  'Пользователи и роли',
  'История изменений',
]

function App() {
  return (
    <div className="app-shell">
      <aside className="sidebar" aria-label="Основная навигация">
        <div className="brand">
          <span className="brand-mark">ПК</span>
          <div>
            <strong>Производственный контроль</strong>
            <small>Единая система учёта</small>
          </div>
        </div>
        <nav>
          {navigation.map((item, index) => (
            <button className={index === 0 ? 'nav-item active' : 'nav-item'} key={item} type="button">
              <span className="nav-icon" aria-hidden="true">{index + 1}</span>
              {item}
            </button>
          ))}
        </nav>
        <div className="sidebar-footer">
          <span className="status-dot" /> Система готовится к запуску
          <small>Версия 0.1.0</small>
        </div>
      </aside>

      <main className="workspace">
        <header className="topbar">
          <label className="search">
            <span>⌕</span>
            <input placeholder="Поиск по номеру, формулировке, объекту, подразделению" disabled />
          </label>
          <div className="user-panel">
            <span className="notification">0</span>
            <div><strong>Пользователь</strong><small>Роль будет назначена</small></div>
          </div>
        </header>

        <section className="content">
          <div className="title-row">
            <div><p className="eyebrow">PK CONTROL</p><h1>Дашборд</h1></div>
            <span className="period">Этап 1 · Каркас системы</span>
          </div>
          <div className="notice">
            <strong>Основа приложения создана.</strong>
            <span>Следующим этапом будут справочники, пользователи и модель проверок.</span>
          </div>
          <section className="kpis" aria-label="Ключевые показатели">
            {['Проверок', 'Нарушений', 'Устранено', 'Не устранено', 'Просрочено', 'Срок ≤ 7 дней'].map((label) => (
              <article className="kpi" key={label}><span>{label}</span><strong>—</strong><small>Данные появятся после импорта</small></article>
            ))}
          </section>
          <section className="placeholder-grid">
            <article><h2>Динамика выявления нарушений</h2><div className="chart-placeholder">Данные не загружены</div></article>
            <article><h2>Распределение по степеням тяжести</h2><div className="chart-placeholder donut">1–9</div></article>
            <article className="wide"><h2>Реестр нарушений</h2><div className="table-placeholder">Реестр будет доступен после создания схемы данных</div></article>
          </section>
        </section>
      </main>
    </div>
  )
}

export default App
