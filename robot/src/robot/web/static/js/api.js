// Small wrapper around the robot's HTTP API.

async function request(method, path, body) {
  const response = await fetch(path, {
    method,
    headers: body ? { "Content-Type": "application/json" } : {},
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!response.ok) {
    const detail = await response.json().catch(() => ({}));
    throw new Error(detail.detail || `${response.status}`);
  }
  return response.status === 204 ? null : response.json();
}

export const get = (path) => request("GET", path);
export const post = (path, body) => request("POST", path, body);
