# Database Sammenligning: MySQL vs Elasticsearch vs Neo4j

## 📊 Oversigt

Dette projekt bruger 3 forskellige databaser, hver med deres eget formål:

| Database | Type | Port | Formål | Styrker |
|----------|------|------|--------|---------|
| **MySQL** | Relational (SQL) | 3307 | Primær database | ACID, strukturerede data, joins |
| **Elasticsearch** | Document (NoSQL) | 9200 | Søgning & Analytics | Full-text søgning, aggregations, hurtig søgning |
| **Neo4j** | Graph (NoSQL) | 7687 | Graph queries & relationships | Relationship queries, graph visualisering |

---

## 🗄️ MySQL (Relational Database)

### Hvad er det?
- **Relational database** - Data gemmes i tabeller med kolonner og rækker
- **SQL** - Bruger SQL queries til at hente data
- **ACID** - Garanterer data integritet (Atomicity, Consistency, Isolation, Durability)

### Struktur
```
User (idUser, username, email)
  ↓ (1:N)
Account (idAccount, name, User_idUser)
  ↓ (1:N)
Transaction (idTransaction, amount, Account_idAccount, Category_idCategory)
```

### Hvornår bruges det?
- ✅ Primær database for alle CRUD operationer
- ✅ Strukturerede data med klare relationer
- ✅ Transaktioner og data integritet
- ✅ Standard REST API endpoints

### Eksempel Query
```sql
SELECT t.*, c.name as category_name, a.name as account_name
FROM Transaction t
JOIN Category c ON t.Category_idCategory = c.idCategory
JOIN Account a ON t.Account_idAccount = a.idAccount
WHERE t.date >= '2024-01-01'
```

### Styrker
- ✅ ACID compliance (data integritet)
- ✅ Komplekse joins mellem tabeller
- ✅ Transaktioner (rollback ved fejl)
- ✅ Mature og veldokumenteret

### Svagheder
- ❌ Ikke optimal til full-text søgning
- ❌ Kan være langsom ved komplekse queries
- ❌ Skal kende strukturen på forhånd

---

## 🔍 Elasticsearch (Document Database)

### Hvad er det?
- **Document database** - Data gemmes som JSON dokumenter
- **NoSQL** - Ingen fast struktur, fleksibel schema
- **Search engine** - Bygget til søgning og analytics

### Struktur
```
Index: "transactions"
Document: {
  "idTransaction": 1,
  "amount": -500.00,
  "description": "Netto køb",
  "date": "2024-12-15",
  "category_name": "Mad & Drikke",
  "account_name": "Min privat"
}
```

### Hvornår bruges det?
- ✅ Full-text søgning i beskrivelser
- ✅ Analytics og aggregations (f.eks. "udgifter pr. kategori")
- ✅ Fuzzy matching (find "neto" når du søger "netto")
- ✅ Hurtig søgning i store datasæt

### Eksempel Query
```json
{
  "query": {
    "multi_match": {
      "query": "netto",
      "fields": ["description", "name"],
      "fuzziness": "AUTO"
    }
  },
  "aggs": {
    "by_category": {
      "terms": {"field": "category_name"},
      "aggs": {"total": {"sum": {"field": "amount"}}}
    }
  }
}
```

### Styrker
- ✅ Ekstremt hurtig søgning
- ✅ Full-text søgning med fuzzy matching
- ✅ Aggregations og analytics
- ✅ Skalerbar til store datasæt

### Svagheder
- ❌ Ikke ACID (eventual consistency)
- ❌ Ikke optimal til komplekse joins
- ❌ Mere kompleks end SQL

---

## 🕸️ Neo4j (Graph Database)

### Hvad er det?
- **Graph database** - Data gemmes som nodes og relationships
- **NoSQL** - Ingen tabeller, kun nodes og edges
- **Cypher** - Eget query sprog til graph queries

### Struktur
```
(User)-[:OWNS]->(Account)-[:HAS_TRANSACTION]->(Transaction)-[:BELONGS_TO_CATEGORY]->(Category)
```

### Hvornår bruges det?
- ✅ Graph queries (f.eks. "find alle transaktioner for en bruger gennem deres konti")
- ✅ Relationship analysis
- ✅ Graph visualisering
- ✅ GraphQL API

### Eksempel Query (Cypher)
```cypher
MATCH (u:User {username: "johan"})-[:OWNS]->(a:Account)-[:HAS_TRANSACTION]->(t:Transaction)
WHERE t.date >= date('2024-01-01')
RETURN t, a, u
ORDER BY t.date DESC
```

