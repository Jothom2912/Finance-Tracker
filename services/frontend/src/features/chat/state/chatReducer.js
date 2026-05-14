export const initialState = {
  phase: 'idle',
  intent: null,
  data: null,
  currentProse: '',
  messageId: null,
  metadata: null,
  error: null,
  history: [],
};

const ACTIVE_PHASES = new Set(['routing', 'fetching', 'streaming']);
const STARTABLE_PHASES = new Set(['idle', 'done', 'error']);

export function chatReducer(state, action) {
  switch (action.type) {
    case 'USER_MESSAGE_SENT':
      return {
        ...state,
        history: [
          ...state.history,
          { id: crypto.randomUUID(), role: 'user', content: action.payload },
        ],
      };

    case 'STREAM_STARTED': {
      if (!STARTABLE_PHASES.has(state.phase)) return state;
      return {
        ...state,
        phase: 'routing',
        intent: null,
        data: null,
        currentProse: '',
        messageId: null,
        metadata: null,
        error: null,
      };
    }

    // 'fetching' covers both "dispatcher is fetching data" and "waiting for
    // first prose token from responder" — intents without data still pass
    // through fetching until the first PROSE_CHUNK arrives.
    case 'INTENT_RESOLVED': {
      if (state.phase !== 'routing') return state;
      return { ...state, phase: 'fetching', intent: action.payload };
    }

    case 'DATA_READY': {
      if (state.phase !== 'fetching') return state;
      return { ...state, data: action.payload };
    }

    case 'PROSE_CHUNK': {
      if (state.phase !== 'fetching' && state.phase !== 'streaming') return state;
      return {
        ...state,
        phase: 'streaming',
        currentProse: state.currentProse + action.payload,
      };
    }

    case 'STREAM_DONE': {
      if (state.phase !== 'fetching' && state.phase !== 'streaming') return state;
      const messageId = crypto.randomUUID();
      const metadata = action.payload?.metadata ?? null;
      return {
        ...state,
        phase: 'done',
        messageId,
        metadata,
        currentProse: '',
        intent: null,
        data: null,
        history: [
          ...state.history,
          {
            id: messageId,
            role: 'assistant',
            content: state.currentProse,
            intent: state.intent,
            data: state.data,
            metadata,
          },
        ],
      };
    }

    case 'STREAM_ERROR': {
      if (!ACTIVE_PHASES.has(state.phase)) return state;
      return { ...state, phase: 'error', error: action.payload };
    }

    case 'STREAM_CANCELLED': {
      if (!ACTIVE_PHASES.has(state.phase)) return state;
      const hasPartial = !!(state.currentProse || state.intent || state.data);
      const partialMessage = hasPartial
        ? {
            id: crypto.randomUUID(),
            role: 'assistant',
            content: state.currentProse,
            intent: state.intent,
            data: state.data,
            metadata: null,
            cancelled: true,
          }
        : null;
      return {
        ...initialState,
        history: partialMessage
          ? [...state.history, partialMessage]
          : state.history,
      };
    }

    case 'RESET':
      return { ...initialState, history: state.history };

    default:
      return state;
  }
}

export function eventToAction(event) {
  switch (event.type) {
    case 'intent_resolved':
      return {
        type: 'INTENT_RESOLVED',
        payload: {
          name: event.data.intent,
          period: event.data.period,
          slots: event.data.slots,
        },
      };
    case 'data_ready':
      return { type: 'DATA_READY', payload: event.data };
    case 'prose_chunk':
      return { type: 'PROSE_CHUNK', payload: event.data.delta };
    case 'done':
      return { type: 'STREAM_DONE', payload: event.data };
    case 'error':
      return { type: 'STREAM_ERROR', payload: event.data };
    default:
      return null;
  }
}
