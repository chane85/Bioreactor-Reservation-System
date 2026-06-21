import { useRef, useState, useEffect, useCallback, useMemo, memo } from 'react';
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

function eqNum(r, eqMap) {
  if (eqMap[r.id]) return eqMap[r.id];
  const parts = r.id.split('-');
  if (parts.length >= 2 && parts[1].startsWith('EQ')) return parts[1].replace('EQ0000', '');
  return '—';
}

function labelColors(r) {
  if (r.id.startsWith('Ambr250')) return { eq: '#e0e0e0', vessel: '#B2EBF2' };
  if (r.id.startsWith('Ambr15'))  return { eq: '#e0e0e0', vessel: '#FFDAC1' };
  return { eq: '#F5F5F5', vessel: SCALE_COLORS[r.scale] ?? '#fff' };
}

const ROW_HEIGHT = { '배양기': 40, 'Ambr250': 30, 'Ambr15': 26 };

function Gantt({ bookings, reactors, colors, user, onMove, onMoveMultiple, onDelete, onConflict, scope, eqMap = {} }) {
  const H = ROW_HEIGHT[scope] ?? 32;
  const viewStart = formatDate(addDays(today(), -DAYS_BEFORE));
  const totalDays = DAYS_BEFORE + DAYS_AFTER + 1;
  const todayStr  = formatDate(today());

  // Scroll sync between label column and main grid
  const mainRef   = useRef(null);
  const labelsRef = useRef(null);
  const syncScroll = (src, target) => { if (target.current) target.current.scrollTop = src.scrollTop; };

  // Hover date tooltip (ref-based — zero re-renders on mousemove)
  const tooltipRef = useRef(null);

  // ── Selection ─────────────────────────────────────────────────
  const [selectedIds, setSelectedIds] = useState(new Set());
  // Refs so event-handler closures always see latest values without recreating handlers
  const selectedIdsRef = useRef(selectedIds);
  useEffect(() => { selectedIdsRef.current = selectedIds; }, [selectedIds]);
  const bookingsRef = useRef(bookings);
  useEffect(() => { bookingsRef.current = bookings; }, [bookings]);

  // ── Drag state ────────────────────────────────────────────────
  const dragRef  = useRef(null);
  const [drag, setDrag] = useState(null); // {booking, deltaX, deltaY, isMulti}

  // ── Resize state ──────────────────────────────────────────────
  const resizeRef = useRef(null);
  const [resize, setResize] = useState(null);

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
    if (!user) return;
    e.preventDefault();

    const isCtrl = e.ctrlKey || e.metaKey;
    const reactorIndex = reactors.findIndex(r => r.id === booking.reactor_id);
    const isAlreadySelected = selectedIdsRef.current.has(booking.booking_id);

    dragRef.current = { booking, startX: e.clientX, startY: e.clientY, reactorIndex, isCtrl, isAlreadySelected };
    let didDrag = false;

    const onMove_ = (e) => {
      if (!dragRef.current || dragRef.current.isCtrl) return;
      const dx = e.clientX - dragRef.current.startX;
      const dy = e.clientY - dragRef.current.startY;
      if (Math.abs(dx) < 4 && Math.abs(dy) < 4) return;
      didDrag = true;
      const isMulti = dragRef.current.isAlreadySelected && selectedIdsRef.current.size > 1;
      setDrag({ booking: dragRef.current.booking, deltaX: dx, deltaY: dy, isMulti });
    };

    const onUp = (e) => {
      document.removeEventListener('mousemove', onMove_);
      document.removeEventListener('mouseup', onUp);

      if (!dragRef.current) { setDrag(null); return; }

      const dx = e.clientX - dragRef.current.startX;
      const dy = e.clientY - dragRef.current.startY;
      const { booking: b, reactorIndex: ri, isCtrl: ctrl, isAlreadySelected: wasSel } = dragRef.current;
      dragRef.current = null;
      setDrag(null);

      const movedEnough = didDrag || Math.abs(dx) >= 4 || Math.abs(dy) >= 4;

      // ── Click (no significant movement, or Ctrl held) ──
      if (!movedEnough || ctrl) {
        if (ctrl) {
          setSelectedIds(prev => {
            const next = new Set(prev);
            if (next.has(b.booking_id)) next.delete(b.booking_id);
            else next.add(b.booking_id);
            return next;
          });
        } else {
          setSelectedIds(new Set([b.booking_id]));
        }
        return;
      }

      // ── Drag ──
      const curSelected = selectedIdsRef.current;
      const isMulti = wasSel && curSelected.size > 1;
      const dragBookings = isMulti
        ? bookingsRef.current.filter(bk => curSelected.has(bk.booking_id))
        : [b];

      if (!wasSel) setSelectedIds(new Set([b.booking_id]));

      const rawDayShift = Math.round(dx / DAY_WIDTH);
      const rowShift    = isMulti ? 0 : Math.round(dy / H); // no vertical shift for multi

      // Clamp dayShift so no bar exits the view bounds
      let clampedShift = rawDayShift;
      if (rawDayShift !== 0) {
        let minAllowed = -Infinity, maxAllowed = Infinity;
        for (const bk of dragBookings) {
          const fromStart = daysBetween(viewStart, bk.start);
          const toEnd     = (totalDays - 1) - daysBetween(viewStart, bk.end);
          minAllowed = Math.max(minAllowed, -fromStart);
          maxAllowed = Math.min(maxAllowed, toEnd);
        }
        clampedShift = Math.max(minAllowed, Math.min(maxAllowed, rawDayShift));
      }

      if (clampedShift === 0 && rowShift === 0) return;

      const moves = dragBookings.map(bk => {
        const bkRi = isMulti
          ? reactors.findIndex(r => r.id === bk.reactor_id)
          : ri;
        const newRi = Math.max(0, Math.min(reactors.length - 1, bkRi + rowShift));
        return {
          bookingId:    bk.booking_id,
          newReactorId: reactors[newRi].id,
          newStart:     formatDate(addDays(parseDate(bk.start), clampedShift)),
          newEnd:       formatDate(addDays(parseDate(bk.end),   clampedShift)),
        };
      });

      // Reject drop if any bar would land on top of an existing bar
      const movingIds = new Set(moves.map(m => m.bookingId));
      const conflict = moves.some(m =>
        bookingsRef.current.some(bk =>
          !movingIds.has(bk.booking_id) &&
          bk.reactor_id === m.newReactorId &&
          bk.start <= m.newStart && bk.end >= m.newEnd
        )
      );
      if (conflict) { onConflict?.(); return; }

      if (moves.length === 1) {
        onMove(moves[0].bookingId, moves[0].newReactorId, moves[0].newStart, moves[0].newEnd);
      } else {
        onMoveMultiple(moves);
      }
    };

    document.addEventListener('mousemove', onMove_);
    document.addEventListener('mouseup', onUp);
  }, [user, reactors, H, viewStart, totalDays, onMove, onMoveMultiple]);

  // Pre-compute EQ groups for Ambr scopes
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
    const isSelected  = selectedIds.has(b.booking_id);
    const isDragging  = drag?.booking?.booking_id === b.booking_id ||
                        (drag?.isMulti && isSelected);
    const isResizing  = resize?.booking?.booking_id === b.booking_id;
    return {
      position:        'absolute',
      left:            `${left}px`,
      width:           `${Math.max(width, 4)}px`,
      height:          `${H - 6}px`,
      top:             '3px',
      backgroundColor: bg,
      color:           fg,
      border:          isSelected && !isDragging ? '2px solid #1565c0' : '2px solid rgba(0,0,0,0.35)',
      boxShadow:       isSelected && !isDragging ? '0 0 0 2px #90caf9' : 'none',
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

  const WD = ['일','월','화','수','목','금','토'];
  const handleGridMouseMove = useCallback((e) => {
    if (!tooltipRef.current || !mainRef.current) return;
    const rect = mainRef.current.getBoundingClientRect();
    const x = e.clientX - rect.left + mainRef.current.scrollLeft;
    const dayIdx = Math.floor(x / DAY_WIDTH);
    if (dayIdx < 0 || dayIdx >= totalDays) { tooltipRef.current.style.display = 'none'; return; }
    const dateStr = formatDate(addDays(parseDate(viewStart), dayIdx));
    const d = parseDate(dateStr);
    tooltipRef.current.textContent = `${dateStr} (${WD[d.getDay()]})`;
    tooltipRef.current.style.left    = `${e.clientX}px`;
    tooltipRef.current.style.top     = `${e.clientY - 36}px`;
    tooltipRef.current.style.display = 'block';
  }, [viewStart, totalDays]);

  const handleGridMouseLeave = useCallback(() => {
    if (tooltipRef.current) tooltipRef.current.style.display = 'none';
  }, []);

  // Overlay bar(s) that follow the cursor during drag
  function DragOverlay() {
    if (!drag || !mainRef.current) return null;
    const { booking, deltaX, deltaY, isMulti } = drag;
    const scrollLeft = mainRef.current?.scrollLeft ?? 0;
    const scrollTop  = mainRef.current?.scrollTop  ?? 0;

    const barsToShow = isMulti
      ? bookings.filter(bk => selectedIds.has(bk.booking_id))
      : [booking];

    return barsToShow.map(bk => {
      const ridx = reactors.findIndex(r => r.id === bk.reactor_id);
      const left = (daysBetween(viewStart, bk.start) * DAY_WIDTH) + deltaX + LABEL_WIDTH - scrollLeft;
      // For multi-drag: no vertical shift (row locked); single-drag: follow cursor vertically
      const top  = (ridx * H) + (isMulti ? 0 : deltaY) + 60 - scrollTop;
      const proj = normalizeProject(bk.project);
      const bg   = colors?.bg?.[proj]   ?? '#808080';
      const fg   = colors?.font?.[proj] ?? '#000';
      const w    = (daysBetween(bk.start, bk.end) + 1) * DAY_WIDTH - 2;
      return (
        <div key={bk.booking_id} style={{
          position: 'fixed', left: `${left}px`, top: `${top}px`,
          width: `${Math.max(w, 4)}px`, height: `${H - 6}px`,
          backgroundColor: bg, color: fg, borderRadius: '3px',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: '11px', fontWeight: 'bold', opacity: 0.85,
          pointerEvents: 'none', zIndex: 1000, boxShadow: '0 3px 10px rgba(0,0,0,0.3)',
        }}>
          {bk.project}
        </div>
      );
    });
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
      <div ref={tooltipRef} style={{
        display: 'none', position: 'fixed', transform: 'translateX(-50%)',
        background: 'rgba(30,30,30,0.88)', color: '#fff',
        fontSize: 11, fontWeight: 'bold', padding: '3px 8px',
        borderRadius: 4, pointerEvents: 'none', whiteSpace: 'nowrap',
        zIndex: 9999, boxShadow: '0 2px 6px rgba(0,0,0,0.3)',
      }} />

      {/* ── Left: sticky reactor labels ── */}
      <div style={{ width: LABEL_WIDTH, flexShrink: 0, overflow: 'hidden', borderRight: '2px solid #999', zIndex: 5 }}>
        <div style={{ height: 50, borderBottom: '1px solid #ccc', background: '#f5f5f5' }} />
        <div ref={labelsRef} style={{ overflowY: 'hidden', height: 'calc(100% - 50px)' }}>
          {eqGroups ? (
            eqGroups.map(group => (
              <div key={group.eq} style={{ display: 'flex', height: group.reactors.length * H }}>
                <div style={{
                  width: 80, flexShrink: 0,
                  background: labelColors(group.reactors[0]).eq,
                  borderRight: '1px solid #bbb', borderBottom: '2px solid #999',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: '13px', fontWeight: 'bold', color: '#000',
                }}>
                  {group.eq}
                </div>
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
            {monthSpans.map((span, si) => (
              <div key={span.label} style={{
                width: span.count * DAY_WIDTH, flexShrink: 0, boxSizing: 'border-box',
                textAlign: 'center', fontSize: '13px', fontWeight: 'bold',
                borderLeft: si > 0 ? '3px solid #333' : 'none',
                lineHeight: '24px', overflow: 'hidden',
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
                  width: DAY_WIDTH, flexShrink: 0, boxSizing: 'border-box',
                  textAlign: 'center', fontSize: '10px', lineHeight: '26px',
                  borderRight: '1px solid #eee',
                  boxShadow: isMonth1 ? 'inset 3px 0 0 #333' : 'none',
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
        <div
          style={{ position: 'relative', width: totalWidth }}
          onMouseMove={handleGridMouseMove}
          onMouseLeave={handleGridMouseLeave}
          onClick={(e) => {
            // Clear selection when clicking empty grid space (not on a bar)
            if (!e.target.closest('[data-bar]')) setSelectedIds(new Set());
          }}
        >
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

          {/* Month boundary vertical lines */}
          {dates.map((d, i) => parseDate(d).getDate() === 1 && (
            <div key={`mb-${d}`} style={{
              position: 'absolute', left: i * DAY_WIDTH, top: 0, bottom: 0,
              width: 3, background: 'rgba(0,0,0,0.75)',
              pointerEvents: 'none', zIndex: 1,
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
                  data-bar="true"
                  style={barStyle(b)}
                  onMouseDown={(e) => handleDragStart(e, b)}
                  onClick={(e) => e.stopPropagation()}
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
