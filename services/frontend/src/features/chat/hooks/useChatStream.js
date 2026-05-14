import { useReducer, useRef, useCallback } from 'react';
import { useMutation } from '@tanstack/react-query';
import { chatReducer, initialState, eventToAction } from '../state/chatReducer';
import { streamChat, AuthError, StreamError } from '../api/streamChat';

const ACTIVE_PHASES = new Set(['routing', 'fetching', 'streaming']);

export function useChatStream() {
  const [state, dispatch] = useReducer(chatReducer, initialState);
  const abortRef = useRef(null);

  const mutation = useMutation({
    mutationFn: async (question) => {
      await streamChat({
        question,
        signal: abortRef.current.signal,
        onEvent: (event) => {
          const action = eventToAction(event);
          if (action) dispatch(action);
          else console.warn('Unknown SSE event type:', event.type);
        },
      });
    },
    onError: (err) => {
      if (err.name === 'AbortError') return;
      if (err instanceof AuthError) return;
      dispatch({
        type: 'STREAM_ERROR',
        payload: {
          code: err instanceof StreamError ? (err.code || `http_${err.status}`) : 'network_error',
          message: err.message,
        },
      });
    },
  });

  const send = useCallback((question) => {
    if (ACTIVE_PHASES.has(state.phase)) return;
    // Synkron dispatch FØR mutate() — TanStack Querys mutationFn kører via microtask,
    // så hvis vi dispatcher derinde, ser UI'en ikke phase-ændringen før næste tick.
    // Synkrone dispatches her giver instant feedback når brugeren klikker send.
    abortRef.current = new AbortController();
    dispatch({ type: 'USER_MESSAGE_SENT', payload: question });
    dispatch({ type: 'STREAM_STARTED' });
    mutation.mutate(question);
  }, [mutation, state.phase]);

  const cancel = useCallback(() => {
    if (!ACTIVE_PHASES.has(state.phase)) return;
    abortRef.current?.abort();
    dispatch({ type: 'STREAM_CANCELLED' });
  }, [state.phase]);

  return {
    state,
    send,
    cancel,
    isStreaming: ACTIVE_PHASES.has(state.phase),
  };
}
