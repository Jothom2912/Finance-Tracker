import { vi, describe, it, expect, beforeEach } from 'vitest';

const { handleUnauthorizedMock, requestMock } = vi.hoisted(() => ({
  handleUnauthorizedMock: vi.fn(),
  requestMock: vi.fn(),
}));

vi.mock('../utils/handleUnauthorized', () => ({
  handleUnauthorized: handleUnauthorizedMock,
}));

vi.mock('graphql-request', () => ({
  GraphQLClient: vi.fn().mockImplementation(() => ({
    request: requestMock,
  })),
}));

import { gqlRequest } from './graphqlClient';

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
});

describe('gqlRequest 401 interceptor', () => {
  it('calls handleUnauthorized when graphql-request throws a 401', async () => {
    const gqlError = new Error('Unauthorized');
    gqlError.response = { status: 401 };
    requestMock.mockRejectedValue(gqlError);

    const resultPromise = gqlRequest('{ me { id } }');

    const raced = await Promise.race([
      resultPromise.then(() => 'resolved'),
      new Promise((r) => setTimeout(() => r('pending'), 50)),
    ]);

    expect(raced).toBe('pending');
    expect(handleUnauthorizedMock).toHaveBeenCalledOnce();
  });

  it('re-throws non-401 errors without calling handleUnauthorized', async () => {
    const gqlError = new Error('Server error');
    gqlError.response = { status: 500 };
    requestMock.mockRejectedValue(gqlError);

    await expect(gqlRequest('{ me { id } }')).rejects.toThrow('Server error');
    expect(handleUnauthorizedMock).not.toHaveBeenCalled();
  });

  it('re-throws errors without a response property', async () => {
    requestMock.mockRejectedValue(new Error('Network error'));

    await expect(gqlRequest('{ me { id } }')).rejects.toThrow('Network error');
    expect(handleUnauthorizedMock).not.toHaveBeenCalled();
  });

  it('returns data normally on success', async () => {
    const data = { me: { id: 1 } };
    requestMock.mockResolvedValue(data);

    const result = await gqlRequest('{ me { id } }');

    expect(result).toEqual(data);
    expect(handleUnauthorizedMock).not.toHaveBeenCalled();
  });
});
