# Computer control

Desktop adapters are disabled by default and require the optional desktop packages plus OS accessibility/input permissions. Each action has a one-time approval showing the exact operation and arguments. `computer.input` can click a validated screen point, type bounded ASCII text, send validated keyboard shortcuts, read the cursor position, or read the clipboard. PyAutoGUI's corner failsafe remains enabled.

A dispatched keyboard/mouse operation is not proof that the intended app changed. The tool reports this distinction; capture and inspect the screen afterward for verification. No automatic application launching, window management, shutdown, process killing, or message sending is implemented in this release. File operations and process inspection have their own tools.

High-risk project test execution is also a computer action: it can run arbitrary code from the trusted workspace. Approval is mandatory. Arguments are fixed to pytest/unittest runners, execution uses no shell, provider credentials are removed from the child environment, output is bounded, and timed-out subprocesses are terminated. These controls are not an OS sandbox. Only test projects you trust, preferably in a separate OS account or container.
