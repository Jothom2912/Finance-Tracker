function ChatError({ error, onRetry }) {
  return (
    <div className="chat-error-banner" role="alert">
      <div className="chat-error-banner-content">
        <p className="chat-error-banner-message">{error.message}</p>
        {error.code && (
          <span className="chat-error-banner-code">{error.code}</span>
        )}
      </div>
      <button type="button" className="secondary" onClick={onRetry}>
        Prøv igen
      </button>
    </div>
  );
}

export default ChatError;
