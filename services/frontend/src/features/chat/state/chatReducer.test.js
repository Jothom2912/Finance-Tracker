import { chatReducer, initialState, eventToAction } from './chatReducer';

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;

const INTENT = { name: 'largest_expense', period: '2026-04', slots: {} };
const DATA = { kind: 'single_value', payload: { value: 288.0, currency: 'kr', label: 'Største udgift' } };
const METADATA = { router_ms: 142.3, dispatch_ms: 89.5, responder_ms: 1205.7, total_tokens: 47 };
const ERROR = { code: 'service_unavailable', message: 'Ollama er nede' };

function applyActions(actions) {
  return actions.reduce(chatReducer, initialState);
}

describe('chatReducer', () => {
  describe('USER_MESSAGE_SENT', () => {
    it('adds user message to history from idle', () => {
      const state = chatReducer(initialState, { type: 'USER_MESSAGE_SENT', payload: 'Hej' });
      expect(state.history).toHaveLength(1);
      expect(state.history[0]).toMatchObject({ role: 'user', content: 'Hej' });
      expect(state.history[0].id).toMatch(UUID_PATTERN);
    });

    it('adds user message even during active phases', () => {
      const routing = chatReducer(initialState, { type: 'STREAM_STARTED' });
      const state = chatReducer(routing, { type: 'USER_MESSAGE_SENT', payload: 'Mere' });
      expect(state.history).toHaveLength(1);
      expect(state.history[0].content).toBe('Mere');
    });
  });

  describe('STREAM_STARTED', () => {
    it('transitions idle → routing', () => {
      const state = chatReducer(initialState, { type: 'STREAM_STARTED' });
      expect(state.phase).toBe('routing');
      expect(state.intent).toBeNull();
      expect(state.data).toBeNull();
      expect(state.currentProse).toBe('');
      expect(state.messageId).toBeNull();
      expect(state.metadata).toBeNull();
      expect(state.error).toBeNull();
    });

    it('transitions done → routing and clears previous metadata', () => {
      const done = applyActions([
        { type: 'STREAM_STARTED' },
        { type: 'INTENT_RESOLVED', payload: INTENT },
        { type: 'PROSE_CHUNK', payload: 'Svar' },
        { type: 'STREAM_DONE', payload: { metadata: METADATA } },
      ]);
      expect(done.phase).toBe('done');
      expect(done.metadata).toEqual(METADATA);

      const state = chatReducer(done, { type: 'STREAM_STARTED' });
      expect(state.phase).toBe('routing');
      expect(state.metadata).toBeNull();
      expect(state.messageId).toBeNull();
      expect(state.history).toBe(done.history);
    });

    it('transitions error → routing and clears error', () => {
      const errored = applyActions([
        { type: 'STREAM_STARTED' },
        { type: 'STREAM_ERROR', payload: ERROR },
      ]);
      expect(errored.phase).toBe('error');
      expect(errored.error).toEqual(ERROR);

      const state = chatReducer(errored, { type: 'STREAM_STARTED' });
      expect(state.phase).toBe('routing');
      expect(state.error).toBeNull();
    });

    it('rejects transition from active phase', () => {
      const routing = chatReducer(initialState, { type: 'STREAM_STARTED' });
      const state = chatReducer(routing, { type: 'STREAM_STARTED' });
      expect(state).toBe(routing);
    });
  });

  describe('INTENT_RESOLVED', () => {
    it('transitions routing → fetching and sets intent', () => {
      const routing = chatReducer(initialState, { type: 'STREAM_STARTED' });
      const state = chatReducer(routing, { type: 'INTENT_RESOLVED', payload: INTENT });
      expect(state.phase).toBe('fetching');
      expect(state.intent).toEqual(INTENT);
    });

    it('rejects transition from non-routing phase', () => {
      const state = chatReducer(initialState, { type: 'INTENT_RESOLVED', payload: INTENT });
      expect(state).toBe(initialState);
    });
  });

  describe('DATA_READY', () => {
    it('sets data and stays in fetching', () => {
      const fetching = applyActions([
        { type: 'STREAM_STARTED' },
        { type: 'INTENT_RESOLVED', payload: INTENT },
      ]);
      const state = chatReducer(fetching, { type: 'DATA_READY', payload: DATA });
      expect(state.phase).toBe('fetching');
      expect(state.data).toEqual(DATA);
    });

    it('rejects transition from non-fetching phase', () => {
      const routing = chatReducer(initialState, { type: 'STREAM_STARTED' });
      const state = chatReducer(routing, { type: 'DATA_READY', payload: DATA });
      expect(state).toBe(routing);
    });
  });

  describe('PROSE_CHUNK', () => {
    it('transitions fetching → streaming on first chunk', () => {
      const fetching = applyActions([
        { type: 'STREAM_STARTED' },
        { type: 'INTENT_RESOLVED', payload: INTENT },
      ]);
      const state = chatReducer(fetching, { type: 'PROSE_CHUNK', payload: 'Din ' });
      expect(state.phase).toBe('streaming');
      expect(state.currentProse).toBe('Din ');
    });

    it('accumulates chunks in streaming phase', () => {
      const streaming = applyActions([
        { type: 'STREAM_STARTED' },
        { type: 'INTENT_RESOLVED', payload: INTENT },
        { type: 'PROSE_CHUNK', payload: 'Din ' },
      ]);
      const state = chatReducer(streaming, { type: 'PROSE_CHUNK', payload: 'største' });
      expect(state.phase).toBe('streaming');
      expect(state.currentProse).toBe('Din største');
    });

    it('rejects transition from idle', () => {
      const state = chatReducer(initialState, { type: 'PROSE_CHUNK', payload: 'x' });
      expect(state).toBe(initialState);
    });

    it('rejects transition from routing', () => {
      const routing = chatReducer(initialState, { type: 'STREAM_STARTED' });
      const state = chatReducer(routing, { type: 'PROSE_CHUNK', payload: 'x' });
      expect(state).toBe(routing);
    });
  });

  describe('STREAM_DONE', () => {
    it('archives message with intent, data, metadata and clears transient state', () => {
      const streaming = applyActions([
        { type: 'USER_MESSAGE_SENT', payload: 'Spørgsmål' },
        { type: 'STREAM_STARTED' },
        { type: 'INTENT_RESOLVED', payload: INTENT },
        { type: 'DATA_READY', payload: DATA },
        { type: 'PROSE_CHUNK', payload: 'Din største udgift' },
      ]);
      const state = chatReducer(streaming, { type: 'STREAM_DONE', payload: { metadata: METADATA } });

      expect(state.phase).toBe('done');
      expect(state.messageId).toMatch(UUID_PATTERN);
      expect(state.metadata).toEqual(METADATA);

      // transient fields cleared at top level
      expect(state.intent).toBeNull();
      expect(state.data).toBeNull();
      expect(state.currentProse).toBe('');

      // but preserved on the archived message
      const archived = state.history[1];
      expect(archived.role).toBe('assistant');
      expect(archived.content).toBe('Din største udgift');
      expect(archived.intent).toEqual(INTENT);
      expect(archived.data).toEqual(DATA);
      expect(archived.metadata).toEqual(METADATA);
      expect(archived.id).toBe(state.messageId);
    });

    it('works from fetching (zero prose chunks)', () => {
      const fetching = applyActions([
        { type: 'STREAM_STARTED' },
        { type: 'INTENT_RESOLVED', payload: INTENT },
        { type: 'DATA_READY', payload: DATA },
      ]);
      const state = chatReducer(fetching, { type: 'STREAM_DONE', payload: { metadata: METADATA } });
      expect(state.phase).toBe('done');
      expect(state.history).toHaveLength(1);
      expect(state.history[0].content).toBe('');
    });

    it('rejects transition from idle', () => {
      const state = chatReducer(initialState, { type: 'STREAM_DONE', payload: { metadata: METADATA } });
      expect(state).toBe(initialState);
    });

    it('rejects transition from routing', () => {
      const routing = chatReducer(initialState, { type: 'STREAM_STARTED' });
      const state = chatReducer(routing, { type: 'STREAM_DONE', payload: { metadata: METADATA } });
      expect(state).toBe(routing);
    });
  });

  describe('STREAM_ERROR', () => {
    it('transitions active phase → error', () => {
      const streaming = applyActions([
        { type: 'STREAM_STARTED' },
        { type: 'INTENT_RESOLVED', payload: INTENT },
        { type: 'PROSE_CHUNK', payload: 'partial' },
      ]);
      const state = chatReducer(streaming, { type: 'STREAM_ERROR', payload: ERROR });
      expect(state.phase).toBe('error');
      expect(state.error).toEqual(ERROR);
    });

    it('works from routing', () => {
      const routing = chatReducer(initialState, { type: 'STREAM_STARTED' });
      const state = chatReducer(routing, { type: 'STREAM_ERROR', payload: ERROR });
      expect(state.phase).toBe('error');
    });

    it('works from fetching', () => {
      const fetching = applyActions([
        { type: 'STREAM_STARTED' },
        { type: 'INTENT_RESOLVED', payload: INTENT },
      ]);
      const state = chatReducer(fetching, { type: 'STREAM_ERROR', payload: ERROR });
      expect(state.phase).toBe('error');
    });

    it('rejects transition from idle', () => {
      const state = chatReducer(initialState, { type: 'STREAM_ERROR', payload: ERROR });
      expect(state).toBe(initialState);
    });

    it('rejects transition from done', () => {
      const done = applyActions([
        { type: 'STREAM_STARTED' },
        { type: 'INTENT_RESOLVED', payload: INTENT },
        { type: 'PROSE_CHUNK', payload: 'text' },
        { type: 'STREAM_DONE', payload: { metadata: METADATA } },
      ]);
      const state = chatReducer(done, { type: 'STREAM_ERROR', payload: ERROR });
      expect(state).toBe(done);
    });

    it('rejects transition from error', () => {
      const errored = applyActions([
        { type: 'STREAM_STARTED' },
        { type: 'STREAM_ERROR', payload: ERROR },
      ]);
      const state = chatReducer(errored, { type: 'STREAM_ERROR', payload: ERROR });
      expect(state).toBe(errored);
    });
  });

  describe('STREAM_CANCELLED', () => {
    it('preserves partial message with cancelled flag in history', () => {
      const streaming = applyActions([
        { type: 'USER_MESSAGE_SENT', payload: 'Spørgsmål' },
        { type: 'STREAM_STARTED' },
        { type: 'INTENT_RESOLVED', payload: INTENT },
        { type: 'PROSE_CHUNK', payload: 'partial text' },
      ]);
      const state = chatReducer(streaming, { type: 'STREAM_CANCELLED' });
      expect(state.phase).toBe('idle');
      expect(state.history).toHaveLength(2);

      const partial = state.history[1];
      expect(partial.role).toBe('assistant');
      expect(partial.content).toBe('partial text');
      expect(partial.intent).toEqual(INTENT);
      expect(partial.cancelled).toBe(true);
      expect(partial.metadata).toBeNull();
      expect(partial.id).toMatch(UUID_PATTERN);
    });

    it('preserves intent-only partial (no prose yet)', () => {
      const fetching = applyActions([
        { type: 'STREAM_STARTED' },
        { type: 'INTENT_RESOLVED', payload: INTENT },
      ]);
      const state = chatReducer(fetching, { type: 'STREAM_CANCELLED' });
      expect(state.phase).toBe('idle');
      expect(state.history).toHaveLength(1);
      expect(state.history[0].cancelled).toBe(true);
      expect(state.history[0].intent).toEqual(INTENT);
    });

    it('does not add message when no partial content exists', () => {
      const routing = chatReducer(initialState, { type: 'STREAM_STARTED' });
      const state = chatReducer(routing, { type: 'STREAM_CANCELLED' });
      expect(state.phase).toBe('idle');
      expect(state.history).toHaveLength(0);
    });

    it('returns unchanged state from idle', () => {
      const state = chatReducer(initialState, { type: 'STREAM_CANCELLED' });
      expect(state).toBe(initialState);
    });

    it('returns unchanged state from done', () => {
      const done = applyActions([
        { type: 'STREAM_STARTED' },
        { type: 'INTENT_RESOLVED', payload: INTENT },
        { type: 'PROSE_CHUNK', payload: 'text' },
        { type: 'STREAM_DONE', payload: { metadata: METADATA } },
      ]);
      const state = chatReducer(done, { type: 'STREAM_CANCELLED' });
      expect(state).toBe(done);
    });

    it('returns unchanged state from error', () => {
      const errored = applyActions([
        { type: 'STREAM_STARTED' },
        { type: 'STREAM_ERROR', payload: ERROR },
      ]);
      const state = chatReducer(errored, { type: 'STREAM_CANCELLED' });
      expect(state).toBe(errored);
    });
  });

  describe('RESET', () => {
    it('resets to idle but preserves history by reference', () => {
      const done = applyActions([
        { type: 'USER_MESSAGE_SENT', payload: 'Spørgsmål' },
        { type: 'STREAM_STARTED' },
        { type: 'INTENT_RESOLVED', payload: INTENT },
        { type: 'PROSE_CHUNK', payload: 'Svar' },
        { type: 'STREAM_DONE', payload: { metadata: METADATA } },
      ]);
      const state = chatReducer(done, { type: 'RESET' });
      expect(state.phase).toBe('idle');
      expect(state.intent).toBeNull();
      expect(state.error).toBeNull();
      // .toBe checks reference identity — history array is reused, not copied
      expect(state.history).toBe(done.history);
    });
  });

  describe('unknown action', () => {
    it('returns state unchanged without throwing', () => {
      const state = chatReducer(initialState, { type: 'NONSENSE' });
      expect(state).toBe(initialState);
    });
  });

  describe('immutability', () => {
    it('does not mutate the input state', () => {
      const before = applyActions([
        { type: 'USER_MESSAGE_SENT', payload: 'Hej' },
        { type: 'STREAM_STARTED' },
        { type: 'INTENT_RESOLVED', payload: INTENT },
        { type: 'DATA_READY', payload: DATA },
        { type: 'PROSE_CHUNK', payload: 'Din ' },
      ]);
      const snapshot = JSON.parse(JSON.stringify(before));

      chatReducer(before, { type: 'PROSE_CHUNK', payload: 'største' });
      chatReducer(before, { type: 'STREAM_DONE', payload: { metadata: METADATA } });
      chatReducer(before, { type: 'STREAM_ERROR', payload: ERROR });
      chatReducer(before, { type: 'STREAM_CANCELLED' });
      chatReducer(before, { type: 'RESET' });

      expect(before).toEqual(snapshot);
    });
  });
});

