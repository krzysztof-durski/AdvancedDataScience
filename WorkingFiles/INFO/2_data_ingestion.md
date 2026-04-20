# Data ingestion

## Goal

Plan a program that reads data from flat files into a database.

## Assumptions

In production, your requirements might be a combination of the following:

- there are many entries (1B+)
- for entries, extra annotation may be added in the future (1MB per entry)
- incremental updates should be possible
- a complete reload of the data should be possible
- writing any entry might fail in a non-predictable way
- the data model will be subject to further change
- the data is stored in a redundant storage system with **eventual consistency**
- retroactive deletion should be possible (GDPR requirement)
- the client is in a hurry

## Ingestion Strategies

From the assumptions it should be clear that the follwing strategy will not work:

1. read entries from a file
2. write the entries to the database

Here are a few alternative strategies. Pick one of them:

- check before writing whether an entry exists
- calculate a unique hash for each entry and use them to identify unique entries
- write checkpoints and metadata of already processed entries
- proceed in batches, repeat failed batches

> **Note:** What are pros and cons of these strategies?

## Database Identifiers

Consider the following identifiers. Which are **good** or **bad**?

```text
john.doe@email
1
user_001
a
a4bf2m8
Il1O0o
550e8400-e29b-41d4-a716-446655440000
ABC123!@#
あいう123
temp_id_will_change
2024-01-15-record-42
```
