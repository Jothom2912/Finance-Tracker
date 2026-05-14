import IntentBadge from './IntentBadge';

function ChatStream({ intent, data, currentProse }) {
  return (
    <article className="chat-message assistant chat-streaming" aria-live="polite">
      {intent && <IntentBadge intent={intent} />}
      {/* TODO PR 3: erstat JSON-stub med DataPanel-dispatcher når kind-værdier er verificeret */}
      {data && (
        <pre className="chat-data-stub">{JSON.stringify(data, null, 2)}</pre>
      )}
      <p>{currentProse}<span className="chat-cursor" aria-hidden="true" /></p>
    </article>
  );
}

export default ChatStream;
