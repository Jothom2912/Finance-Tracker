import { fetchEventSource } from '@microsoft/fetch-event-source';
import { AI_SERVICE_URL } from '../../../config/serviceUrls';
import { handleUnauthorized } from '../../../utils/handleUnauthorized';

export class AuthError extends Error {
  constructor(message = 'Authentication required') {
    super(message);
    this.name = 'AuthError';
  }
}

export class StreamError extends Error {
  constructor({ status, body, code, message }) {
    super(message ?? `Stream failed: ${code ?? status}`);
    this.name = 'StreamError';
    this.status = status;
    this.body = body;
    this.code = code;
  }
}

export async function streamChat({ question, onEvent, signal }) {
  const token = localStorage.getItem('access_token');
  const accountId = localStorage.getItem('account_id');
  if (!token || !accountId) throw new AuthError();

  let doneReceived = false;
  let closeError = null;

  await fetchEventSource(`${AI_SERVICE_URL}/chat/stream`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'X-Account-ID': accountId,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ question }),
    signal,
    openWhenHidden: true,

    async onopen(response) {
      if (response.ok) return;
      if (response.status === 401) {
        handleUnauthorized();
        throw new AuthError();
      }
      const body = await response.text();
      throw new StreamError({ status: response.status, body });
    },

    onmessage(ev) {
      // sse-starlette sender ping-comments (": ping - <ts>") som keepalive.
      // @microsoft/fetch-event-source fyrer onmessage for disse med tom data
      // i stedet for at filtrere dem som spec'en kræver. Vi skipper tomme
      // events her — det er IKKE den oprindelige fail-loud-strategi, men
      // det er nødvendigt for at coexistere med standard SSE-keepalives.
      if (!ev.data) return;
      if (ev.event === 'done') doneReceived = true;
      onEvent({ type: ev.event, data: JSON.parse(ev.data) });
    },

    onclose() {
      if (!doneReceived) {
        closeError = new StreamError({
          code: 'incomplete_stream',
          message: 'Stream closed without done event',
        });
      }
    },

    onerror(err) {
      throw err;
    },
  });

  if (closeError) throw closeError;
}
