import { useState, useEffect, useMemo, useCallback } from 'react';
import Gantt from './Gantt';
import * as api from './api';

const BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';
import { compareReactors } from './ganttUtils';
import './App.css';

const FLOORS     = ['6층', '5층', '7층'];
const SCOPES     = ['배양기', 'Ambr250', 'Ambr15'];
const SCALES_ALL = ['2L', '5L', '10L', '50L', '200L', 'Wave'];

const SCOPE_SCALES = {
  '배양기':  ['2L', '5L', '10L', '50L', '200L', 'Wave'],
  'Ambr250': ['Ambr250'],
  'Ambr15':  ['Ambr15'],
};
const SEARCH_STAGES = ['N', 'N-1', 'N-2', 'N-3', 'N-4'];
const METHOD_OPTIONS = {
  '2L':     ['Fed-batch', 'EFB', 'iEFB', 'N1', 'EN1'],
  '5L':     ['Fed-batch', 'EFB', 'iEFB', 'N1', 'EN1'],
  '10L':    ['Fed-batch', 'EFB', 'iEFB', 'N1', 'EN1'],
  '50L':    ['Fed-batch', 'EFB', 'iEFB', 'N1', 'EN1'],
  '200L':   ['Fed-batch', 'EFB', 'iEFB', 'N1', 'EN1'],
  'Wave':   ['Fed-batch'],
  'Ambr250':['EFB', 'iEFB', 'EN1'],
  'Ambr15': ['Fed-batch'],
};

