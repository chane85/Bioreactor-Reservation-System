import { useRef, useState, useCallback, useMemo, memo } from 'react';
import {
  today, parseDate, formatDate, addDays, daysBetween,
  isWeekend, reactorLabel, normalizeProject,
} from './ganttUtils';
const DAY_WIDTH    = 22;   // px per day
const LABEL_WIDTH  = 160;  // px for reactor label column (80 EQ + 80 label)

const SCALE_COLORS = {
  '2L':   '#BDD7EE',
  '5L':   '#90EE90',
  '10L':  '#32CD32',
  '50L':  '#FFA500',
  '200L': '#CC0000',
  'Wave': '#D3D3D3',
};
const DAYS_BEFORE  = 7;
const DAYS_AFTER   = 100;

// Returns the EQ number for any reactor type, matching Home.py display format.
// Bioreactors: look up static map (EQ_411 etc.)
// Ambr systems: extract from ID and strip 'EQ0000' prefix (EQ00005350 → 5350)
function eqNum(r, eqMap) {
  if (eqMap[r.id]) return eqMap[r.id];
  const parts = r.id.split('-');
  if (parts.length >= 2 && parts[1].startsWith('EQ')) return parts[1].replace('EQ0000', '');
  return '—';
}

// Background colors for the EQ + vessel label columns
function labelColors(r) {
  if (r.id.startsWith('Ambr250')) return { eq: '#e0e0e0', vessel: '#B2EBF2' };
  if (r.id.startsWith('Ambr15'))  return { eq: '#e0e0e0', vessel: '#FFDAC1' };
  return { eq: '#F5F5F5', vessel: SCALE_COLORS[r.scale] ?? '#fff' };
}

const ROW_HEIGHT = { '배양기': 40, 'Ambr250': 30, 'Ambr15': 26 };