### Styrker
- ✅ Perfekt til relationship queries
- ✅ Visuelt (kan visualisere relationships)
- ✅ Hurtig ved komplekse graph traversals
- ✅ GraphQL integration

### Svagheder
- ❌ Ikke optimal til simple CRUD
- ❌ Mindre mature end SQL databaser
- ❌ Kræver anden tænkemåde (graph vs relational)

---

## 🔄 Sammenligning

### Data Struktur

| Feature | MySQL | Elasticsearch | Neo4j |
|---------|-------|---------------|-------|
| **Struktur** | Tabeller (rows/columns) | Dokumenter (JSON) | Nodes & Relationships |
| **Schema** | Fast (defineret på forhånd) | Fleksibel (dynamic mapping) | Ingen (nodes har properties) |
| **Relationships** | Foreign keys | Ingen (flattened data) | Native relationships |

### Query Sprog

| Database | Query Sprog | Eksempel |
|----------|-------------|----------|
| **MySQL** | SQL | `SELECT * FROM Transaction WHERE date > '2024-01-01'` |
| **Elasticsearch** | Query DSL (JSON) | `{"query": {"range": {"date": {"gte": "2024-01-01"}}}}` |
| **Neo4j** | Cypher | `MATCH (t:Transaction) WHERE t.date >= date('2024-01-01') RETURN t` |

### Use Cases

| Opgave | MySQL | Elasticsearch | Neo4j |
|--------|-------|---------------|-------|
| **Opret/Slet data** | ✅ Bedst | ⚠️ OK | ⚠️ OK |
| **Søg i tekst** | ❌ Dårlig | ✅ Bedst | ❌ Dårlig |
| **Analytics** | ⚠️ OK | ✅ Bedst | ⚠️ OK |
| **Relationships** | ✅ OK (joins) | ❌ Ingen | ✅ Bedst (native) |
| **Graph queries** | ❌ Dårlig | ❌ Dårlig | ✅ Bedst |

---

## 🎯 Hvornår bruger vi hvilken?

### MySQL (Primær Database)
- **Alle CRUD operationer** (Create, Read, Update, Delete)
- **REST API endpoints** (standard FastAPI routes)
- **Data integritet** (foreign keys, constraints)
- **Transaktioner** (rollback ved fejl)

### Elasticsearch (Søgning & Analytics)
- **Søgning** i transaktionsbeskrivelser
- **Analytics** (udgifter pr. kategori, måned, etc.)
- **Full-text søgning** med fuzzy matching
- **Dashboard queries** (hurtig aggregering)

### Neo4j (Graph & GraphQL)
- **Graph queries** (find alle data for en bruger gennem relationships)
- **GraphQL API** (fleksibel data hentning)
- **Visualisering** (se relationships grafisk)
- **Komplekse relationship queries**

---

## 📝 Praktisk Eksempel

### Scenario: "Find alle transaktioner for bruger 'johan' i december 2024"

**MySQL:**
```sql
SELECT t.* FROM Transaction t
JOIN Account a ON t.Account_idAccount = a.idAccount
JOIN User u ON a.User_idUser = u.idUser
WHERE u.username = 'johan' 
  AND t.date >= '2024-12-01' 
  AND t.date < '2025-01-01'
```
✅ Fungerer godt, men kræver joins

**Elasticsearch:**
```json
{
  "query": {
    "bool": {
      "must": [
        {"term": {"username": "johan"}},
        {"range": {"date": {"gte": "2024-12-01", "lt": "2025-01-01"}}}
      ]
    }
  }
}
```
✅ Hurtig, men data skal være flattened (username i transaction dokument)

**Neo4j:**
```cypher
MATCH (u:User {username: "johan"})-[:OWNS]->(a:Account)-[:HAS_TRANSACTION]->(t:Transaction)
WHERE t.date >= date('2024-12-01') AND t.date < date('2025-01-01')
RETURN t
```
✅ Naturlig graph query, viser relationships tydeligt

---

## 🚀 Konklusion

**MySQL** = Primær database for al data
- Brug til: CRUD, REST API, data integritet

**Elasticsearch** = Søgning og analytics
- Brug til: Søgning, aggregations, dashboards

**Neo4j** = Graph queries og visualisering
- Brug til: GraphQL, relationship queries, visualisering

Alle tre databaser arbejder sammen for at give den bedste løsning til hver opgave! 🎯

