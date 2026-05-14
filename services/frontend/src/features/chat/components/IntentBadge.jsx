function IntentBadge({ intent }) {
  if (!intent) return null;

  const details = [
    intent.period && `periode: ${intent.period}`,
    intent.slots && Object.keys(intent.slots).length > 0 &&
      Object.entries(intent.slots).map(([k, v]) => `${k}: ${v}`).join(', '),
  ].filter(Boolean).join(' · ');

  return (
    <span className="intent-badge" title={details || undefined}>
      {intent.name}
    </span>
  );
}

export default IntentBadge;
