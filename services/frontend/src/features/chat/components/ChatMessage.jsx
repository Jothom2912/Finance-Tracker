import IntentBadge from './IntentBadge';
import MessageMetadata from './MessageMetadata';

function ChatMessage({ message }) {
  const isAssistant = message.role === 'assistant';

  return (
    <article className={`chat-message ${message.role}`}>
      {isAssistant && message.intent && <IntentBadge intent={message.intent} />}
      <p>{message.content}</p>
      {/* TODO PR 3: erstat JSON-stub med DataPanel-dispatcher når kind-værdier er verificeret */}
      {isAssistant && message.data && (
        <pre className="chat-data-stub">{JSON.stringify(message.data, null, 2)}</pre>
      )}
      {isAssistant && message.cancelled && (
        <span className="chat-cancelled-tag">Afbrudt</span>
      )}
      {isAssistant && <MessageMetadata metadata={message.metadata} />}
    </article>
  );
}

export default ChatMessage;
