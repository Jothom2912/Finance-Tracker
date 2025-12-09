# Migration Guide: repository/ → repositories/

## 🔄 Hvad er ændret?

Den gamle `repository/` mappe er erstattet med en ny `repositories/` struktur:

**Før:**
```
repository/
├── base_repository.py
├── mysql_repository.py
├── elasticsearch_repository.py
└── __init__.py
```

**Nu:**
```
repositories/
├── base.py
├── mysql/
│   ├── transaction_repository.py
│   ├── category_repository.py
│   └── ...
├── elasticsearch/
│   ├── transaction_repository.py
│   └── category_repository.py
├── neo4j/
│   ├── transaction_repository.py
│   └── ...
└── __init__.py (factory functions)
```

## 📝 Import Ændringer

### Før:
```python
from backend.repository import get_transaction_repository
from backend.repository.base_repository import ITransactionRepository
```

### Nu:
```python
from backend.repositories import get_transaction_repository
from backend.repositories.base import ITransactionRepository
```

## ✅ Hvad virker stadig?

Den gamle `repository/` mappe kan stadig bruges, men anbefales ikke. Alle nye features skal bruge `repositories/`.

## 🚀 Opgradering

1. **Opdater imports:**
   - `backend.repository` → `backend.repositories`
   - `base_repository` → `base`

2. **Brug factory functions:**
   ```python
   from backend.repositories import get_transaction_repository
   repo = get_transaction_repository()
   ```

3. **Skift database:**
   ```bash
   # I .env
   ACTIVE_DB=mysql        # eller elasticsearch eller neo4j
   ```

## 📚 Se også

- `repositories/README.md` - Komplet guide til repository strukturen

