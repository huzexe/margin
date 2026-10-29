// Small wrapper around fetch() for the JSON API. Errors carry a message that is safe to show.

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

export async function api(path, { method = 'GET', body, keepalive = false } = {}) {
  const options = { method, keepalive, headers: {} };
  if (body !== undefined) {
    options.headers['Content-Type'] = 'application/json';
    options.body = JSON.stringify(body);
  }

  let res;
  try {
    res = await fetch(path, options);
  } catch {
    throw new ApiError("Can't reach Margin. Check that the app is still running in the terminal.", 0);
  }

  if (res.status === 204) return null;
  let data = null;
  try { data = await res.json(); } catch { /* not JSON */ }
  if (!res.ok) {
    throw new ApiError(data?.detail || `Something went wrong (error ${res.status}).`, res.status);
  }
  return data;
}
