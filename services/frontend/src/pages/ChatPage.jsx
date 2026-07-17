import { useChatStream } from '../features/chat/hooks/useChatStream';
import ChatInput from '../features/chat/components/ChatInput';
import ChatMessage from '../features/chat/components/ChatMessage';
import ChatStream from '../features/chat/components/ChatStream';
import ChatError from '../features/chat/components/ChatError';
import './ChatPage.css';

const EXAMPLE_QUESTIONS = [
  'Hvad er min største udgift i april 2026?',
  'Hvad brugte jeg hos Netto?',
  'Har jeg brugt penge på restauranter?',
];

function ChatPage() {
  const { state, send, cancel, isStreaming } = useChatStream();
  const isActive = state.phase !== 'idle' && state.phase !== 'done' && state.phase !== 'error';

  return (
    <div className="chat-page">
      <div className="chat-page-header">
        <div className="chat-header-content">
          <h1>Finans Chat</h1>
          <p className="chat-header-subtitle">
            Stil spørgsmål om dine transaktioner — svar fra lokal LLM med streaming
          </p>
        </div>
      </div>

      <section className="chat-examples" aria-label="Eksempelspørgsmål">
        {EXAMPLE_QUESTIONS.map((example) => (
          <button
            key={example}
            type="button"
            className="chat-example-chip"
            onClick={() => send(example)}
            disabled={isStreaming}
          >
            {example}
          </button>
        ))}
      </section>

      {state.phase === 'error' && state.error && (
        <ChatError error={state.error} onRetry={() => send(state.history.at(-1)?.content ?? '')} />
      )}

      <section className="chat-panel" aria-label="Chatbeskeder">
        {state.history.length === 0 && !isActive ? (
          <div className="chat-empty-state">
            <h2>Stil et spørgsmål om din økonomi</h2>
            <p>
              Spørg om forbrug, kategorier, butikker og perioder — dine
              transaktioner er automatisk indekseret.
            </p>
          </div>
        ) : (
          <>
            {state.history.map((message) => (
              <ChatMessage key={message.id} message={message} />
            ))}
            {isActive && (
              <ChatStream
                intent={state.intent}
                data={state.data}
                currentProse={state.currentProse}
              />
            )}
          </>
        )}
      </section>

      <ChatInput
        onSend={send}
        isStreaming={isStreaming}
        onCancel={cancel}
      />
    </div>
  );
}

export default ChatPage;
