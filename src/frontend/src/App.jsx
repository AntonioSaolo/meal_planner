import { Fragment, useEffect, useMemo, useState } from 'react';

const API_BASE_URL = (() => {
  const configuredUrl = import.meta.env.VITE_API_BASE_URL;
  if (configuredUrl) {
    return configuredUrl.replace(/\/$/, '');
  }

  if (typeof window !== 'undefined') {
    const { protocol, hostname } = window.location;
    return `${protocol}//${hostname}:8000`;
  }

  return 'http://localhost:8000';
})();
const LOCAL_STORAGE_KEY = 'meal-planner-local-meals';
const TOKEN_STORAGE_KEY = 'meal_planner_token';
const DAY_NAMES = ['Lunedì', 'Martedì', 'Mercoledì', 'Giovedì', 'Venerdì', 'Sabato', 'Domenica'];

function startOfWeek(date) {
  const copy = new Date(date);
  const day = (copy.getDay() + 6) % 7;
  copy.setHours(0, 0, 0, 0);
  copy.setDate(copy.getDate() - day);
  return copy;
}

function addDays(date, days) {
  const copy = new Date(date);
  copy.setDate(copy.getDate() + days);
  return copy;
}

function formatDateKey(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function formatDateLong(date) {
  return new Intl.DateTimeFormat('it-IT', {
    weekday: 'short',
    day: '2-digit',
    month: '2-digit',
  }).format(date);
}

function formatWeekLabel(startDate) {
  const endDate = addDays(startDate, 6);
  const startMonth = startDate.toLocaleDateString('it-IT', { month: 'long' });
  const endMonth = endDate.toLocaleDateString('it-IT', { month: 'long' });
  const startYear = startDate.getFullYear();
  const endYear = endDate.getFullYear();

  if (startMonth === endMonth && startYear === endYear) {
    return `${startDate.getDate()} - ${endDate.getDate()} ${startMonth} ${startYear}`;
  }

  return `${startDate.getDate()} ${startMonth} ${startYear} - ${endDate.getDate()} ${endMonth} ${endYear}`;
}

function formatLocalDate(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function formatLocalDateTime(date, time = '12:00') {
  return `${formatLocalDate(date)}T${time}:00`;
}

function getMealTime(meal) {
  if (!meal?.datetime) return '12:00';
  const dateTime = new Date(meal.datetime);
  if (Number.isNaN(dateTime.getTime())) {
    return '12:00';
  }
  const hour = String(dateTime.getHours()).padStart(2, '0');
  const minute = String(dateTime.getMinutes()).padStart(2, '0');
  return `${hour}:${minute}`;
}

function formatMealEntries(meal) {
  const antonio = (meal?.antonio || '').trim();
  const annalisa = (meal?.annalisa || '').trim();

  if (antonio || annalisa) {
    const entries = [];
    if (antonio) entries.push(`Antonio\n${antonio}`);
    if (annalisa) entries.push(`Annalisa\n${annalisa}`);
    return entries.join('\n\n');
  }

  const legacyDescription = (meal?.description || '').trim();
  return legacyDescription || 'Pasto';
}

function mergeRemoteMeals(localMeals, remoteMeals) {
  const merged = [...localMeals];
  const keys = new Set(localMeals.map((meal) => `${meal.datetime}_${meal.type_id}_${meal.id || 'local'}`));

  remoteMeals.forEach((meal) => {
    const key = `${meal.datetime}_${meal.type_id}_${meal.id || 'remote'}`;
    if (!keys.has(key)) {
      merged.push(meal);
      keys.add(key);
    }
  });

  return merged;
}

function sortTypes(types) {
  return [...types].sort((a, b) => {
    const left = Number(a?.idx ?? Number.MAX_SAFE_INTEGER);
    const right = Number(b?.idx ?? Number.MAX_SAFE_INTEGER);
    return left - right || String(a?.name || '').localeCompare(String(b?.name || ''));
  });
}

function isValidUuid(value) {
  return typeof value === 'string' && /^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$/.test(value);
}

function generateId() {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }

  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (character) => {
    const random = Math.random() * 16 | 0;
    const value = character === 'x' ? random : (random & 0x3) | 0x8;
    return value.toString(16);
  });
}

function normalizeLocalMeal(meal) {
  if (!meal || typeof meal !== 'object') return meal;
  if (meal.id && !isValidUuid(meal.id)) {
    return { ...meal, id: generateId() };
  }
  return meal;
}

