# Browser and research

Install the browser extra with `python -m pip install -e ".[browser]"`, then `python -m playwright install chromium`. Linux may also need Playwright's OS dependencies. The core portable build does not include browser binaries.

`browser.control` supports navigate, extract, accessible-role/exact-name click, fill, and close. It returns a session ID for later steps. Up to four isolated anonymous contexts may exist. Failed sessions close automatically, and runtime shutdown closes every context. The adapter tries an exact text fallback if a role target is missing; ambiguous targets fail instead of guessing.

Every network request is intercepted and served through the same guarded HTTPS fetcher used by research. POST requests, private addresses, unapproved hosts, service workers, WebSockets, and downloads are blocked. This is a restricted research browser, not a signed-in general web automation environment. Cookies are not imported from your browser. Third-party assets require explicit host approval and some JavaScript-heavy sites will not work. Browser operations are approval-gated.

Research accepts up to six source URLs or uses Brave Search when its key is configured. Three requests run concurrently. Redirects must also pass the host/IP policy. Source failures are retained and an all-source failure is an error. Offline synthesis is explicitly an excerpt compilation. Model synthesis is instructed to cite supplied sources and identify uncertainty or contradictions; those claims still need human review.

The read-only fetcher validates every DNS answer and pins its TLS connection to a validated public IP while verifying the original hostname. It limits redirects, response sizes, and elapsed time. It does not inherit environment proxy settings or send local credentials to target websites.
