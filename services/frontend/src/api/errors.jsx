export class ApiError extends Error {
  constructor(message, status, detail) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }
}

export async function parseApiError(response) {
  let detail;
  try {
    const body = await response.json();
    if (typeof body === 'string') {
      detail = body;
    } else if (Array.isArray(body.detail)) {
      detail = body.detail.map((e) => e.msg || JSON.stringify(e)).join(', ');
    } else if (typeof body.detail === 'string') {
      detail = body.detail;
    } else if (body.detail) {
      detail = JSON.stringify(body.detail);
    } else {
      detail = JSON.stringify(body);
    }
  } catch {
    detail = `HTTP ${response.status}: ${response.statusText}`;
  }

  return new ApiError(detail, response.status, detail);
}
