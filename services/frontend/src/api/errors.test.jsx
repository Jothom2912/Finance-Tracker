import { ApiError, parseApiError } from './errors';

describe('ApiError', () => {
  it('is an instance of Error with name, status, and detail', () => {
    const err = new ApiError('Not found', 404, 'Resource missing');

    expect(err).toBeInstanceOf(Error);
    expect(err.name).toBe('ApiError');
    expect(err.message).toBe('Not found');
    expect(err.status).toBe(404);
    expect(err.detail).toBe('Resource missing');
  });
});

describe('parseApiError', () => {
  function fakeResponse(status, body, { jsonFails = false } = {}) {
    return {
      status,
      statusText: 'Error',
      json: jsonFails
        ? () => Promise.reject(new SyntaxError('Unexpected token'))
        : () => Promise.resolve(body),
    };
  }

  it('extracts detail when body.detail is a string', async () => {
    const err = await parseApiError(fakeResponse(400, { detail: 'Bad request' }));

    expect(err).toBeInstanceOf(ApiError);
    expect(err.message).toBe('Bad request');
    expect(err.status).toBe(400);
  });

  it('joins messages when body.detail is an array of validation errors', async () => {
    const detail = [
      { msg: 'Field required', loc: ['body', 'email'] },
      { msg: 'Invalid format', loc: ['body', 'date'] },
    ];
    const err = await parseApiError(fakeResponse(422, { detail }));

    expect(err.message).toBe('Field required, Invalid format');
  });

  it('stringifies array items without msg', async () => {
    const detail = [{ code: 'missing' }];
    const err = await parseApiError(fakeResponse(422, { detail }));

    expect(err.message).toContain('missing');
  });

  it('stringifies detail when it is a non-string object', async () => {
    const err = await parseApiError(fakeResponse(400, { detail: { code: 42 } }));

    expect(err.message).toBe(JSON.stringify({ code: 42 }));
  });

  it('stringifies the entire body when detail is absent', async () => {
    const body = { error: 'something went wrong' };
    const err = await parseApiError(fakeResponse(500, body));

    expect(err.message).toBe(JSON.stringify(body));
  });

  it('uses body directly when it is a plain string', async () => {
    const err = await parseApiError(fakeResponse(500, 'Server error'));

    expect(err.message).toBe('Server error');
  });

  it('falls back to HTTP status when JSON parsing fails', async () => {
    const err = await parseApiError(fakeResponse(503, null, { jsonFails: true }));

    expect(err.message).toBe('HTTP 503: Error');
    expect(err.status).toBe(503);
  });
});