function Gantt({ bookings, reactors, colors, user, onMove, onDelete, scope, eqMap = {} }) {
  const H = ROW_HEIGHT[scope] ?? 32;
  const viewStart = formatDate(addDays(today(), -DAYS_BEFORE));
  const totalDays = DAYS_BEFORE + DAYS_AFTER + 1;
  const todayStr  = formatDate(today());

  // Scroll sync between label column and main grid
  const mainRef   = useRef(null);
  const labelsRef = useRef(null);
  const syncScroll = (src, target) => { if (target.current) target.current.scrollTop = src.scrollTop; };

  // Drag state (move)
  const dragRef  = useRef(null);
  const [drag, setDrag] = useState(null);

  // Resize state
  const resizeRef = useRef(null);
  const [resize, setResize] = useState(null); // {booking, newStart, newEnd}

  const handleResizeStart = useCallback((e, booking, edge) => {
    if (!user) return;
    e.preventDefault();
    resizeRef.current = {
      booking, edge,
      startX: e.clientX,
      originalStart: booking.start,
      originalEnd:   booking.end,
    };
    setResize({ booking, newStart: booking.start, newEnd: booking.end });

    const onMove_ = (e) => {
      const { booking, edge, originalStart, originalEnd } = resizeRef.current;
      const dayShift = Math.round((e.clientX - resizeRef.current.startX) / DAY_WIDTH);
      let newStart = originalStart, newEnd = originalEnd;
      if (edge === 'left') {
        newStart = formatDate(addDays(parseDate(originalStart), dayShift));
        if (newStart >= originalEnd) newStart = formatDate(addDays(parseDate(originalEnd), -1));
      } else {
        newEnd = formatDate(addDays(parseDate(originalEnd), dayShift));
        if (newEnd <= originalStart) newEnd = formatDate(addDays(parseDate(originalStart), 1));
      }
      setResize({ booking, newStart, newEnd });
    };

    const onUp = (e) => {
      if (resizeRef.current) {
        const { booking, edge, originalStart, originalEnd } = resizeRef.current;
        const dayShift = Math.round((e.clientX - resizeRef.current.startX) / DAY_WIDTH);
        let newStart = originalStart, newEnd = originalEnd;
        if (edge === 'left') {
          newStart = formatDate(addDays(parseDate(originalStart), dayShift));
          if (newStart >= originalEnd) newStart = formatDate(addDays(parseDate(originalEnd), -1));
        } else {
          newEnd = formatDate(addDays(parseDate(originalEnd), dayShift));
          if (newEnd <= originalStart) newEnd = formatDate(addDays(parseDate(originalStart), 1));
        }
        onMove(booking.booking_id, booking.reactor_id, newStart, newEnd);
      }
      resizeRef.current = null;
      setResize(null);
      document.removeEventListener('mousemove', onMove_);
      document.removeEventListener('mouseup',   onUp);
    };

    document.addEventListener('mousemove', onMove_);
    document.addEventListener('mouseup',   onUp);
  }, [user, onMove]);

  const handleDragStart = useCallback((e, booking) => {
    if (!user) return;   // read-only when not in sandbox
    e.preventDefault();
    const reactorIndex = reactors.findIndex(r => r.id === booking.reactor_id);
    dragRef.current = { booking, startX: e.clientX, startY: e.clientY, reactorIndex };
    setDrag({ booking, deltaX: 0, deltaY: 0 });

    const onMove_ = (e) => setDrag({
      booking: dragRef.current.booking,
      deltaX: e.clientX - dragRef.current.startX,
      deltaY: e.clientY - dragRef.current.startY,
    });

    const onUp = (e) => {
      if (dragRef.current) {
        const dx = e.clientX - dragRef.current.startX;
        const dy = e.clientY - dragRef.current.startY;
        const dayShift = Math.round(dx / DAY_WIDTH);
        const rowShift = Math.round(dy / H);
        const { booking, reactorIndex } = dragRef.current;
        const newIdx      = Math.max(0, Math.min(reactors.length - 1, reactorIndex + rowShift));
        const newReactor  = reactors[newIdx].id;
        const newStart    = formatDate(addDays(parseDate(booking.start), dayShift));
        const newEnd      = formatDate(addDays(parseDate(booking.end),   dayShift));
        onMove(booking.booking_id, newReactor, newStart, newEnd);
      }
      dragRef.current = null;
      setDrag(null);
      document.removeEventListener('mousemove', onMove_);
      document.removeEventListener('mouseup',   onUp);
    };

    document.addEventListener('mousemove', onMove_);
    document.addEventListener('mouseup',   onUp);
  }, [user, reactors, H, onMove]);

  // Pre-compute EQ groups for Ambr scopes (EQ cell spans multiple vessel rows)
  const eqGroups = useMemo(() => {
    if (scope !== 'Ambr250' && scope !== 'Ambr15') return null;
    const groups = [];
    let i = 0;
    while (i < reactors.length) {
      const eq = eqNum(reactors[i], eqMap);
      let j = i;
      while (j < reactors.length && eqNum(reactors[j], eqMap) === eq) j++;
      groups.push({ eq, reactors: reactors.slice(i, j) });
      i = j;
    }
    return groups;
  }, [reactors, scope]);

  // Pre-compute bookings grouped by reactor (exclude VBLOCK rows)
  const byReactor = useMemo(() => {
    const map = {};
    for (const b of bookings) {
      if (b.booking_id.startsWith('VBLOCK_')) continue;
      if (!map[b.reactor_id]) map[b.reactor_id] = [];
      map[b.reactor_id].push(b);
    }
    return map;
  }, [bookings]);

  // Build date column headers
  const dates = useMemo(() => {
    const arr = [];
    for (let i = 0; i < totalDays; i++) arr.push(formatDate(addDays(today(), i - DAYS_BEFORE)));
    return arr;
  }, []);

  // Month label spans
  const monthSpans = useMemo(() => {
    const spans = [];
    let cur = null;
    dates.forEach((d, i) => {
      const label = parseDate(d).toLocaleString('en', { month: 'short', year: 'numeric' });
      if (!cur || cur.label !== label) {
        if (cur) spans.push(cur);
        cur = { label, start: i, count: 1 };
      } else {
        cur.count++;
      }
    });
    if (cur) spans.push(cur);
    return spans;
  }, [dates]);

  const totalWidth = totalDays * DAY_WIDTH;

  function barStyle(b) {
    const left  = daysBetween(viewStart, b.start) * DAY_WIDTH;
    const width = (daysBetween(b.start, b.end) + 1) * DAY_WIDTH - 2;
    const proj  = normalizeProject(b.project);
    const bg    = (colors?.bg?.[proj])   ?? '#808080';
    const fg    = (colors?.font?.[proj]) ?? '#000';
    const isDragging = drag?.booking?.booking_id === b.booking_id;
    const isResizing = resize?.booking?.booking_id === b.booking_id;
    return {
      position:        'absolute',
      left:            `${left}px`,
      width:           `${Math.max(width, 4)}px`,
      height:          `${H - 6}px`,
      top:             '3px',
      backgroundColor: bg,
      color:           fg,
      border:          '2px solid rgba(0,0,0,0.35)',
      borderRadius:    '3px',
      display:         'flex',
      alignItems:      'center',
      justifyContent:  'center',
      fontSize:        '12px',
      fontWeight:      'bold',
      cursor:          user ? 'grab' : 'default',
      userSelect:      'none',
      opacity:         isDragging || isResizing ? 0.35 : 1,
      overflow:        'hidden',
      whiteSpace:      'nowrap',
      zIndex:          2,
    };
  }

  const fmtShort = (d) => { const dt = parseDate(d); return `${dt.getMonth()+1}/${dt.getDate()}`; };

  // Overlay bar that follows the cursor during drag
  function DragOverlay() {
    if (!drag || !mainRef.current) return null;
    const { booking, deltaX, deltaY } = drag;
    const ridx    = reactors.findIndex(r => r.id === booking.reactor_id);
    const origTop = ridx * H + DAYS_BEFORE; // approximate, ignores header
    const left    = (daysBetween(viewStart, booking.start) * DAY_WIDTH) + deltaX + LABEL_WIDTH - (mainRef.current?.scrollLeft ?? 0);
    const top     = (ridx * H) + deltaY + 60 - (mainRef.current?.scrollTop ?? 0); // 60 = header approx

    const proj = normalizeProject(booking.project);
    const bg   = colors?.bg?.[proj]   ?? '#808080';
    const fg   = colors?.font?.[proj] ?? '#000';
    const w    = (daysBetween(booking.start, booking.end) + 1) * DAY_WIDTH - 2;

    return (
      <div style={{
        position: 'fixed', left: `${left}px`, top: `${top}px`,
        width: `${w}px`, height: `${H - 6}px`,
        backgroundColor: bg, color: fg, borderRadius: '3px',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: '11px', fontWeight: 'bold', opacity: 0.85,
        pointerEvents: 'none', zIndex: 1000, boxShadow: '0 3px 10px rgba(0,0,0,0.3)',
      }}>
        {booking.project} ({booking.stage})
      </div>
    );
  }

  function ResizeOverlay() {
    if (!resize || !mainRef.current) return null;
    const { booking, newStart, newEnd } = resize;
    const ridx = reactors.findIndex(r => r.id === booking.reactor_id);
    const proj = normalizeProject(booking.project);
    const bg   = colors?.bg?.[proj] ?? '#808080';
    const fg   = colors?.font?.[proj] ?? '#000';
    const left = (daysBetween(viewStart, newStart) * DAY_WIDTH) + LABEL_WIDTH - (mainRef.current?.scrollLeft ?? 0);
    const top  = (ridx * H) + 60 + 3 - (mainRef.current?.scrollTop ?? 0);
    const w    = (daysBetween(newStart, newEnd) + 1) * DAY_WIDTH - 2;
    return (
      <div style={{
        position: 'fixed', left: `${left}px`, top: `${top}px`,
        width: `${Math.max(w, 4)}px`, height: `${H - 6}px`,
        backgroundColor: bg, color: fg, borderRadius: '3px',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: '11px', fontWeight: 'bold', opacity: 0.85,
        pointerEvents: 'none', zIndex: 1000,
        boxShadow: '0 3px 10px rgba(0,0,0,0.3)',
        border: '2px dashed rgba(255,255,255,0.7)',
      }}>
        {fmtShort(newStart)} ~ {fmtShort(newEnd)}
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', height: '100%', overflow: 'hidden', border: '1px solid #ddd', position: 'relative' }}>
      <DragOverlay />
      <ResizeOverlay />

      {/* ── Left: sticky reactor labels ── */}
      <div style={{ width: LABEL_WIDTH, flexShrink: 0, overflow: 'hidden', borderRight: '2px solid #999', zIndex: 5 }}>
        {/* corner spacer (height matches date header) */}
        <div style={{ height: 50, borderBottom: '1px solid #ccc', background: '#f5f5f5' }} />
        {/* label rows — scroll locked to main */}
        <div ref={labelsRef} style={{ overflowY: 'hidden', height: 'calc(100% - 50px)' }}>
          {eqGroups ? (
            /* Ambr: EQ cell spans all vessel rows for that equipment */
            eqGroups.map(group => (
              <div key={group.eq} style={{ display: 'flex', height: group.reactors.length * H }}>
                {/* EQ number — single tall cell */}
                <div style={{
                  width: 80, flexShrink: 0,
                  background: labelColors(group.reactors[0]).eq,
                  borderRight: '1px solid #bbb', borderBottom: '2px solid #999',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: '13px', fontWeight: 'bold', color: '#000',
                }}>
                  {group.eq}
                </div>
                {/* Vessel rows */}
                <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
                  {group.reactors.map((r, vi) => (
                    <div key={r.id} style={{
                      height: H, flexShrink: 0,
                      background: labelColors(r).vessel,
                      borderBottom: vi === group.reactors.length - 1 ? '2px solid #999' : '1px solid #e8e8e8',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      fontSize: '12px', fontWeight: 'bold', color: '#000',
                      overflow: 'hidden', whiteSpace: 'nowrap', padding: '0 2px',
                    }}>
                      {reactorLabel(r.id)}
                    </div>
                  ))}
                </div>
              </div>
            ))
          ) : (
            /* Bioreactor: one row per reactor */
            reactors.map(r => (
              <div key={r.id} style={{
                height: H, display: 'flex', alignItems: 'stretch',
                borderBottom: '1px solid #e8e8e8', overflow: 'hidden',
              }}>
                <div style={{
                  width: 80, flexShrink: 0,
                  background: labelColors(r).eq, borderRight: '1px solid #bbb',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: '13px', fontWeight: 'bold', color: '#000',
                }}>
                  {eqNum(r, eqMap)}
                </div>
                <div style={{
                  flex: 1,
                  background: labelColors(r).vessel,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: '12px', fontWeight: 'bold',
                  color: r.scale === '200L' ? '#fff' : '#000',
                  overflow: 'hidden', whiteSpace: 'nowrap', padding: '0 2px',
                }}>
                  {reactorLabel(r.id)}
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* ── Right: scrollable Gantt grid ── */}
      <div
        ref={mainRef}
        onScroll={(e) => syncScroll(e.target, labelsRef)}
        style={{ flex: 1, overflow: 'auto', position: 'relative' }}
      >
        {/* ── Date header ── */}
        <div style={{ position: 'sticky', top: 0, zIndex: 10, background: '#fff', height: 50, width: totalWidth }}>
          {/* Month row */}
          <div style={{ display: 'flex', height: 24, borderBottom: '1px solid #ddd' }}>
            {monthSpans.map(span => (
              <div key={span.label} style={{
                width: span.count * DAY_WIDTH, flexShrink: 0,
                textAlign: 'center', fontSize: '13px', fontWeight: 'bold',
                borderRight: '2px solid #333', lineHeight: '24px', overflow: 'hidden',
              }}>
                {span.label}
              </div>
            ))}
          </div>
          {/* Day row */}
          <div style={{ display: 'flex', height: 26 }}>
            {dates.map(d => {
              const dObj = parseDate(d);
              const isToday   = d === todayStr;
              const isWknd    = isWeekend(dObj);
              const isMonth1  = dObj.getDate() === 1;
              return (
                <div key={d} style={{
                  width: DAY_WIDTH, flexShrink: 0, textAlign: 'center',
                  fontSize: '10px', lineHeight: '26px',
                  borderRight: isMonth1 ? '2px solid #333' : '1px solid #eee',
                  background: isToday ? '#ffecec' : isWknd ? '#fff0f0' : '#fff',
                  fontWeight: isToday ? 'bold' : 'normal',
                  color: isWknd ? '#cc0000' : '#333',
                }}>
                  {dObj.getDate()}
                </div>
              );
            })}
          </div>
        </div>

        {/* ── Reactor rows ── */}
        <div style={{ position: 'relative', width: totalWidth }}>
          {/* Today vertical line */}
          <div style={{
            position: 'absolute',
            left:  daysBetween(viewStart, todayStr) * DAY_WIDTH + DAY_WIDTH / 2,
            top:   0, bottom: 0, width: 2,
            background: '#ff4b4b', zIndex: 3, pointerEvents: 'none',
          }} />

          {/* Weekend column shading */}
          {dates.map((d, i) => isWeekend(parseDate(d)) && (
            <div key={d} style={{
              position: 'absolute', left: i * DAY_WIDTH, top: 0, bottom: 0,
              width: DAY_WIDTH, background: 'rgba(255,200,200,0.25)',
              pointerEvents: 'none', zIndex: 0,
            }} />
          ))}

          {reactors.map((r, ri) => (
            <div key={r.id} style={{
              position: 'relative', height: H,
              borderBottom: '1px solid #ececec',
              background: ri % 2 === 0 ? 'rgba(220,220,220,0.18)' : 'transparent',
            }}>
              {(byReactor[r.id] ?? []).map(b => (
                <div
                  key={b.booking_id}
                  style={barStyle(b)}
                  onMouseDown={(e) => handleDragStart(e, b)}
                  title={(() => {
                    const days = daysBetween(b.start, b.end) + 1;
                    return [
                      b.project,
                      `User: ${b.user ?? '—'}`,
                      `${b.start} ~ ${b.end}`,
                      `${days} Days`,
                    ].join('\n');
                  })()}
                >
                  {/* Left resize handle */}
                  {user && (
                    <div
                      style={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: 8, cursor: 'ew-resize', zIndex: 4 }}
                      onMouseDown={(e) => { e.stopPropagation(); handleResizeStart(e, b, 'left'); }}
                    />
                  )}
                  <span style={{ padding: '0 12px', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {b.project} ({daysBetween(b.start, b.end) + 1}d)
                  </span>
                  {user && (
                    <span
                      style={{
                        marginLeft: 4, color: 'inherit', fontWeight: 'normal',
                        fontSize: 12, cursor: 'pointer', opacity: 0.7,
                        flexShrink: 0,
                      }}
                      onMouseDown={(e) => e.stopPropagation()}
                      onClick={(e) => { e.stopPropagation(); onDelete(b.booking_id); }}
                      title="Delete this booking"
                    >
                      ✕
                    </span>
                  )}
                  {/* Right resize handle */}
                  {user && (
                    <div
                      style={{ position: 'absolute', right: 0, top: 0, bottom: 0, width: 8, cursor: 'ew-resize', zIndex: 4 }}
                      onMouseDown={(e) => { e.stopPropagation(); handleResizeStart(e, b, 'right'); }}
                    />
                  )}
                </div>
              ))}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export default memo(Gantt);
