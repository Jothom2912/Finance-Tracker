import { useState, useMemo } from 'react';

function ChatInput({ onSend, isStreaming, isDisabled, onCancel }) {
  const [question, setQuestion] = useState('');

  const canSubmit = useMemo(
    () => question.trim().length > 0 && !isStreaming && !isDisabled,
    [question, isStreaming, isDisabled],
  );

  const handleSubmit = (event) => {
    event.preventDefault();
    const trimmed = question.trim();
    if (!trimmed || !canSubmit) return;
    onSend(trimmed);
    setQuestion('');
  };

  return (
    <form className="chat-form" onSubmit={handleSubmit}>
      <label htmlFor="finance-question">Spørgsmål</label>
      <div className="chat-input-row">
        <textarea
          id="finance-question"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              if (canSubmit) handleSubmit(e);
            }
          }}
          placeholder="Stil et spørgsmål om dine transaktioner..."
          rows={1}
          disabled={isStreaming || isDisabled}
        />
        {isStreaming && onCancel ? (
          <button type="button" className="chat-cancel-btn" onClick={onCancel}>
            Annullér
          </button>
        ) : (
          <button type="submit" disabled={!canSubmit}>
            {isStreaming ? 'Genererer...' : 'Send'}
          </button>
        )}
      </div>
    </form>
  );
}

export default ChatInput;
