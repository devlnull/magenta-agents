# Data: <title>

{{header}}

## Current state
- Tables and size (rows, growth):
- Read and write rate:
- Migration tool and engine version:

## Target state
<schema change, with the data ownership from 03-design.md>

## Migration plan
| Step | Release | Change (SQL or migration) | Lock and duration | Verification | Rollback |
|---|---|---|---|---|---|
| 1 Expand | | | | | |

## Backfill
- Batch size and pause:
- Resume key:
- Stop condition (replication lag, load):

## Queries and indexes
| Query (hot path) | Plan before | Plan after | Index | Write cost |
|---|---|---|---|---|

## One-way doors
<drops, renames, type changes; each needs the approval of the human>

## Checks
| Check | What it tests | Set |
|---|---|---|

{{handoff}}
