import { useEffect, useMemo, useRef, useState } from 'react';
import { askFinanceQuestion, ingestTransactionsForRag } from '../api/ai';
import './ChatPage.css';

const EXAMPLE_QUESTIONS = [
  'Hvad er min største udgift i april 2026?',
  'Hvad brugte jeg hos Netto?',
  'Har jeg brugt penge på restauranter?',
];

const LOADING_STEPS = [
  'Henter relevante transaktioner...',
  'Bygger prompt med 4T\'s skabelon...',
  'Lokal LLM genererer svar — dette kan tage 30-60 sekunder...',
];
const STEP_INTERVAL_MS = 4000;

function ChatPage() {
  const [question, setQuestion] = useState('');
  const [messages, setMessages] = useState([]);
  const [isAsking, setIsAsking] = useState(false);
  const [isIngesting, setIsIngesting] = useState(false);
  const [hasIngested, setHasIngested] = useState(
    () => localStorage.getItem('rag_ingested') === 'true',
  );
  const [statusMessage, setStatusMessage] = useState('');
  const [error, setError] = useState('');

  const canSubmit = useMemo(
    () => question.trim().length > 0 && !isAsking,
    [question, isAsking],
  );

  const handleIngest = async () => {
    setError('');
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
      setError(err.message || 'Kunne ikke opdatere vidensbasen.');
    } finally {
      setIsIngesting(false);
    }
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    const trimmed = question.trim();
    if (!trimmed) return;

    const userMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content: trimmed,
    };

    setMessages((current) => [...current, userMessage]);
    setQuestion('');
    setError('');
    setStatusMessage('');
    setIsAsking(true);

    try {
      const response = await askFinanceQuestion(trimmed);
      setMessages((current) => [
        ...current,
        {
          id: crypto.randomUUID(),
          role: 'assistant',
          content: response.answer,
          sources: response.sources || [],
          sourceCount: response.source_count || 0,
        },
      ]);
    } catch (err) {
      setError(err.message || 'Kunne ikke hente svar fra AI-servicen.');
    } finally {
      setIsAsking(false);
    }
  };

  const applyExample = (example) => {
    setQuestion(example);
  };

  return (
    <div className="chat-page">
      <div className="chat-page-header">
        <div className="chat-header-content">
          <h1>Finans Chat</h1>
          <p className="chat-header-subtitle">
            Stil spørgsmål om dine transaktioner — svar fra lokal LLM og RAG
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
            onClick={() => applyExample(example)}
          >
            {example}
          </button>
        ))}
      </section>

      {statusMessage && <p className="chat-status">{statusMessage}</p>}
      {error && <p className="chat-error">{error}</p>}

      {!hasIngested && messages.length === 0 && !isIngesting && (
        <p className="chat-ingest-hint">
          Vidensbasen er tom. Tryk <strong>Opdater vidensbase</strong> for at
          indeksere dine transaktioner, før du stiller spørgsmål.
        </p>
      )}

      <section className="chat-panel" aria-label="Chatbeskeder">
        {messages.length === 0 ? (
          <div className="chat-empty-state">
            <h2>Start med at opdatere vidensbasen</h2>
            <p>
              Når transaktionerne er indlæst, kan du spørge om forbrug, kategorier,
              butikker og perioder.
            </p>
          </div>
        ) : (
          messages.map((message) => (
            <ChatMessage key={message.id} message={message} />
          ))
        )}
        {isAsking && <LoadingIndicator />}
      </section>

      <form className="chat-form" onSubmit={handleSubmit}>
        <label htmlFor="finance-question">Spørgsmål</label>
        <div className="chat-input-row">
          <textarea
            id="finance-question"
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault();
                if (canSubmit) handleSubmit(event);
              }
            }}
            placeholder="Stil et spørgsmål om dine transaktioner..."
            rows={1}
            disabled={isAsking}
          />
          <button type="submit" disabled={!canSubmit}>
            {isAsking ? 'Genererer...' : 'Send'}
          </button>
        </div>
      </form>
    </div>
  );
}

function ChatMessage({ message }) {
  return (
    <article className={`chat-message ${message.role}`}>
      <p>{message.content}</p>
      {message.role === 'assistant' && message.sources?.length > 0 && (
        <details className="chat-sources">
          <summary>Baseret på {message.sourceCount} transaktioner</summary>
          <ul>
            {message.sources.map((source) => (
              <li key={`${source.transaction_id}-${source.date}-${source.distance}`}>
                <span>{source.date}</span>
                <span>{formatAmount(source.amount)} kr</span>
                <span>{source.category || 'Ukategoriseret'}</span>
                <span>{source.description || 'Ingen tekst'}</span>
              </li>
            ))}
          </ul>
        </details>
      )}
    </article>
  );
}

function LoadingIndicator() {
  const [step, setStep] = useState(0);
  const timerRef = useRef(null);

  useEffect(() => {
    timerRef.current = setInterval(() => {
      setStep((prev) => Math.min(prev + 1, LOADING_STEPS.length - 1));
    }, STEP_INTERVAL_MS);
    return () => clearInterval(timerRef.current);
  }, []);

  return (
    <div className="chat-message assistant chat-loading" aria-live="polite">
      <div className="chat-loading-dots" aria-hidden="true">
        <span /><span /><span />
      </div>
      <p>{LOADING_STEPS[step]}</p>
    </div>
  );
}

function formatAmount(amount) {
  if (typeof amount !== 'number') return '-';
  return new Intl.NumberFormat('da-DK', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(amount);
}

export default ChatPage;