export default function App() {
  const [weekStart, setWeekStart] = useState(startOfWeek(new Date()));
  const [types, setTypes] = useState([]);
  const [meals, setMeals] = useState(() => {
    try {
      const saved = JSON.parse(localStorage.getItem(LOCAL_STORAGE_KEY) || '[]');
      return Array.isArray(saved) ? saved.map(normalizeLocalMeal) : [];
    } catch (error) {
      return [];
    }
  });
  const [modalState, setModalState] = useState({ open: false, meal: null, date: null, type: null, mode: 'edit' });
  const [form, setForm] = useState({ id: '', type_id: '', date: '', time: '12:00', antonio: '', annalisa: '' });
  const [isAuthenticated, setIsAuthenticated] = useState(Boolean(localStorage.getItem(TOKEN_STORAGE_KEY)));
  const [loginForm, setLoginForm] = useState({
    username: '',
    password: '',
  });
  const [loginError, setLoginError] = useState('');
  const [isLoggingIn, setIsLoggingIn] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [copyModal, setCopyModal] = useState({ open: false, type: 'week', sourceFrom: '', sourceTo: '', destFrom: '', destTo: '' });

  useEffect(() => {
    if (isAuthenticated) {
      loadPlannerData();
    }
  }, [weekStart, isAuthenticated]);

  useEffect(() => {
    localStorage.setItem(LOCAL_STORAGE_KEY, JSON.stringify(meals));
  }, [meals]);

  async function loginWithCredentials(event) {
    event.preventDefault();
    setIsLoggingIn(true);
    setLoginError('');

    try {
      const response = await fetch(`${API_BASE_URL}/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          username: loginForm.username,
          password: loginForm.password,
        }),
      });

      const data = await response.json();
      if (!response.ok || !data.access_token) {
        throw new Error(data.msg || 'Credenziali non valide');
      }

      localStorage.setItem(TOKEN_STORAGE_KEY, data.access_token);
      setIsAuthenticated(true);
      await loadPlannerData(data.access_token);
    } catch (error) {
      setLoginError(error.message || 'Login non riuscito');
    } finally {
      setIsLoggingIn(false);
    }
  }

  async function loadPlannerData(token = localStorage.getItem(TOKEN_STORAGE_KEY)) {
    if (!token) {
      setTypes([]);
      return;
    }

    await fetchTypes(token);
    await loadMealsForWeek(weekStart, token);
  }

  async function fetchTypes(token = localStorage.getItem(TOKEN_STORAGE_KEY)) {
    try {
      const headers = token ? { Authorization: `Bearer ${token}` } : {};
      const response = await fetch(`${API_BASE_URL}/types`, { headers });
      if (!response.ok) throw new Error('Cannot load types');
      const data = await response.json();
      setTypes(sortTypes(data));
    } catch (error) {
      setTypes([]);
    }
  }

  async function loadMealsForWeek(startDate, token = localStorage.getItem(TOKEN_STORAGE_KEY)) {
    const from = formatLocalDateTime(startDate, '00:00');
    const to = formatLocalDateTime(addDays(startDate, 6), '23:59');

    try {
      const headers = token ? { Authorization: `Bearer ${token}` } : {};
      const response = await fetch(`${API_BASE_URL}/meals?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}`, { headers });
      if (!response.ok) throw new Error('Cannot load meals');
      const remoteMeals = await response.json();
      const localMeals = JSON.parse(localStorage.getItem(LOCAL_STORAGE_KEY) || '[]');
      setMeals(mergeRemoteMeals(Array.isArray(localMeals) ? localMeals : [], Array.isArray(remoteMeals) ? remoteMeals : []));
    } catch (error) {
      const localMeals = JSON.parse(localStorage.getItem(LOCAL_STORAGE_KEY) || '[]');
      setMeals(Array.isArray(localMeals) ? localMeals : []);
    }
  }

  const weekDays = useMemo(
    () => Array.from({ length: 7 }, (_, index) => addDays(weekStart, index)),
    [weekStart],
  );

  const mealsByDayAndType = useMemo(() => {
    const map = {};
    meals.forEach((meal) => {
      const dateKey = (meal.datetime || '').slice(0, 10);
      if (!map[dateKey]) map[dateKey] = {};
      map[dateKey][meal.type_id] = meal;
    });
    return map;
  }, [meals]);

  function openModal(date, type, meal) {
    const nextMode = meal ? 'view' : 'edit';
    const chosenTypeId = type?.id || meal?.type_id || '';
    setModalState({ open: true, meal, date, type, mode: nextMode });
    setForm({
      id: meal?.id || '',
      type_id: chosenTypeId,
      date: formatLocalDate(date),
      time: getMealTime(meal),
      antonio: meal?.antonio || '',
      annalisa: meal?.annalisa || '',
    });
  }

  function openEditMode() {
    setModalState((current) => ({ ...current, mode: 'edit' }));
  }

  function closeModal() {
    setModalState({ open: false, meal: null, date: null, type: null, mode: 'edit' });
    setForm({ id: '', type_id: '', date: '', time: '12:00', antonio: '', annalisa: '' });
  }

  function persistMealList(nextMeals) {
    const normalized = Array.isArray(nextMeals) ? nextMeals.map(normalizeLocalMeal) : [];
    setMeals(normalized);
    localStorage.setItem(LOCAL_STORAGE_KEY, JSON.stringify(normalized));
  }

  async function handleSaveMeal(event) {
    event.preventDefault();

    const antonio = form.antonio.trim();
    const annalisa = form.annalisa.trim();
    const nextMeal = {
      id: isValidUuid(form.id) ? form.id : generateId(),
      datetime: formatLocalDateTime(new Date(`${form.date}T00:00:00`), form.time),
      type_id: form.type_id,
      antonio,
      annalisa,
      description: [antonio, annalisa].filter(Boolean).join('\n\n'),
    };

    const localMeals = JSON.parse(localStorage.getItem(LOCAL_STORAGE_KEY) || '[]');
    const existingIndex = (Array.isArray(localMeals) ? localMeals : []).findIndex(
      (meal) => meal.id === nextMeal.id || (meal.type_id === nextMeal.type_id && meal.datetime.slice(0, 10) === nextMeal.datetime.slice(0, 10)),
    );

    let updatedMeals = Array.isArray(localMeals) ? [...localMeals] : [];
    if (existingIndex >= 0) {
      updatedMeals[existingIndex] = { ...updatedMeals[existingIndex], ...nextMeal };
    } else {
      updatedMeals.push(nextMeal);
    }

    persistMealList(updatedMeals);

    try {
      const token = localStorage.getItem(TOKEN_STORAGE_KEY);
      if (!token) {
        throw new Error('Effettua prima il login');
      }

      const response = await fetch(`${API_BASE_URL}/meal`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({
          id: nextMeal.id,
          datetime: nextMeal.datetime,
          type_id: nextMeal.type_id,
          description: nextMeal.description,
          antonio: nextMeal.antonio,
          annalisa: nextMeal.annalisa,
        }),
      });

      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload.msg || 'Impossibile salvare il pasto');
      }
    } catch (error) {
      console.warn('Salvataggio locale non sincronizzato con il backend:', error);
    }

    closeModal();
    loadMealsForWeek(weekStart);
  }

  async function handleDeleteMeal() {
    if (!modalState.meal?.id) return;

    const mealId = modalState.meal.id;
    const filteredMeals = meals.filter((meal) => meal.id !== mealId);
    persistMealList(filteredMeals);

    try {
      const token = localStorage.getItem(TOKEN_STORAGE_KEY);
      if (token && isValidUuid(mealId)) {
        const response = await fetch(`${API_BASE_URL}/meal?id=${mealId}`, {
          method: 'DELETE',
          headers: { Authorization: `Bearer ${token}` },
        });

        if (!response.ok) {
          throw new Error('Delete failed');
        }
      }
    } catch (error) {
      console.warn('Local-only delete used because backend is unavailable or protected.', error);
    }

    closeModal();
    loadMealsForWeek(weekStart);
  }

  function handleLogout() {
    localStorage.removeItem(TOKEN_STORAGE_KEY);
    setIsAuthenticated(false);
    setTypes([]);
    setMeals([]);
    setLoginForm({ username: '', password: '' });
    setShowPassword(false);
  }

  function openCopyModal(type, presetDate = null) {
    if (type === 'week') {
      const sourceFrom = weekStart;
      const sourceTo = addDays(weekStart, 6);
      const destFrom = addDays(weekStart, 7);
      const destTo = addDays(weekStart, 13);
      setCopyModal({
        open: true,
        type,
        sourceFrom: formatLocalDate(sourceFrom),
        sourceTo: formatLocalDate(sourceTo),
        destFrom: formatLocalDate(destFrom),
        destTo: formatLocalDate(destTo),
      });
      return;
    }

    const sourceDate = presetDate ? new Date(presetDate) : weekStart;
    const destDate = addDays(sourceDate, 1);
    setCopyModal({
      open: true,
      type,
      sourceFrom: formatLocalDate(sourceDate),
      sourceTo: formatLocalDate(sourceDate),
      destFrom: formatLocalDate(destDate),
      destTo: formatLocalDate(destDate),
    });
  }

  function updateCopyField(name, value) {
    setCopyModal((current) => {
      const next = { ...current, [name]: value };

      if (current.type === 'week') {
        if (name === 'sourceFrom') {
          const sourceDate = new Date(`${value}T00:00:00`);
          next.sourceTo = formatLocalDate(addDays(sourceDate, 6));
        }
        if (name === 'destFrom') {
          const destDate = new Date(`${value}T00:00:00`);
          next.destTo = formatLocalDate(addDays(destDate, 6));
        }
      } else if (name === 'sourceFrom') {
        next.sourceTo = value;
      } else if (name === 'destFrom') {
        next.destTo = value;
      }

      return next;
    });
  }

  async function handleCopyMeals() {
    const token = localStorage.getItem(TOKEN_STORAGE_KEY);
    if (!token || !copyModal.sourceFrom || !copyModal.destFrom) {
      return;
    }

    const params = new URLSearchParams({
      source_from: `${copyModal.sourceFrom}T00:00:00`,
      source_to: `${copyModal.sourceTo}T23:59:59`,
      dest_from: `${copyModal.destFrom}T00:00:00`,
      dest_to: `${copyModal.destTo}T23:59:59`,
    });

    try {
      const response = await fetch(`${API_BASE_URL}/copy_meals?${params.toString()}`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      });

      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload.msg || 'Copia non riuscita');
      }

      const sourceDate = new Date(`${copyModal.destFrom}T00:00:00`);
      setWeekStart(startOfWeek(sourceDate));
      await loadPlannerData(token);
      setCopyModal({ open: false, type: 'week', sourceFrom: '', sourceTo: '', destFrom: '', destTo: '' });
    } catch (error) {
      console.warn('Copia non riuscita:', error);
    }
  }

  const currentWeekLabel = formatWeekLabel(weekStart);

  function renderCopyIcon() {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true" className="icon-svg">
        <path d="M9 9.5A2.5 2.5 0 0 1 11.5 7H18a3 3 0 0 1 3 3v6.5A2.5 2.5 0 0 1 18.5 19H11.5A2.5 2.5 0 0 1 9 16.5v-7Zm-4.5 1A2.5 2.5 0 0 1 7 8h6.5A2.5 2.5 0 0 1 16 10.5v7A2.5 2.5 0 0 1 13.5 20H7a2.5 2.5 0 0 1-2.5-2.5v-7Z" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    );
  }

  function renderPrintIcon() {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true" className="icon-svg">
        <path d="M7 9V4.5A1.5 1.5 0 0 1 8.5 3h7A1.5 1.5 0 0 1 17 4.5V9M6 15H4.5A1.5 1.5 0 0 1 3 13.5v-3A1.5 1.5 0 0 1 4.5 9h15A1.5 1.5 0 0 1 21 10.5v3a1.5 1.5 0 0 1-1.5 1.5H18M7 15h10v5H7v-5Zm2 0v3h6v-3" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    );
  }

  if (!isAuthenticated) {
    return (
      <div className="login-shell">
        <form className="login-card" onSubmit={loginWithCredentials}>
          <h1>Meal Planner</h1>
          <label>
            Username
            <input
              type="text"
              value={loginForm.username}
              onChange={(event) => setLoginForm((current) => ({ ...current, username: event.target.value }))}
              autoComplete="username"
              required
            />
          </label>

          <label>
            Password
            <div className="password-field">
              <input
                type={showPassword ? 'text' : 'password'}
                value={loginForm.password}
                onChange={(event) => setLoginForm((current) => ({ ...current, password: event.target.value }))}
                autoComplete="current-password"
                required
              />
              <button
                type="button"
                className="password-toggle"
                onClick={() => setShowPassword((current) => !current)}
                aria-label={showPassword ? 'Nascondi password' : 'Mostra password'}
              >
                {showPassword ? (
                  <svg viewBox="0 0 24 24" aria-hidden="true" className="eye-icon">
                    <path d="M2.5 12s3.5-6 9.5-6 9.5 6 9.5 6-3.5 6-9.5 6-9.5-6-9.5-6Zm9.5 3.2a3.2 3.2 0 1 0 0-6.4 3.2 3.2 0 0 0 0 6.4Z" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>
                ) : (
                  <svg viewBox="0 0 24 24" aria-hidden="true" className="eye-icon">
                    <path d="M2.5 12S6 6 12 6s9.5 6 9.5 6-3.5 6-9.5 6S2.5 12 2.5 12Zm9.5 3.2A3.2 3.2 0 1 0 12 8.8a3.2 3.2 0 0 0 0 6.4Zm0 0 7.6 7.6M4.4 4.4l15.2 15.2" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>
                )}
              </button>
            </div>
          </label>

          {loginError && <div className="login-error">{loginError}</div>}

          <button type="submit" className="primary-button login-button" disabled={isLoggingIn}>
            {isLoggingIn ? 'Accesso...' : 'Accedi'}
          </button>
        </form>
      </div>
    );
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="week-navigation" aria-label="Navigazione settimana">
          <button type="button" className="nav-button" onClick={() => setWeekStart((current) => addDays(current, -7))} aria-label="Settimana precedente">
            ←
          </button>
          <button type="button" className="today-button" onClick={() => setWeekStart(startOfWeek(new Date()))}>
            Today
          </button>
          <div className="week-label">Settimana {currentWeekLabel}</div>
          <button type="button" className="nav-button" onClick={() => setWeekStart((current) => addDays(current, 7))} aria-label="Settimana successiva">
            →
          </button>
        </div>

        <div className="header-actions">
          <button type="button" className="secondary-button copy-button subtle-action" onClick={() => openCopyModal('week')}>
            <span className="button-icon">{renderCopyIcon()}</span>
            <span>Copia settimana</span>
          </button>
          <button type="button" className="secondary-button copy-button subtle-action print-button" onClick={() => window.print()}>
            <span className="button-icon">{renderPrintIcon()}</span>
            <span>Stampa</span>
          </button>
          <button type="button" className="logout-button" onClick={handleLogout}>
            Logout
          </button>
        </div>
      </header>

      <main className="planner-panel">
        <div className="planner-grid" role="grid" aria-label="Piano settimanale dei pasti">
          <div className="grid-corner">Tipo</div>

          {weekDays.map((day) => (
            <div key={formatDateKey(day)} className="day-header" role="columnheader">
              <div className="day-header-main">
                <span>{DAY_NAMES[(day.getDay() + 6) % 7]}</span>
                <small>{day.getDate()}</small>
              </div>
              <button
                type="button"
                className="day-copy-button"
                onClick={() => openCopyModal('day', day)}
                aria-label={`Copia il giorno ${formatDateKey(day)}`}
              >
                {renderCopyIcon()}
              </button>
            </div>
          ))}

          {types.map((type) => (
            <Fragment key={type.id}>
              <div className="type-label">{type.name}</div>

              {weekDays.map((day) => {
                const dateKey = formatDateKey(day);
                const meal = mealsByDayAndType[dateKey]?.[type.id];

                return (
                  <button
                    key={`${type.id}-${dateKey}`}
                    type="button"
                    className={`meal-cell ${meal ? 'filled' : 'empty'}`}
                    onClick={() => {
                      const currentMeal = mealsByDayAndType[dateKey]?.[type.id] || meal;
                      openModal(day, type, currentMeal);
                    }}
                  >
                    {meal ? (
                      <span className="meal-text">{formatMealEntries(meal)}</span>
                    ) : (
                      <span className="plus-sign">+</span>
                    )}
                  </button>
                );
              })}
            </Fragment>
          ))}
        </div>
      </main>

      {copyModal.open && (
        <div className="modal-overlay" onClick={() => setCopyModal((current) => ({ ...current, open: false }))}>
          <div className="copy-modal" onClick={(event) => event.stopPropagation()}>
            <div className="modal-header">
              <h3>{copyModal.type === 'week' ? 'Copia settimana' : 'Copia giorno'}</h3>
              <button type="button" className="close-button" onClick={() => setCopyModal((current) => ({ ...current, open: false }))}>
                ×
              </button>
            </div>

            <p className="copy-help">
              {copyModal.type === 'week'
                ? 'Copia tutti i pasti della settimana di origine nella settimana di destinazione.'
                : 'Copia tutti i pasti del giorno di origine nel giorno di destinazione.'}
            </p>

            <div className="copy-range-box">
              <div className="range-row">
                <span className="range-label">Origine</span>
                <strong>{copyModal.sourceFrom || '—'} → {copyModal.sourceTo || '—'}</strong>
              </div>
              <div className="range-row">
                <span className="range-label">Destinazione</span>
                <strong>{copyModal.destFrom || '—'} → {copyModal.destTo || '—'}</strong>
              </div>
            </div>

            {copyModal.type === 'week' ? (
              <>
                <label>
                  Inizio settimana origine
                  <input type="date" value={copyModal.sourceFrom} onChange={(event) => updateCopyField('sourceFrom', event.target.value)} />
                </label>
                <label>
                  Inizio settimana destinazione
                  <input type="date" value={copyModal.destFrom} onChange={(event) => updateCopyField('destFrom', event.target.value)} />
                </label>
              </>
            ) : (
              <>
                <label>
                  Giorno origine
                  <input type="date" value={copyModal.sourceFrom} onChange={(event) => updateCopyField('sourceFrom', event.target.value)} />
                </label>
                <label>
                  Giorno destinazione
                  <input type="date" value={copyModal.destFrom} onChange={(event) => updateCopyField('destFrom', event.target.value)} />
                </label>
              </>
            )}

            <div className="modal-actions compact-actions">
              <button type="button" className="secondary-button" onClick={() => setCopyModal((current) => ({ ...current, open: false }))}>
                Annulla
              </button>
              <button type="submit" className="primary-button" onClick={handleCopyMeals}>
                Copia
              </button>
            </div>
          </div>
        </div>
      )}

      {modalState.open && modalState.mode === 'view' && (
        <div className="modal-overlay" onClick={closeModal}>
          <div className="summary-card" onClick={(event) => event.stopPropagation()}>
            <div className="summary-header">
              <button type="button" className="close-button" onClick={closeModal}>
                ×
              </button>
            </div>

            <div className="summary-meta">
              {modalState.date ? `${String(modalState.date.getDate()).padStart(2, '0')}/${String(modalState.date.getMonth() + 1).padStart(2, '0')}/${modalState.date.getFullYear()}` : ''} · {modalState.type?.name || 'Pasto'} · {modalState.meal ? getMealTime(modalState.meal) : '12:00'}
            </div>

            <div className="summary-text">
              {modalState.meal ? formatMealEntries(modalState.meal) : 'Nessuna descrizione'}
            </div>

            <div className="summary-actions">
              {modalState.meal && (
                <button type="button" className="danger-button compact-button" onClick={handleDeleteMeal}>
                  Cancella
                </button>
              )}
              <button type="button" className="secondary-button compact-button" onClick={openEditMode}>
                Modifica
              </button>
            </div>
          </div>
        </div>
      )}

      {modalState.open && modalState.mode !== 'view' && (
        <div className="modal-overlay" onClick={closeModal}>
          <div className="modal-card" onClick={(event) => event.stopPropagation()}>
            <div className="modal-header">
              <h3>{modalState.meal ? 'Modifica pasto' : 'Aggiungi pasto'}</h3>
              <button type="button" className="close-button" onClick={closeModal}>
                ×
              </button>
            </div>

            <div className="entry-meta">
              {modalState.date ? `${String(modalState.date.getDate()).padStart(2, '0')}/${String(modalState.date.getMonth() + 1).padStart(2, '0')}/${modalState.date.getFullYear()}` : ''} · {modalState.type?.name || 'Pasto'}
            </div>

            <form onSubmit={handleSaveMeal} className="meal-form">
              <label>
                Antonio
                <textarea
                  rows="3"
                  value={form.antonio}
                  onChange={(event) => setForm((current) => ({ ...current, antonio: event.target.value }))}
                  placeholder="Es. Pasta al pomodoro..."
                />
              </label>

              <label>
                Annalisa
                <textarea
                  rows="3"
                  value={form.annalisa}
                  onChange={(event) => setForm((current) => ({ ...current, annalisa: event.target.value }))}
                  placeholder="Es. Insalata e pollo..."
                />
              </label>

              <div className="modal-actions compact-actions">
                <button type="button" className="secondary-button" onClick={closeModal}>
                  Annulla
                </button>
                <button type="submit" className="primary-button">
                  {modalState.meal ? 'Salva modifiche' : 'Aggiungi'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
