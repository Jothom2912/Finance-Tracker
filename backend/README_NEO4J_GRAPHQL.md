# Neo4j & GraphQL Setup Guide

Denne guide forklarer hvordan du bruger Neo4j graph database og GraphQL API med Finance Tracker.

## 📋 Indholdsfortegnelse

- [Installation](#installation)
- [Neo4j Setup](#neo4j-setup)
- [Migration](#migration)
- [GraphQL API](#graphql-api)
- [Eksempler](#eksempler)

---

## 🚀 Installation

### 1. Installer dependencies

```bash
pip install -r requirements.txt
```

Dette installerer:
- `neo4j` - Neo4j Python driver
- `strawberry-graphql[fastapi]` - GraphQL framework

### 2. Start Neo4j

**Med Docker (anbefalet):**
```bash
docker run -d \
  --name neo4j \
  -p 7474:7474 \
  -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/password \
  neo4j:latest
```

**Eller download Neo4j Desktop:**
- Download fra https://neo4j.com/download/
- Opret ny database
- Start database

---

## 🗄️ Neo4j Setup

### Konfiguration

Tilføj til `.env` filen:

```bash
# Neo4j konfiguration
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password
USE_NEO4J=false  # Sæt til true for at bruge Neo4j i GraphQL resolvers
```

### Graph Struktur

Neo4j bruger nodes og relationships:

**Nodes:**
- `User` - Brugere
- `Account` - Konti
- `Category` - Kategorier
- `Transaction` - Transaktioner
- `Budget` - Budgetter
- `Goal` - Mål
- `AccountGroup` - Kontogrupper

**Relationships:**
- `(User)-[:OWNS]->(Account)` - Bruger ejer konto
- `(Account)-[:HAS_TRANSACTION]->(Transaction)` - Konto har transaktioner
- `(Transaction)-[:BELONGS_TO_CATEGORY]->(Category)` - Transaktion tilhører kategori
- `(Account)-[:HAS_BUDGET]->(Budget)` - Konto har budgetter
- `(Budget)-[:FOR_CATEGORY]->(Category)` - Budget for kategori
- `(Account)-[:HAS_GOAL]->(Goal)` - Konto har mål
- `(User)-[:MEMBER_OF]->(AccountGroup)` - Bruger er medlem af gruppe

---

## 📦 Migration

### Migrer data fra MySQL til Neo4j

```bash
python -m backend.migrate_to_neo4j
```

Dette script:
1. Tester Neo4j forbindelse
2. Sletter eksisterende data (hvis nødvendigt)
3. Opretter constraints og indexes
4. Migrerer alle data i korrekt rækkefølge:
   - Users → Categories → Accounts → Transactions → Budgets → Goals → AccountGroups

**Output eksempel:**
```
🚀 STARTER MIGRATION TIL NEO4J
✓ Forbindelse til Neo4j OK
✓ Constraints oprettet
📦 Migrerer brugere...
  ✓ Succesfuldt migreret 3 brugere
📦 Migrerer kategorier...
  ✓ Succesfuldt migreret 11 kategorier
...
✅ MIGRATION FULDFØRT!
```

---

## 🔌 GraphQL API

### Endpoint

GraphQL endpoint er tilgængelig på:
```
http://localhost:8000/graphql
```

### GraphQL Playground

Åbn i browseren:
```
http://localhost:8000/graphql
```

### Query Eksempler

#### Hent alle brugere
```graphql
query {
  users {
    idUser
    username
    email
  }
}
```

#### Hent konti med transaktioner
```graphql
query {
  accounts {
    idAccount
    name
    saldo
    user {
      username
    }
    transactions {
      idTransaction
      amount
      description
      date
      category {
        name
      }
    }
  }
}
```

#### Hent transaktioner med filtrering
```graphql
query {
  transactions(filter: {
    start_date: "2024-01-01"
    end_date: "2024-12-31"
    type: "expense"
  }) {
    idTransaction
    amount
    description
    date
    category {
      name
      type
    }
    account {
      name
    }
  }
}
```

#### Opret transaktion
```graphql
mutation {
  createTransaction(input: {
    amount: -500.00
    description: "Netto køb"
    date: "2024-12-15T10:00:00"
    type: "expense"
    category_id: 1
    account_id: 1
  }) {
    idTransaction
    amount
    description
  }
}
```

### GraphQL Schema

Alle tilgængelige queries og mutations:

**Queries:**
- `users` - Hent alle brugere
- `user(id: Int)` - Hent specifik bruger
- `accounts(user_id: Int)` - Hent konti
- `account(id: Int)` - Hent specifik konto
- `categories` - Hent alle kategorier
- `category(id: Int)` - Hent specifik kategori
- `transactions(filter: TransactionFilter)` - Hent transaktioner
- `transaction(id: Int)` - Hent specifik transaktion
- `budgets(account_id: Int)` - Hent budgetter
- `goals(account_id: Int)` - Hent mål

**Mutations:**
- `createTransaction(input: TransactionCreate)` - Opret transaktion
- `updateTransaction(id: Int, input: TransactionCreate)` - Opdater transaktion
- `deleteTransaction(id: Int)` - Slet transaktion

---

## 💡 Eksempler

### Neo4j Cypher Queries

Du kan også køre Cypher queries direkte i Neo4j Browser:

**Find alle transaktioner for en bruger:**
```cypher
MATCH (u:User {username: "johan"})-[:OWNS]->(a:Account)-[:HAS_TRANSACTION]->(t:Transaction)
RETURN t, a
ORDER BY t.date DESC
LIMIT 10
```

**Find udgifter pr. kategori:**
```cypher
MATCH (t:Transaction {type: "expense"})-[:BELONGS_TO_CATEGORY]->(c:Category)
RETURN c.name, SUM(t.amount) as total
ORDER BY total DESC
```

**Find brugere med flest transaktioner:**
```cypher
MATCH (u:User)-[:OWNS]->(a:Account)-[:HAS_TRANSACTION]->(t:Transaction)
RETURN u.username, COUNT(t) as transaction_count
ORDER BY transaction_count DESC
```

---

## 🔄 Skifte mellem MySQL og Neo4j

GraphQL resolvers kan bruge enten MySQL eller Neo4j baseret på `USE_NEO4J` environment variable:

```bash
# Brug MySQL (standard)
USE_NEO4J=false

# Brug Neo4j
USE_NEO4J=true
```

---

## 📝 Noter

- Neo4j er perfekt til graph queries (f.eks. "find alle transaktioner for en bruger gennem deres konti")
- MySQL er bedre til simple CRUD operationer
- GraphQL giver fleksibel data hentning med nested queries
- Du kan bruge begge databaser samtidig - MySQL til REST API, Neo4j til GraphQL

---

## 🐛 Fejlfinding

### "Cannot connect to Neo4j"
- Tjek at Neo4j kører: `docker ps`
- Tjek URI i `.env`: `NEO4J_URI=bolt://localhost:7687`
- Tjek credentials: `NEO4J_USER` og `NEO4J_PASSWORD`

### "Constraint already exists"
- Dette er normalt - constraints oprettes kun én gang
- Scriptet håndterer dette automatisk

### GraphQL endpoint ikke tilgængelig
- Tjek at `strawberry-graphql[fastapi]` er installeret
- Genstart FastAPI serveren
- Tjek `/graphql` endpoint i browseren

