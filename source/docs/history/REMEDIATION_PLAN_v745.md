# Build 745 — log-owned minimal storage identity
Baseline Build 744, companion Build Process v170 (unchanged).
1. Retain existing inventory-name and path output, root marker and destructive-operation safeguards.
2. Store minimal identity snapshots in all numbered log headers at writable scope open. Use the existing durable folderOperations.log for registrations, explicit changes and archived reversal evidence. No new log file or active separate storage DB is needed.
3. For a known verified root, refresh the last mount/label and last-seen time. Preserve distinct generations and scopes; refuse a contradictory drive or partition. An unregistered writable log scope records an observation, never silently adopts legacy inventory. Read-only Search/Research never modifies logs.
4. Read legacy JSON and SQLite if present, and atomically migrate the registrations and reversal evidence on the first verified registration/update. Leave the legacy files byte-for-byte intact as historical backups, ignored after successful migration. No migration or deletion on reads.
5. Store just disk serial/alternate identifier; partition GUID or offset/start plus size fallback; filesystem serial/UUID if exposed to detect reformat. Retain logical inventory identifier, marker, label/path, previous locations, timestamp and backup relationship. No model, overall disk size, partition number/style in active new storage records.
6. Exercise real log reopen, migrated legacy data, copied logs, multi-root and clone conflicts, reversal evidence pruning/truncation, safe failure and the app regression suite. Update requirements, manual, FAQ, version metadata and verified source archive.
Native Windows/macOS/WSL hardware adapters and hosted signing/installer acceptance are pending.

Execution: all six source remediation steps completed. Local regression and both preflights passed; see REGRESSION_RESULTS_v745.txt and docs/validation. Final native acceptance is not yet established.
