function MessageMetadata({ metadata }) {
  if (!metadata) return null;

  const entries = Object.entries(metadata);
  if (entries.length === 0) return null;

  return (
    <details className="chat-metadata">
      <summary>Pipeline metadata</summary>
      <dl className="chat-metadata-list">
        {entries.map(([key, value]) => (
          <div key={key} className="chat-metadata-entry">
            <dt>{key}</dt>
            <dd>{typeof value === 'number' ? value.toFixed(1) : String(value)}</dd>
          </div>
        ))}
      </dl>
    </details>
  );
}

export default MessageMetadata;
