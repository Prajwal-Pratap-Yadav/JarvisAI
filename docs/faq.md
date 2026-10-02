# FAQ

**Is this AGI?** No. It is an extensible cognitive/runtime architecture with observable tools and explicit limits. No benchmark or human-level intelligence claim is made.

**Does offline mode fabricate a chat response?** No. It runs real local tools and explains when a model is needed. Ollama can add local conversation if installed separately.

**Can it control my computer without asking?** Desktop input is disabled by default. Enabled actions still require exact approval. Project tests also require approval because they execute real code.

**Can it read everything on my computer?** File tools are workspace-confined. Approved test code and desktop actions have broader OS authority; they are not sandboxed.

**Can it send email or use my signed-in browser?** No. Neither capability is implemented. The optional browser uses isolated anonymous sessions and restricted networking.

**Is every integration verified on hardware?** No. Read the implementation/validation status. A mock protocol test is not a live provider or device test.

**Where are updates?** GitHub Releases. This preview has manual, checksum-verifiable portable updates; no silent automatic updater or signed Windows installer.
