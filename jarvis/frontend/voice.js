/** Browser speech adapter. Nothing listens until the user presses the microphone. */
export function commandFromTranscript(text, wakeMode) {
  const cleaned = text.trim();
  if (!wakeMode) return cleaned;
  const match = /\b(?:hey\s+)?jarvis\b[,.! ]*(.*)$/i.exec(cleaned);
  return match ? match[1].trim() : '';
}

export class Voice {
  constructor({onCommand, onState, onNotice, emit, canvas}) {
    Object.assign(this, {onCommand, onState, onNotice, emit, canvas});
    this.active = false;
    this.recognition = null;
    this.stream = null;
    this.audio = null;
    this.frame = null;
    this.silenceSince = 0;
  }
  supported() { return Boolean(window.SpeechRecognition || window.webkitSpeechRecognition); }
  async start(wakeMode) {
    if (this.active) { this.stop(); return; }
    if (!this.supported()) throw new Error('Speech recognition is unavailable in this browser. Text input and browser text-to-speech remain available.');
    window.speechSynthesis?.cancel();
    try {
      this.stream = await navigator.mediaDevices.getUserMedia({audio: true});
      this.audio = new AudioContext();
      const source = this.audio.createMediaStreamSource(this.stream);
      const analyser = this.audio.createAnalyser();
      analyser.fftSize = 256;
      source.connect(analyser);
      const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
      this.recognition = new Recognition();
      this.recognition.lang = navigator.language || 'en-US';
      this.recognition.continuous = true;
      this.recognition.interimResults = true;
      this.active = true;
      this.onState('LISTENING');
      this.emit('VOICE_STARTED');
      this.onNotice(wakeMode ? 'Listening for “Hey Jarvis” followed by your request. Click Stop voice to end.' : 'Listening. Speak a request; silence ends this session.');
      this.recognition.onresult = event => {
        const result = event.results[event.resultIndex];
        this.onNotice(result[0].transcript);
        if (result.isFinal) {
          const command = commandFromTranscript(result[0].transcript, wakeMode);
          if (command) {
            this.emit('VOICE_TRANSCRIPT');
            this.stop();
            this.onCommand(command);
          }
        }
      };
      this.recognition.onerror = event => { this.onNotice(`Speech service: ${event.error}. You can continue by typing.`); this.stop(); };
      this.recognition.onend = () => { if (this.active) this.stop(); };
      this.recognition.start();
      const samples = new Uint8Array(analyser.fftSize);
      const ctx = this.canvas.getContext('2d');
      const draw = () => {
        if (!this.active) return;
        analyser.getByteTimeDomainData(samples);
        const rms = Math.sqrt(samples.reduce((sum, v) => sum + ((v-128)/128)**2, 0)/samples.length);
        ctx.clearRect(0,0,80,20);
        ctx.fillStyle = '#65e7c8';
        for (let i=0; i<20; i++) {
          const magnitude = Math.abs((samples[i*8]-128)/128)*18;
          ctx.fillRect(i*4,10-magnitude/2,2,Math.max(1,magnitude));
        }
        if (rms < .012) this.silenceSince ||= performance.now(); else this.silenceSince = 0;
        if (!wakeMode && this.silenceSince && performance.now()-this.silenceSince > 8000) { this.stop(); return; }
        this.frame = requestAnimationFrame(draw);
      };
      draw();
    } catch (error) { this.stop(); throw error; }
  }
  stop() {
    const wasActive = this.active;
    this.active = false;
    this.recognition?.abort();
    this.recognition = null;
    this.stream?.getTracks().forEach(track => track.stop());
    this.stream = null;
    this.audio?.close().catch(() => {});
    this.audio = null;
    if (this.frame) cancelAnimationFrame(this.frame);
    this.canvas?.getContext('2d')?.clearRect(0,0,80,20);
    this.silenceSince = 0;
    this.onState('IDLE');
    if (wasActive) this.emit('VOICE_STOPPED');
  }
  speak(text) {
    if (!window.speechSynthesis) { this.onNotice('Text-to-speech is unavailable in this browser.'); return; }
    this.stop();
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text.slice(0,3000));
    utterance.onstart = () => { this.onState('SPEAKING'); this.emit('SPEAKING'); };
    utterance.onend = utterance.onerror = () => this.onState('IDLE');
    window.speechSynthesis.speak(utterance);
  }
  interrupt() {
    this.stop();
    window.speechSynthesis?.cancel();
    this.emit('USER_INTERRUPTED');
    this.onNotice('Voice stopped. Running tasks can be cancelled in the task workspace.');
  }
}
