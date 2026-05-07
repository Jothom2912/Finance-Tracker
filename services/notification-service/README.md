# Notification Service (Planned)

**Status: Not yet implemented.**

This service will handle email and push notifications for budget alerts (80% threshold), goal evaluations, and other financial events.

## Planned Port

```
8008
```

## Planned Event Flow

- Listens for `budget.threshold.80pct` events
- Listens for `goal.evaluated` events
- Sends notifications via email/push