export default function App() {
  const [schedule,  setSchedule]  = useState(null);
  const [eqMap,     setEqMap]     = useState({});
  const [bookings,  setBookings]  = useState([]);
  const [lock,      setLock]      = useState(null);
  const _urlUser = new URLSearchParams(window.location.search).get('user') || '';
  const [user,      setUser]      = useState('');
  const [userInput, setUserInput] = useState(_urlUser);
  const [scope,     setScope]     = useState('배양기');
  const [floors,    setFloors]    = useState(['6층']);
  const [scales,    setScales]    = useState(['2L', '5L', '10L', '50L', '200L', 'Wave']);
  const [diff,      setDiff]      = useState({ added: [], removed: [] });
  const [showDiff,  setShowDiff]  = useState(false);
  const [applying,   setApplying]  = useState(false);
  const [applyUser,  setApplyUser] = useState('admin');
  const [applyPwd,   setApplyPwd]  = useState('');
  const [applyMsg,   setApplyMsg]  = useState(null);
  const [busy,      setBusy]      = useState(false);
  const [toast,     setToast]     = useState(null);

  // ── Quick Reserve / Vacancy Search ───────────────────────────
  const [showSearch,      setShowSearch]      = useState(false);
  const [srchProject,     setSrchProject]     = useState('');
  const [srchStart,       setSrchStart]       = useState(new Date().toISOString().slice(0, 10));
  const [srchDays,        setSrchDays]        = useState(15);
  const [srchScale,       setSrchScale]       = useState('2L');
  const [srchStage,       setSrchStage]       = useState('N');
  const [srchMethod,      setSrchMethod]      = useState('Fed-batch');
  const [srchQty,         setSrchQty]         = useState(1);
  const [searchResults,   setSearchResults]   = useState(null);
  const [selectedReactors,setSelectedReactors]= useState([]);

  useEffect(() => {
    const savedUser = sessionStorage.getItem('sandbox_user');
    api.getEqMap().then(m => setEqMap(m)).catch(() => {});
    api.getSchedule().then(async d => {
      setSchedule(d); setLock(d.lock);
      if (savedUser && d.lock && d.lock.user === savedUser) {
        // Restore sandbox session after refresh
        setUser(savedUser);
        setUserInput(savedUser);
        try {
          const sb = await api.getSandboxState();
          setBookings(sb.bookings);
          const df = await api.getDiff();
          setDiff(df);
        } catch { setBookings(d.bookings); }
      } else {
        setBookings(d.bookings);
        if (savedUser) sessionStorage.removeItem('sandbox_user');
      }
    }).catch(() => showToast('백엔드에 연결할 수 없습니다 — uvicorn이 실행 중인지 확인하세요', 'error'));
  }, []);

  // Release lock when tab is closed or refreshed
  useEffect(() => {
    const release = () => {
      const u = sessionStorage.getItem('sandbox_user');
      if (!u) return;
      const blob = new Blob([JSON.stringify({ user: u })], { type: 'application/json' });
      navigator.sendBeacon(`${BASE}/api/sandbox/unlock`, blob);
      sessionStorage.removeItem('sandbox_user');
    };
    window.addEventListener('beforeunload', release);
    return () => window.removeEventListener('beforeunload', release);
  }, []);

  function showToast(msg, type = 'info') {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 4000);
  }

  const visibleReactors = useMemo(() => {
    if (!schedule) return [];
    let rs = schedule.reactors;
    if (scope === '배양기') {
      rs = rs.filter(r => !r.id.startsWith('Ambr'));
      rs = rs.filter(r => floors.some(f => r.id.startsWith(f)));
      rs = rs.filter(r => scales.includes(r.scale));
    } else if (scope === 'Ambr250') {
      rs = rs.filter(r => r.id.startsWith('Ambr250'));
    } else {
      rs = rs.filter(r => r.id.startsWith('Ambr15') && !r.id.includes('-V'));
    }
    // Ambr: preserve API order (already in INVENTORY_CONFIGS order from backend)
    // Bioreactor: sort by floor/scale/number
    if (scope === '배양기') return [...rs].sort((a, b) => compareReactors(a.id, b.id));
    return rs;
  }, [schedule, scope, floors, scales]);

  // ── Lock ──────────────────────────────────────────────────────
  async function enterSandbox() {
    if (!userInput.trim()) return showToast('이름을 입력하세요', 'error');
    setBusy(true);
    try {
      const d = await api.claimLock(userInput.trim());
      setUser(userInput.trim());
      sessionStorage.setItem('sandbox_user', userInput.trim());
      setLock(d.lock);
      setBookings(d.bookings);
      showToast('샌드박스 활성화 — 드래그로 일정 변경', 'success');
    } catch (e) {
      showToast(e.status === 423 ? (e.detail?.message ?? '샌드박스 사용 중') : '입장 실패', 'error');
    } finally { setBusy(false); }
  }

  async function exitSandbox() {
    setBusy(true);
    const lockUser = lock?.user || user;
    try { await api.releaseLock(lockUser); } catch (_) {}
    sessionStorage.removeItem('sandbox_user');
    const d = await api.getSchedule();
    setSchedule(d); setBookings(d.bookings); setLock(null);
    setUser(''); setUserInput(''); setDiff({ added: [], removed: [] }); setApplyMsg(null);
    setBusy(false);
    showToast('샌드박스 종료 — 변경사항 폐기');
  }

  // ── Sandbox mutations ─────────────────────────────────────────
  const handleMove = useCallback(async (bookingId, newReactorId, newStart, newEnd) => {
    try {
      const d = await api.moveBooking(user, bookingId, newReactorId, newStart, newEnd);
      setBookings(d.bookings);
      const df = await api.getDiff(); setDiff(df);
    } catch (e) { showToast(String(e.detail ?? '이동 실패'), 'error'); }
  }, [user]);

  const handleMoveMultiple = useCallback(async (moves) => {
    try {
      let d;
      for (const m of moves) {
        d = await api.moveBooking(user, m.bookingId, m.newReactorId, m.newStart, m.newEnd);
      }
      if (d) setBookings(d.bookings);
      const df = await api.getDiff(); setDiff(df);
    } catch (e) { showToast(String(e.detail ?? '이동 실패'), 'error'); }
  }, [user]);

  const handleDelete = useCallback(async (bookingId) => {
    try {
      const d = await api.deleteBooking(user, bookingId);
      setBookings(d.bookings);
      const df = await api.getDiff(); setDiff(df);
    } catch (e) { showToast(String(e.detail ?? '삭제 실패'), 'error'); }
  }, [user]);

  // Reset method when scale changes
  useEffect(() => {
    const methods = METHOD_OPTIONS[srchScale] || ['Fed-batch'];
    if (!methods.includes(srchMethod)) setSrchMethod(methods[0]);
  }, [srchScale]);

  // Ambr runs are always N-stage — auto-lock stage when Ambr scale is selected
  useEffect(() => {
    if (srchScale === 'Ambr250' || srchScale === 'Ambr15') setSrchStage('N');
  }, [srchScale]);

  // Reset srchScale to the first valid option when the scope tab changes
  useEffect(() => {
    const validScales = SCOPE_SCALES[scope] ?? [];
    if (!validScales.includes(srchScale)) setSrchScale(validScales[0]);
  }, [scope]);

  async function handleSearch() {
    setBusy(true);
    try {
      const d = await api.findAvailable(srchScale, srchStart, srchDays, srchStage, srchMethod);
      setSearchResults(d);
      setSelectedReactors(d.available.slice(0, srchQty));
    } catch (e) {
      showToast('검색 실패: ' + String(e.detail ?? e), 'error');
    } finally { setBusy(false); }
  }

  async function handleAddBooking() {
    if (!inSandbox || !srchProject.trim() || selectedReactors.length === 0) return;
    setBusy(true);
    try {
      const d = await api.addBooking(
        user, selectedReactors, srchProject.trim(),
        srchStage, srchMethod, searchResults.start, searchResults.end
      );
      setBookings(d.bookings);
      const df = await api.getDiff(); setDiff(df);
      setSearchResults(null); setSelectedReactors([]);
      showToast(`${d.n_added}개 예약이 샌드박스에 추가되었습니다`, 'success');
    } catch (e) {
      showToast(String(e.detail?.message ?? e.detail ?? '추가 실패'), 'error');
    } finally { setBusy(false); }
  }

  // ── Refresh ───────────────────────────────────────────────────
  async function handleRefresh() {
    setBusy(true);
    try {
      const d = await api.getSchedule();
      setSchedule(d); setBookings(d.bookings); setLock(d.lock);
      showToast('일정이 새로고침되었습니다', 'success');
    } catch { showToast('새로고침 실패', 'error'); }
    finally { setBusy(false); }
  }

  // ── Apply ─────────────────────────────────────────────────────
  async function handleApply() {
    if (!applyUser.trim() || !applyPwd.trim()) return;
    setBusy(true); setApplyMsg(null);
    try {
      const d = await api.applyChanges(user, applyUser, applyPwd);
      setApplyMsg({ type: 'success', text: `적용 완료: ${d.n_added}건 추가, ${d.n_removed}건 삭제` });
      setApplyPwd(''); setApplyUser('admin');
      sessionStorage.removeItem('sandbox_user');
      const fresh = await api.getSchedule();
      setSchedule(fresh); setBookings(fresh.bookings);
      setLock(null); setUser(''); setDiff({ added: [], removed: [] });
    } catch (e) {
      if (e.status === 409)      setApplyMsg({ type: 'conflict', text: '충돌 발생 — 적용 취소:', conflicts: e.detail?.conflicts });
      else if (e.status === 401) setApplyMsg({ type: 'error', text: '인증 실패' });
      else                       setApplyMsg({ type: 'error', text: String(e.detail ?? '적용 실패') });
    } finally { setBusy(false); }
  }

  const inSandbox       = !!user && !!lock && lock.user === user;
  const lockOtherUser   = lock && (!user || lock.user !== user);
  const nChanges        = diff.added.length + diff.removed.length;

  // Poll lock status while in sandbox — warn when expiry is close
  // Must be after inSandbox is defined
  useEffect(() => {
    if (!inSandbox) return;
    const id = setInterval(async () => {
      try {
        const sb = await api.getSandboxState();
        if (!sb.lock) return;
        const secs = sb.lock.expires_in_seconds ?? 0;
        if (secs <= 300 && secs > 0) showToast(`샌드박스 잠금이 ${Math.ceil(secs / 60)}분 후 만료됩니다`, 'error');
      } catch { /* backend unreachable — ignore */ }
    }, 60_000);
    return () => clearInterval(id);
  }, [inSandbox]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="app">
      {toast && <div className={`toast toast-${toast.type}`}>{toast.msg}</div>}

      {/* ── Top bar ── */}
      <div className="topbar">
        <span className="topbar-title">🧫 배양기 운용 시뮬레이션</span>

        <div className="selector-group">
          {SCOPES.map(s => (
            <button key={s} className={`scope-btn ${scope === s ? 'active' : ''}`} onClick={() => setScope(s)}>{s}</button>
          ))}
        </div>

        {scope === '배양기' && (
          <>
            <div className="selector-group">
              {FLOORS.map(f => (
                <button key={f}
                  className={`scope-btn ${floors.includes(f) ? 'active' : ''}`}
                  onClick={() => setFloors(p => p.includes(f) ? p.filter(x => x !== f) : [...p, f])}
                >{f}</button>
              ))}
            </div>
            <div className="selector-group">
              {SCALES_ALL.map(sc => (
                <button key={sc}
                  className={`scope-btn ${scales.includes(sc) ? 'active' : ''}`}
                  onClick={() => setScales(p => p.includes(sc) ? p.filter(x => x !== sc) : [...p, sc])}
                >{sc}</button>
              ))}
            </div>
          </>
        )}

        <button
          className={`scope-btn ${showSearch ? 'active' : ''}`}
          style={{ marginLeft: 4 }}
          onClick={() => { setShowSearch(v => !v); setSearchResults(null); setSelectedReactors([]); }}
        >🔍 빈 자리 찾기</button>

        <button
          className="scope-btn"
          style={{ marginLeft: 4 }}
          title={inSandbox ? '샌드박스 중에는 새로고침할 수 없습니다' : '예약 현황을 최신 데이터로 새로고침'}
          disabled={busy || inSandbox}
          onClick={handleRefresh}
        >🔄 새로고침</button>

        <div style={{ flex: 1 }} />

        {!lock && (
          <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
            {!_urlUser && (
              <input
                placeholder="이름 입력"
                value={userInput}
                onChange={e => setUserInput(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && enterSandbox()}
                className="text-input"
              />
            )}
            {_urlUser && (
              <span style={{ fontSize: 13, color: '#555' }}>{_urlUser}</span>
            )}
            <button className="btn btn-primary" onClick={enterSandbox} disabled={busy}>
              {busy ? '...' : '▶ 입장'}
            </button>
          </div>
        )}

        {lock && (
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <span className="sandbox-badge">✏️ {lock.user}</span>
            {inSandbox && (
              <>
                <button className="btn" onClick={() => setShowDiff(v => !v)}>
                  {nChanges > 0 ? `📋 변경 ${nChanges}건` : '📋 변경 없음'}
                </button>
                <button className="btn btn-warning" onClick={() => { setApplying(true); setApplyMsg(null); }}>
                  💾 적용
                </button>
              </>
            )}
            <button className="btn" onClick={exitSandbox} disabled={busy}>🚪 나가기</button>
          </div>
        )}
      </div>

      {/* ── Quick Reserve / Vacancy Search panel ── */}
      {showSearch && (
        <div className="search-panel">
          <div className="search-inputs">
            <div className="field-group">
              <span className="field-label">제품명</span>
              <input className="text-input" style={{ width: 88 }} placeholder="SB4" value={srchProject}
                onChange={e => setSrchProject(e.target.value)} />
            </div>
            <div className="field-group">
              <span className="field-label">시작일</span>
              <input type="date" className="text-input" style={{ width: 130 }} value={srchStart}
                onChange={e => setSrchStart(e.target.value)} />
            </div>
            <div className="field-group">
              <span className="field-label">배양 일수</span>
              <input type="number" className="text-input" style={{ width: 58 }} min={1} max={365}
                value={srchDays} onChange={e => setSrchDays(Number(e.target.value))} />
            </div>
            <div className="field-group">
              <span className="field-label">Scale</span>
              <select className="text-input" style={{ width: 68 }} value={srchScale}
                disabled={SCOPE_SCALES[scope]?.length === 1}
                onChange={e => setSrchScale(e.target.value)}>
                {(SCOPE_SCALES[scope] ?? []).map(s => <option key={s}>{s}</option>)}
              </select>
            </div>
            <div className="field-group">
              <span className="field-label">Stage</span>
              <select className="text-input" style={{ width: 68 }} value={srchStage}
                disabled={srchScale === 'Ambr250' || srchScale === 'Ambr15'}
                onChange={e => setSrchStage(e.target.value)}>
                {SEARCH_STAGES.map(s => <option key={s}>{s}</option>)}
              </select>
            </div>
            <div className="field-group">
              <span className="field-label">공정</span>
              <select className="text-input" style={{ width: 98 }} value={srchMethod}
                onChange={e => setSrchMethod(e.target.value)}>
                {(METHOD_OPTIONS[srchScale] || ['Fed-batch']).map(m => <option key={m}>{m}</option>)}
              </select>
            </div>
            <div className="field-group">
              <span className="field-label">수량</span>
              <input type="number" className="text-input" style={{ width: 50 }} min={1} max={30}
                value={srchQty} onChange={e => setSrchQty(Number(e.target.value))} />
            </div>
            <button className="btn btn-primary" onClick={handleSearch} disabled={busy}>🔍 확인</button>
            <button className="btn" onClick={() => { setShowSearch(false); setSearchResults(null); setSelectedReactors([]); }}>닫기</button>
          </div>

          {searchResults && (
            <div style={{ marginTop: 10 }}>
              {searchResults.available.length === 0 ? (
                <div className="apply-msg apply-error">
                  ❌ {searchResults.start} ~ {searchResults.end} ({searchResults.days}일) 가용 배양기 없음
                </div>
              ) : searchResults.available.length < srchQty ? (
                <div className="apply-msg apply-conflict">
                  ⚠️ {searchResults.available.length}개만 가용 (필요: {srchQty}개) — {searchResults.start} ~ {searchResults.end}
                </div>
              ) : (
                <div className="apply-msg apply-success" style={{ marginBottom: 8 }}>
                  ✅ {searchResults.available.length}개 가용 — {searchResults.start} ~ {searchResults.end} ({searchResults.days}일)
                </div>
              )}

              {searchResults.available.length > 0 && (
                <>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5, marginBottom: 8 }}>
                    {searchResults.available.map(rid => {
                      const eq    = eqMap[rid] || '';
                      const label = rid.split('-').slice(1).join('-');
                      const sel   = selectedReactors.includes(rid);
                      return (
                        <button key={rid}
                          className={`scope-btn ${sel ? 'active' : ''}`}
                          style={{ fontSize: 12 }}
                          onClick={() => setSelectedReactors(p =>
                            p.includes(rid) ? p.filter(x => x !== rid) : [...p, rid]
                          )}>
                          {eq && <span style={{ fontSize: 10, opacity: 0.75 }}>{eq} </span>}{label}
                        </button>
                      );
                    })}
                  </div>
                  {inSandbox ? (
                    <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                      <button className="btn btn-primary"
                        onClick={handleAddBooking}
                        disabled={busy || !srchProject.trim() || selectedReactors.length === 0}>
                        ✅ 샌드박스에 추가 ({selectedReactors.length}개)
                      </button>
                      {!srchProject.trim() && (
                        <span style={{ fontSize: 11, color: '#e53' }}>제품명을 먼저 입력하세요</span>
                      )}
                    </div>
                  ) : (
                    <div style={{ fontSize: 12, color: '#888' }}>▶ 샌드박스 입장 후 추가할 수 있습니다</div>
                  )}
                </>
              )}
            </div>
          )}
        </div>
      )}

      {/* ── Diff panel ── */}
      {showDiff && nChanges > 0 && (
        <div className="diff-panel">
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
            <strong>대기 중인 변경 ({nChanges}건)</strong>
            <button className="btn" style={{ padding: '2px 8px', fontSize: 12 }} onClick={() => setShowDiff(false)}>닫기</button>
          </div>
          <table className="diff-table">
            <thead><tr><th>구분</th><th>Reactor</th><th>Project</th><th>Stage</th><th>Start</th><th>End</th></tr></thead>
            <tbody>
              {diff.added.map(b => (
                <tr key={b.booking_id} style={{ background: '#e8f5e9' }}>
                  <td>➕ 추가</td><td>{b.reactor_id}</td><td>{b.project}</td><td>{b.stage}</td><td>{b.start}</td><td>{b.end}</td>
                </tr>
              ))}
              {diff.removed.map(b => (
                <tr key={b.booking_id} style={{ background: '#fce4ec' }}>
                  <td>➖ 삭제</td><td>{b.reactor_id}</td><td>{b.project}</td><td>{b.stage}</td><td>{b.start}</td><td>{b.end}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* ── Apply modal ── */}
      {applying && (
        <div className="modal-backdrop" onClick={() => { setApplying(false); setApplyMsg(null); }}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <h3 style={{ marginTop: 0 }}>💾 시뮬레이션 적용</h3>
            <p style={{ color: '#555', fontSize: 13, marginTop: 0 }}>
              Admin 계정으로 인증 후 적용하면 live CSV에 즉시 반영됩니다.
            </p>
            {applyMsg && (
              <div className={`apply-msg apply-${applyMsg.type}`}>
                <strong>{applyMsg.text}</strong>
                {applyMsg.conflicts && (
                  <ul style={{ margin: '6px 0 0 0', paddingLeft: 18 }}>
                    {applyMsg.conflicts.map((c, i) => <li key={i}>{c.message}</li>)}
                  </ul>
                )}
              </div>
            )}
            {applyMsg?.type !== 'success' && (
              <>
                <input
                  type="text"
                  placeholder="아이디 (예: admin)"
                  value={applyUser}
                  onChange={e => setApplyUser(e.target.value)}
                  className="text-input"
                  style={{ width: '100%', marginBottom: 8 }}
                  autoFocus
                />
                <input
                  type="password"
                  placeholder="비밀번호"
                  value={applyPwd}
                  onChange={e => setApplyPwd(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && handleApply()}
                  className="text-input"
                  style={{ width: '100%', marginBottom: 10 }}
                />
                <div style={{ display: 'flex', gap: 8 }}>
                  <button className="btn btn-primary" onClick={handleApply} disabled={busy || !applyUser.trim() || !applyPwd.trim()}>
                    {busy ? '적용 중...' : '🚀 확인 적용'}
                  </button>
                  <button className="btn" onClick={() => { setApplying(false); setApplyMsg(null); }}>취소</button>
                </div>
              </>
            )}
            {applyMsg?.type === 'success' && (
              <button className="btn btn-primary" onClick={() => { setApplying(false); setApplyMsg(null); }}>닫기</button>
            )}
          </div>
        </div>
      )}

      {/* ── Gantt ── */}
      <div className="gantt-wrapper">
        {!schedule
          ? <div className="placeholder">불러오는 중...</div>
          : visibleReactors.length === 0
            ? <div className="placeholder">선택한 조건에 해당하는 배양기가 없습니다.</div>
            : <Gantt
                bookings={bookings}
                reactors={visibleReactors}
                colors={schedule.colors}
                user={inSandbox ? user : null}
                onMove={handleMove}
                onMoveMultiple={handleMoveMultiple}
                onDelete={handleDelete}
                onConflict={() => showToast('다른 예약과 겹칩니다 — 이동이 취소되었습니다', 'error')}
                scope={scope}
                eqMap={eqMap}
              />
        }
      </div>
    </div>
  );
}
