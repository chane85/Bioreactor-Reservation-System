const BASE = import.meta.env.VITE_API_BASE || '';

async function request(method, path, body, extraHeaders = {}) {
  const opts = { method, headers: { ...extraHeaders } };
  if (body) {
    opts.headers['Content-Type'] = 'application/json';
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(`${BASE}${path}`, opts);
  const data = await res.json();
  if (!res.ok) throw { status: res.status, detail: data.detail };
  return data;
}

export const getSchedule      = ()                                     => request('GET',    '/api/schedule');
export const getEqMap         = ()                                     => request('GET',    '/api/inventory/eq-map');
export const claimLock         = (user)                                 => request('POST',   '/api/sandbox/lock', { user });
export const releaseLock       = (user)                                 => request('DELETE', `/api/sandbox/lock?user=${encodeURIComponent(user)}`);
export const getSandboxState   = ()                                     => request('GET',    '/api/sandbox/bookings');
export const moveBooking       = (user, booking_id, new_reactor_id, new_start, new_end) =>
  request('POST', '/api/sandbox/move',   { user, booking_id, new_reactor_id, new_start, new_end });
export const deleteBooking     = (user, booking_id)                     => request('POST',   '/api/sandbox/delete', { user, booking_id });
export const undoChange        = (user)                                 => request('POST',   '/api/sandbox/undo', { user });
export const getDiff           = ()                                     => request('GET',    '/api/sandbox/diff');
export const applyChanges      = (user, adminUser, adminPassword)       => request('POST',   '/api/sandbox/apply',  { user }, { Authorization: 'Basic ' + btoa(`${adminUser}:${adminPassword}`) });
export const unlockSandbox     = (user)                                 => request('POST',   '/api/sandbox/unlock', { user });
export const findAvailable     = (scale, start_date, days, stage, method) =>
  request('POST', '/api/sandbox/find-available', { scale, start_date, days, stage, method });
export const addBooking        = (user, reactor_ids, project, stage, method, start_date, end_date) =>
  request('POST', '/api/sandbox/add', { user, reactor_ids, project, stage, method, start_date, end_date });
