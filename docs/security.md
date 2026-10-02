# Security model and reporting

JARVIS is a single-user localhost application. It binds to 127.0.0.1, authenticates API requests with a random access token, validates Host and Origin, and requires a first WebSocket authentication message. The launcher puts the token in the URL fragment, which is not sent in HTTP requests; frontend JavaScript clears the fragment and keeps it in sessionStorage. Access logs are disabled. Tokens must not be shared. Regenerate a token by stopping the app and removing `access.token` from the data directory.

File tools accept workspace-relative paths and reject traversal, symlinks, Windows alternate-stream syntax, credential paths, and Git metadata. Writes require approval, expected hashes for existing files, atomic replacement, and read-back verification. Per-path async locks serialize concurrent app writes. A malicious local process with the same OS permissions can still race or modify files; this is application-level confinement, not a kernel sandbox.

Tool approval is tied to run ID, node ID, tool name, and a canonical argument hash. It expires after ten minutes and is consumed once. Plans cannot create grants, forge successful execution, or reference undeclared task outputs. Medium/high-risk tools are not silently executed. No generic shell, credential-reading, deletion, shutdown, or external messaging tool exists.

The network allowlist is exact-host and HTTPS-only. All resolved addresses must be public; connections pin the validated IP and retain TLS hostname checking. Redirect targets are revalidated. Browser HTTP requests use that same fetcher; non-GET methods and unapproved network channels are blocked. A language-model prompt is never an authority to relax these restrictions.

Task logs are local plaintext. Known credential patterns are redacted in events/checkpoints and rejected in long-term memory/file writes; this is not a complete secret or personal-data detector. The provider key remains environment-only. Project test subprocesses receive a restricted environment but still have OS permissions and can read other files if their code chooses. The safe default is a dedicated trusted workspace, desktop disabled, and no cloud model.

Release gates include credential-pattern and forbidden-path scans, dependency auditing, authentication/policy tests, and installation smoke checks. Scans reduce mistakes; they are not a formal security audit. Report a vulnerability privately to the repository owner's listed contact rather than posting an exploit containing secrets in a public issue.
