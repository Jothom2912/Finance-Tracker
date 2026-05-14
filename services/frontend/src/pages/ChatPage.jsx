import { useState } from 'react';
import { ingestTransactionsForRag } from '../api/ai';
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

  const [isIngesting, setIsIngesting] = useState(false);
  const [hasIngested, setHasIngested] = useState(
    () => localStorage.getItem('rag_ingested') === 'true',
  );
  const [statusMessage, setStatusMessage] = useState('');
  const [ingestError, setIngestError] = useState('');

  const handleIngest = async () => {
    setIngestError('');
    setStatusMessage('');
    setIsIngesting(true);
    try {
      const result = await ingestTransactionsForRag();
      setHasIngested(true);
      localStorage.setItem('rag_ingested', 'true');
      setStatusMessage(
        `Vidensbasen er opdateret med ${result.transactions_ingested} transaktioner.`,
      );
    } catch (err) {
      setIngestError(err.message || 'Kunne ikke opdatere vidensbasen.');
    } finally {
      setIsIngesting(false);
    }
  };

  return (
    <div className="chat-page">
      <div className="chat-page-header">
        <div className="chat-header-content">
          <h1>Finans Chat</h1>
          <p className="chat-header-subtitle">
            Stil spørgsmål om dine transaktioner — svar fra lokal LLM med streaming
          </p>
        </div>
        <button
          type="button"
          className="secondary"
          onClick={handleIngest}
          disabled={isIngesting}
        >
          {isIngesting ? 'Opdaterer...' : 'Opdater vidensbase'}
        </button>
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

      {statusMessage && <p className="chat-status">{statusMessage}</p>}
      {ingestError && <p className="chat-error">{ingestError}</p>}

      {state.phase === 'error' && state.error && (
        <ChatError error={state.error} onRetry={() => send(state.history.at(-1)?.content ?? '')} />
      )}

      {!hasIngested && state.history.length === 0 && !isIngesting && (
        <p className="chat-ingest-hint">
          Vidensbasen er tom. Tryk <strong>Opdater vidensbase</strong> for at
          indeksere dine transaktioner, før du stiller spørgsmål.
        </p>
      )}

      <section className="chat-panel" aria-label="Chatbeskeder">
        {state.history.length === 0 && !isActive ? (
          <div className="chat-empty-state">
            <h2>Start med at opdatere vidensbasen</h2>
            <p>
              Når transaktionerne er indlæst, kan du spørge om forbrug, kategorier,
              butikker og perioder.
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