describe('eventToAction', () => {
  it('maps intent_resolved → INTENT_RESOLVED with name/period/slots', () => {
    const action = eventToAction({
      type: 'intent_resolved',
      data: { intent: 'largest_expense', period: '2026-04', slots: { category: 'mad' } },
    });
    expect(action).toEqual({
      type: 'INTENT_RESOLVED',
      payload: { name: 'largest_expense', period: '2026-04', slots: { category: 'mad' } },
    });
  });

  it('maps data_ready → DATA_READY', () => {
    const action = eventToAction({ type: 'data_ready', data: DATA });
    expect(action).toEqual({ type: 'DATA_READY', payload: DATA });
  });

  it('maps prose_chunk → PROSE_CHUNK with delta as payload', () => {
    const action = eventToAction({ type: 'prose_chunk', data: { delta: 'token' } });
    expect(action).toEqual({ type: 'PROSE_CHUNK', payload: 'token' });
  });

  it('maps done → STREAM_DONE with metadata', () => {
    const action = eventToAction({ type: 'done', data: { metadata: METADATA } });
    expect(action).toEqual({ type: 'STREAM_DONE', payload: { metadata: METADATA } });
  });

  it('maps error → STREAM_ERROR', () => {
    const action = eventToAction({ type: 'error', data: ERROR });
    expect(action).toEqual({ type: 'STREAM_ERROR', payload: ERROR });
  });

  it('returns null for unknown event type', () => {
    const action = eventToAction({ type: 'heartbeat', data: {} });
    expect(action).toBeNull();
  });
});
