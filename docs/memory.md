# Memory and retention

Working conversation memory exists only in process memory and is bounded. Persistent records may be episodic, semantic, procedural, task, or preference knowledge. Each has an ID, timestamp, source, confidence, metadata, and normalized-content fingerprint. Users save, edit (API), search, or delete records explicitly. Repeated identical content updates the same record.

The candidate-consolidation function evaluates an importance threshold, recognized secrets, and near-duplicate lexical matches. It returns a reviewable candidate; it does not automatically persist conversations. Successful procedures can be saved by the user as procedural memory, without modifying application source.

Default retrieval is token-frequency cosine similarity, not neural semantic search. Provider embedding adapters exist, but embedding storage and neural retrieval are not wired into this release. Confidence is supplied metadata, not a calibrated probability.

Task history is separate from long-term memory: plans, outputs, errors, durations, and validation are retained in a local SQLite database for thirty days by default. Recognized credential patterns are redacted; arbitrary personal information is not reliably identifiable. The database is not encrypted. Protect the OS account and data directory. Deleting a memory removes its record but does not scrub backups or unrelated task logs.
