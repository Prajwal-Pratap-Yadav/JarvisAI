# Voice

The browser adapter is opt-in. Press the microphone button to request microphone permission and start Web Speech recognition. The waveform comes from actual Web Audio microphone samples. Without wake-phrase mode, eight seconds of measured silence ends listening; final recognized speech submits a normal goal. Wake-phrase mode requires a transcript containing “Hey Jarvis” or “Jarvis” followed by a command. It is transcript filtering, not a dedicated on-device wake-word model.

Speech recognition availability and network behavior depend on the browser; a remote recognition service may be used. There is no guaranteed offline speech recognition. The adapter reports unsupported browsers and denied permissions without pretending to hear speech. The browser uses its default microphone, language, and speech voice; choose devices/voices through OS/browser settings. Custom microphone selection and swappable local STT engines are future work.

Enable **Speak results** to use browser speech synthesis. Stop voice cancels both recognition and speaking, closes the audio context, stops every media track, and posts an interruption event. It does not cancel an unrelated task; use Cancel run for that. Speech state is reflected in the core. No synthesized/random waveform is used.

The automated test verifies wake-phrase handling. Hardware recording, language recognition quality, audio routing, and audible TTS need an interactive device test; no such hardware result is fabricated in the release report.
