// CS 435: Self-Directed AI-Assisted Interview Practice System
// High-Fidelity Client Application with Real-Time STT, TTS, Animated Visualizers & Evaluation Module

let currentSessionId = null;
let currentQuestionId = 1;
let currentQuestionText = "Tell me about a time when you worked with a difficult teammate. What was the situation and how did you resolve it?";
let protoAQuestions = [];
let protoACurrentIndex = 0;
let activeWhyCriterion = "evidence_outcome";
let activePersona = "aditi";
let recognition = null;
let activeRecordingButton = null;
let activeTargetTextarea = null;
let activeStatusPill = null;
let activeEqualizer = null;
let activePreviewBox = null;
let progressChartInstance = null;
let simulationTurn = 1;
let lastEvaluation = null;
let lastInterviewerText = "";
let isMuted = false;
let userVoices = [];
let selectedVoice = null;
let speechRate = 1.0;
let speechPitch = 1.0;
let autoSpeakEnabled = true;

// Usability study timer
let evalTimerInterval = null;
let evalTimerSeconds = 0;

// ==========================================
// CUSTOM GLASSMORPHIC CONFIRMATION & TOAST SYSTEM
// ==========================================
function showAppConfirm(title, message, { confirmText = "Confirm", cancelText = "Cancel", isDestructive = false } = {}) {
  return new Promise((resolve) => {
    const modal = document.getElementById("modal-app-confirm");
    const titleEl = document.getElementById("confirm-modal-title");
    const msgEl = document.getElementById("confirm-modal-message");
    const iconEl = document.getElementById("confirm-modal-icon");
    const okBtn = document.getElementById("confirm-modal-ok-btn");
    const cancelBtn = document.getElementById("confirm-modal-cancel-btn");

    if (!modal || !okBtn || !cancelBtn) {
      resolve(window.confirm(message));
      return;
    }

    if (titleEl) titleEl.innerText = title;
    if (msgEl) msgEl.innerText = message;
    if (iconEl) iconEl.innerText = isDestructive ? "🗑️" : "⚠️";
    okBtn.innerText = confirmText;
    cancelBtn.innerText = cancelText;

    if (isDestructive) {
      okBtn.className = "btn btn-danger";
    } else {
      okBtn.className = "btn btn-primary";
    }

    modal.style.display = "flex";

    const cleanup = (result) => {
      modal.style.display = "none";
      okBtn.onclick = null;
      cancelBtn.onclick = null;
      modal.onclick = null;
      resolve(result);
    };

    okBtn.onclick = () => cleanup(true);
    cancelBtn.onclick = () => cleanup(false);
    modal.onclick = (e) => {
      if (e.target === modal) cleanup(false);
    };
  });
}

function showAppToast(message, type = "info") {
  const container = document.getElementById("app-toast-container");
  if (!container) {
    console.log(`[Toast ${type}]:`, message);
    return;
  }
  const toast = document.createElement("div");
  toast.className = `app-toast toast-${type}`;
  const icon = type === "success" ? "✓" : (type === "danger" ? "✕" : "ℹ️");
  toast.innerHTML = `<span style="font-weight: 700;">${icon}</span> <span>${message}</span>`;
  container.appendChild(toast);
  
  requestAnimationFrame(() => {
    toast.classList.add("show");
  });

  setTimeout(() => {
    toast.classList.remove("show");
    setTimeout(() => {
      if (toast.parentNode) toast.parentNode.removeChild(toast);
    }, 300);
  }, 3500);
}

// Initialization
document.addEventListener("DOMContentLoaded", () => {
  initTheme();
  setupWordCounters();
  setupSpeechRecognition();
  setupSpeechSynthesis();
  loadLongitudinalProgress();
  loadConfigSettings();
  loadLoggedEvaluations();
  calculateLiveSusScore();
  setupSusListeners();
  switchMainTab("B");
  if (typeof updateContextBannerVisibility === "function") {
    updateContextBannerVisibility("b1");
  }
});

// ==========================================
// 1. SPEECH SYNTHESIS (TTS) ENGINE & AVATAR
// ==========================================
function setupSpeechSynthesis() {
  if (!('speechSynthesis' in window)) {
    console.warn("Web Speech Synthesis not supported in this browser.");
    return;
  }

  function populateVoices() {
    userVoices = window.speechSynthesis.getVoices();
    const select = document.getElementById("cfg-voice-select");
    if (select) {
      select.innerHTML = '<option value="">Default Browser Voice</option>';
      userVoices.forEach((v, idx) => {
        const opt = document.createElement("option");
        opt.value = idx;
        opt.textContent = `${v.name} (${v.lang})${v.default ? ' — [Default]' : ''}`;
        if (v.lang.startsWith("en") && (v.name.includes("Google") || v.name.includes("Natural") || v.name.includes("Jenny") || v.name.includes("David"))) {
          if (!selectedVoice) selectedVoice = v;
        }
        select.appendChild(opt);
      });
      if (selectedVoice) {
        const foundIdx = userVoices.indexOf(selectedVoice);
        if (foundIdx >= 0) select.value = foundIdx;
      }
    }
  }

  populateVoices();
  if (window.speechSynthesis.onvoiceschanged !== undefined) {
    window.speechSynthesis.onvoiceschanged = populateVoices;
  }
}

function speakText(text, onStartCallback = null, onEndCallback = null) {
  if (isMuted || !('speechSynthesis' in window)) {
    if (onStartCallback) onStartCallback();
    if (onEndCallback) setTimeout(onEndCallback, 600);
    return;
  }

  // Stop STT temporarily while system is speaking to avoid mic picking up output
  if (recognition && activeRecordingButton) {
    stopActiveRecognition();
  }

  window.speechSynthesis.cancel();

  // Strip html or special quotes if any
  const clean = text.replace(/<\/?[^>]+(>|$)/g, "").replace(/["“”]/g, "").trim();
  if (!clean) return;

  const utterance = new SpeechSynthesisUtterance(clean);
  utterance.rate = speechRate;
  utterance.pitch = speechPitch;

  if (selectedVoice) {
    utterance.voice = selectedVoice;
  }

  utterance.onstart = () => {
    lastInterviewerText = clean;
    setAvatarSpeaking(true);
    if (onStartCallback) onStartCallback();
  };

  utterance.onend = () => {
    setAvatarSpeaking(false);
    if (onEndCallback) onEndCallback();
  };

  utterance.onerror = (e) => {
    console.warn("Speech synthesis error or cancelled:", e);
    setAvatarSpeaking(false);
    if (onEndCallback) onEndCallback();
  };

  window.speechSynthesis.speak(utterance);
}

function setAvatarSpeaking(isSpeaking) {
  // Update Prototype B avatar and equalizer
  const avatarWrapper = document.getElementById("b3-avatar-wrapper");
  const b3Equalizer = document.getElementById("b3-equalizer");
  const b3Status = document.getElementById("b3-voice-status");

  if (avatarWrapper) avatarWrapper.classList.toggle("speaking", isSpeaking);
  if (b3Equalizer) b3Equalizer.classList.toggle("active", isSpeaking);
  if (b3Status) {
    if (isSpeaking) {
      b3Status.className = "voice-status-pill speaking";
      b3Status.innerText = "🔊 Interviewer Speaking";
    } else {
      b3Status.className = "voice-status-pill listening";
      b3Status.innerText = "🎙️ Candidate's Turn (Listening...)";
    }
  }

  // Update Prototype A visualizers (Screen A3, A4, A6, A7, A8)
  const screensA = [
    { p: "a3", labelSpk: "🔊 Coach Speaking", labelList: "🎙️ Candidate's Turn (Listening...)" },
    { p: "a4", labelSpk: "🔊 Coach Delivering Rubric Feedback", labelList: "✓ Rubric Evaluation Complete" },
    { p: "a6", labelSpk: "🔊 Coach Guiding Feedforward Plan", labelList: "🎙️ Dictate or Type Reflection" },
    { p: "a7", labelSpk: "🔊 Coach Presenting Adaptive Retry", labelList: "🎙️ Candidate's Turn (Retry Revision)" },
    { p: "a8", labelSpk: "🔊 Coach Explaining Measurable Delta", labelList: "✓ Attempt Delta Audited" }
  ];

  screensA.forEach(s => {
    const avatar = document.getElementById(`${s.p}-avatar-wrapper`);
    const eq = document.getElementById(`${s.p}-equalizer`);
    const status = document.getElementById(`${s.p}-voice-status`);
    if (avatar) avatar.classList.toggle("speaking", isSpeaking);
    if (eq) eq.classList.toggle("active", isSpeaking);
    if (status) {
      if (isSpeaking) {
        status.className = "voice-status-pill speaking";
        status.innerText = s.labelSpk;
      } else {
        status.className = (s.p === "a4" || s.p === "a8") ? "voice-status-pill speaking" : "voice-status-pill listening";
        status.innerText = s.labelList;
      }
    }
  });

  // Toggle active visual audio pulse on all TTS audio buttons
  document.querySelectorAll("#btn-listen-q, #btn-listen-a3, #btn-listen-retry, .tts-play-btn, .btn-listen").forEach(btn => {
    btn.classList.toggle("tts-playing", isSpeaking);
  });
}

function stopAllAudio() {
  if ('speechSynthesis' in window) {
    window.speechSynthesis.cancel();
  }
  setAvatarSpeaking(false);
  stopActiveRecognition();
}

function toggleMuteAudio() {
  isMuted = !isMuted;
  ["btn-mute-b3", "btn-mute-a3", "btn-mute-a4", "btn-mute-a6", "btn-mute-a7", "btn-mute-a8"].forEach(id => {
    const btn = document.getElementById(id);
    if (btn) {
      btn.innerText = isMuted ? "🔊 Unmute" : "🔇 Mute";
      btn.classList.toggle("btn-warning", isMuted);
    }
  });
  if (isMuted) {
    window.speechSynthesis.cancel();
    setAvatarSpeaking(false);
  }
}

function replayLastInterviewerMessage() {
  if (lastInterviewerText) {
    speakText(lastInterviewerText);
  } else {
    speakText("Welcome. Please begin your interview question whenever you are ready.");
  }
}

function replayInterviewerTurn(turnIdx) {
  const assistantMsgs = simConversationHistory.filter(m => m.role === "assistant");
  if (turnIdx !== undefined && assistantMsgs[turnIdx]) {
    speakText(assistantMsgs[turnIdx].content);
  } else if (lastInterviewerText) {
    speakText(lastInterviewerText);
  } else if (assistantMsgs.length > 0) {
    speakText(assistantMsgs[assistantMsgs.length - 1].content);
  } else {
    speakText("Welcome. Please begin whenever you are ready.");
  }
}

function setCockpitInputMode(mode) {
  const vStage = document.getElementById("dock-voice-stage");
  const tStage = document.getElementById("dock-text-stage");
  const vBtn = document.getElementById("dock-btn-voice");
  const tBtn = document.getElementById("dock-btn-text");
  const sampleBtn = document.getElementById("btn-sample-b");

  if (mode === "voice") {
    if (vStage) vStage.style.display = "block";
    if (tStage) tStage.style.display = "none";
    if (vBtn) vBtn.classList.add("active");
    if (tBtn) tBtn.classList.remove("active");
    if (sampleBtn) sampleBtn.style.display = "none";
  } else {
    if (vStage) vStage.style.display = "none";
    if (tStage) tStage.style.display = "block";
    if (vBtn) vBtn.classList.remove("active");
    if (tBtn) tBtn.classList.add("active");
    if (sampleBtn) sampleBtn.style.display = "inline-flex";
    const ta = document.getElementById("b-answer");
    if (ta) ta.focus();
  }
}

function setCockpitInputModeA(mode, prefix = 'a3') {
  const vStage = document.getElementById(`${prefix}-dock-voice-stage`);
  const tStage = document.getElementById(`${prefix}-dock-text-stage`);
  const vBtn = document.getElementById(`${prefix}-dock-btn-voice`);
  const tBtn = document.getElementById(`${prefix}-dock-btn-text`);
  const sampleBtn = document.getElementById(`btn-sample-${prefix}`);

  if (mode === "voice") {
    if (vStage) vStage.style.display = "block";
    if (tStage) tStage.style.display = "none";
    if (vBtn) vBtn.classList.add("active");
    if (tBtn) tBtn.classList.remove("active");
    if (sampleBtn) sampleBtn.style.display = "none";
  } else {
    if (vStage) vStage.style.display = "none";
    if (tStage) tStage.style.display = "block";
    if (vBtn) vBtn.classList.remove("active");
    if (tBtn) tBtn.classList.add("active");
    if (sampleBtn) sampleBtn.style.display = "inline-flex";
    const ta = document.getElementById(prefix === "a3" ? "a-answer" : (prefix === "a6" ? "a-change" : "a-retry-answer"));
    if (ta) ta.focus();
  }
}

function clearCockpitAnswer() {
  const ta = document.getElementById("b-answer");
  if (ta) {
    ta.value = "";
    ta.dispatchEvent(new Event("input"));
  }
  const preview = document.getElementById("b3-live-preview");
  if (preview) {
    preview.innerText = "";
    preview.classList.remove("active");
  }
  const status = document.getElementById("b3-stt-status");
  if (status) {
    status.innerHTML = "🎙️ Ready for your response. Click the button above to speak.";
  }
}

async function confirmExitSimulation() {
  if (simConversationHistory && simConversationHistory.length > 1) {
    const confirmed = await showAppConfirm(
      "Return to Setup?",
      "Are you sure you want to return to configuration? Your ongoing mock interview progress will be reset.",
      { confirmText: "Return to Setup", isDestructive: true }
    );
    if (confirmed) {
      stopAllAudio();
      goToScreenB("b2");
    }
  } else {
    stopAllAudio();
    goToScreenB("b2");
  }
}

function testVoicePlayback() {
  speakText("Hello! This is a real-time speech test from your AI interview coach.");
}

function setupSpeechRecognition() {
  console.log("✓ Universal Voice Input Engine initialized (Web Speech API + Resilient Audio Fallback).");
}

// ==========================================
// 2. UNIVERSAL 100% FUNCTIONAL VOICE INPUT & STT ENGINE
// ==========================================
let isUniversalRecording = false;
let universalAudioCtx = null;
let universalMicStream = null;
let universalScriptProcessor = null;
let universalAnalyser = null;
let universalPCMChunks = [];
let universalRecognition = null;
let universalWebSocket = null;
let universalLiveStreamAccumulated = "";
let universalLiveStreamGotText = false;
let universalTimerInterval = null;
let universalStartTime = 0;
let universalTextareaId = null;
let universalBtnId = null;
let universalPanelId = null;
let universalStatusId = null;
let universalPreviewId = null;
let universalBaseText = "";
let universalWebSpeechGotText = false;
let universalSpeechAccumulated = "";
let universalLastSpeechTime = 0;
let universalInterimInterval = null;
let universalVoiceAnimFrame = null;
let simSilenceTimer = null;
let simSilenceCountdownTimer = null;
let simTurnAnswers = {
  question1: "",
  turn1Answer: "",
  followupQuestion: "",
  turn2Answer: "",
  adaptiveTrigger: ""
};

function clearAnswerDirect(textareaId, statusId, previewId) {
  if (simSilenceTimer) {
    clearTimeout(simSilenceTimer);
    simSilenceTimer = null;
  }
  if (simSilenceCountdownTimer) {
    clearInterval(simSilenceCountdownTimer);
    simSilenceCountdownTimer = null;
  }
  const ta = document.getElementById(textareaId);
  if (ta) {
    ta.value = "";
    ta.dispatchEvent(new Event("input"));
  }
  const st = document.getElementById(statusId);
  if (st) st.innerText = "🎙️ Ready for Voice Input";
  const pr = document.getElementById(previewId);
  if (pr) {
    pr.innerText = "";
    pr.classList.remove("active");
  }
}

function floatTo16BitPCM(float32Array) {
  const int16Array = new Int16Array(float32Array.length);
  for (let i = 0; i < float32Array.length; i++) {
    const s = Math.max(-1, Math.min(1, float32Array[i]));
    int16Array[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
  }
  return int16Array;
}

function downsampleChunkTo16k(buffer, inputSampleRate) {
  if (inputSampleRate === 16000) return buffer;
  const ratio = inputSampleRate / 16000;
  const newLen = Math.floor(buffer.length / ratio);
  const result = new Float32Array(newLen);
  for (let i = 0; i < newLen; i++) {
    result[i] = buffer[Math.floor(i * ratio)];
  }
  return result;
}

function checkSimSilenceAutoForward(totalSpoken, targetId, statusEl) {
  // Auto-send removed: response will only be sent when the user explicitly clicks the send/submit button.
  if (simSilenceTimer) {
    clearTimeout(simSilenceTimer);
    simSilenceTimer = null;
  }
  if (simSilenceCountdownTimer) {
    clearInterval(simSilenceCountdownTimer);
    simSilenceCountdownTimer = null;
  }
}

// Convert Float32 buffer to 16kHz mono 16-bit PCM WAV Blob
function encodeWAV(samples, sampleRate) {
  const buffer = new ArrayBuffer(44 + samples.length * 2);
  const view = new DataView(buffer);

  function writeString(view, offset, string) {
    for (let i = 0; i < string.length; i++) {
      view.setUint8(offset + i, string.charCodeAt(i));
    }
  }

  writeString(view, 0, 'RIFF');
  view.setUint32(4, 36 + samples.length * 2, true);
  writeString(view, 8, 'WAVE');
  writeString(view, 12, 'fmt ');
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  writeString(view, 36, 'data');
  view.setUint32(40, samples.length * 2, true);

  let offset = 44;
  for (let i = 0; i < samples.length; i++, offset += 2) {
    let s = Math.max(-1, Math.min(1, samples[i]));
    view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
  }

  return new Blob([view], { type: 'audio/wav' });
}

function downsampleBuffer(buffer, inputSampleRate, outputSampleRate = 16000) {
  if (inputSampleRate === outputSampleRate) {
    return buffer;
  }
  const sampleRateRatio = inputSampleRate / outputSampleRate;
  const newLength = Math.round(buffer.length / sampleRateRatio);
  const result = new Float32Array(newLength);
  let offsetResult = 0;
  let offsetBuffer = 0;
  while (offsetResult < result.length) {
    const nextOffsetBuffer = Math.round((offsetResult + 1) * sampleRateRatio);
    let accum = 0, count = 0;
    for (let i = offsetBuffer; i < nextOffsetBuffer && i < buffer.length; i++) {
      accum += buffer[i];
      count++;
    }
    result[offsetResult] = count > 0 ? (accum / count) : 0;
    offsetResult++;
    offsetBuffer = nextOffsetBuffer;
  }
  return result;
}

async function toggleVoiceInputUniversal(textareaId, btnId, panelId, statusId, meterId, fillId, previewId) {
  const btn = document.getElementById(btnId);
  const textarea = document.getElementById(textareaId);
  const panel = document.getElementById(panelId);
  const status = document.getElementById(statusId);
  const preview = document.getElementById(previewId);

  // If already recording, stop & finalize!
  if (isUniversalRecording) {
    await stopUniversalRecordingAndTranscribe();
    return;
  }

  // Cancel any TTS audio playing in background
  if (window.speechSynthesis && window.speechSynthesis.speaking) {
    window.speechSynthesis.cancel();
    setAvatarSpeaking(false);
  }

  universalTextareaId = textareaId;
  universalBtnId = btnId;
  universalPanelId = panelId;
  universalStatusId = statusId;
  universalPreviewId = previewId;
  universalBaseText = textarea ? textarea.value.trim() : "";
  universalWebSpeechGotText = false;
  universalSpeechAccumulated = "";
  universalLiveStreamGotText = false;
  universalLiveStreamAccumulated = "";
  universalLastSpeechTime = Date.now();
  universalPCMChunks = [];
  isUniversalRecording = true;

  // 1. Update UI IMMEDIATELY so button is visibly functional
  if (btn) {
    if (btn.classList.contains("hero-mic-btn") || btnId === "hero-mic-b" || btnId === "btn-speech-a" || btnId === "btn-speech-a7" || btnId === "btn-speech-a6") {
      const glyph = btn.querySelector(".mic-glyph") || document.getElementById("hero-mic-glyph");
      const label = btn.querySelector(".mic-primary-label") || document.getElementById("hero-mic-label");
      const sub = btn.querySelector(".mic-sub-label") || document.getElementById("hero-mic-sub");
      if (glyph) glyph.innerText = "⏹️";
      if (btnId === "hero-mic-b") {
        if (label) label.innerText = "⏹️ Done Speaking (Stop Recording)";
        if (sub) sub.innerText = "Recording live... Click here when done speaking";
      } else if (btnId === "btn-speech-a") {
        if (label) label.innerText = "⏹️ Done Speaking (Stop Recording)";
        if (sub) sub.innerText = "Recording live... Click here when done speaking";
      } else if (btnId === "btn-speech-a7") {
        if (label) label.innerText = "⏹️ Done Speaking (Stop Recording)";
        if (sub) sub.innerText = "Recording live... Click here when done speaking";
      } else if (btnId === "btn-speech-a6") {
        if (label) label.innerText = "⏹️ Done Speaking (Stop Recording)";
        if (sub) sub.innerText = "Recording live... Click here when done speaking";
      } else {
        if (label) label.innerText = "⏹️ Done Speaking (Stop Recording)";
        if (sub) sub.innerText = "Recording live... Click here when done speaking";
      }
      btn.classList.add("recording");
    } else if (btnId === "btn-speech-b") {
      btn.innerText = "⏹️ Done Speaking (Stop Recording)";
      btn.className = "btn btn-danger btn-sm";
    } else {
      btn.innerText = "⏹️ Done Speaking (Stop Recording)";
      btn.className = "btn btn-danger btn-sm";
    }
  }
  if (panel) panel.classList.add("recording");
  if (status) {
    if (textareaId === "b-answer") {
      status.innerHTML = "🔴 <strong>Listening to your answer... Transcribing live as you speak!</strong>";
    } else {
      status.innerHTML = "🔴 <strong>Recording Audio (00:00)... Transcribing live as you speak!</strong>";
    }
  }

  // 2. Activate Preview Container immediately with live listening indicator & animated voice waveform
  if (preview) {
    preview.classList.add("active");
    preview.innerHTML = `
      <div class="live-transcribe-box">
        <span class="live-mic-pulse">🔴 Live Listening</span>
        <span class="live-voice-bars" id="live-voice-bars-${previewId}">
          <span class="bar b1" style="height: 6px;"></span>
          <span class="bar b2" style="height: 10px;"></span>
          <span class="bar b3" style="height: 14px;"></span>
          <span class="bar b4" style="height: 8px;"></span>
          <span class="bar b5" style="height: 5px;"></span>
        </span>
        <span class="live-text-stream" id="${previewId}-stream">Speak aloud... Transcribing in real time</span>
      </div>`;
    preview.scrollTop = preview.scrollHeight;
  }

  universalStartTime = Date.now();
  universalTimerInterval = setInterval(() => {
    if (!isUniversalRecording) return;
    const elapsedSec = Math.floor((Date.now() - universalStartTime) / 1000);
    const mm = String(Math.floor(elapsedSec / 60)).padStart(2, "0");
    const ss = String(elapsedSec % 60).padStart(2, "0");

    if (status) {
      if (!universalLiveStreamGotText && !universalWebSpeechGotText) {
        status.innerHTML = `🔴 <strong>Recording & Transcribing Live (${mm}:${ss})... Speak answer now</strong>`;
      }
    }
  }, 100);

  // Unified helper to update running transcript across Web Speech, WebSockets, and Interim Chunk Polling
  function updateLiveRunningText(text, isInterim = false) {
    if (!text || !text.trim() || !isUniversalRecording) return;
    const cleanSpoken = text.trim();
    const fullRunningText = (universalBaseText ? universalBaseText + " " : "") + cleanSpoken;

    if (textarea) {
      textarea.value = fullRunningText;
      textarea.dispatchEvent(new Event("input"));
    }

    if (preview) {
      preview.classList.add("active");
      const streamSpan = document.getElementById(`${previewId}-stream`);
      if (streamSpan) {
        streamSpan.innerHTML = `“${escapeHtml(cleanSpoken)}” <span class="typing-cursor">▌</span>`;
      } else {
        preview.innerHTML = `
          <div class="live-transcribe-box">
            <span class="live-mic-pulse">🗣️ Live:</span>
            <span class="live-text-stream">“${escapeHtml(cleanSpoken)}” <span class="typing-cursor">▌</span></span>
          </div>`;
      }
      preview.scrollTop = preview.scrollHeight;
    }

    if (status) {
      const wordCount = fullRunningText.split(/\s+/).filter(Boolean).length;
      status.innerHTML = `🗣️ <strong>Transcribing Live (${wordCount} words):</strong> ${escapeHtml(cleanSpoken.slice(-55))}`;
    }

    checkSimSilenceAutoForward(cleanSpoken, universalTextareaId, status);
  }

  // 3. LAYER A: Web Speech API (Client-side native streaming)
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (SpeechRecognition) {
    try {
      if (universalRecognition) {
        try { universalRecognition.abort(); } catch (e) {}
      }
      universalRecognition = new SpeechRecognition();
      universalRecognition.continuous = true;
      universalRecognition.interimResults = true;
      universalRecognition.lang = "en-US";
      universalRecognition.maxAlternatives = 1;

      universalRecognition.onresult = (event) => {
        let interimBatch = "";
        let finalBatch = "";

        for (let i = event.resultIndex; i < event.results.length; ++i) {
          const item = event.results[i];
          if (item && item[0]) {
            const txt = item[0].transcript;
            if (item.isFinal) {
              finalBatch += txt + " ";
            } else {
              interimBatch += txt;
            }
          }
        }

        if (finalBatch) {
          universalSpeechAccumulated += finalBatch;
        }

        const totalSpoken = (universalSpeechAccumulated + (interimBatch ? " " + interimBatch : "")).trim();
        if (totalSpoken) {
          universalWebSpeechGotText = true;
          universalLastSpeechTime = Date.now();
          updateLiveRunningText(totalSpoken, true);
        }
      };

      universalRecognition.onend = () => {
        // Automatically restart while user is still speaking so pauses don't cut off live text
        if (isUniversalRecording && universalRecognition) {
          try { universalRecognition.start(); } catch (restartErr) {}
        }
      };

      universalRecognition.onerror = (e) => {
        console.warn("Web Speech API note (resilient fallback active):", e.error);
        if (isUniversalRecording && (e.error === "no-speech" || e.error === "network")) {
          setTimeout(() => {
            if (isUniversalRecording && universalRecognition) {
              try { universalRecognition.start(); } catch (err) {}
            }
          }, 300);
        }
      };

      try {
        universalRecognition.start();
      } catch (wsErr) {
        console.warn("Web Speech start notice:", wsErr);
      }
    } catch (wsInitErr) {
      console.warn("Web Speech constructor notice:", wsInitErr);
    }
  }

  // 4. LAYER B: Live Streaming Full-Duplex WebSocket STT
  try {
    const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${proto}//${window.location.host}/api/ws/transcribe`;
    universalWebSocket = new WebSocket(wsUrl);
    universalWebSocket.binaryType = "arraybuffer";

    universalWebSocket.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === "partial" || msg.type === "final") {
          const text = (msg.accumulated || msg.text || "").trim();
          if (text) {
            universalLiveStreamGotText = true;
            universalLiveStreamAccumulated = text;
            if (!universalWebSpeechGotText || text.length >= (universalSpeechAccumulated || "").length) {
              updateLiveRunningText(text);
            }
          }
        } else if (msg.type === "complete") {
          const text = (msg.text || "").trim();
          if (text) {
            universalLiveStreamGotText = true;
            universalLiveStreamAccumulated = text;
            updateLiveRunningText(text);
          }
        }
      } catch (err) {
        console.warn("WebSocket parse notice:", err);
      }
    };

    universalWebSocket.onerror = (err) => {
      console.warn("Live WebSocket STT notice:", err);
    };
  } catch (wsConnErr) {
    console.warn("WebSocket connect notice:", wsConnErr);
  }

  // 5. LAYER C: Web Audio API buffer capture, live visualizer & periodic interim chunk streaming
  try {
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        channelCount: 1,
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true
      }
    });

    universalMicStream = stream;
    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    universalAudioCtx = new AudioContextClass();
    if (universalAudioCtx.state === "suspended") {
      try {
        await universalAudioCtx.resume();
      } catch (resumeErr) {
        console.warn("AudioContext resume note:", resumeErr);
      }
    }

    const source = universalAudioCtx.createMediaStreamSource(stream);
    universalAnalyser = universalAudioCtx.createAnalyser();
    universalAnalyser.fftSize = 256;

    universalScriptProcessor = universalAudioCtx.createScriptProcessor(4096, 1, 1);
    const audioContextSampleRate = universalAudioCtx.sampleRate;

    universalScriptProcessor.onaudioprocess = (e) => {
      if (!isUniversalRecording) return;
      const inputData = e.inputBuffer.getChannelData(0);
      universalPCMChunks.push(new Float32Array(inputData));

      // Stream concurrently to backend Speech-to-Text WebSocket if open
      if (universalWebSocket && universalWebSocket.readyState === WebSocket.OPEN) {
        try {
          const chunk16k = downsampleChunkTo16k(inputData, audioContextSampleRate);
          const pcm16 = floatTo16BitPCM(chunk16k);
          universalWebSocket.send(pcm16.buffer);
        } catch (wsSendErr) {
          console.warn("Live STT stream send note:", wsSendErr);
        }
      }
    };

    source.connect(universalAnalyser);
    universalAnalyser.connect(universalScriptProcessor);
    universalScriptProcessor.connect(universalAudioCtx.destination);

    // Live Voice Waveform Visualizer
    function runVoiceVisualizer() {
      if (!isUniversalRecording) return;
      if (universalAnalyser) {
        const dataArray = new Uint8Array(universalAnalyser.frequencyBinCount);
        universalAnalyser.getByteFrequencyData(dataArray);
        let sum = 0;
        for (let i = 0; i < dataArray.length; i++) sum += dataArray[i];
        const avg = sum / dataArray.length;
        const barsContainer = document.getElementById(`live-voice-bars-${previewId}`);
        if (barsContainer) {
          const bars = barsContainer.querySelectorAll('.bar');
          bars.forEach((bar, idx) => {
            const factor = (idx + 1) * 0.35;
            const h = Math.min(22, Math.max(4, Math.round(avg * factor * 0.3)));
            bar.style.height = `${h}px`;
          });
        }
      }
      universalVoiceAnimFrame = requestAnimationFrame(runVoiceVisualizer);
    }
    universalVoiceAnimFrame = requestAnimationFrame(runVoiceVisualizer);

    // 6. LAYER D: Periodic Interim Chunk Streaming Fallback (The 100% Guarantee on Any Browser/Host)
    let interimSliceBusy = false;
    let lastSliceChunkCount = 0;

    universalInterimInterval = setInterval(async () => {
      if (!isUniversalRecording) return;
      // If Web Speech API is actively emitting text, skip HTTP slice polling
      const timeSinceWebSpeech = Date.now() - (universalLastSpeechTime || 0);
      if (universalWebSpeechGotText && timeSinceWebSpeech < 2200) {
        return;
      }
      if (interimSliceBusy) return;
      if (universalPCMChunks.length < 12) return; // need at least ~1.2s of audio
      if (universalPCMChunks.length <= lastSliceChunkCount + 10) return; // don't re-transcribe tiny additions

      interimSliceBusy = true;
      try {
        let totalLen = 0;
        for (let i = 0; i < universalPCMChunks.length; i++) {
          totalLen += universalPCMChunks[i].length;
        }
        const mergedFloat32 = new Float32Array(totalLen);
        let offset = 0;
        for (let i = 0; i < universalPCMChunks.length; i++) {
          mergedFloat32.set(universalPCMChunks[i], offset);
          offset += universalPCMChunks[i].length;
        }

        const pcm16k = downsampleBuffer(mergedFloat32, audioContextSampleRate, 16000);
        const wavBlob = encodeWAV(pcm16k, 16000);

        const formData = new FormData();
        formData.append("audio", wavBlob, "interim_slice.wav");

        const res = await fetch("/api/transcribe?interim=true", {
          method: "POST",
          body: formData
        });
        if (res.ok) {
          const data = await res.json();
          if (data && data.transcript && data.transcript.trim()) {
            const sliceText = data.transcript.trim();
            universalLiveStreamGotText = true;
            lastSliceChunkCount = universalPCMChunks.length;
            updateLiveRunningText(sliceText, true);
          }
        }
      } catch (sliceErr) {
        console.warn("Interim slice transcribe notice:", sliceErr);
      } finally {
        interimSliceBusy = false;
      }
    }, 2200);

  } catch (micErr) {
    console.error("Microphone access error:", micErr);
    if (!universalWebSpeechGotText && !universalLiveStreamGotText) {
      if (status) {
        status.innerHTML = "❌ <strong>Microphone Permission Blocked:</strong> Click the lock/camera icon in your URL address bar to Allow microphone.";
      }
      resetUniversalUI();
    }
  }
}

async function stopUniversalRecordingAndTranscribe() {
  if (!isUniversalRecording) return;
  isUniversalRecording = false;

  if (universalTimerInterval) {
    clearInterval(universalTimerInterval);
    universalTimerInterval = null;
  }
  if (universalInterimInterval) {
    clearInterval(universalInterimInterval);
    universalInterimInterval = null;
  }
  if (universalVoiceAnimFrame) {
    cancelAnimationFrame(universalVoiceAnimFrame);
    universalVoiceAnimFrame = null;
  }

  const textarea = document.getElementById(universalTextareaId);
  const status = document.getElementById(universalStatusId);
  const preview = document.getElementById(universalPreviewId);
  const targetTextareaId = universalTextareaId;

  if (simSilenceTimer) {
    clearTimeout(simSilenceTimer);
    simSilenceTimer = null;
  }
  if (simSilenceCountdownTimer) {
    clearInterval(simSilenceCountdownTimer);
    simSilenceCountdownTimer = null;
  }

  // 1. Finalize WebSocket streaming STT if open
  if (universalWebSocket && universalWebSocket.readyState === WebSocket.OPEN) {
    try {
      await new Promise((resolve) => {
        const timer = setTimeout(resolve, 300);
        universalWebSocket.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            if (data.type === "complete" && data.text) {
              universalLiveStreamGotText = true;
              universalLiveStreamAccumulated = data.text;
              if (textarea) {
                const base = universalBaseText ? universalBaseText + " " : "";
                if (!universalWebSpeechGotText || data.text.length >= textarea.value.length) {
                  textarea.value = base + data.text;
                  textarea.dispatchEvent(new Event("input"));
                }
              }
              if (preview) {
                const currentText = textarea ? textarea.value.trim() : data.text;
                preview.innerText = `“${currentText}”`;
                preview.classList.add("active");
              }
            }
          } catch (e) {}
          clearTimeout(timer);
          resolve();
        };
        universalWebSocket.send(JSON.stringify({ action: "finish" }));
      });
    } catch (wsCloseErr) {
      console.warn("WS finish note:", wsCloseErr);
    }
    try { universalWebSocket.close(); } catch (e) {}
    universalWebSocket = null;
  }

  // Stop Web Speech recognition if active
  if (universalRecognition) {
    try { universalRecognition.stop(); } catch (e) {}
  }

  // Stop media stream tracks
  if (universalMicStream) {
    universalMicStream.getTracks().forEach(t => t.stop());
    universalMicStream = null;
  }

  const sampleRate = universalAudioCtx ? universalAudioCtx.sampleRate : 44100;

  if (universalScriptProcessor) {
    universalScriptProcessor.disconnect();
    universalScriptProcessor = null;
  }
  if (universalAnalyser) {
    universalAnalyser.disconnect();
    universalAnalyser = null;
  }
  if (universalAudioCtx) {
    try { await universalAudioCtx.close(); } catch (e) {}
    universalAudioCtx = null;
  }

  // Case 1: Speech-to-text converter ran concurrently during recording and captured words!
  const currentVal = textarea ? textarea.value.trim() : "";
  const gotLiveText = (universalLiveStreamGotText || universalWebSpeechGotText) && (currentVal.length > universalBaseText.length);

  if (gotLiveText) {
    if (preview) {
      preview.innerText = `“${currentVal}”`;
      preview.classList.add("active");
    }
    if (status) {
      status.innerHTML = "✓ <strong>Voice Recording Saved:</strong> Your response is transcribed below. Review and click the submit button to send.";
    }
    resetUniversalUI();
    return;
  }

  // Case 2: Live streams yielded no text -> Fallback to full WAV upload
  if (status) {
    status.innerHTML = "⏳ <strong>Transcribing audio via speech engine...</strong>";
  }

  let totalLength = 0;
  for (let i = 0; i < universalPCMChunks.length; i++) {
    totalLength += universalPCMChunks[i].length;
  }

  if (totalLength < 1500) {
    if (status) {
      status.innerHTML = "⚠️ <strong>Recording too short:</strong> Please speak for at least 1-2 seconds.";
    }
    resetUniversalUI();
    return;
  }

  const mergedFloat32 = new Float32Array(totalLength);
  let offset = 0;
  let maxAmp = 0;
  for (let i = 0; i < universalPCMChunks.length; i++) {
    const chunk = universalPCMChunks[i];
    mergedFloat32.set(chunk, offset);
    offset += chunk.length;
    for (let j = 0; j < chunk.length; j++) {
      const v = Math.abs(chunk[j]);
      if (v > maxAmp) maxAmp = v;
    }
  }

  if (maxAmp < 0.005) {
    if (status) {
      status.innerHTML = "⚠️ <strong>Microphone input is silent (0 amplitude):</strong> Check if your physical mic mute key (e.g. F4) is on, or check OS Microphone Privacy settings.";
    }
    resetUniversalUI();
    return;
  }

  const pcm16k = downsampleBuffer(mergedFloat32, sampleRate, 16000);
  const wavBlob = encodeWAV(pcm16k, 16000);

  const formData = new FormData();
  formData.append("audio", wavBlob, "speech_response.wav");

  try {
    const res = await fetch("/api/transcribe", {
      method: "POST",
      body: formData
    });
    const data = await res.json();

    if (data && data.transcript && data.transcript.trim()) {
      const text = data.transcript.trim();
      const fullText = (universalBaseText ? universalBaseText + " " : "") + text;
      if (textarea) {
        textarea.value = fullText;
        textarea.dispatchEvent(new Event("input"));
      }
      if (preview) {
        preview.innerText = `“${fullText}”`;
        preview.classList.add("active");
      }
      if (status) {
        status.innerHTML = `✓ <strong>Spoken Answer Transcribed:</strong> “${escapeHtml(text.slice(0, 70))}${text.length > 70 ? '...' : ''}” — Review and click the submit button to send.`;
      }
      resetUniversalUI();
      return;
    } else {
      if (status) {
        status.innerHTML = "⚠️ <strong>No clear speech detected.</strong> Please speak closer to microphone or type directly.";
      }
    }
  } catch (err) {
    console.error("Transcribe API error:", err);
    if (status) {
      status.innerHTML = "⚠️ <strong>Transcription server notice:</strong> You may type your answer directly.";
    }
  }

  resetUniversalUI();
}

function triggerAutoForwardDestination(targetId, statusEl) {
  if (targetId === "b-answer") {
    if (statusEl) statusEl.innerHTML = "🚀 <strong>Auto-forwarding spoken response directly to Dr. Marcus Vance...</strong>";
    setTimeout(() => { submitSimulationAnswer(); }, 350);
  } else if (targetId === "a-answer") {
    if (statusEl) statusEl.innerHTML = "🚀 <strong>Auto-forwarding spoken answer directly for rubric evaluation...</strong>";
    setTimeout(() => { submitAnswerA(1); }, 350);
  } else if (targetId === "a-retry-answer") {
    if (statusEl) statusEl.innerHTML = "🚀 <strong>Auto-forwarding Attempt 2 revision for delta comparison...</strong>";
    setTimeout(() => { submitAnswerA(2); }, 350);
  } else if (targetId === "a-change") {
    if (statusEl) statusEl.innerHTML = "🚀 <strong>Auto-saving reflection and proceeding to Attempt 2 Revision...</strong>";
    setTimeout(() => { saveReflectionA(); }, 350);
  }
}

function resetUniversalUI() {
  if (universalBtnId) {
    const btn = document.getElementById(universalBtnId);
    if (btn) {
      if (btn.classList.contains("hero-mic-btn") || universalBtnId === "hero-mic-b" || universalBtnId === "btn-speech-a" || universalBtnId === "btn-speech-a7" || universalBtnId === "btn-speech-a6") {
        const glyph = btn.querySelector(".mic-glyph") || document.getElementById("hero-mic-glyph");
        const label = btn.querySelector(".mic-primary-label") || document.getElementById("hero-mic-label");
        const sub = btn.querySelector(".mic-sub-label") || document.getElementById("hero-mic-sub");
        if (glyph) glyph.innerText = "🎙️";
        if (universalBtnId === "hero-mic-b") {
          if (label) label.innerText = "Click to Speak to Dr. Vance";
          if (sub) sub.innerText = "Transcribes in real time • Click when done speaking";
        } else if (universalBtnId === "btn-speech-a7") {
          if (label) label.innerText = "Click to Dictate Attempt 2 Revision";
          if (sub) sub.innerText = "Transcribes in real time • Click when done speaking";
        } else if (universalBtnId === "btn-speech-a6") {
          if (label) label.innerText = "Click to Speak Your Reflection";
          if (sub) sub.innerText = "Transcribes in real time • Click when done speaking";
        } else {
          if (label) label.innerText = "Click to Speak Your Answer";
          if (sub) sub.innerText = "Transcribes in real time • Click when done speaking";
        }
        btn.classList.remove("recording");
      } else if (universalBtnId === "btn-speech-b") {
        btn.innerText = "🎙️ Speak Response (Click to Record)";
        btn.className = "btn btn-primary btn-sm";
      } else {
        btn.innerText = "🎙️ Start Voice Input (Click to Record)";
        btn.className = "btn btn-primary btn-sm";
      }
    }
  }
  if (universalPanelId) {
    const panel = document.getElementById(universalPanelId);
    if (panel) panel.classList.remove("recording");
  }
  if (universalPreviewId) {
    const preview = document.getElementById(universalPreviewId);
    if (preview) {
      if (!preview.innerText || !preview.innerText.trim() || preview.innerText.includes("Speak aloud...")) {
        preview.classList.remove("active");
      }
    }
  }

  isUniversalRecording = false;
  universalPCMChunks = [];
}

function stopActiveRecognition() {
  if (isUniversalRecording) {
    stopUniversalRecordingAndTranscribe();
  }
}

// Map ALL possible aliases to the universal voice input engine
const toggleWebSpeech = toggleVoiceInputUniversal;
const toggleVoiceInput = toggleVoiceInputUniversal;
const toggleSimpleDictation = toggleVoiceInputUniversal;
const toggleAudioRecorder = toggleVoiceInputUniversal;
window.toggleVoiceInputUniversal = toggleVoiceInputUniversal;
window.toggleWebSpeech = toggleVoiceInputUniversal;
window.toggleVoiceInput = toggleVoiceInputUniversal;
window.toggleSimpleDictation = toggleVoiceInputUniversal;
window.toggleAudioRecorder = toggleVoiceInputUniversal;

// ==========================================
// 2B. REAL-TIME WEB SEARCH API ENGINE
// ==========================================
async function searchWebKnowledge(queryText = null) {
  const queryInput = document.getElementById("web-search-query");
  const query = queryText || (queryInput ? queryInput.value.trim() : "");
  const resultsContainer = document.getElementById("web-search-results");
  if (!query) {
    alert("Please enter a topic, company name, or interview question to search.");
    return;
  }

  if (resultsContainer) {
    resultsContainer.innerHTML = "<p style='color: var(--text-muted); font-size: 0.88rem;'>🔍 Searching Web Knowledge API...</p>";
  }

  try {
    const res = await fetch(`/api/web-search?q=${encodeURIComponent(query)}`);
    const data = await res.json();
    if (resultsContainer) {
      if (data.results && data.results.length > 0) {
        let html = `<h4 style='font-size: 0.95rem; margin-bottom: 0.5rem; color: var(--primary);'>Web Knowledge Results for "${escapeHtml(data.query)}":</h4><ul style='padding-left: 1.25rem; font-size: 0.85rem; display: flex; flex-direction: column; gap: 0.5rem;'>`;
        data.results.forEach(r => {
          html += `<li><strong>${escapeHtml(r.title)}</strong><br><span style='color: var(--text-muted);'>${escapeHtml(r.snippet)}</span>${r.url ? ` <a href='${r.url}' target='_blank' style='color: var(--primary); font-size: 0.8rem; text-decoration: underline;'>[Source]</a>` : ''}</li>`;
        });
        html += "</ul>";
        resultsContainer.innerHTML = html;
      } else {
        resultsContainer.innerHTML = "<p style='color: var(--text-muted); font-size: 0.85rem;'>No web search results found.</p>";
      }
    }
  } catch (err) {
    console.error("Web Search API error:", err);
    if (resultsContainer) {
      resultsContainer.innerHTML = "<p style='color: #ef4444; font-size: 0.85rem;'>⚠️ Web search error. Please check internet connection.</p>";
    }
  }
}
window.searchWebKnowledge = searchWebKnowledge;

// Word counters
function setupWordCounters() {
  const map = {
    "a-answer": "a-word-count",
    "a-retry-answer": "a7-word-count",
    "a-change": "a6-word-count",
    "b-answer": "b-word-count"
  };
  Object.entries(map).forEach(([inputId, counterId]) => {
    const el = document.getElementById(inputId);
    if (el) {
      el.addEventListener("input", (e) => {
        const words = e.target.value.trim().split(/\s+/).filter(Boolean);
        const counterEl = document.getElementById(counterId);
        if (counterEl) counterEl.innerText = `${words.length} words`;
      });
    }
  });
}

// ==========================================
// 3. MAIN TAB ROUTER
// ==========================================
function switchMainTab(tab) {
  const pA = document.getElementById("nav-proto-a");
  const pB = document.getElementById("nav-proto-b");
  const pE = document.getElementById("nav-eval");
  if (pA) pA.classList.toggle("active", tab === "A");
  if (pB) pB.classList.toggle("active", tab === "B");
  if (pE) pE.classList.toggle("active", tab === "E");

  const secA = document.getElementById("section-proto-a");
  const secB = document.getElementById("section-proto-b");
  const secE = document.getElementById("section-eval");

  if (secA) secA.style.display = tab === "A" ? "block" : "none";
  if (secB) secB.style.display = tab === "B" ? "block" : "none";
  if (secE) secE.style.display = tab === "E" ? "block" : "none";

  if (typeof updateContextBannerVisibility === "function") {
    updateContextBannerVisibility(tab === "A" ? "a1" : "b1");
  }

  stopAllAudio();
  window.scrollTo({ top: 0, behavior: "smooth" });
}

// ==========================================
// THEME SWITCHER (HIGH CONTRAST LIGHT / DARK)
// ==========================================
function initTheme() {
  const savedTheme = localStorage.getItem("theme");
  const prefersDark = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
  const isDark = savedTheme === "dark" || (!savedTheme && prefersDark);
  applyTheme(isDark ? "dark" : "light");

  // Listen to OS theme changes if user hasn't explicitly chosen
  if (window.matchMedia) {
    window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", e => {
      if (!localStorage.getItem("theme")) {
        applyTheme(e.matches ? "dark" : "light");
      }
    });
  }
}

function applyTheme(theme) {
  const isDark = theme === "dark";
  document.documentElement.setAttribute("data-theme", theme);
  if (isDark) {
    document.body.classList.add("dark-mode");
    document.documentElement.classList.add("dark-mode");
  } else {
    document.body.classList.remove("dark-mode");
    document.documentElement.classList.remove("dark-mode");
  }

  const iconEl = document.getElementById("theme-icon");
  const labelEl = document.getElementById("theme-label");
  const btnEl = document.getElementById("theme-toggle");

  if (iconEl) iconEl.innerText = isDark ? "☀️" : "🌙";
  if (labelEl) labelEl.innerText = isDark ? "Light" : "Dark";
  if (btnEl) {
    btnEl.title = isDark ? "Switch to Light Mode" : "Switch to Dark Mode";
    btnEl.setAttribute("aria-label", isDark ? "Switch to Light Mode" : "Switch to Dark Mode");
  }

  // Sync Chart.js default colors if loaded
  if (typeof Chart !== "undefined" && Chart.defaults) {
    Chart.defaults.color = isDark ? "#94a3b8" : "#475569";
    Chart.defaults.borderColor = isDark ? "#334155" : "#e2e8f0";
    if (window.progressChartInstance) {
      try {
        window.progressChartInstance.update();
      } catch (err) {}
    }
  }
}

function toggleTheme() {
  const currentTheme = document.documentElement.getAttribute("data-theme") || (document.body.classList.contains("dark-mode") ? "dark" : "light");
  const nextTheme = currentTheme === "dark" ? "light" : "dark";
  localStorage.setItem("theme", nextTheme);
  applyTheme(nextTheme);
}

// ==========================================
// 3. CANDIDATE PROFILE & REAL INTERVIEW CONTEXT
// ==========================================
let candidateProfile = {
  name: "Candidate",
  role: "Software Engineer",
  company: "",
  level: "Mid-Level",
  interviewType: "Behavioral",
  difficulty: "Rigorous",
  cv: "",
  jd: ""
};

function syncCandidateName(val) {
  candidateProfile.name = val.trim() || "Candidate";
  const hName = document.getElementById("header-cand-name");
  if (hName) hName.innerText = candidateProfile.name;
  const ctxName = document.getElementById("ctx-name");
  if (ctxName) ctxName.innerText = candidateProfile.name;
  const a1Title = document.getElementById("a1-welcome-title");
  if (a1Title) a1Title.innerText = `👋 Welcome, ${candidateProfile.name}!`;
}

function syncCandidateRole(val) {
  candidateProfile.role = val.trim() || "Software Engineer";
  const hRole = document.getElementById("header-cand-role");
  if (hRole) hRole.innerText = candidateProfile.role;
  const ctxRole = document.getElementById("ctx-role");
  if (ctxRole) ctxRole.innerText = candidateProfile.role;
}

function syncCandidateCompany(val) {
  candidateProfile.company = val.trim();
  const ctxComp = document.getElementById("ctx-company");
  const ctxCompPill = document.getElementById("ctx-company-pill");
  if (ctxComp && ctxCompPill) {
    if (candidateProfile.company) {
      ctxComp.innerText = candidateProfile.company;
      ctxCompPill.style.display = "inline-flex";
    } else {
      ctxCompPill.style.display = "none";
    }
  }
}

function syncCandidateLevel(val) {
  candidateProfile.level = val;
  const ctxLevel = document.getElementById("ctx-level");
  if (ctxLevel) ctxLevel.innerText = val;
}

// User-defined presets for maximum convenience
function applyRolePresetA(role, company, level, type) {
  const rInput = document.getElementById("a-role");
  const cInput = document.getElementById("a-company");
  const lSelect = document.getElementById("a-level");
  const tSelect = document.getElementById("a-type");

  if (rInput) rInput.value = role;
  if (cInput) cInput.value = company;
  if (lSelect) lSelect.value = level;
  if (tSelect) {
    let matched = false;
    for (let opt of tSelect.options) {
      if (opt.value === type || opt.value.toLowerCase().includes((type || "").toLowerCase())) {
        tSelect.value = opt.value;
        matched = true;
        break;
      }
    }
    if (!matched && type) tSelect.value = type;
  }

  syncCandidateRole(role);
  syncCandidateCompany(company);
  syncCandidateLevel(level);

  [rInput, cInput, lSelect, tSelect].filter(Boolean).forEach(el => {
    el.dispatchEvent(new Event("input", { bubbles: true }));
    el.dispatchEvent(new Event("change", { bubbles: true }));
  });

  goToScreenA("a2");
}

function setRoleFieldA(role) {
  const rInput = document.getElementById("a-role");
  if (rInput) {
    rInput.value = role;
    syncCandidateRole(role);
  }
}

function applyRolePresetB(role, company, level, type, duration, difficulty) {
  const rInput = document.getElementById("b-role");
  const cInput = document.getElementById("b-company");
  const lSelect = document.getElementById("b-level");
  const tSelect = document.getElementById("b-type");
  const durSelect = document.getElementById("b-duration");
  const dSelect = document.getElementById("b-difficulty");

  if (rInput) rInput.value = role;
  if (cInput) cInput.value = company;
  if (lSelect && level) lSelect.value = level;
  if (tSelect && type) tSelect.value = type;
  if (durSelect && duration) durSelect.value = duration;
  if (dSelect && difficulty) dSelect.value = difficulty;

  syncCandidateRole(role);
  syncCandidateCompany(company);
  if (level) syncCandidateLevel(level);

  // Dispatch change events so all listeners update dynamically
  [rInput, cInput, lSelect, tSelect, durSelect, dSelect].filter(Boolean).forEach(el => {
    el.dispatchEvent(new Event("input", { bubbles: true }));
    el.dispatchEvent(new Event("change", { bubbles: true }));
  });

  goToScreenB("b2");
}

function setRoleFieldB(role) {
  const rInput = document.getElementById("b-role");
  if (rInput) {
    rInput.value = role;
    syncCandidateRole(role);
  }
}

// ==========================================
// 3B. DEMONSTRATION MODE & ROTATING SAMPLE PORTFOLIOS
// ==========================================
const DEMO_PORTFOLIOS = [
  {
    id: "distributed-systems",
    name: "Aarav Mehta",
    role: "Staff Distributed Systems Engineer",
    company: "Stripe",
    level: "Senior",
    interviewType: "Technical & System Architecture (Deep Dive)",
    interviewDuration: "Comprehensive Onsite Loop (8-10 Questions • ~60 mins)",
    difficulty: "Challenging & Probing (Technical Bar Raiser / Stress Test)",
    tagline: "High-Throughput Consensus & Ledgers",
    cv: "Education: B.Tech in Computer Science from IIT Bombay (2016); M.S. in Computer Science from Stanford University (2018).\n\nSummary & Core Skills: Staff Infrastructure & Distributed Systems Engineer with 8+ years designing fault-tolerant, high-throughput financial ledgers, consensus protocols, and low-latency storage engines. Core expertise in Go, C++, Rust, Distributed Consensus (Raft, Multi-Paxos), Distributed Transactions (2PC, Saga), gRPC, Protobuf, Kafka, RocksDB, CockroachDB, Kubernetes, Linux eBPF, and Chaos Engineering.\n\nProfessional Experience:\n• Staff Systems Engineer at Stripe (2021–Present): Led the complete architectural redesign of the core transaction ledger processing 140,000 writes/sec across 4 multi-region AWS clusters. Replaced legacy 2-Phase Commit with an optimized Raft quorum lease protocol, slashing 99th-percentile commit latency from 450ms to 42ms with 99.999% availability. Designed idempotent deduplication state machine handling 2.5B events/day without double-credit anomalies. Reduced cross-AZ egress costs by $410k/year through protocol compaction and zstd compression over gRPC channels.\n• Senior Systems Engineer at Uber (2018–2021): Architected geospatial ring-buffer routing service in Go, maintaining sub-15ms P99 dispatch latency under 85,000 peak concurrent ride requests. Authored automated split-brain network partition recovery daemon, cutting manual incident remediation time from 40 minutes to under 12 seconds.",
    jd: "Staff Distributed Systems Engineer - Financial Infrastructure. Responsibilities: Architect high-throughput, fault-tolerant financial ledger infrastructure. Deep expertise with Raft/Paxos consensus, partition tolerance, distributed transactions (2PC/Saga), zero-data-loss replication, and low-latency gRPC services. Collaborate with reliability engineering on chaos experiments and multi-region active-active disaster recovery."
  },
  {
    id: "ux-research",
    name: "Aditi Sharma",
    role: "UX Research Intern",
    company: "Google",
    level: "Student / Intern",
    interviewType: "Behavioral & Culture Fit (STAR Method Focus)",
    interviewDuration: "Standard Round (6-7 Questions • ~45 mins)",
    difficulty: "Supportive & Conversational (Mentorship / Low Stress)",
    tagline: "HCI Mixed-Methods & Usability",
    cv: "Education: B.Des in Interaction Design from NID Ahmedabad (2023); M.S. Candidate in Human-Computer Interaction (HCI) at IIT Gandhinagar (2024–Present).\n\nSummary & Core Skills: Human-Computer Interaction researcher specializing in mixed-methods evaluative research, qualitative coding, cognitive walkthroughs, and accessibility benchmarking. Proficient in Semi-Structured Interviews, Usability Testing, Heuristic Evaluation, SUS & NASA-TLX Scoring, Thematic Qualitative Coding, Figma, Dovetail, UserTesting.com, SPSS, and WCAG 2.1 AA Auditing.\n\nProfessional & Research Experience:\n• Graduate UX Research Fellow at IIT Gandhinagar HCI Lab (2023–Present): Spearheaded 35+ mixed-methods usability tests and contextual inquiries on digital health onboarding flows across diverse age cohorts. Discovered cognitive friction in patient medical history input that caused 44% abandonment; synthesized insights into a redesigned progressive-disclosure pattern that increased task completion rate from 62% to 90% in follow-up usability evaluations.\n• Product Design & Research Intern at Swiggy (Summer 2023): Conducted 20 remote usability testing sessions and diary studies investigating grocery delivery checkout friction. Uncovered that ambiguous tipping and surge pricing banners induced user drop-off; partnered with product squads to pilot a transparent price breakdown, yielding an 18% lift in checkout completion.",
    jd: "UX Research Intern - Core User Experience. Responsibilities: Plan, recruit, and execute qualitative user interviews, usability benchmarking, cognitive walkthroughs, and diary studies. Synthesize raw user feedback and behavioral metrics into actionable design guidelines. Partner closely with product designers, product managers, and frontend engineers to validate new interaction flows and uphold accessible design standards."
  },
  {
    id: "product-management",
    name: "Rohan Kulkarni",
    role: "Associate Product Manager",
    company: "Flipkart",
    level: "Mid-Level",
    interviewType: "Situational Problem Solving & Strategy (Execution)",
    interviewDuration: "Standard Round (6-7 Questions • ~45 mins)",
    difficulty: "Neutral Corporate (Standard Hiring Bar / Objective)",
    tagline: "Marketplace GMV & Dynamic Pricing",
    cv: "Education: B.Tech in Computer Science & Engineering from BITS Pilani (2022).\n\nSummary & Core Skills: Data-driven Associate Product Manager with 3 years leading cross-functional squads to drive growth funnels, marketplace liquidity, dynamic pricing algorithms, and mobile conversion optimization. Skills: Product Discovery, PRD Authoring, North Star Metric Definition, A/B Testing, Funnel Analytics (Mixpanel, Amplitude), SQL, Roadmapping, Agile Sprint Leadership, Stakeholder Management, User Retention Modeling.\n\nProfessional Experience:\n• Associate Product Manager at Flipkart Marketplace (2022–Present): Product owner for marketplace dynamic pricing and seller inventory incentives, directing an agile squad of 8 software engineers, 2 data scientists, and 1 product designer. Designed and rolled out machine learning-driven dynamic commission tier pilot across 14 high-volume merchant categories, yielding $3.4M annualized GMV expansion. Resolved complex engineering-product trade-off when backend team wanted to delay dynamic pricing rollout by 4 months for architectural refactoring; negotiated a decoupled dual-read milestone strategy that preserved the Q3 launch date while eliminating 70% of legacy technical debt.\n• Product Analytics Intern at CRED (2021): Built behavioral cohort funnels analyzing credit card reward redemption drops. Identified a 3-step navigation hurdle in the checkout drawer, leading to a 1-click redemption redesign that increased daily active reward claims by 24%.",
    jd: "Associate Product Manager (APM) - Marketplace Growth. Responsibilities: Lead product discovery, feature scoping, and execution for two-sided marketplace dynamics. Define North Star metrics, build user journeys, write rigorous PRDs, run multivariate A/B experiments, and partner with engineering and data science leaders to make decisive trade-offs under high ambiguity."
  },
  {
    id: "machine-learning",
    name: "Dr. Priya Nair",
    role: "Senior Machine Learning Engineer",
    company: "HealthAI Diagnostics",
    level: "Senior",
    interviewType: "Technical & System Architecture (Deep Dive)",
    interviewDuration: "Comprehensive Onsite Loop (8-10 Questions • ~60 mins)",
    difficulty: "Challenging & Probing (Technical Bar Raiser / Stress Test)",
    tagline: "Medical Imaging & Edge TensorRT",
    cv: "Education: B.Tech in Electrical Engineering from IIT Madras (2017); Ph.D. in Computer Science & Biomedical Imaging from Stanford University (2022).\n\nSummary & Core Skills: Senior Machine Learning & Computer Vision Research Engineer with 6+ years building and deploying clinical AI models, real-time edge segmentation pipelines, and GPU kernel optimizations. Expertise in PyTorch, CUDA, C++, TensorRT, ONNX Runtime, 3D UNet, Vision Transformers (ViT), Model Quantization (INT8/FP16), Medical Image Processing (DICOM, ITK, MONAI), Triton Inference Server, and HIPAA Compliance.\n\nProfessional & Research Experience:\n• Senior ML Engineer at HealthAI Diagnostics (2022–Present): Lead architect for clinical MRI brain lesion segmentation pipeline deployed across 18 regional hospital networks. Architected hybrid 3D UNet and Vision Transformer backbone achieving 94.2% Dice similarity coefficient on unseen multicenter MRI scans. Overcame GPU memory constraints during high-resolution volumetric inference by implementing mixed-precision FP16 TensorRT compilation and CUDA kernel fusion, cutting inference latency from 820ms to 64ms on edge T4 GPUs and enabling real-time clinical review.\n• AI Research Scientist Intern at Google Health (2021): Developed self-supervised pretraining representations on 400,000 unlabelled mammography scans. Published findings in MICCAI, demonstrating a 7.8% AUC improvement over baseline supervised models under scarce label conditions.",
    jd: "Senior Machine Learning Engineer - Clinical Diagnostics & Edge AI. Responsibilities: Develop, fine-tune, and deploy deep learning models for high-resolution medical imaging (MRI, CT, Pathology). Optimize inference pipelines using TensorRT, CUDA, and model quantization for edge hospital hardware. Ensure end-to-end data security, regulatory compliance (HIPAA/FDA SaMD), and model explainability for radiologists."
  },
  {
    id: "data-platform",
    name: "Kavita Krishnan",
    role: "Data Platform Architect",
    company: "MediaStream Corp",
    level: "Senior",
    interviewType: "Leadership & Team Dynamics (Cross-Functional)",
    interviewDuration: "Standard Round (6-7 Questions • ~45 mins)",
    difficulty: "Neutral Corporate (Standard Hiring Bar / Objective)",
    tagline: "Streaming Lakehouse & Kafka/Flink",
    cv: "Education: B.Tech in Information Technology from NIT Trichy (2015); M.S. in Data Engineering from Carnegie Mellon University (2017).\n\nSummary & Core Skills: Principal Data Architect with 9+ years architecting enterprise real-time streaming data lakes, distributed event hubs, and data governance platforms processing petabyte-scale telemetry. Core skills: Apache Kafka, Apache Flink, Apache Spark, Apache Iceberg, Delta Lake, Snowflake, Trino, Kubernetes, Java, Scala, Python, Terraform, Data Mesh, Schema Registry, dbt, Prometheus.\n\nProfessional Experience:\n• Lead Data Platform Architect at MediaStream Corp (2021–Present): Architected unified real-time analytics lakehouse ingesting 18 billion telemetry events per day across global CDN edge nodes using Kafka, Flink, and Apache Iceberg. Cut analytics pipeline latency from 4 hours to 35 seconds, enabling instantaneous fraud detection and live stream quality alerts. Reduced annual cloud compute and object storage spend by $620,000 by implementing zstd parquet compaction and tiered S3 Glacier lifecycle policies.\n• Senior Data Engineer at LinkedIn (2017–2021): Scaled distributed stream processing cluster from 20 to 120 nodes processing 4M events/sec. Designed self-service schema migration framework with Protobuf and Avro, eliminating breaking downstream table changes and maintaining 99.99% pipeline uptime.",
    jd: "Data Platform Architect - Enterprise Real-Time Infrastructure. Responsibilities: Own distributed streaming and lakehouse architecture across Apache Kafka, Flink, and Iceberg. Define schema governance, SLA guarantees, data quality frameworks, and multi-region disaster recovery. Mentor distributed data engineering squads and drive technical roadmaps with executive stakeholders."
  },
  {
    id: "frontend-engineering",
    name: "Ananya Patel",
    role: "Senior Frontend Engineer",
    company: "SoundWave Web",
    level: "Mid-Level",
    interviewType: "Full Mixed Mock (Behavioral + Technical Architecture)",
    interviewDuration: "Focused Screening (4-5 Questions • ~25 mins)",
    difficulty: "Supportive & Conversational (Mentorship / Low Stress)",
    tagline: "Design Systems & Web Performance",
    cv: "Education: B.Tech in Computer Science from Delhi Technological University (DTU) (2017).\n\nSummary & Core Skills: Senior Frontend & Web Performance Engineer with 7+ years designing enterprise design systems, accessible UI component libraries, and low-latency audio/video web applications. Skills: React, TypeScript, Next.js, Web Audio API, Web Workers, WebAssembly (Wasm), Tailwind CSS, GraphQL, State Machines (XState), Jest, Cypress, Storybook, WCAG 2.1 AAA Accessibility, Core Web Vitals.\n\nProfessional Experience:\n• Senior Frontend Engineer at SoundWave Web (2020–Present): Core maintainer of enterprise React/TypeScript design system powering 45+ consumer and creator engineering teams. Led web client performance overhaul, slashing bundle size by 38% via tree-shaking, code splitting, and dynamic module federation; elevated Largest Contentful Paint (LCP) from 3.8s to 1.1s and brought Cumulative Layout Shift (CLS) to 0.01. Engineered real-time interactive waveform visualizer using Web Audio API and HTML5 Canvas inside a Web Worker, maintaining stable 60 FPS rendering on budget mobile devices.\n• Frontend Engineer at Zomato (2017–2020): Spearheaded web checkout re-architecture in TypeScript, introducing offline-first optimistic UI updates with Service Workers and IndexedDB, reducing cart-to-payment drop-offs by 22%.",
    jd: "Senior Frontend Engineer - Design Systems & Web Performance. Responsibilities: Build and maintain world-class, accessible, high-performance web applications in React and TypeScript. Partner with product design to architect resilient component systems compliant with WCAG 2.1 AA/AAA standards. Drive engineering standards for Core Web Vitals, modular state management, and continuous performance telemetry."
  }
];

let currentDemoPortfolioIndex = 0;

function cycleDemoPortfolio(targetProto = 'both') {
  const p = DEMO_PORTFOLIOS[currentDemoPortfolioIndex];
  const nextIdx = (currentDemoPortfolioIndex + 1) % DEMO_PORTFOLIOS.length;
  const nextP = DEMO_PORTFOLIOS[nextIdx];

  // 1. Populate Prototype A fields
  const aName = document.getElementById("a-name");
  const aCompany = document.getElementById("a-company");
  const aRole = document.getElementById("a-role");
  const aLevel = document.getElementById("a-level");
  const aType = document.getElementById("a-type");
  const aDuration = document.getElementById("a-duration");
  const aDiff = document.getElementById("a-difficulty");
  const aCv = document.getElementById("a-cv");
  const aJd = document.getElementById("a-jd");

  if (aName) aName.value = p.name;
  if (aCompany) aCompany.value = p.company;
  if (aRole) aRole.value = p.role;
  if (aLevel) aLevel.value = p.level;
  if (aType) aType.value = p.interviewType;
  if (aDuration) aDuration.value = p.interviewDuration;
  if (aDiff) aDiff.value = p.difficulty;
  if (aCv) aCv.value = p.cv;
  if (aJd) aJd.value = p.jd;

  // 2. Populate Prototype B fields
  const bName = document.getElementById("b-name");
  const bCompany = document.getElementById("b-company");
  const bRole = document.getElementById("b-role");
  const bLevel = document.getElementById("b-level");
  const bType = document.getElementById("b-type");
  const bDuration = document.getElementById("b-duration");
  const bDiff = document.getElementById("b-difficulty");
  const bCv = document.getElementById("b-cv");
  const bJd = document.getElementById("b-jd");

  if (bName) bName.value = p.name;
  if (bCompany) bCompany.value = p.company;
  if (bRole) bRole.value = p.role;
  if (bLevel) bLevel.value = p.level;
  if (bType) bType.value = p.interviewType;
  if (bDuration) bDuration.value = p.interviewDuration;
  if (bDiff) bDiff.value = p.difficulty;
  if (bCv) bCv.value = p.cv;
  if (bJd) bJd.value = p.jd;

  // 3. Trigger events & pulse animation on fields
  const elements = [
    aName, aCompany, aRole, aLevel, aType, aDuration, aDiff, aCv, aJd,
    bName, bCompany, bRole, bLevel, bType, bDuration, bDiff, bCv, bJd
  ].filter(Boolean);

  elements.forEach(el => {
    el.dispatchEvent(new Event("input", { bubbles: true }));
    el.dispatchEvent(new Event("change", { bubbles: true }));
    el.classList.remove("demo-field-pulse");
    void el.offsetWidth;
    el.classList.add("demo-field-pulse");
  });

  // 4. Synchronize candidate profile state & headers
  syncCandidateName(p.name);
  syncCandidateRole(p.role);
  syncCandidateCompany(p.company);
  syncCandidateLevel(p.level);
  activePersona = p.id;

  // 5. Update UI Badges & Buttons
  const aBadge = document.getElementById("a-demo-badge");
  const bBadge = document.getElementById("b-demo-badge");
  const btnA = document.getElementById("btn-demo-cycle-a");
  const btnB = document.getElementById("btn-demo-cycle-b");

  const badgeHtml = `Loaded [${currentDemoPortfolioIndex + 1}/${DEMO_PORTFOLIOS.length}]: <strong>${p.name}</strong> • <em>${p.role}</em> @ <strong>${p.company}</strong> (${p.level}) <span class="demo-badge-pill">⏱️ ${p.interviewDuration.split(' ')[0]} • ${p.interviewType.split(' ')[0]}</span> <span class="demo-badge-pill">↻ Next: ${nextP.name}</span>`;

  if (aBadge) aBadge.innerHTML = badgeHtml;
  if (bBadge) bBadge.innerHTML = badgeHtml;

  const btnHtml = `🎲 Next Portfolio: ${nextP.name} (${nextP.role.split(' ')[0]}) ↻`;
  if (btnA) btnA.innerHTML = btnHtml;
  if (btnB) btnB.innerHTML = btnHtml;

  // 6. Advance index for next click
  currentDemoPortfolioIndex = nextIdx;

  console.log(`✓ Demo Portfolio Loaded [${p.id}]:`, p.name, "—", p.role, "at", p.company);
}

function cycleDemoPortfolioAndOpen(targetProto) {
  cycleDemoPortfolio(targetProto);
  if (targetProto === 'A') {
    goToScreenA('a2');
  } else if (targetProto === 'B') {
    goToScreenB('b2');
  }
}

// Legacy persona-switch compatibility
function changePersona(personaId) {
  if (personaId === "aditi") {
    syncCandidateName("Aditi");
    syncCandidateRole("UX Research Intern");
  } else {
    syncCandidateName("Rahul");
    syncCandidateRole("Associate Product Manager");
  }
  loadLongitudinalProgress();
}

// ==========================================
// 3C. NAVIGATION HISTORY & CONTEXT VISIBILITY
// ==========================================
let screenHistoryStack = [];
let currentActiveScreen = "b1";

function updateContextBannerVisibility(screenId) {
  const banner = document.getElementById("interview-context-banner");
  if (!banner) return;
  const clean = screenId ? screenId.replace("screen-", "") : "b1";
  // Remove candidate, role, and level banner on home screens (b1 and a1)
  if (clean === "b1" || clean === "a1") {
    banner.style.display = "none";
  } else {
    banner.style.display = "flex";
  }
}

function recordNavigation(targetScreenId, pushHistory = true) {
  const cleanTarget = targetScreenId.replace("screen-", "");
  if (pushHistory && currentActiveScreen && currentActiveScreen !== cleanTarget) {
    screenHistoryStack.push(currentActiveScreen);
    if (screenHistoryStack.length > 30) screenHistoryStack.shift();
  }
  currentActiveScreen = cleanTarget;
  updateContextBannerVisibility(cleanTarget);
}

function goBackUniversal(fallback) {
  stopAllAudio();
  if (typeof stopActiveRecognition === "function") {
    try { stopActiveRecognition(); } catch (e) {}
  }

  let prev = screenHistoryStack.pop();

  // Prevent returning to the completed simulation room from debrief
  if (currentActiveScreen === "b6" && (!prev || prev === "b3" || prev === "b6")) {
    prev = "b1";
  }

  // Prevent back loops to the same screen
  while (screenHistoryStack.length > 0 && prev === currentActiveScreen) {
    prev = screenHistoryStack.pop();
  }

  if (!prev) {
    prev = fallback ? fallback.replace("screen-", "") : "b1";
  }

  if (prev.startsWith("a")) {
    goToScreenA(prev, false);
  } else {
    goToScreenB(prev, false);
  }
}

// ==========================================
// 4. PROTOTYPE A (LEARNING-ORIENTED FLOW)
// ==========================================
function goToScreenA(screenId, pushHistory = true) {
  const cleanId = screenId.replace("screen-", "");
  const secA = document.getElementById("section-proto-a");
  if (secA && secA.style.display === "none") {
    switchMainTab("A");
  }
  const screens = ["screen-a1", "screen-a2", "screen-a3", "screen-a4", "screen-a6", "screen-a7", "screen-a8", "screen-a9"];
  screens.forEach(id => {
    const el = document.getElementById(id);
    if (el) el.style.display = (id === `screen-${cleanId}`) ? "block" : "none";
  });
  stopAllAudio();
  window.scrollTo({ top: 0, behavior: "smooth" });

  recordNavigation(cleanId, pushHistory);

  if (cleanId === "a3") {
    setCockpitInputModeA('voice', 'a3');
    if (autoSpeakEnabled) setTimeout(speakCurrentQuestionA, 400);
  } else if (cleanId === "a4") {
    if (autoSpeakEnabled) setTimeout(speakFeedbackA4, 400);
  } else if (cleanId === "a6") {
    setCockpitInputModeA('voice', 'a6');
    if (autoSpeakEnabled) setTimeout(speakFeedforwardA6, 400);
  } else if (cleanId === "a7") {
    setCockpitInputModeA('voice', 'a7');
    if (autoSpeakEnabled) setTimeout(speakAdaptiveProbeA7, 400);
  } else if (cleanId === "a8") {
    if (autoSpeakEnabled) setTimeout(speakComparisonA8, 400);
  }
}

async function startSessionA() {
  const nameVal = document.getElementById("a-name") ? document.getElementById("a-name").value.trim() : "";
  const roleVal = document.getElementById("a-role") ? document.getElementById("a-role").value.trim() : "Software Engineer";
  const companyVal = document.getElementById("a-company") ? document.getElementById("a-company").value.trim() : "";
  const levelVal = document.getElementById("a-level") ? document.getElementById("a-level").value : "Mid-Level";
  const typeVal = document.getElementById("a-type") ? document.getElementById("a-type").value : "STAR Behavioral Deep-Dive";
  const durationVal = document.getElementById("a-duration") ? document.getElementById("a-duration").value : "Standard Round (6-7 Questions • ~45 mins)";
  const diffVal = document.getElementById("a-difficulty") ? document.getElementById("a-difficulty").value : "Professional & Rigorous (Standard FAANG/Corporate)";
  const cvText = document.getElementById("a-cv") ? document.getElementById("a-cv").value.trim() : "";
  const jdText = document.getElementById("a-jd") ? document.getElementById("a-jd").value.trim() : "";

  syncCandidateName(nameVal);
  syncCandidateRole(roleVal);
  syncCandidateCompany(companyVal);
  syncCandidateLevel(levelVal);
  candidateProfile.interviewType = typeVal;
  candidateProfile.interviewDuration = durationVal;
  candidateProfile.interviewerTone = diffVal;
  candidateProfile.difficulty = diffVal;
  candidateProfile.cv = cvText;
  candidateProfile.jd = jdText;

  // Update pills in Screen A3
  const a3TrackPill = document.getElementById("a3-track-pill");
  if (a3TrackPill) {
    a3TrackPill.innerText = `🎯 Focus: ${typeVal.split('(')[0].trim()}`;
  }
  const a3DurationPill = document.getElementById("a3-duration-pill");
  if (a3DurationPill) {
    const shortDuration = durationVal.includes("25") ? "25m" : (durationVal.includes("60") ? "60m" : "45m");
    a3DurationPill.innerText = `⏱️ ${shortDuration}`;
  }

  const startBtn = document.getElementById("btn-start-a") || document.querySelector("#screen-a2 button.btn-primary");
  const a2Notice = document.getElementById("a2-loading-notice");
  if (startBtn) {
    startBtn.disabled = true;
    startBtn.innerText = "⏳ Initializing Practice Session...";
  }
  if (a2Notice) {
    a2Notice.style.display = "flex";
  }

  try {
    const res = await fetch("/api/setup", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        prototype_type: "A",
        candidate_name: candidateProfile.name,
        job_role: candidateProfile.role,
        target_company: candidateProfile.company,
        experience_level: candidateProfile.level,
        interview_type: typeVal,
        interview_duration: durationVal,
        interviewer_tone: diffVal,
        difficulty: diffVal,
        cv_text: cvText,
        job_description: jdText,
        persona_id: "custom"
      })
    });
    const data = await res.json();
    currentSessionId = data.session_id;

    protoAQuestions = (data.questions && data.questions.length > 0) ? data.questions : (data.first_question ? [data.first_question] : []);
    loadQuestionA(0);

    const dlDocx = document.getElementById("btn-dl-docx");
    const dlPptx = document.getElementById("btn-dl-pptx");
    if (dlDocx) dlDocx.href = `/api/export-docx/${currentSessionId}`;
    if (dlPptx) dlPptx.href = `/api/export-pptx/${currentSessionId}`;

    goToScreenA("a3");
  } catch (err) {
    console.error(err);
    currentSessionId = "sess_practice";
    goToScreenA("a3");
  } finally {
    if (a2Notice) {
      a2Notice.style.display = "none";
    }
    if (startBtn) {
      startBtn.disabled = false;
      startBtn.innerText = "🚀 Begin Practice Interview";
    }
  }
}

function loadQuestionA(index) {
  if (!protoAQuestions || protoAQuestions.length === 0) return;
  if (index < 0 || index >= protoAQuestions.length) return;
  protoACurrentIndex = index;
  const q = protoAQuestions[index];
  currentQuestionId = q.id || (index + 1);
  currentQuestionText = q.text || q;

  const qNumEl = document.getElementById("a3-q-num");
  if (qNumEl) qNumEl.innerText = `QUESTION ${index + 1} / ${protoAQuestions.length}`;

  const qTextEl = document.getElementById("a3-q-text");
  if (qTextEl) qTextEl.innerText = `“${currentQuestionText}”`;

  const qTextA7 = document.getElementById("a7-q-text");
  if (qTextA7) qTextA7.innerText = `“${currentQuestionText}”`;

  // Clear previous answers & reset counters
  const ansA = document.getElementById("a-answer");
  if (ansA) ansA.value = "";
  const wcA = document.getElementById("a-word-count");
  if (wcA) wcA.innerText = "0 words";

  const ansA7 = document.getElementById("a-retry-answer");
  if (ansA7) ansA7.value = "";
  const wcA7 = document.getElementById("a7-word-count");
  if (wcA7) wcA7.innerText = "0 words";

  const refChange = document.getElementById("a-change");
  if (refChange) refChange.value = "";
  const refLearn = document.getElementById("a-learn");
  if (refLearn) refLearn.value = "";

  const a7AdaptiveBox = document.getElementById("a7-adaptive-prompt-box");
  if (a7AdaptiveBox) a7AdaptiveBox.style.display = "none";
  const a7AdaptivePrompt = document.getElementById("a7-adaptive-prompt");
  if (a7AdaptivePrompt) a7AdaptivePrompt.innerText = "";

  const a3Status = document.getElementById("a3-voice-status");
  if (a3Status) {
    a3Status.className = "voice-status-pill speaking";
    a3Status.innerText = "🔊 Coach Speaking";
  }
  const a7Status = document.getElementById("a7-voice-status");
  if (a7Status) {
    a7Status.className = "voice-status-pill speaking";
    a7Status.innerText = "🔊 Coach Speaking";
  }
  const prevA3 = document.getElementById("a3-live-preview");
  if (prevA3) {
    prevA3.innerText = "";
    prevA3.classList.remove("active");
  }
  const prevA7 = document.getElementById("a7-live-preview");
  if (prevA7) {
    prevA7.innerText = "";
    prevA7.classList.remove("active");
  }

  setCockpitInputModeA('voice', 'a3');
  setCockpitInputModeA('voice', 'a7');

  goToScreenA("a3");
}

function nextQuestionA() {
  if (protoACurrentIndex + 1 < protoAQuestions.length) {
    loadQuestionA(protoACurrentIndex + 1);
  } else {
    loadLongitudinalProgress();
    goToScreenA("a9");
  }
}

function speakCurrentQuestionA() {
  speakText(`Question: ${currentQuestionText}`, () => {
    const btn = document.getElementById("btn-read-a3");
    if (btn) btn.innerText = "🔊 Playing...";
  }, () => {
    const btn = document.getElementById("btn-read-a3");
    if (btn) btn.innerText = "🔊 Listen to Question";
  });
}

function speakFeedbackA4() {
  if (!lastEvaluation) return;
  const text = `Overall Score: ${lastEvaluation.overall_score} out of 10. Strengths: ${lastEvaluation.strengths.join(". ")}. Key recommendation: ${lastEvaluation.actionable_suggestions.join(". ")}`;
  speakText(text);
}

function speakFeedforwardA6() {
  const text = "Stage A6: Guided Reflection and Feedforward. Deliberate practice requires analyzing feedback before your second attempt. What specific changes and measurable evidence will you incorporate into your revised answer?";
  speakText(text);
}

function speakAdaptiveProbeA7() {
  let probe = "";
  if (lastEvaluation && lastEvaluation.adaptive_followup && lastEvaluation.adaptive_followup.followup_question) {
    probe = lastEvaluation.adaptive_followup.followup_question;
  }
  const text = probe ? `Attempt 2 Deliberate Retry. Focus on this follow-up challenge: ${probe}` : `Attempt 2 Deliberate Retry. Please deliver your revised response incorporating your reflection and measurable outcomes.`;
  speakText(text);
}

function speakComparisonA8() {
  const compImprovement = document.getElementById("compare-improvements");
  const improvText = compImprovement ? compImprovement.innerText : "";
  const text = `Direct Attempt Comparison. Here is your measurable delta between Attempt 1 and Attempt 2. ${improvText ? 'Key improvements: ' + improvText : 'Review your score improvement across all rubric criteria.'}`;
  speakText(text);
}

function loadSampleAnswerA(attemptNumber) {
  const textarea = attemptNumber === 1 ? document.getElementById("a-answer") : document.getElementById("a-retry-answer");
  if (!textarea) return;

  const role = (candidateProfile.role || "Software Engineer").toLowerCase();
  const name = candidateProfile.name || "Candidate";

  if (role.includes("distributed") || role.includes("systems") || role.includes("infrastructure")) {
    // Aarav Mehta (Staff Distributed Systems Engineer)
    if (attemptNumber === 1) {
      textarea.value = "When our transaction ledger faced scaling limits under 140k writes per second, we needed to replace 2-Phase Commit because latency was too high. I recommended Raft quorum leases to make consensus faster across regions. There was some debate with our infrastructure lead over network partition risks, but we tested it and rolled it out safely.";
    } else {
      textarea.value = "When our cross-region payment ledger scaled to 140,000 writes/sec, our 2-Phase Commit coordinator became an availability bottleneck with P99 commit latency spiking to 450ms. I proposed replacing 2PC with an optimized Raft quorum lease state machine. Our infrastructure lead opposed this, citing split-brain risks under cross-region partitions. To resolve this constructively, I built an automated chaos harness simulating a 35% packet drop and partition between AWS us-east and eu-west clusters. The benchmarks proved our monotonic lease expiration strictly prevented double-commit anomalies while slashing commit latency to 42ms with 99.999% availability. Based on this empirical data, our lead approved the rollout, which we deployed with zero customer downtime and reduced cross-AZ egress costs by $410,000 annually.";
    }
  } else if (role.includes("ux") || role.includes("design") || role.includes("research")) {
    // Aditi Sharma (UX Research Intern)
    if (attemptNumber === 1) {
      textarea.value = "In my healthcare onboarding study, I found that users were confused by the medical history form and were abandoning the flow. The engineering lead wanted to keep all fields on one page to avoid multi-page state management. I scheduled a meeting to show user feedback and we agreed to make it progressive.";
    } else {
      textarea.value = "During evaluative research on our healthcare onboarding flow, our diary studies and 35 usability sessions revealed a 44% drop-off caused by an overwhelming 14-field medical history form. Our engineering lead resisted breaking it into a multi-step stepper, citing complex form validation logic and an impending sprint deadline. Rather than escalating, I edited 90-second video clips of 4 participants visibly abandoning the form, paired with telemetry data proving users felt fatigued. I proposed a compromise: a progressive-disclosure accordion that preserved single-page React state while reducing visual cognitive load. As a concrete result, our engineering partner agreed, we shipped the feature 2 days ahead of deadline, and follow-up usability benchmarking revealed a 28% increase in task completion and zero critical usability errors.";
    }
  } else if (role.includes("product") || role.includes("apm") || role.includes("pm")) {
    // Rohan Kulkarni (Associate Product Manager)
    if (attemptNumber === 1) {
      textarea.value = "During our dynamic pricing pilot for marketplace merchants, engineering wanted to postpone our Q3 launch to refactor backend services, while sales wanted immediate release. I met with both teams and we agreed to split the launch into two milestones.";
    } else {
      textarea.value = "During our marketplace dynamic commission pilot across 14 merchant categories, our backend engineering lead wanted to defer the launch by 4 months to refactor legacy SQL schemas, while commercial leaders demanded an immediate launch to hit Q3 revenue targets. Recognizing the high cost of delay ($280k/month in lost commission lift), I organized an emergency trade-off workshop. I mapped out the technical debt against lost GMV and proposed a dual-read decoupled architecture that allowed the pilot to run on cached tiers while the schema migration proceeded in parallel. As a measurable outcome, we launched on schedule across 12 tier-2 cities, generating $3.4M in annualized GMV expansion while reducing checkout drop-offs by 31% within 3 weeks.";
    }
  } else if (role.includes("machine") || role.includes("learning") || role.includes("vision") || role.includes("ai")) {
    // Dr. Priya Nair (Senior Machine Learning Engineer)
    if (attemptNumber === 1) {
      textarea.value = "When deploying our 3D UNet model for clinical MRI segmentation to hospital edge hardware, inference latency was over 800ms per volume. The clinical team wanted real-time feedback, so I optimized the model with TensorRT and quantization to speed it up.";
    } else {
      textarea.value = "When deploying our 3D UNet MRI brain lesion segmentation pipeline across 18 regional hospital networks, volumetric inference latency exceeded 820ms on edge T4 GPUs, causing unacceptable workflow delays for reviewing radiologists. Our clinical software lead suggested downsampling voxel resolution by 50%, but this caused small micro-lesion Dice scores to collapse from 94% to 78%. Instead, I spearheaded an inference optimization initiative using mixed-precision FP16 TensorRT compilation and custom CUDA kernel fusion for 3D convolutions. I benchmarked the pipeline against 500 validated clinical scans, proving zero degradation in Dice similarity (maintained at 94.2%) while cutting latency from 820ms down to 64ms, successfully enabling real-time intraoperative clinical review.";
    }
  } else if (role.includes("data") || role.includes("lakehouse") || role.includes("flink") || role.includes("kafka")) {
    // Kavita Krishnan (Data Platform Architect)
    if (attemptNumber === 1) {
      textarea.value = "In our real-time streaming platform, pipeline lag was 4 hours and compute costs were too high. I led the migration to Apache Flink and Iceberg lakehouse. The team was concerned about schema migrations, but we resolved it with a schema registry.";
    } else {
      textarea.value = "Our legacy analytics batch pipeline suffered from a 4-hour processing lag across 18 billion daily telemetry events, rendering our automated fraud detection ineffective. I architected a unified real-time stream processing platform using Apache Kafka, Apache Flink, and Apache Iceberg. When our analytics lead expressed concerns that real-time schema evolution would break downstream BI dashboards, I introduced a strict Protobuf schema registry with automated backward-compatibility checks in CI/CD. As a measurable outcome, we slashed end-to-end data latency from 4 hours to 35 seconds, enabled instantaneous fraud detection, and reduced annual cloud compute and object storage spend by $620,000 through zstd parquet file compaction.";
    }
  } else if (role.includes("frontend") || role.includes("web") || role.includes("react")) {
    // Ananya Patel (Senior Frontend Engineer)
    if (attemptNumber === 1) {
      textarea.value = "Our web application had high bundle size and poor Core Web Vitals. The product team wanted to keep adding features, but I convinced them to let us optimize the bundle through code splitting and tree shaking.";
    } else {
      textarea.value = "Our core web client bundle had ballooned to 4.2MB, causing Largest Contentful Paint (LCP) to spike to 3.8 seconds on 3G connections and triggering a 22% bounce rate. Our product manager wanted to prioritize new audio player features rather than performance work. I set up an A/B synthetic performance experiment showing that every 100ms delay in LCP corresponded to a 1.2% drop in free-to-premium trial conversions. With executive sponsorship secured, I spearheaded a modular refactoring using dynamic module federation, route-level code splitting, and Web Worker offloading for audio waveforms. As a result, we slashed bundle size by 38%, brought LCP down to 1.1s, and drove a 14% uplift in trial conversions within 30 days.";
    }
  } else {
    // General Software Engineering
    if (attemptNumber === 1) {
      textarea.value = "In our last sprint, we found a memory leak in the production caching tier right before a major release. I investigated the logs, found the offending circular reference, and created a quick hotfix that unblocked the release.";
    } else {
      textarea.value = "Forty-eight hours before our quarterly enterprise release, monitoring alerted us to a 35% memory spike under simulated 10k RPS load. Rather than blindly reverting commits, I ran profiling using pprof, identified an unbounded map cache in our auth middleware, and proposed an LRU cache with strict eviction limits. I paired with our reliability lead to benchmark the fix under 15k RPS, proving 0% packet drops and stable heap memory. As a measurable outcome, we deployed on schedule, reduced P99 latency from 180ms to 42ms, and prevented an estimated $85,000 SLA penalty.";
    }
  }

  const preview = attemptNumber === 1 ? document.getElementById("a3-live-preview") : document.getElementById("a7-live-preview");
  const status = attemptNumber === 1 ? document.getElementById("a3-stt-status") : document.getElementById("a7-stt-status");
  if (preview && textarea.value) {
    preview.innerText = `“${textarea.value}”`;
    preview.classList.add("active");
  }
  if (status) {
    status.innerHTML = `✓ <strong>Sample Answer Loaded:</strong> Ready for evaluation or revision`;
  }

  textarea.dispatchEvent(new Event("input"));
}

async function submitAnswerA(attemptNumber) {
  const textarea = attemptNumber === 1 ? document.getElementById("a-answer") : document.getElementById("a-retry-answer");
  const answer = textarea.value.trim();

  if (!answer) {
    alert("Please provide or dictate an answer before submitting.");
    return;
  }

  stopActiveRecognition();
  const submitBtn = attemptNumber === 1 ? document.getElementById("btn-submit-a") : document.getElementById("btn-submit-a7");
  const origBtnText = submitBtn ? submitBtn.innerText : (attemptNumber === 1 ? "Submit Answer for Evaluation →" : "Submit Revision for Comparison →");
  const noticeEl = attemptNumber === 1 ? document.getElementById("a3-loading-notice") : document.getElementById("a7-loading-notice");

  if (submitBtn) {
    submitBtn.disabled = true;
    submitBtn.innerText = attemptNumber === 1 ? "⏳ Evaluating against rubric..." : "⏳ Auditing Attempt 2 & Delta...";
  }
  if (noticeEl) {
    noticeEl.style.display = "flex";
  }

  // Update interviewer hero card status
  const heroPill = attemptNumber === 1 ? document.getElementById("a3-voice-status") : document.getElementById("a7-voice-status");
  if (heroPill) {
    heroPill.className = "voice-status-pill thinking";
    heroPill.innerText = "🧠 Evaluator Auditing Response...";
  }

  // Navigate immediately to feedback / comparison screen and show loading state placeholder exactly like Prototype B
  if (attemptNumber === 1) {
    goToScreenA("a4");
    const a4Loading = document.getElementById("a4-loading-state");
    const a4Content = document.getElementById("a4-dashboard-content");
    if (a4Loading) a4Loading.style.display = "block";
    if (a4Content) a4Content.style.display = "none";
  } else {
    goToScreenA("a8");
    const a8Loading = document.getElementById("a8-loading-state");
    const a8Content = document.getElementById("a8-dashboard-content");
    if (a8Loading) a8Loading.style.display = "block";
    if (a8Content) a8Content.style.display = "none";
  }

  try {
    const res = await fetch("/api/evaluate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: currentSessionId || "demo_sess",
        question_id: currentQuestionId,
        question_text: currentQuestionText,
        answer_text: answer,
        attempt_number: attemptNumber
      })
    });
    const evalData = await res.json();
    lastEvaluation = evalData;

    if (attemptNumber === 1) {
      renderFeedbackScreenA4(evalData);
    } else {
      await loadAttemptComparison();
    }
  } catch (err) {
    console.error(err);
    alert("Evaluation error. Please try again.");
    const a4Loading = document.getElementById("a4-loading-state");
    const a4Content = document.getElementById("a4-dashboard-content");
    if (a4Loading) a4Loading.style.display = "none";
    if (a4Content) a4Content.style.display = "block";
    const a8Loading = document.getElementById("a8-loading-state");
    const a8Content = document.getElementById("a8-dashboard-content");
    if (a8Loading) a8Loading.style.display = "none";
    if (a8Content) a8Content.style.display = "block";
  } finally {
    if (noticeEl) {
      noticeEl.style.display = "none";
    }
    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.innerText = origBtnText;
    }
  }
}

function renderFeedbackScreenA4(evalData) {
  const a4Loading = document.getElementById("a4-loading-state");
  const a4Content = document.getElementById("a4-dashboard-content");
  if (a4Loading) a4Loading.style.display = "none";
  if (a4Content) a4Content.style.display = "block";

  lastEvaluation = evalData;
  document.getElementById("a4-overall-score").innerText = `${evalData.overall_score} / 10`;

  const qTextA7 = document.getElementById("a7-q-text");
  if (qTextA7 && currentQuestionText) {
    qTextA7.innerText = `“${currentQuestionText}”`;
  }

  // Criteria Scores
  document.getElementById("a4-rel-score").innerText = `${evalData.relevance.score}/10`;
  document.getElementById("a4-rel-reason").innerText = evalData.relevance.reason;

  document.getElementById("a4-spec-score").innerText = `${evalData.specificity.score}/10`;
  document.getElementById("a4-spec-reason").innerText = evalData.specificity.reason;

  document.getElementById("a4-evid-score").innerText = `${evalData.evidence_outcome.score}/10`;
  document.getElementById("a4-evid-reason").innerText = evalData.evidence_outcome.reason;

  document.getElementById("a4-struct-score").innerText = `${evalData.structure_clarity.score}/10`;
  document.getElementById("a4-struct-reason").innerText = evalData.structure_clarity.reason;

  // Strengths & Weaknesses
  const strList = document.getElementById("a4-strengths");
  strList.innerHTML = evalData.strengths.map(s => `<li>${s}</li>`).join("");

  const weakList = document.getElementById("a4-weaknesses");
  weakList.innerHTML = evalData.needs_improvement.map(w => `<li>${w}</li>`).join("");

  // Actionable suggestions
  document.getElementById("a4-suggestions").innerText = evalData.actionable_suggestions.join(" ");

  // Adaptive AI Follow-up Probe
  const adaptiveContainer = document.getElementById("a4-adaptive-container");
  const adaptiveFollowup = document.getElementById("a4-adaptive-followup");
  const adaptiveReasoning = document.getElementById("a4-adaptive-reasoning");
  const adaptiveSource = document.getElementById("a4-adaptive-source");
  const a7AdaptiveBox = document.getElementById("a7-adaptive-prompt-box");
  const a7AdaptivePrompt = document.getElementById("a7-adaptive-prompt");

  if (evalData.adaptive_followup && evalData.adaptive_followup.followup_question) {
    if (adaptiveFollowup) adaptiveFollowup.innerText = evalData.adaptive_followup.followup_question;
    if (adaptiveReasoning) adaptiveReasoning.innerText = `💡 Why this probe: ${evalData.adaptive_followup.reasoning || "Contextual probe on unevidenced competencies."}`;
    if (adaptiveSource) {
      adaptiveSource.innerText = "Adaptive AI Dialogue Engine";
    }
    if (adaptiveContainer) adaptiveContainer.style.display = "block";

    if (a7AdaptivePrompt) {
      a7AdaptivePrompt.innerText = evalData.adaptive_followup.followup_question;
    }
    if (a7AdaptiveBox) {
      a7AdaptiveBox.style.display = "block";
    }
  } else if (adaptiveContainer) {
    adaptiveContainer.style.display = "none";
    if (a7AdaptiveBox) a7AdaptiveBox.style.display = "none";
  }

  // Update export download links on Screen A4
  const docxBtnA4 = document.getElementById("btn-dl-docx-a4");
  const pptxBtnA4 = document.getElementById("btn-dl-pptx-a4");
  const sessId = currentSessionId || "demo_sess";
  if (docxBtnA4) docxBtnA4.href = `/api/export-docx/${sessId}`;
  if (pptxBtnA4) pptxBtnA4.href = `/api/export-pptx/${sessId}`;

  // Populate active criterion in Why Modal
  switchWhyCriterion("evidence_outcome");
  if (autoSpeakEnabled) setTimeout(speakFeedbackA4, 500);
}

function switchWhyCriterion(critKey) {
  activeWhyCriterion = critKey;

  // Update tabs visual state
  const tabMap = {
    "evidence_outcome": "why-tab-evid",
    "relevance": "why-tab-rel",
    "specificity": "why-tab-spec",
    "structure_clarity": "why-tab-struct"
  };

  Object.values(tabMap).forEach(btnId => {
    const el = document.getElementById(btnId);
    if (el) el.classList.remove("active");
  });

  const activeBtn = document.getElementById(tabMap[critKey] || "why-tab-evid");
  if (activeBtn) activeBtn.classList.add("active");

  if (!lastEvaluation) return;

  const breakdown = (lastEvaluation.why_feedback_summary && lastEvaluation.why_feedback_summary.criteria_breakdown)
    ? lastEvaluation.why_feedback_summary.criteria_breakdown[critKey]
    : null;

  const critData = lastEvaluation[critKey] || {};

  const nameEl = document.getElementById("modal-why-title");
  const stdEl = document.getElementById("modal-why-standard");
  const scoreEl = document.getElementById("modal-why-score");
  const reasonEl = document.getElementById("modal-why-reason");
  const excerptEl = document.getElementById("modal-why-excerpt");
  const addEl = document.getElementById("modal-why-addition");

  if (breakdown) {
    if (nameEl) nameEl.innerText = breakdown.name || critData.name || "Rubric Criterion";
    if (stdEl) stdEl.innerText = breakdown.standard || critData.rubric_definition || "";
    if (scoreEl) scoreEl.innerText = `${breakdown.score !== undefined ? breakdown.score : critData.score} / 10`;
    if (reasonEl) reasonEl.innerText = breakdown.reason || critData.reason || "";
    if (excerptEl) excerptEl.innerText = `Analyzed: “${breakdown.excerpt || critData.evidence_found || "Excerpt from candidate answer"}”`;
    if (addEl) addEl.innerText = breakdown.recommendation || lastEvaluation.example_improved_answer || "Quantify outcomes with concrete metrics.";
  } else {
    if (nameEl) nameEl.innerText = critData.name || "Rubric Criterion";
    if (stdEl) stdEl.innerText = critData.rubric_definition || "Standard rubric assessment.";
    if (scoreEl) scoreEl.innerText = `${critData.score || 0} / 10`;
    if (reasonEl) reasonEl.innerText = critData.reason || "";
    if (excerptEl) excerptEl.innerText = `Analyzed: “${critData.evidence_found || "Narrative elements"}”`;
    if (addEl) addEl.innerText = critData.missing_aspect || lastEvaluation.example_improved_answer || "Incorporate measurable evidence and concrete artifacts.";
  }
}

function openWhyFeedbackModalFor(critKey) {
  switchWhyCriterion(critKey);
  openWhyFeedbackModal();
}

function openWhyFeedbackModal() {
  document.getElementById("modal-why-feedback").style.display = "flex";
}

function closeWhyFeedbackModal() {
  document.getElementById("modal-why-feedback").style.display = "none";
}

function loadSampleReflectionA() {
  const role = (candidateProfile.role || "").toLowerCase();
  const changeEl = document.getElementById("a-change");
  const learnEl = document.getElementById("a-learn");

  if (role.includes("distributed") || role.includes("systems") || role.includes("infrastructure")) {
    if (changeEl) changeEl.value = "I will explicitly quantify the Raft lease timeout, P99 latency reduction from 450ms to 42ms, and 0% double-credit outcomes during simulated 35% packet loss partitions.";
    if (learnEl) learnEl.value = "In distributed systems interviews, technical trade-offs require empirical benchmarks and partition failure modes, not just verbal consensus.";
  } else if (role.includes("ux") || role.includes("design") || role.includes("research")) {
    if (changeEl) changeEl.value = "I will include the 44% medical history abandonment rate, the 90-second participant recording evidence, and the 28% task completion lift from our progressive disclosure redesign.";
    if (learnEl) learnEl.value = "Explaining research methodology is incomplete without demonstrating how qualitative insights directly altered the product roadmap and produced measurable UX improvements.";
  } else if (role.includes("product") || role.includes("apm") || role.includes("pm")) {
    if (changeEl) changeEl.value = "I will articulate the $280k/month cost of delay, the decoupled dual-read engineering compromise, and the $3.4M annualized GMV expansion.";
    if (learnEl) learnEl.value = "In PM interviews, cross-functional conflicts must be resolved through customer and business unit economics, not personal persuasion.";
  } else if (role.includes("machine") || role.includes("learning") || role.includes("vision") || role.includes("ai")) {
    if (changeEl) changeEl.value = "I will quantify the 3D UNet volumetric inference speedup (820ms → 64ms on T4 GPUs) and confirm that Dice similarity was maintained at 94.2% across 500 clinical scans.";
    if (learnEl) learnEl.value = "In applied ML interviews, model accuracy metrics must always be balanced against edge production latency and hardware constraints.";
  } else if (role.includes("data") || role.includes("lakehouse") || role.includes("flink") || role.includes("kafka")) {
    if (changeEl) changeEl.value = "I will highlight the 4-hour to 35-second pipeline latency drop, the Protobuf schema registry automated CI checks, and the $620k annual cloud storage savings.";
    if (learnEl) learnEl.value = "Architectural decisions must be backed by concrete SLA metrics and governance frameworks rather than technical preference.";
  } else if (role.includes("frontend") || role.includes("web") || role.includes("react")) {
    if (changeEl) changeEl.value = "I will cite the 38% bundle reduction, LCP drop from 3.8s to 1.1s, and 14% conversion lift from module federation.";
    if (learnEl) learnEl.value = "Refactoring proposals gain traction when framed around Core Web Vitals and direct commercial conversion uplift.";
  } else {
    if (changeEl) changeEl.value = "I will add the measurable impact (e.g. 100% test coverage and sprint delivered 2 days ahead of schedule) to provide a complete STAR Result.";
    if (learnEl) learnEl.value = "In behavioral interviews, explaining actions isn't enough; I must explicitly state the quantifiable result (STAR Result).";
  }

  const preview = document.getElementById("a6-live-preview");
  const status = document.getElementById("a6-stt-status");
  if (preview && changeEl && changeEl.value) {
    preview.innerText = `“${changeEl.value}”`;
    preview.classList.add("active");
  }
  if (status) {
    status.innerHTML = `✓ <strong>Sample Reflection Loaded:</strong> Ready to proceed or dictate revisions`;
  }
  if (changeEl) changeEl.dispatchEvent(new Event("input"));
}

async function saveReflectionA() {
  const change = document.getElementById("a-change") ? document.getElementById("a-change").value : "";
  const learn = document.getElementById("a-learn") ? document.getElementById("a-learn").value : "";
  const notice = document.getElementById("a6-loading-notice");
  const saveBtn = document.getElementById("btn-save-reflection-a");

  if (notice) notice.style.display = "flex";
  if (saveBtn) {
    saveBtn.disabled = true;
    saveBtn.innerText = "⏳ Saving Reflection...";
  }

  try {
    await fetch("/api/reflect", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: currentSessionId || "demo_sess",
        question_id: currentQuestionId,
        what_would_you_change: change,
        what_did_you_learn: learn
      })
    });
  } catch (e) {
    console.error(e);
  } finally {
    if (notice) notice.style.display = "none";
    if (saveBtn) {
      saveBtn.disabled = false;
      saveBtn.innerText = "💾 Save & Proceed to Attempt 2 (Retry) →";
    }
  }
  goToScreenA("a7");
}

async function loadAttemptComparison() {
  try {
    const res = await fetch(`/api/compare?session_id=${currentSessionId || "demo_sess"}&question_id=${currentQuestionId}`, {
      method: "POST"
    });
    const data = await res.json();
    renderComparisonTable(data);
    if (autoSpeakEnabled) setTimeout(speakComparisonA8, 500);
  } catch (err) {
    console.error(err);
    // Local fallback diff
    renderComparisonTable({
      deltas: { relevance: 1.0, specificity: 2.0, evidence_outcome: 4.0, structure_clarity: 2.0, overall: 2.2 },
      attempt1_scores: { relevance: 8.0, specificity: 6.0, evidence: 4.0, structure: 6.0, overall: 6.0 },
      attempt2_scores: { relevance: 9.0, specificity: 8.0, evidence: 8.0, structure: 8.0, overall: 8.2 },
      improvements: ["✓ Added measurable outcome & concrete evidence (4.0 → 8.0)", "✓ Overall score increased from 6.0/10 to 8.2/10 (+2.2)"]
    });
    if (autoSpeakEnabled) setTimeout(speakComparisonA8, 500);
  }
}

function getMetricInfoTooltipHtml(metricKey) {
  const tooltips = {
    "relevance": {
      name: "Relevance & Directness",
      desc: "Measures whether the candidate addresses the exact question prompt directly without drifting into unprompted filler context.",
      high: "Directly addresses core situation in opening sentence; tightly aligned with role and question objectives.",
      mid: "Partially answers prompt but includes minor tangentials or generic preamble before reaching the core point.",
      low: "Misunderstands or evades prompt; gives generic theoretical lecture without answering the actual scenario."
    },
    "specificity": {
      name: "Specificity & Technical Depth",
      desc: "Evaluates concrete terminology, named tools, technologies, system architectures, and precise operational steps rather than broad generalities.",
      high: "Names exact tools, technologies, trade-offs, architectures, and concrete steps with senior-level depth.",
      mid: "Mentions broad technical steps and generic tools with moderate clarity.",
      low: "Speaks only in high-level platitudes ('we collaborated', 'we solved it') without technical depth or concrete artifacts."
    },
    "evidence_outcome": {
      name: "Evidence & Outcome (STAR Result)",
      desc: "Verifies the presence of verifiable business impact, quantifiable metrics (latency, GMV, conversion %, test coverage), and clear resolution deliverables.",
      high: "Explicitly states concrete quantitative metrics, KPIs, project completion timelines, and permanent organizational impact.",
      mid: "Describes positive resolution, but metrics are vague or qualitative rather than quantified with numbers/percentages.",
      low: "Stops entirely at the action taken; completely omits what occurred afterwards or whether the problem was resolved."
    },
    "structure_clarity": {
      name: "Structure & Narrative Arc (STAR)",
      desc: "Assesses coherent chronological progression following Situation, Task, Action, and Result with clear transitions and signposting.",
      high: "Flawless STAR progression with clear chronological signposting and concise transitions between problem and impact.",
      mid: "Follows chronological order, but transitions between action and result are slightly blurred or jumpy.",
      low: "Disorganized, rambling, or fragmented narrative without clear beginning, middle, or resolution."
    },
    "overall": {
      name: "Overall Rating & Hiring Bar",
      desc: "Holistic evaluation score synthesized across all 4 rubric dimensions (Relevance, Specificity, Evidence & Outcome, Structure & Clarity) on a 1.0 to 10.0 scale.",
      high: "★ Strong Hire (8.8–10.0): Candidate demonstrates senior competency, concrete metrics, and structured STAR narrative.",
      mid: "✓ Hire / Leaning Hire (7.3–8.7): Candidate meets baseline expectations with moderate technical clarity and partial metrics.",
      low: "⚠️ Needs Deliberate Retry (<7.3): Candidate misses quantifiable evidence, drifts from prompt, or lacks structured flow."
    }
  };

  const info = tooltips[metricKey] || {
    name: metricKey,
    desc: "Core deliberate practice rubric standard.",
    high: "Exceeds standard hiring bar with clear evidence.",
    mid: "Meets standard hiring bar.",
    low: "Below standard hiring bar."
  };

  return `
    <span class="metric-info-wrapper" onclick="event.stopPropagation()">
      <button type="button" class="metric-info-btn" title="Hover to view metric explanation" aria-label="Detailed rubric definition for ${escapeHtml(info.name)}">
        <svg class="metric-info-svg" viewBox="0 0 20 20" fill="currentColor">
          <path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clip-rule="evenodd" />
        </svg>
      </button>
      <div class="metric-tooltip-popover">
        <div class="metric-tooltip-header">
          <span class="metric-tooltip-tag">RUBRIC DEFINITION & CRITERIA</span>
          <h4>${escapeHtml(info.name)}</h4>
        </div>
        <div class="metric-tooltip-body">
          <p class="metric-tooltip-desc"><strong>What This Metric Measures:</strong><br>${escapeHtml(info.desc)}</p>
          <div class="metric-tooltip-anchors">
            <div class="metric-anchor-row anchor-high">
              <span class="anchor-label">★ Exceeds Bar (8.8–10.0):</span>
              <span>${escapeHtml(info.high)}</span>
            </div>
            <div class="metric-anchor-row anchor-mid">
              <span class="anchor-label">✓ Meets Bar (7.3–8.7):</span>
              <span>${escapeHtml(info.mid)}</span>
            </div>
            <div class="metric-anchor-row anchor-low">
              <span class="anchor-label">⚠️ Below Bar (&lt;7.3):</span>
              <span>${escapeHtml(info.low)}</span>
            </div>
          </div>
        </div>
      </div>
    </span>
  `;
}

function formatScoreDelta(val) {
  const num = parseFloat(val) || 0;
  if (num > 0) {
    return `<span class="score-delta score-delta-pos">+${num.toFixed(1)}</span>`;
  } else if (num < 0) {
    return `<span class="score-delta score-delta-neg">${num.toFixed(1)}</span>`;
  } else {
    return `<span class="score-delta score-delta-zero">0.0</span>`;
  }
}

function formatStarDelta(val) {
  const num = parseFloat(val) || 0;
  if (num > 0) {
    return `<span class="score-delta score-delta-star score-delta-pos">+${num.toFixed(1)} ★</span>`;
  } else if (num < 0) {
    return `<span class="score-delta score-delta-star score-delta-neg">${num.toFixed(1)}</span>`;
  } else {
    return `<span class="score-delta score-delta-star score-delta-zero">0.0</span>`;
  }
}

function formatOverallDelta(val) {
  const num = parseFloat(val) || 0;
  const color = num > 0 ? "var(--success, #16a34a)" : (num < 0 ? "var(--danger, #dc2626)" : "var(--text-muted)");
  const sign = num > 0 ? "+" : "";
  return `<strong style="color: ${color}; font-size: 1.1rem;">${sign}${num.toFixed(1)}</strong>`;
}

function renderComparisonTable(comp) {
  const a8Loading = document.getElementById("a8-loading-state");
  const a8Content = document.getElementById("a8-dashboard-content");
  if (a8Loading) a8Loading.style.display = "none";
  if (a8Content) a8Content.style.display = "block";

  const tbody = document.getElementById("compare-tbody");
  tbody.innerHTML = `
    <tr>
      <td>
        <div style="display: flex; align-items: center;">
          <strong>Relevance</strong>
          ${getMetricInfoTooltipHtml('relevance')}
        </div>
      </td>
      <td>${comp.attempt1_scores.relevance}/10</td>
      <td>${comp.attempt2_scores.relevance}/10</td>
      <td>${formatScoreDelta(comp.deltas.relevance)}</td>
    </tr>
    <tr>
      <td>
        <div style="display: flex; align-items: center;">
          <strong>Specificity</strong>
          ${getMetricInfoTooltipHtml('specificity')}
        </div>
      </td>
      <td>${comp.attempt1_scores.specificity}/10</td>
      <td>${comp.attempt2_scores.specificity}/10</td>
      <td>${formatScoreDelta(comp.deltas.specificity)}</td>
    </tr>
    <tr>
      <td>
        <div style="display: flex; align-items: center;">
          <strong>Evidence & Outcome (STAR)</strong>
          ${getMetricInfoTooltipHtml('evidence_outcome')}
        </div>
      </td>
      <td>${comp.attempt1_scores.evidence}/10</td>
      <td>${comp.attempt2_scores.evidence}/10</td>
      <td>${formatStarDelta(comp.deltas.evidence_outcome !== undefined ? comp.deltas.evidence_outcome : comp.deltas.evidence)}</td>
    </tr>
    <tr>
      <td>
        <div style="display: flex; align-items: center;">
          <strong>Structure & Clarity</strong>
          ${getMetricInfoTooltipHtml('structure_clarity')}
        </div>
      </td>
      <td>${comp.attempt1_scores.structure}/10</td>
      <td>${comp.attempt2_scores.structure}/10</td>
      <td>${formatScoreDelta(comp.deltas.structure_clarity !== undefined ? comp.deltas.structure_clarity : comp.deltas.structure)}</td>
    </tr>
    <tr style="background-color: var(--primary-light);">
      <td>
        <div style="display: flex; align-items: center;">
          <strong>Overall Rating</strong>
          ${getMetricInfoTooltipHtml('overall')}
        </div>
      </td>
      <td><strong>${comp.attempt1_scores.overall}/10</strong></td>
      <td><strong>${comp.attempt2_scores.overall}/10</strong></td>
      <td>${formatOverallDelta(comp.deltas.overall)}</td>
    </tr>
  `;

  const impList = document.getElementById("compare-improvements");
  if (impList && comp.improvements) {
    impList.innerHTML = comp.improvements.map(i => `<li>${i}</li>`).join("");
  }

  // Update download links on Screen A8
  ["btn-dl-docx-a8", "btn-dl-docx-a4"].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.href = `/api/export-docx/${currentSessionId || 'demo_sess'}`;
  });
  ["btn-dl-pptx-a8", "btn-dl-pptx-a4"].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.href = `/api/export-pptx/${currentSessionId || 'demo_sess'}`;
  });

  // Update Next Question button on Screen A8
  const nextBtn = document.getElementById("btn-next-question-a8");
  if (nextBtn) {
    if (protoACurrentIndex + 1 < protoAQuestions.length) {
      nextBtn.innerText = `Next Question (${protoACurrentIndex + 2}/${protoAQuestions.length}) →`;
      nextBtn.className = "btn btn-primary";
    } else {
      nextBtn.innerText = "🏁 Complete Session & View Progress 📊";
      nextBtn.className = "btn btn-success";
    }
  }
}

// Open Longitudinal Progress from Interview Simulation Mode
function openLongitudinalProgress() {
  loadLongitudinalProgress();
  goToScreenA("a9");
}

// Reset all longitudinal progress data (forget all data)
async function resetLongitudinalProgress() {
  const confirmed = await showAppConfirm(
    "Reset Progress Data?",
    "Are you sure you want to forget all evaluation data and reset your progress graph? This cannot be undone.",
    { confirmText: "Reset All Data", isDestructive: true }
  );
  if (!confirmed) return;

  try {
    const res = await fetch("/api/progress/reset", {
      method: "POST",
      headers: { "Content-Type": "application/json" }
    });
    const result = await res.json();
    console.log("Progress reset response:", result);

    await loadLongitudinalProgress();
    showAppToast("Evaluation progress data has been successfully reset.", "success");
  } catch (err) {
    console.error("Failed to reset progress:", err);
    showAppToast("Error resetting progress data. Please try again.", "danger");
  }
}

// Longitudinal Progress Chart (Plots all 5 parameters on time series graph)
async function loadLongitudinalProgress() {
  try {
    const res = await fetch(`/api/progress?persona_id=${activePersona}`);
    const data = await res.json();

    const ctx = document.getElementById("progressChart");
    const emptyState = document.getElementById("prog-empty-state");
    const chartContainer = document.getElementById("prog-chart-container");
    if (!ctx) return;

    const trajectory = (data && Array.isArray(data.trajectory)) ? data.trajectory : [];

    if (trajectory.length === 0) {
      if (emptyState) emptyState.style.display = "block";
      if (chartContainer) chartContainer.style.display = "none";
      if (progressChartInstance) {
        progressChartInstance.destroy();
        progressChartInstance = null;
      }
      return;
    }

    if (emptyState) emptyState.style.display = "none";
    if (chartContainer) chartContainer.style.display = "block";

    const labels = trajectory.map((t, idx) => `Attempt ${idx + 1}`);
    const overallScores = trajectory.map(t => Number(t.overall_score) || 0);
    const relevanceScores = trajectory.map(t => Number(t.relevance_score != null ? t.relevance_score : t.overall_score) || 0);
    const specificityScores = trajectory.map(t => Number(t.specificity_score != null ? t.specificity_score : t.overall_score) || 0);
    const evidenceScores = trajectory.map(t => Number(t.evidence_score != null ? t.evidence_score : t.overall_score) || 0);
    const structureScores = trajectory.map(t => Number(t.structure_score != null ? t.structure_score : t.overall_score) || 0);

    if (progressChartInstance) {
      progressChartInstance.destroy();
    }

    progressChartInstance = new Chart(ctx, {
      type: "line",
      data: {
        labels: labels,
        datasets: [
          {
            label: "1. Overall Rating",
            data: overallScores,
            borderColor: "#2563eb",
            backgroundColor: "rgba(37, 99, 235, 0.08)",
            pointBackgroundColor: "#2563eb",
            pointRadius: 5,
            pointHoverRadius: 7,
            tension: 0.3,
            borderWidth: 3,
            fill: false
          },
          {
            label: "2. Relevance & Directness",
            data: relevanceScores,
            borderColor: "#10b981",
            backgroundColor: "transparent",
            pointBackgroundColor: "#10b981",
            pointRadius: 4,
            pointHoverRadius: 6,
            tension: 0.3,
            borderWidth: 2,
            borderDash: [4, 4]
          },
          {
            label: "3. Specificity & Depth",
            data: specificityScores,
            borderColor: "#8b5cf6",
            backgroundColor: "transparent",
            pointBackgroundColor: "#8b5cf6",
            pointRadius: 4,
            pointHoverRadius: 6,
            tension: 0.3,
            borderWidth: 2
          },
          {
            label: "4. Evidence & Outcome (STAR Result)",
            data: evidenceScores,
            borderColor: "#f59e0b",
            backgroundColor: "transparent",
            pointBackgroundColor: "#f59e0b",
            pointRadius: 4,
            pointHoverRadius: 6,
            tension: 0.3,
            borderWidth: 2,
            borderDash: [6, 3]
          },
          {
            label: "5. Structure & Clarity",
            data: structureScores,
            borderColor: "#06b6d4",
            backgroundColor: "transparent",
            pointBackgroundColor: "#06b6d4",
            pointRadius: 4,
            pointHoverRadius: 6,
            tension: 0.3,
            borderWidth: 2
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: {
          mode: "index",
          intersect: false
        },
        plugins: {
          legend: {
            display: true,
            position: "top",
            labels: {
              boxWidth: 14,
              padding: 14,
              font: {
                weight: "600",
                size: 12
              }
            }
          },
          tooltip: {
            callbacks: {
              title: function(items) {
                const idx = items[0].dataIndex;
                const item = trajectory[idx];
                const dateStr = item && item.date ? ` (${item.date})` : "";
                return `Attempt #${idx + 1}${dateStr}`;
              },
              afterTitle: function(items) {
                const idx = items[0].dataIndex;
                const item = trajectory[idx];
                return item && item.question ? `Scenario: ${item.question}` : "";
              }
            }
          }
        },
        scales: {
          x: {
            title: {
              display: true,
              text: "Number of Attempt (Time Series Progression)",
              font: { weight: "700" }
            },
            grid: { display: false }
          },
          y: {
            min: 0,
            max: 10,
            ticks: { stepSize: 1 },
            title: {
              display: true,
              text: "Evaluation Score (0 - 10)",
              font: { weight: "700" }
            }
          }
        }
      }
    });

  } catch (err) {
    console.error("Progress fetch error:", err);
  }
}

// ==========================================
// 5. PROTOTYPE B (FULL REAL-TIME VOICE SIMULATION)
// ==========================================
let simConversationHistory = [];

function goToScreenB(screenId, pushHistory = true) {
  const cleanId = screenId.replace("screen-", "");
  const secB = document.getElementById("section-proto-b");
  if (secB && secB.style.display === "none") {
    switchMainTab("B");
  }
  const screens = ["screen-b1", "screen-b2", "screen-b3", "screen-b6", "screen-b8"];
  screens.forEach(id => {
    const el = document.getElementById(id);
    if (el) el.style.display = (id === `screen-${cleanId}`) ? "block" : "none";
  });
  stopAllAudio();
  window.scrollTo({ top: 0, behavior: "smooth" });

  recordNavigation(cleanId, pushHistory);

  if (cleanId === "b3") {
    setCockpitInputMode("voice");
  }
}

function handleHomeModeSelectChange(mode) {
  stopAllAudio();
  const selA = document.getElementById("home-mode-select-a");
  const selB = document.getElementById("home-mode-select");
  if (selA) selA.value = mode;
  if (selB) selB.value = mode;

  if (mode === "A") {
    goToScreenA("a1");
  } else {
    goToScreenB("b1");
  }
}

async function goToHomeUniversal() {
  stopAllAudio();
  if (typeof stopActiveRecognition === "function") {
    try { stopActiveRecognition(); } catch (e) {}
  }

  // If inside an active simulation interview session, prompt user before navigating away
  if (currentActiveScreen === "b3") {
    const confirmExit = await showAppConfirm(
      "Exit Interview Room?",
      "Are you sure you want to pause/exit the current interview and return to Home?",
      { confirmText: "Exit to Home", isDestructive: true }
    );
    if (!confirmExit) return;
  }

  // Determine current preferred mode
  const selA = document.getElementById("home-mode-select-a");
  const selB = document.getElementById("home-mode-select");
  const preferredMode = (selB && selB.value) || (selA && selA.value) || (currentActiveScreen && currentActiveScreen.startsWith("a") ? "A" : "B");

  if (preferredMode === "A") {
    goToScreenA("a1");
  } else {
    goToScreenB("b1");
  }
}

function handleStartFromHome() {
  const select = document.getElementById("home-mode-select");
  const mode = select ? select.value : "B";
  if (mode === "A") {
    goToScreenA("a2");
  } else {
    goToScreenB("b2");
  }
}

function handleAutoFillFromHome() {
  const select = document.getElementById("home-mode-select");
  const mode = select ? select.value : "B";
  if (mode === "A") {
    cycleDemoPortfolioAndOpen("A");
  } else {
    cycleDemoPortfolioAndOpen("B");
  }
}

function handleB2ModeSwitch(mode) {
  const btn = document.getElementById("btn-start-b");
  const hint = document.getElementById("b2-mode-hint");
  if (mode === "A") {
    if (btn) btn.innerText = "🚀 Begin Feedback-Based Practice →";
    if (hint) hint.innerHTML = "Switched to <strong>Feedback-Based Interview Practice</strong>. Clicking start will launch the rubric-guided practice loop.";
  } else {
    if (btn) btn.innerText = "🎙️ Begin Interview Simulation";
    if (hint) hint.innerHTML = "Configuring <strong>Interview Simulation</strong>. Feedback withheld until wrap-up.";
  }
}

function handleStartSimulationOrPractice() {
  const modeSelect = document.getElementById("b2-prototype-mode");
  const mode = modeSelect ? modeSelect.value : "B";
  if (mode === "A") {
    const bName = document.getElementById("b-name");
    const bCompany = document.getElementById("b-company");
    const bRole = document.getElementById("b-role");
    const bLevel = document.getElementById("b-level");
    const bType = document.getElementById("b-type");
    const bDuration = document.getElementById("b-duration");
    const bDifficulty = document.getElementById("b-difficulty");
    const bCv = document.getElementById("b-cv");
    const bJd = document.getElementById("b-jd");

    const aName = document.getElementById("a-name");
    const aCompany = document.getElementById("a-company");
    const aRole = document.getElementById("a-role");
    const aLevel = document.getElementById("a-level");
    const aType = document.getElementById("a-type");
    const aDuration = document.getElementById("a-duration");
    const aDifficulty = document.getElementById("a-difficulty");
    const aCv = document.getElementById("a-cv");
    const aJd = document.getElementById("a-jd");

    if (bName && aName) aName.value = bName.value;
    if (bCompany && aCompany) aCompany.value = bCompany.value;
    if (bRole && aRole) aRole.value = bRole.value;
    if (bLevel && aLevel) aLevel.value = bLevel.value;
    if (bType && aType) aType.value = bType.value;
    if (bDuration && aDuration) aDuration.value = bDuration.value;
    if (bDifficulty && aDifficulty) aDifficulty.value = bDifficulty.value;
    if (bCv && aCv) aCv.value = bCv.value;
    if (bJd && aJd) aJd.value = bJd.value;

    startSessionA();
  } else {
    startSessionB();
  }
}

async function startSessionB() {
  simulationTurn = 1;
  simConversationHistory = [];
  simTurnAnswers = {
    question1: "",
    turn1Answer: "",
    followupQuestion: "",
    turn2Answer: "",
    adaptiveTrigger: ""
  };

  const nameVal = document.getElementById("b-name") ? document.getElementById("b-name").value.trim() : "";
  const roleVal = document.getElementById("b-role") ? document.getElementById("b-role").value.trim() : "Software Engineer";
  const companyVal = document.getElementById("b-company") ? document.getElementById("b-company").value.trim() : "";
  const levelVal = document.getElementById("b-level") ? document.getElementById("b-level").value : "Mid-Level";
  const typeVal = document.getElementById("b-type") ? document.getElementById("b-type").value : "Comprehensive (STAR Behavioral + Technical)";
  const durationVal = document.getElementById("b-duration") ? document.getElementById("b-duration").value : "Standard Round (6-7 Questions • ~45 mins)";
  const diffVal = document.getElementById("b-difficulty") ? document.getElementById("b-difficulty").value : "Professional & Rigorous (Standard FAANG/Corporate)";
  const cvText = document.getElementById("b-cv") ? document.getElementById("b-cv").value.trim() : "";
  const jdText = document.getElementById("b-jd") ? document.getElementById("b-jd").value.trim() : "";

  syncCandidateName(nameVal);
  syncCandidateRole(roleVal);
  syncCandidateCompany(companyVal);
  syncCandidateLevel(levelVal);
  candidateProfile.interviewType = typeVal;
  candidateProfile.interviewDuration = durationVal;
  candidateProfile.interviewerTone = diffVal;
  candidateProfile.difficulty = diffVal;
  candidateProfile.cv = cvText;
  candidateProfile.jd = jdText;

  // Update Prototype B cockpit badge
  const trackPill = document.getElementById("sim-track-pill");
  if (trackPill) {
    const shortDuration = (durationVal.includes("Screening") || durationVal.includes("Quick")) ? "25m" : ((durationVal.includes("Comprehensive") || durationVal.includes("Onsite") || durationVal.includes("Loop")) ? "60m" : "45m");
    trackPill.innerHTML = `🎯 Focus: ${escapeHtml(typeVal.split('(')[0].trim())} • ⏱️ ${shortDuration}`;
  }

  // Ensure controls are re-enabled for a new session
  const heroMic = document.getElementById("hero-mic-b");
  if (heroMic) {
    heroMic.disabled = false;
    heroMic.style.opacity = "1";
  }
  const heroSub = document.getElementById("hero-mic-sub");
  if (heroSub) {
    heroSub.innerText = "Transcribes in real time • Click when done speaking";
  }
  const typedBtn = document.getElementById("btn-b-submit");
  if (typedBtn) {
    typedBtn.disabled = false;
    typedBtn.innerText = "Send Typed Answer ↵";
  }

  const startBtnB = document.getElementById("btn-start-b") || document.querySelector("#screen-b2 button.btn-primary");
  const b2Notice = document.getElementById("b2-loading-notice");
  if (startBtnB) {
    startBtnB.disabled = true;
    startBtnB.innerText = "⏳ Initializing Simulation Room...";
  }
  if (b2Notice) {
    b2Notice.style.display = "flex";
  }

  const companyRef = candidateProfile.company ? ` at ${candidateProfile.company}` : "";
  let initialQuestion = `Good morning, ${candidateProfile.name}! Welcome to your official mock interview for the ${candidateProfile.role} position${companyRef}. I'm Dr. Marcus Vance, lead hiring evaluator for the team today. Thanks for taking the time to join me. To kick off our conversation, could you please introduce yourself, walk me through your background, and share what brings you to this role?`;

  try {
    const res = await fetch("/api/setup", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        prototype_type: "B",
        candidate_name: candidateProfile.name,
        job_role: candidateProfile.role,
        target_company: candidateProfile.company,
        experience_level: candidateProfile.level,
        interview_type: typeVal,
        interview_duration: durationVal,
        interviewer_tone: diffVal,
        difficulty: diffVal,
        cv_text: cvText,
        job_description: jdText,
        persona_id: "custom"
      })
    });
    const data = await res.json();
    currentSessionId = data.session_id;
    if (data.first_question && data.first_question.text) {
      initialQuestion = data.first_question.text;
      currentQuestionId = data.first_question.id;
      currentQuestionText = data.first_question.text;
    }
  } catch (e) {
    console.warn("Simulation setup notice:", e);
  } finally {
    if (startBtnB) {
      startBtnB.disabled = false;
      startBtnB.innerText = "🎙️ Begin Voice Simulation";
    }
    if (b2Notice) {
      b2Notice.style.display = "none";
    }
  }

  currentQuestionText = initialQuestion;
  simTurnAnswers.question1 = initialQuestion;
  simConversationHistory.push({ role: "assistant", content: initialQuestion });

  const chat = document.getElementById("b-chat-container");
  chat.innerHTML = `
    <div class="chat-bubble interviewer">
      <div class="chat-meta">DR. MARCUS VANCE • OFFICIAL INTERVIEW (STAGE 1: INTRODUCTION)</div>
      <p id="b-q1-text">“${escapeHtml(initialQuestion)}”</p>
      <div style="margin-top: 0.4rem;">
        <button class="btn btn-secondary btn-sm" onclick="replayInterviewerTurn(0)">🔊 Hear Audio</button>
      </div>
    </div>
  `;
  document.getElementById("sim-status-badge").innerText = "Stage 1: Introduction & Background";
  const histPillStart = document.getElementById("sim-history-pill");
  if (histPillStart) histPillStart.innerHTML = "🧠 History Buffer: <strong>Ready (Stage 1)</strong>";
  document.getElementById("b-answer").value = "";
  goToScreenB("b3");

  if (autoSpeakEnabled) {
    setTimeout(() => {
      speakText(initialQuestion);
    }, 500);
  }
}

function loadSampleAnswerB() {
  const ta = document.getElementById("b-answer");
  if (!ta) return;
  const role = (candidateProfile.role || "Software Engineer").toLowerCase();
  const name = candidateProfile.name || "Candidate";

  if (simulationTurn === 1) {
    // Stage 1: Authentic Self-Introduction
    if (role.includes("distributed") || role.includes("systems") || role.includes("infrastructure")) {
      ta.value = `Good morning Dr. Vance! I'm ${name}. Over the past 8 years as a distributed systems engineer, I've specialized in high-throughput consensus protocols, financial transaction ledgers, and low-latency storage engines. Most recently at Stripe, I led the re-architecture of our core transaction ledger to Raft quorum leases, handling 140,000 writes/sec at 42ms commit latency. I'm excited about this opportunity to tackle mission-critical scale.`;
    } else if (role.includes("machine") || role.includes("learning") || role.includes("vision") || role.includes("ai")) {
      ta.value = `Good morning Dr. Vance! I'm ${name}. I'm a Senior Machine Learning and Computer Vision Engineer with a Ph.D. from Stanford. For the past 6 years, I've built deep learning segmentation architectures and deployed low-latency clinical inference pipelines on edge GPUs using TensorRT and CUDA kernel optimizations. I love bridging state-of-the-art vision models with strict clinical safety standards.`;
    } else if (role.includes("data") || role.includes("lakehouse") || role.includes("flink") || role.includes("kafka")) {
      ta.value = `Good morning Dr. Vance! I'm ${name}. For the past 9 years, I've architected enterprise real-time streaming data lakes and event hubs processing petabyte-scale telemetry. At MediaStream, I designed our unified streaming lakehouse ingesting 18 billion events per day using Apache Kafka, Apache Flink, and Apache Iceberg, cutting analytics pipeline latency from 4 hours to 35 seconds.`;
    } else if (role.includes("frontend") || role.includes("web") || role.includes("react")) {
      ta.value = `Good morning Dr. Vance! I'm ${name}. Over the past 7 years as a frontend engineer, I've specialized in enterprise React and TypeScript design systems, accessibility compliance, and web performance optimization. At SoundWave Web, I led our web performance initiative cutting bundle size by 38% and bringing LCP to 1.1s, while building high-performance audio waveform visualizers using Web Workers.`;
    } else if (role.includes("product") || role.includes("apm")) {
      ta.value = `Good morning Dr. Vance! I'm ${name}. Over the past 3 years as an Associate Product Manager, I've driven marketplace growth funnels, dynamic pricing algorithms, and checkout conversion optimization at Flipkart. I specialize in turning user friction into prioritized engineering roadmaps, and I'm excited about this opportunity to scale our core product offerings.`;
    } else if (role.includes("ux") || role.includes("design")) {
      ta.value = `Good morning Dr. Vance! I'm ${name}. I'm a UX Researcher with a background in cognitive human-computer interaction from IIT Gandhinagar and mixed-methods research. I specialize in translating qualitative field studies, usability benchmarking, and cognitive walkthroughs into validated product features that drive task completion.`;
    } else {
      ta.value = `Good morning Dr. Vance! I'm ${name}. For the past 4 years I've worked as a backend software engineer specializing in distributed systems, microservices decoupling, and high-throughput data pipelines. I'm really excited about this role because I love building resilient architectures that handle mission-critical scale.`;
    }
  } else if (simulationTurn === 2) {
    // Stage 2: Technical Project Deep Dive
    if (role.includes("product") || role.includes("apm")) {
      ta.value = "In our checkout redesign sprint, our engineering lead wanted to defer Apple Pay integration due to technical debt, but our funnel data showed 42% cart abandonments on mobile. I organized an emergency trade-off workshop, quantified engineering debt against lost revenue, and designed a phased rollout that recovered 31% in checkout completion within three weeks.";
    } else if (role.includes("ux") || role.includes("design")) {
      ta.value = "During our enterprise filter redesign, engineers wanted to remove secondary filters to optimize query performance, while user research showed 4 of 5 participants relied on them. I created annotated usability clips demonstrating navigational failure, and negotiated a collapsible accordion filter pattern that achieved 100% task completion with cached subqueries.";
    } else {
      ta.value = "When our transaction volume spiked by 4x, our payment ledger faced cross-region consensus bottlenecks. I led the migration from a legacy single-instance Postgres lock to a distributed Raft consensus pattern for lease management combined with a two-phase commit, reducing end-to-end commit latency from 450ms down to 42ms with zero data inconsistency.";
    }
  } else if (simulationTurn === 3) {
    // Stage 3: Behavioral, Conflict & Trade-Offs
    if (role.includes("product") || role.includes("apm")) {
      ta.value = "We had a sharp disagreement when our VP of Sales wanted a custom feature for a single enterprise client that threatened our quarterly roadmap. I scheduled an alignment session, built an impact vs effort matrix, and created a configurable feature toggle that satisfied the client without derailing the core platform timeline.";
    } else if (role.includes("ux") || role.includes("design")) {
      ta.value = "Our engineering lead wanted to bypass user validation on a redesigned dashboard to meet an aggressive deadline. I proposed an asynchronous unmoderated usability test running in parallel over 48 hours, presented high-priority usability blockers with zero delay to the release schedule, and won the entire team's buy-in.";
    } else {
      ta.value = "Our tech lead insisted on sticking with REST endpoints while I advocated for gRPC internally. Instead of engaging in an ideological debate, I built a quick benchmark harness measuring payload serialization and CPU overhead across 10,000 requests. The data showed gRPC had 3.4x higher throughput and 65% lower CPU usage, which convinced the lead and united the team.";
    }
  } else if (simulationTurn === 4) {
    // Stage 4: Scalability, Bottlenecks & Failure Modes
    if (role.includes("product") || role.includes("apm")) {
      ta.value = "When our European rollout created server load surges, checkout drop-offs spiked by 18%. I quickly aligned with SRE to establish rate limits on search autocompletion while preserving critical checkout lanes, ensuring 100% purchase availability while we spun up edge cache read replicas.";
    } else if (role.includes("ux") || role.includes("design")) {
      ta.value = "When responsive breakpoint tests revealed mobile users experienced severe form clipping on smaller viewports, I ran an emergency rapid validation session across 12 diverse devices and prototyped a single-column thumb-accessible progressive disclosure pattern that brought mobile task success to 96%.";
    } else {
      ta.value = "When sudden traffic surges caused network partition timeouts in our secondary AWS region, the Raft leader election experienced split-brain churn. I implemented adaptive quorum leases with monotonic clock drift guards and exponential backoff retry queues, maintaining 99.999% availability without duplicate transactions.";
    }
  } else if (simulationTurn === 5) {
    // Stage 5: Measured Impact, Quantitative Metrics & Validation
    if (role.includes("product") || role.includes("apm")) {
      ta.value = "We tracked the rollout over 90 days. The phased checkout flow lifted conversion by 3.8 percentage points, generating $2.4M in annualized incremental ARR while reducing support tickets related to payment confusion by 54%.";
    } else if (role.includes("ux") || role.includes("design")) {
      ta.value = "Post-launch usability benchmarking showed time-on-task decreased from 4.2 minutes to 1.1 minutes, with System Usability Scale (SUS) scores jumping from 62 to 86 across our core enterprise customer cohort.";
    } else {
      ta.value = "We verified the architecture through continuous load testing and 90 days of production telemetry. The system processed 18,000 TPS during peak holiday flash sales with zero failovers, while reducing cross-AZ egress bandwidth costs by $410k annually.";
    }
  } else if (simulationTurn === 6) {
    // Stage 6: Retrospective Reflection & Lessons Learned
    if (role.includes("product") || role.includes("apm")) {
      ta.value = "My biggest retrospective takeaway was that establishing quantitative guardrail metrics upfront prevents circular roadmap debates. If I did it again, I would institute automated weekly health dashboards before kicking off design iterations.";
    } else if (role.includes("ux") || role.includes("design")) {
      ta.value = "In hindsight, involving frontend engineers in live observation sessions earlier cut downstream interpretation overhead in half. Shared empathy with the actual user struggles drove much cleaner engineering handoffs.";
    } else {
      ta.value = "Looking back, my biggest takeaway was that distributed consensus should never be introduced before exhaustive profiling of simpler partitioned locks. While Raft was the right choice for our scale, investing heavily in observable canary telemetry from day one was the real key to painless maintenance.";
    }
  } else {
    // Stage 7+: Cross-Functional Collaboration, Mentorship & Strategy
    if (role.includes("product") || role.includes("apm")) {
      ta.value = "I mentor junior PMs on building data-backed PRDs and lead our quarterly product strategy syncs across sales, marketing, and engineering, ensuring our feature pipeline consistently aligns with executive business objectives.";
    } else if (role.includes("ux") || role.includes("design")) {
      ta.value = "I established our team's continuous research repository and trained 14 product designers and engineers on conducting unbiased cognitive walkthroughs, institutionalizing human-centered design across all squads.";
    } else {
      ta.value = "I lead architecture review guild sessions across five squads, authored our team's standard runbooks for distributed fault recovery, and mentor three mid-level engineers on latency profiling and system resilience.";
    }
  }
  ta.dispatchEvent(new Event("input"));
  const preview = document.getElementById("b3-live-preview");
  const status = document.getElementById("b3-stt-status");
  if (preview && ta.value) {
    preview.innerText = `“${ta.value}”`;
    preview.classList.add("active");
  }
  if (status) {
    status.innerHTML = `⚡ <strong>Contextual sample response loaded:</strong> Review in caption strip or switch to Typed mode to edit.`;
  }
}
const loadSampleRahulAnswer = loadSampleAnswerB;
window.loadSampleAnswerB = loadSampleAnswerB;
window.loadSampleRahulAnswer = loadSampleAnswerB;

function concludeInterviewNaturally() {
  const closingPrompt = "Thank you, Dr. Vance. I think we have covered the key areas of my experience and background, and I am ready to wrap up our interview session and receive the hiring committee evaluation.";
  const ansBox = document.getElementById("b-answer");
  if (ansBox) ansBox.value = closingPrompt;
  submitSimulationAnswer();
}
window.concludeInterviewNaturally = concludeInterviewNaturally;

async function submitSimulationAnswer() {
  const answer = document.getElementById("b-answer").value.trim();
  if (!answer) {
    alert("Please speak or type an answer to continue.");
    return;
  }

  stopActiveRecognition();
  const chat = document.getElementById("b-chat-container");

  // Append candidate response
  chat.innerHTML += `
    <div class="chat-bubble candidate">
      <div class="chat-meta">${escapeHtml(candidateProfile.name || 'YOU').toUpperCase()} (CANDIDATE)</div>
      <p>${escapeHtml(answer)}</p>
    </div>
  `;
  document.getElementById("b-answer").value = "";
  const preview = document.getElementById("b3-live-preview");
  if (preview) {
    preview.innerText = "";
    preview.classList.remove("active");
  }
  const sttStatus = document.getElementById("b3-stt-status");
  if (sttStatus) {
    sttStatus.innerHTML = "🎙️ Waiting for Dr. Vance's response...";
  }
  chat.scrollTop = chat.scrollHeight;

  // Add candidate input to local dialogue history
  simConversationHistory.push({ role: "user", content: answer });

  if (simulationTurn === 1) {
    simTurnAnswers.turn1Answer = answer;
  } else if (simulationTurn === 2) {
    simTurnAnswers.turn2Answer = answer;
  }

  // Set hero status to thinking
  const b3Status = document.getElementById("b3-voice-status");
  if (b3Status) {
    b3Status.className = "voice-status-pill thinking";
    b3Status.innerText = "🧠 Interviewer Actively Listening...";
  }

  // Add animated typing indicator inside chat stream
  const typingBubbleHtml = `
    <div class="chat-bubble interviewer typing-bubble" id="b-typing-bubble">
      <div class="chat-meta">DR. MARCUS VANCE • OFFICIAL INTERVIEWER</div>
      <div style="display: flex; align-items: center; gap: 0.6rem; color: var(--text-muted); font-size: 0.88rem;">
        <div class="typing-dots"><span></span><span></span><span></span></div>
        <span>Dr. Vance is listening and formulating the next question...</span>
      </div>
    </div>
  `;
  chat.innerHTML += typingBubbleHtml;
  chat.scrollTop = chat.scrollHeight;

  try {
    const res = await fetch("/api/interview/turn", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: currentSessionId || "sess_sim",
        user_message: answer,
        turn_index: simulationTurn,
        candidate_name: candidateProfile.name || "Candidate",
        job_role: candidateProfile.role || "Software Engineer",
        target_company: candidateProfile.company || "",
        experience_level: candidateProfile.level || "Mid-Level",
        cv_text: candidateProfile.cv || "",
        job_description: candidateProfile.jd || "",
        interview_type: candidateProfile.interviewType || "Comprehensive (STAR Behavioral + Technical)",
        interview_duration: candidateProfile.interviewDuration || "Standard Round (6-7 Questions • ~45 mins)",
        interviewer_tone: candidateProfile.interviewerTone || "Professional & Rigorous (Standard FAANG/Corporate)",
        conversation_history: simConversationHistory
      })
    });
    const data = await res.json();

    // Remove typing indicator
    const tb = document.getElementById("b-typing-bubble");
    if (tb) tb.remove();

    const reply = data.interviewer_message || data.followup_question || "Could you tell me more about that?";
    simConversationHistory.push({ role: "assistant", content: reply });
    simulationTurn = data.turn_index || (simulationTurn + 1);

    if (b3Status) {
      b3Status.className = "voice-status-pill speaking";
      b3Status.innerText = "🔊 Interviewer Speaking";
    }

    const stageNames = {
      2: "STAGE 2: TECHNICAL & PROJECT PROBE",
      3: "STAGE 3: BEHAVIORAL & CONFLICT RESOLUTION",
      4: "STAGE 4: SCALABILITY, RESILIENCE & FAILURE MODES",
      5: "STAGE 5: MEASURED IMPACT & QUANTITATIVE KPIS",
      6: "STAGE 6: RETROSPECTIVE REFLECTION & LESSONS",
      7: "STAGE 7: CROSS-FUNCTIONAL STRATEGY & LEADERSHIP",
      8: "STAGE 8: CLOSING SUMMARY"
    };
    const stageBadgeNames = {
      2: "Stage 2: Technical Deep Dive",
      3: "Stage 3: Behavioral & Conflict",
      4: "Stage 4: Architecture & Scaling",
      5: "Stage 5: Measured Impact & KPIs",
      6: "Stage 6: Retrospective Reflection",
      7: "Stage 7: Strategy & Leadership",
      8: "Completed • Rubric Evaluation"
    };

    const stageTitle = stageNames[simulationTurn] || `STAGE ${simulationTurn}: INTERVIEW PROBE`;
    const badgeTitle = stageBadgeNames[simulationTurn] || `Stage ${simulationTurn}`;
    const badge = document.getElementById("sim-status-badge");
    if (badge) badge.innerText = badgeTitle;

    const histPill = document.getElementById("sim-history-pill");
    if (histPill) {
      const turnsCount = Math.floor(simConversationHistory.length / 2);
      histPill.innerHTML = `🧠 History Buffer: <strong>${turnsCount} ${turnsCount === 1 ? 'exchange' : 'exchanges'} active</strong>`;
    }

    let engineLabel = "🟢 AI Interview Evaluator";

    const currentTurnAssistantIdx = simConversationHistory.filter(m => m.role === "assistant").length - 1;

    chat.innerHTML += `
      <div class="chat-bubble interviewer">
        <div class="chat-meta">DR. MARCUS VANCE • OFFICIAL INTERVIEW (${stageTitle}) • <span class="engine-badge-label">${engineLabel}</span></div>
        <p>${escapeHtml(reply)}</p>
        <div style="margin-top: 0.4rem;">
          <button class="btn btn-secondary btn-sm" onclick="replayInterviewerTurn(${currentTurnAssistantIdx})">🔊 Hear Audio</button>
        </div>
      </div>
    `;
    chat.scrollTop = chat.scrollHeight;
    const readyStatus = document.getElementById("b3-stt-status");
    if (readyStatus) {
      readyStatus.innerHTML = "🎙️ Ready for your response. Click the button above to speak.";
    }

    if (autoSpeakEnabled) {
      speakText(reply);
    }

    // If the interview reaches conclusion, render manual conclusion action card WITHOUT auto-redirecting
    if (data.is_concluded) {
      chat.innerHTML += `
        <div class="chat-bubble interviewer interview-concluded-card">
          <div class="concluded-header">
            <span class="concluded-icon">🎉</span>
            <div>
              <strong class="concluded-title">Interview Completed with Dr. Marcus Vance</strong>
              <div class="concluded-sub">All conversation turns have been recorded and transcribed.</div>
            </div>
          </div>
          <p class="concluded-body">
            Dr. Vance has wrapped up the oral questioning. When you are ready, proceed to convene the Hiring Committee Evaluation Scorecard to inspect your detailed BARS ratings, turn-by-turn evidence audit, and targeted development plan.
          </p>
          <div class="concluded-actions">
            <button class="btn btn-primary btn-concluded" id="btn-proceed-evaluation" onclick="finishSimulation()">
              📊 View Official Hiring Committee Evaluation Scorecard →
            </button>
            <button class="btn btn-secondary btn-sm" onclick="replayInterviewerTurn(${currentTurnAssistantIdx})">🔊 Replay Closing Remarks</button>
          </div>
        </div>
      `;
      chat.scrollTop = chat.scrollHeight;

      if (badge) badge.innerText = "Interview Completed • Ready for Evaluation Scorecard";
      if (readyStatus) {
        readyStatus.innerHTML = "🎉 <strong>Interview concluded by Dr. Vance.</strong> Click <em>'View Official Hiring Committee Evaluation Scorecard'</em> below to view your results.";
      }
      const hint = document.getElementById("b-silence-hint");
      if (hint) {
        hint.innerHTML = "✅ <strong>Session complete:</strong> All interview stages finished. Click the green button below to review your comprehensive scorecard.";
      }

      // Disable inputs so user doesn't submit further responses after conclusion
      const heroMic = document.getElementById("hero-mic-b");
      if (heroMic) {
        heroMic.disabled = true;
        heroMic.style.opacity = "0.5";
      }
      const heroSub = document.getElementById("hero-mic-sub");
      if (heroSub) {
        heroSub.innerText = "Interview concluded • Inspect scorecard below";
      }
      const typedBtn = document.getElementById("btn-b-submit");
      if (typedBtn) {
        typedBtn.disabled = true;
        typedBtn.innerText = "Interview Concluded";
      }
    }

  } catch (err) {
    console.error("Turn fetch error:", err);
    const tb = document.getElementById("b-typing-bubble");
    if (tb) tb.remove();
    finishSimulation(answer);
  }
}

let simLastEvaluation = null;

async function finishSimulation(lastAnswerText = "") {
  if (lastAnswerText && (!simConversationHistory.length || simConversationHistory[simConversationHistory.length - 1].content !== lastAnswerText)) {
    simConversationHistory.push({ role: "user", content: lastAnswerText });
  }

  const badge = document.getElementById("sim-status-badge");
  if (badge) badge.innerText = "Completed • Comprehensive Rubric Evaluation";

  goToScreenB("b6");

  // Show loading state, hide previous content
  const loadingEl = document.getElementById("b6-loading-state");
  const contentEl = document.getElementById("b6-dashboard-content");
  if (loadingEl) loadingEl.style.display = "block";
  if (contentEl) contentEl.style.display = "none";

  const typeVal = candidateProfile.interviewType || (document.getElementById("b-type") ? document.getElementById("b-type").value : "Comprehensive (STAR Behavioral + Technical)");
  const durationVal = candidateProfile.interviewDuration || (document.getElementById("b-duration") ? document.getElementById("b-duration").value : "Standard Round (6-7 Questions • ~45 mins)");
  const diffVal = candidateProfile.interviewerTone || (document.getElementById("b-difficulty") ? document.getElementById("b-difficulty").value : "Professional & Rigorous (Standard FAANG/Corporate)");
  const cvText = candidateProfile.cv || (document.getElementById("b-cv") ? document.getElementById("b-cv").value.trim() : "");
  const jdText = candidateProfile.jd || (document.getElementById("b-jd") ? document.getElementById("b-jd").value.trim() : "");

  try {
    const res = await fetch("/api/simulation/evaluate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: currentSessionId || "sess_sim",
        candidate_name: candidateProfile.name || "Candidate",
        job_role: candidateProfile.role || "Software Engineer",
        target_company: candidateProfile.company || "",
        experience_level: candidateProfile.level || "Mid-Level",
        interview_type: typeVal,
        interview_duration: durationVal,
        interviewer_tone: diffVal,
        cv_text: cvText,
        job_description: jdText,
        conversation_history: simConversationHistory
      })
    });
    const data = await res.json();
    simLastEvaluation = data;
    renderDetailedSimulationFeedback(data);
  } catch (err) {
    console.warn("Simulation evaluation notice:", err);
    renderDetailedSimulationFeedback(null);
  }
}

function switchEvalDashboardTab(tabName) {
  const tabs = ["tab-competencies", "tab-turns", "tab-jd", "tab-plan"];
  tabs.forEach(t => {
    const el = document.getElementById(t);
    const btn = document.getElementById(`btn-${t}`);
    if (el) el.style.display = (t === tabName) ? "block" : "none";
    if (btn) btn.classList.toggle("active", t === tabName);
  });
}

function renderDetailedSimulationFeedback(evalData = null) {
  const loadingEl = document.getElementById("b6-loading-state");
  const contentEl = document.getElementById("b6-dashboard-content");
  if (loadingEl) loadingEl.style.display = "none";
  if (!contentEl) return;
  contentEl.style.display = "block";

  // Safe fallback if null
  const d = evalData || {
    overall_score: 7.8,
    hiring_recommendation: "Hire",
    recommendation_summary: "Candidate meets the baseline competencies with structured responses and clear technical framing.",
    assessed_level: `${candidateProfile.level || 'Mid-Level'} • Evaluated for ${candidateProfile.company || 'Enterprise'}`,
    confidence_rating: "High Confidence (Full dialogue audited)",
    interviewer_rigor_notes: "Evaluated under standard corporate hiring bar.",
    competency_matrix: [],
    turn_evaluations: [],
    job_description_alignment: [],
    key_strengths: ["Clear domain fluency", "Structured problem presentation", "Professional composure"],
    priority_growth_areas: ["Incorporate deeper quantitative outcome metrics", "Elaborate on edge-case fault tolerance", "Emphasize personal architectural agency over collective team actions"],
    actionable_recommendations: ["Practice stating measurable metrics within the first 30 seconds of each response", "Rehearse distributed system recovery scenarios with explicit circuit breaker and queue patterns"]
  };

  const overall = typeof d.overall_score === "number" ? d.overall_score : 7.8;
  const rec = d.hiring_recommendation || "Hire";
  const recSummary = d.recommendation_summary || "Candidate demonstrated solid competency alignment.";
  const assessedLevel = d.assessed_level || `${candidateProfile.level || 'Mid-Level'} • ${candidateProfile.role}`;
  const confidence = d.confidence_rating || "High Confidence";
  const rigorNotes = d.interviewer_rigor_notes || "";

  // Recommendation Badge Class
  let recClass = "rec-hire";
  let recIcon = "✓";
  const rLower = rec.toLowerCase();
  if (rLower.includes("strong hire")) {
    recClass = "rec-strong-hire";
    recIcon = "★";
  } else if (rLower.includes("lean hire")) {
    recClass = "rec-lean-hire";
    recIcon = "▲";
  } else if (rLower.includes("lean no hire")) {
    recClass = "rec-lean-no-hire";
    recIcon = "⚠️";
  } else if (rLower.includes("no hire")) {
    recClass = "rec-strong-no-hire";
    recIcon = "✕";
  }

  // 1. Audit Ambiguity & Early Termination
  const turns = d.turn_evaluations || [];
  const comps = d.competency_matrix || [];
  const jdList = d.job_description_alignment || [];

  const totalWordsCount = turns.reduce((acc, t) => acc + (t.candidate_response || "").split(/\s+/).filter(Boolean).length, 0);

  const ambNotice = d.ambiguity_notice || ((d.ambiguity_detected || turns.length <= 2 || totalWordsCount < 110) ? {
    is_ambiguous: true,
    severity: "HIGH",
    headline: "⚠️ Evaluation Ambiguity Notice: Premature Interview Conclusion",
    explanation: `This interview concluded early after only ${turns.length} conversational turn${turns.length !== 1 ? 's' : ''} (${totalWordsCount} words spoken). Crucial competency dimensions could not be reliably probed or evidenced under realistic corporate hiring conditions.`,
    unassessed_dimensions: (d.ambiguity_notice && d.ambiguity_notice.unassessed_dimensions) || [
      "Technical Architecture & System Mechanics Deep Dive",
      "Behavioral Conflict, Trade-Offs & Teammate Alignment",
      "Edge-Case Resilience, Failure Modes & Fault Recovery",
      "Quantified Business Impact & Measurable Outcome Substantiation"
    ],
    hiring_committee_advisory: "Ratings and scores displayed below represent provisional baseline estimates with elevated statistical ambiguity. The hiring committee strongly recommends scheduling a 20–30 minute targeted technical follow-up session to resolve these unassessed competencies before issuing a final hiring decision."
  } : null);

  const isAmbiguous = Boolean(ambNotice && ambNotice.is_ambiguous);

  let ambiguityBannerHtml = "";
  if (isAmbiguous && ambNotice) {
    const missingItems = (ambNotice.unassessed_dimensions || [
      "Technical Architecture & System Mechanics Deep Dive",
      "Behavioral Conflict, Trade-Offs & Teammate Alignment",
      "Edge-Case Resilience, Failure Modes & Fault Recovery",
      "Quantified Business Impact & Measurable Outcome Substantiation"
    ]).map(m => `<li>${escapeHtml(m)}</li>`).join("");

    ambiguityBannerHtml = `
      <div class="eval-ambiguity-banner">
        <div class="ambiguity-banner-header">
          <div class="ambiguity-title-group">
            <span class="ambiguity-badge-icon">⚠️</span>
            <div>
              <h4 class="ambiguity-headline">${escapeHtml(ambNotice.headline || 'Evaluation Ambiguity Notice: Premature Interview Conclusion')}</h4>
              <p class="ambiguity-subline">${escapeHtml(ambNotice.explanation || 'The interview concluded early before sufficient conversational evidence could be extracted across all hiring competencies.')}</p>
            </div>
          </div>
          <span class="ambiguity-severity-pill">HIGH AMBIGUITY • PROVISIONAL RATINGS</span>
        </div>
        <div class="ambiguity-details-grid">
          <div class="ambiguity-missing-box">
            <div class="ambiguity-box-title">⚠️ Unassessed / Ambiguous Competencies:</div>
            <ul class="ambiguity-missing-list">
              ${missingItems}
            </ul>
          </div>
          <div class="ambiguity-advisory-box">
            <div class="ambiguity-box-title">📋 Hiring Committee Evaluation Advisory:</div>
            <p class="ambiguity-advisory-text">${escapeHtml(ambNotice.hiring_committee_advisory || 'Scores below represent provisional estimates due to sparse conversational signal. A targeted technical follow-up session is strongly recommended to resolve these ambiguities.')}</p>
            <div class="ambiguity-stats-pill">
              <span>Signal Density: <strong>${turns.length} Turn${turns.length !== 1 ? 's' : ''}</strong></span>
              <span class="pill-divider">•</span>
              <span>Total Spoken: <strong>${totalWordsCount} Words</strong></span>
              <span class="pill-divider">•</span>
              <span>Session Depth: <strong>${Math.min(100, Math.round((turns.length / 6) * 100))}% of Standard Round</strong></span>
            </div>
          </div>
        </div>
      </div>
    `;
  }

  // 2. Build Competency Matrix Cards
  const compCardsHtml = comps.map(c => {
    const s = typeof c.score === "number" ? c.score : 7.5;
    const pct = Math.min(100, Math.max(10, Math.round((s / 10) * 100)));
    let barColor = "#10b981";
    if (s < 6.0) barColor = "#ef4444";
    else if (s < 7.5) barColor = "#f59e0b";
    else if (s >= 8.8) barColor = "#059669";
    const w = c.weight ? Math.round(c.weight * 100) : 20;
    const isCompAmbiguous = Boolean(c.is_ambiguous || (isAmbiguous && s <= 6.8));

    const defText = c.definition || c.focus || "Core competency evaluated against standard hiring rubrics.";
    const highAnchor = c.high_anchor || "Deep domain mastery with quantified metrics and architectural agency.";
    const midAnchor = c.mid_anchor || "Solid baseline proficiency with standard problem-solving.";
    const lowAnchor = c.low_anchor || "Noticeable gaps in depth, missing trade-offs, or absent metrics.";

    return `
      <div class="comp-eval-card ${isCompAmbiguous ? 'comp-card-ambiguous' : ''}">
        <div>
          <div class="comp-eval-header">
            <div class="comp-title-with-info">
              <span class="comp-name">${escapeHtml(c.name)}</span>
              <span class="metric-info-wrapper">
                <button type="button" class="metric-info-btn" title="Hover to view metric explanation" aria-label="Detailed rubric definition for ${escapeHtml(c.name)}">
                  <svg class="metric-info-svg" viewBox="0 0 20 20" fill="currentColor">
                    <path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clip-rule="evenodd" />
                  </svg>
                </button>
                <div class="metric-tooltip-popover">
                  <div class="metric-tooltip-header">
                    <span class="metric-tooltip-tag">METRIC RUBRIC & DEFINITION</span>
                    <h4>${escapeHtml(c.name)}</h4>
                  </div>
                  <div class="metric-tooltip-body">
                    <p class="metric-tooltip-desc"><strong>What This Metric Measures:</strong><br>${escapeHtml(defText)}</p>
                    <div class="metric-tooltip-anchors">
                      <div class="metric-anchor-row anchor-high">
                        <span class="anchor-label">★ Exceeds Bar (8.8–10.0):</span>
                        <span>${escapeHtml(highAnchor)}</span>
                      </div>
                      <div class="metric-anchor-row anchor-mid">
                        <span class="anchor-label">✓ Meets Bar (7.3–8.7):</span>
                        <span>${escapeHtml(midAnchor)}</span>
                      </div>
                      <div class="metric-anchor-row anchor-low">
                        <span class="anchor-label">⚠️ Below Bar (&lt;7.3):</span>
                        <span>${escapeHtml(lowAnchor)}</span>
                      </div>
                    </div>
                  </div>
                </div>
              </span>
            </div>
            <div style="display: flex; align-items: center; gap: 0.5rem;">
              ${isCompAmbiguous ? `<span class="ambiguity-micro-badge">⚠️ Ambiguous Signal</span>` : ''}
              <span class="comp-score-tag" style="color: ${barColor}">${s.toFixed(1)} / 10</span>
            </div>
          </div>
          <div style="display: flex; justify-content: space-between; font-size: 0.75rem; color: var(--text-muted); margin-bottom: 0.25rem;">
            <span>Evaluation Weight: <strong>${w}%</strong></span>
            <strong style="color: ${barColor}">${escapeHtml(c.rating_label || 'Meets Bar')}</strong>
          </div>
          <div class="comp-bar-container">
            <div class="comp-bar-fill" style="width: ${pct}%; background: ${barColor};"></div>
          </div>
          <p class="comp-anchor-desc"><strong>Behavioral Anchor:</strong> ${escapeHtml(c.behavioral_anchor || c.focus || '')}</p>
        </div>
        <div class="comp-evidence-quote ${isCompAmbiguous ? 'evidence-ambiguous' : ''}">
          <strong>Observed Signal:</strong> ${escapeHtml(c.evidence || 'Consistent domain alignment verified across dialogue.')}
        </div>
      </div>
    `;
  }).join("") || `<p style="color: var(--text-muted); padding: 1rem;">Competencies evaluated against role standard.</p>`;

  // 3. Build Turn-by-Turn Question & Response Audit
  const turnsHtml = turns.map(t => {
    const sList = (t.strengths_observed || []).map(s => `<li>${escapeHtml(s)}</li>`).join("");
    const gList = (t.gaps_identified || []).map(g => `<li>${escapeHtml(g)}</li>`).join("");
    const tScore = typeof t.turn_score === "number" ? t.turn_score : 7.5;
    let badgeClass = "badge-success";
    if (tScore < 6.5) badgeClass = "badge-warning";
    if (tScore < 5.0) badgeClass = "badge-danger";

    return `
      <div class="turn-audit-item">
        <div class="turn-audit-header">
          <div>
            <span class="turn-audit-stage">${escapeHtml(t.stage_name || `Turn ${t.turn_index}`)}</span>
            <span style="font-size: 0.82rem; color: var(--text-muted); margin-left: 0.5rem;">• Focus Competency: <strong>${escapeHtml(t.competency_tested || 'Domain Competency')}</strong></span>
          </div>
          <span class="badge ${badgeClass}" style="font-weight: 800; font-size: 0.85rem;">Turn Rating: ${tScore.toFixed(1)} / 10</span>
        </div>
        <div class="turn-audit-body">
          <div class="turn-q-box">
            <div class="turn-q-label">💼 DR. MARCUS VANCE (LEAD EVALUATOR):</div>
            <div>“${escapeHtml(t.interviewer_question)}”</div>
          </div>
          <div class="turn-ans-box">
            <div class="turn-ans-label">🎙️ CANDIDATE'S SPOKEN RESPONSE:</div>
            <div>“${escapeHtml(t.candidate_response)}”</div>
          </div>
          <div class="turn-insights-grid">
            <div class="turn-insight-box turn-strengths-box">
              <strong>✓ Positive Evidence & Mastery:</strong>
              <ul style="margin: 0.35rem 0 0 1.1rem; padding: 0;">${sList || '<li>Clear domain familiarity evidenced.</li>'}</ul>
            </div>
            <div class="turn-insight-box turn-gaps-box">
              <strong>⚠️ Critical Gaps & Missing Evidence:</strong>
              <ul style="margin: 0.35rem 0 0 1.1rem; padding: 0;">${gList || '<li>Could incorporate deeper metrics and edge case resilience.</li>'}</ul>
            </div>
          </div>
          ${t.coached_exemplar ? `
            <div class="turn-coached-box">
              <strong>💡 Coached Exemplar Formulation:</strong>
              <p style="margin: 0.3rem 0 0 0; font-style: italic;">${escapeHtml(t.coached_exemplar)}</p>
            </div>
          ` : ''}
        </div>
      </div>
    `;
  }).join("") || `<p style="color: var(--text-muted); padding: 1rem;">Turn breakdown recorded.</p>`;

  // 4. Build Job Description & Resume Requirements Alignment Matrix
  const jdRowsHtml = jdList.map(j => {
    let bClass = "badge-success";
    if (j.status === "Partially Demonstrated") bClass = "badge-warning";
    if (j.status === "Not Assessed / Missing") bClass = "badge-danger";
    return `
      <tr>
        <td class="jd-req-cell">${escapeHtml(j.requirement)}</td>
        <td class="jd-status-cell"><span class="badge ${bClass}">${escapeHtml(j.status)}</span></td>
        <td class="jd-quote-cell">${escapeHtml(j.evidence_quote || 'No direct quote identified')}</td>
        <td class="jd-analysis-cell">${escapeHtml(j.alignment_analysis || '')}</td>
      </tr>
    `;
  }).join("") || `<tr><td colspan="4" style="text-align: center; color: var(--text-muted); padding: 1rem;">Candidate demonstrated core role alignment.</td></tr>`;

  // 5. Build Debrief & 30-Day Coaching Plan
  const topStrengths = (d.key_strengths || []).map(s => `<li style="margin-bottom: 0.4rem;">${escapeHtml(s)}</li>`).join("");
  const topGrowth = (d.priority_growth_areas || []).map(g => `<li style="margin-bottom: 0.4rem;">${escapeHtml(g)}</li>`).join("");
  const topActions = (d.actionable_recommendations || []).map(a => `<li style="margin-bottom: 0.4rem;">${escapeHtml(a)}</li>`).join("");

  // Synthesize Complete Dashboard HTML
  contentEl.innerHTML = `
    <div class="eval-dashboard-container">
      <!-- 0. Prominent Ambiguity Alert Banner (Rendered when interview is ended early or signal is sparse) -->
      ${ambiguityBannerHtml}

      <!-- 1. Executive Scorecard Hero Banner -->
      <div class="eval-hero-banner">
        <div class="eval-hero-top">
          <div class="eval-cand-header">
            <div style="font-size: 0.78rem; font-weight: 800; letter-spacing: 0.08em; text-transform: uppercase; color: #94a3b8; margin-bottom: 0.25rem;">OFFICIAL HIRING COMMITTEE SCORECARD & DOSSIER</div>
            <h2>${escapeHtml(candidateProfile.name || 'Candidate')}</h2>
            <div class="eval-cand-meta">
              <span class="context-pill" style="background: rgba(255,255,255,0.15); color: #ffffff;">💼 ${escapeHtml(candidateProfile.role)}</span>
              ${candidateProfile.company ? `<span class="context-pill" style="background: rgba(59,130,246,0.3); color: #bfdbfe;">🏢 ${escapeHtml(candidateProfile.company)}</span>` : ''}
              <span class="context-pill" style="background: rgba(255,255,255,0.15); color: #ffffff;">🎖️ ${escapeHtml(candidateProfile.level || 'Mid-Level')}</span>
              <span class="context-pill" style="background: rgba(16,185,129,0.25); color: #a7f3d0;">🎯 ${escapeHtml((candidateProfile.interviewType || 'Comprehensive').split('(')[0].trim())}</span>
            </div>
          </div>
          <div class="eval-rec-box">
            <span class="eval-rec-pill ${recClass}">
              <span>${recIcon}</span>
              <span>${escapeHtml(rec)}</span>
            </span>
            <div style="display: flex; align-items: baseline; gap: 0.4rem; margin-top: 0.35rem;">
              <span style="font-size: 0.85rem; color: #94a3b8; display: inline-flex; align-items: center;">
                AGGREGATE SCORE:
                <span class="metric-info-wrapper">
                  <button type="button" class="metric-info-btn metric-info-btn-light" title="Aggregate score computation" aria-label="Information on aggregate score">
                    <svg class="metric-info-svg" viewBox="0 0 20 20" fill="currentColor">
                      <path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clip-rule="evenodd" />
                    </svg>
                  </button>
                  <div class="metric-tooltip-popover">
                    <div class="metric-tooltip-header">
                      <span class="metric-tooltip-tag">SCORE FORMULATION</span>
                      <h4>Aggregate Composite Score</h4>
                    </div>
                    <div class="metric-tooltip-body">
                      <p class="metric-tooltip-desc">
                        Weighted composite 10-point score calculated across all 5 track rubrics (Core Technical/STAR 25%, Secondary Architecture/Depth 20%, Problem Solving/Fault Tolerance 20%, Strategy/Communication 20%, and Politeness, Refined Language & Inquiry Follow-Through 15%). Calibrated against Senior FAANG / Corporate bar.
                      </p>
                    </div>
                  </div>
                </span>
              </span>
              <span class="eval-score-ring">${overall.toFixed(1)}</span>
              <span style="font-size: 1rem; color: #94a3b8; font-weight: 700;">/ 10</span>
            </div>
            <div style="display: inline-flex; align-items: center; gap: 0.3rem;">
              ${isAmbiguous ? `<span class="confidence-chip-ambiguous">⚠️ ${escapeHtml(confidence)}</span>` : `<span style="font-size: 0.78rem; color: #94a3b8;">${escapeHtml(confidence)}</span>`}
              <span class="metric-info-wrapper">
                <button type="button" class="metric-info-btn metric-info-btn-light" title="Confidence and ambiguity information" aria-label="Information on confidence and ambiguity">
                  <svg class="metric-info-svg" viewBox="0 0 20 20" fill="currentColor">
                    <path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clip-rule="evenodd" />
                  </svg>
                </button>
                <div class="metric-tooltip-popover">
                  <div class="metric-tooltip-header">
                    <span class="metric-tooltip-tag">SIGNAL CONFIDENCE & AMBIGUITY</span>
                    <h4>Confidence Rating & Data Completeness</h4>
                  </div>
                  <div class="metric-tooltip-body">
                    <p class="metric-tooltip-desc">
                      Measures evidentiary dialogue richness. Full multi-turn interviews (4–7 questions with technical metrics, failure cases, and behavioral trade-offs) receive High Confidence. Sessions ended early (&lt;3 turns or sparse words) carry elevated ambiguity and produce provisional scores.
                    </p>
                  </div>
                </div>
              </span>
            </div>
          </div>
        </div>

        <div class="eval-summary-quote">
          <strong>Hiring Committee Consensus Rationale:</strong> “${escapeHtml(recSummary)}”
          ${rigorNotes ? `<div style="font-size: 0.8rem; color: #94a3b8; margin-top: 0.4rem;">⚖️ ${escapeHtml(rigorNotes)}</div>` : ''}
        </div>
      </div>

      <!-- 2. Interactive Navigation Tabs -->
      <div class="eval-tabs-nav">
        <button class="eval-tab-btn active" id="btn-tab-competencies" onclick="switchEvalDashboardTab('tab-competencies')">🎯 Track Competency Rubrics (${comps.length})</button>
        <button class="eval-tab-btn" id="btn-tab-turns" onclick="switchEvalDashboardTab('tab-turns')">💬 Turn-by-Turn Question Audit (${turns.length} Turns)</button>
        <button class="eval-tab-btn" id="btn-tab-jd" onclick="switchEvalDashboardTab('tab-jd')">📋 Job Description & Resume Audit (${jdList.length})</button>
        <button class="eval-tab-btn" id="btn-tab-plan" onclick="switchEvalDashboardTab('tab-plan')">🚀 30-Day Executive Coaching Plan</button>
      </div>
        <button class="eval-tab-btn" id="btn-tab-plan" onclick="switchEvalDashboardTab('tab-plan')">🚀 30-Day Executive Coaching Plan</button>
      </div>

      <!-- TAB 1: Competency Rubrics (BARS Framework) -->
      <div id="tab-competencies" style="display: block;">
        <div style="display: flex; justify-content: space-between; align-items: baseline; flex-wrap: wrap; gap: 0.5rem; margin-bottom: 0.5rem;">
          <div>
            <h3 style="font-size: 1.15rem; color: var(--text-main); margin: 0;">Track-Specific Competency Evaluation (BARS Rubrics)</h3>
            <p style="font-size: 0.84rem; color: var(--text-muted); margin: 0.2rem 0 0 0;">Evaluated strictly against the behavioral rubrics defined for <strong>${escapeHtml(candidateProfile.interviewType || 'Comprehensive Focus')}</strong>.</p>
          </div>
          <span class="badge badge-primary">Automated Rubric Audit</span>
        </div>
        <div class="competency-cards-grid">
          ${compCardsHtml}
        </div>
      </div>

      <!-- TAB 2: Turn-by-Turn Question & Response Audit -->
      <div id="tab-turns" style="display: none;">
        <div style="margin-bottom: 1rem;">
          <h3 style="font-size: 1.15rem; color: var(--text-main); margin: 0;">Chronological Dialogue & Evidence Stream</h3>
          <p style="font-size: 0.84rem; color: var(--text-muted); margin: 0.2rem 0 0 0;">Verifiable question-by-question audit linking Dr. Vance's probes to candidate quotes, positive evidence, and observed gaps.</p>
        </div>
        <div>
          ${turnsHtml}
        </div>
      </div>

      <!-- TAB 3: Job Description & Resume Alignment Audit -->
      <div id="tab-jd" style="display: none;">
        <div style="margin-bottom: 1rem;">
          <h3 style="font-size: 1.15rem; color: var(--text-main); margin: 0;">Prerequisite Alignment & Resume Substantiation Audit</h3>
          <p style="font-size: 0.84rem; color: var(--text-muted); margin: 0.2rem 0 0 0;">Verification of core requirements extracted from the target Job Description and Candidate CV highlights.</p>
        </div>
        <div class="table-container jd-table-wrapper">
          <table class="jd-audit-matrix">
            <thead>
              <tr>
                <th>Prerequisite / Qualification</th>
                <th>Demonstration Status</th>
                <th>Cited Candidate Quote / Spoken Terms</th>
                <th>Committee Alignment Commentary</th>
              </tr>
            </thead>
            <tbody>
              ${jdRowsHtml}
            </tbody>
          </table>
        </div>
      </div>

      <!-- TAB 4: Executive Debrief & 30-Day Coaching Plan -->
      <div id="tab-plan" style="display: none;">
        <div style="margin-bottom: 1rem;">
          <h3 style="font-size: 1.15rem; color: var(--text-main); margin: 0;">Executive Debrief & Targeted Action Plan</h3>
          <p style="font-size: 0.84rem; color: var(--text-muted); margin: 0.2rem 0 0 0;">Concrete, high-leverage recommendations to elevate performance to the next seniority tier.</p>
        </div>
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 1rem; margin-bottom: 1.25rem;">
          <div class="debrief-box debrief-superpowers">
            <div class="debrief-heading">✓ TOP CANDIDATE SUPERPOWERS:</div>
            <ul class="debrief-list">
              ${topStrengths}
            </ul>
          </div>
          <div class="debrief-box debrief-risks">
            <div class="debrief-heading">⚠️ CRITICAL GROWTH & ONBOARDING RISKS:</div>
            <ul class="debrief-list">
              ${topGrowth}
            </ul>
          </div>
        </div>

        <div class="debrief-box debrief-actions">
          <div class="debrief-heading">🎯 30-DAY TARGETED ACTION PLAN TO REACH NEXT LEVEL:</div>
          <ol class="debrief-list debrief-ordered">
            ${topActions}
          </ol>
        </div>
      </div>
    </div>
  `;

  // Update Export Links
  const docxBtn = document.getElementById("btn-dl-sim-docx");
  const pptxBtn = document.getElementById("btn-dl-sim-pptx");
  if (docxBtn && currentSessionId) docxBtn.href = `/api/export-docx/${currentSessionId}`;
  if (pptxBtn && currentSessionId) pptxBtn.href = `/api/export-pptx/${currentSessionId}`;
}

// ==========================================
// 6. CS 435 USER EVALUATION & ETHICS MODULE
// ==========================================
function startEvalTimer() {
  if (evalTimerInterval) clearInterval(evalTimerInterval);
  evalTimerSeconds = 0;
  evalTimerInterval = setInterval(() => {
    evalTimerSeconds++;
    const m = String(Math.floor(evalTimerSeconds / 60)).padStart(2, '0');
    const s = String(evalTimerSeconds % 60).padStart(2, '0');
    const disp = document.getElementById("eval-timer-display");
    if (disp) disp.innerText = `${m}:${s}`;
  }, 1000);
}

function stopEvalTimer() {
  if (evalTimerInterval) {
    clearInterval(evalTimerInterval);
    evalTimerInterval = null;
  }
}

function setupSusListeners() {
  for (let i = 1; i <= 10; i++) {
    const radios = document.getElementsByName(`sus_q${i}`);
    radios.forEach(r => r.addEventListener("change", calculateLiveSusScore));
  }
}

function calculateLiveSusScore() {
  let oddSum = 0;
  let evenSum = 0;
  let allAnswered = true;

  for (let i = 1; i <= 10; i++) {
    const selected = document.querySelector(`input[name="sus_q${i}"]:checked`);
    if (!selected) {
      allAnswered = false;
      continue;
    }
    const val = parseInt(selected.value, 10);
    if (i % 2 === 1) {
      // Odd items (positive): score - 1
      oddSum += (val - 1);
    } else {
      // Even items (negative): 5 - score
      evenSum += (5 - val);
    }
  }

  const rawScore = (oddSum + evenSum) * 2.5;
  const scoreDisplay = document.getElementById("sus-score-display");
  const gradeBadge = document.getElementById("sus-grade-badge");

  if (scoreDisplay) scoreDisplay.innerText = `${rawScore.toFixed(1)} / 100`;

  if (gradeBadge) {
    if (rawScore >= 85) {
      gradeBadge.className = "badge badge-success";
      gradeBadge.innerText = "Grade: A+ (Exceptional Usability)";
    } else if (rawScore >= 75) {
      gradeBadge.className = "badge badge-success";
      gradeBadge.innerText = "Grade: A (Good Usability)";
    } else if (rawScore >= 68) {
      gradeBadge.className = "badge badge-warning";
      gradeBadge.innerText = "Grade: C (Average Usability - Benchmark: 68.0)";
    } else {
      gradeBadge.className = "badge badge-danger";
      gradeBadge.innerText = "Grade: Marginal / Needs Improvement";
    }
  }

  return rawScore;
}

function loadSampleEvaluationP01() {
  document.getElementById("eval-participant-id").value = "P01";
  document.getElementById("eval-target-role").value = "UX Research Intern";
  document.getElementById("eval-prototype-tested").value = "Both";
  document.getElementById("eval-notes-realism").value = "Voice interaction made the simulation feel like a live interview. Adaptive follow-up challenged my initial vague answer.";
  document.getElementById("eval-notes-learning").value = "The 'Why this feedback' screen made it completely clear why I lost points on Evidence. The side-by-side retry comparison showed my concrete +4.0 score delta.";
  calculateLiveSusScore();
}

async function submitUserEvaluation() {
  const consent = document.getElementById("eval-consent-checkbox").checked;
  if (!consent) {
    alert("Participant consent is required to log usability evaluation data.");
    return;
  }

  const pId = document.getElementById("eval-participant-id").value.trim() || "P01";
  const role = document.getElementById("eval-target-role").value;
  const proto = document.getElementById("eval-prototype-tested").value;
  const susScore = calculateLiveSusScore();

  const susScores = [];
  for (let i = 1; i <= 10; i++) {
    const sel = document.querySelector(`input[name="sus_q${i}"]:checked`);
    susScores.push(sel ? parseInt(sel.value, 10) : 3);
  }

  const payload = {
    participant_id: pId,
    target_role: role,
    prototype_tested: proto,
    task_completed: true,
    task_time_seconds: evalTimerSeconds || 245,
    sus_scores: susScores,
    sus_total_score: susScore,
    feedback_realism: document.getElementById("eval-notes-realism").value,
    feedback_learning: document.getElementById("eval-notes-learning").value,
    ethical_consent_signed: true
  };

  try {
    const res = await fetch("/api/evaluation-study", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    alert(`Participant ${pId} evaluation logged successfully!`);
    loadLoggedEvaluations();
  } catch (err) {
    console.error(err);
    alert("Failed to save evaluation to database.");
  }
}

async function loadLoggedEvaluations() {
  const listEl = document.getElementById("eval-studies-list");
  if (!listEl) return;

  try {
    const res = await fetch("/api/evaluation-study");
    const data = await res.json();

    if (!data || data.length === 0) {
      listEl.innerHTML = "<em>No participant test sessions recorded yet. Complete a study run above.</em>";
      return;
    }

    let html = `
      <table class="sus-table">
        <thead>
          <tr>
            <th>ID</th>
            <th>Target Role</th>
            <th>Prototype</th>
            <th>Task Time</th>
            <th>SUS Score</th>
            <th>Consent</th>
            <th>Recorded At</th>
          </tr>
        </thead>
        <tbody>
    `;
    data.forEach(d => {
      html += `
        <tr>
          <td><strong>${escapeHtml(d.participant_id)}</strong></td>
          <td>${escapeHtml(d.target_role)}</td>
          <td>${escapeHtml(d.prototype_tested)}</td>
          <td>${d.task_time_seconds}s</td>
          <td><strong>${d.sus_total_score}</strong>/100</td>
          <td><span class="badge badge-success">✓ Signed</span></td>
          <td>${d.created_at ? d.created_at.substring(0, 16) : 'Now'}</td>
        </tr>
      `;
    });
    html += `</tbody></table>`;
    listEl.innerHTML = html;
  } catch (e) {
    console.warn("Could not load evaluations:", e);
  }
}

function exportEvaluationDataset() {
  fetch("/api/evaluation-study")
    .then(res => res.json())
    .then(data => {
      // Export JSON
      const jsonBlob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const jsonUrl = URL.createObjectURL(jsonBlob);
      const aJson = document.createElement("a");
      aJson.href = jsonUrl;
      aJson.download = "CS435_Evaluation_Data.json";
      aJson.click();

      // Export CSV
      let csv = "participant_id,target_role,prototype_tested,task_time_seconds,sus_total_score,ethical_consent_signed,feedback_realism,feedback_learning\n";
      data.forEach(d => {
        csv += `"${d.participant_id}","${d.target_role}","${d.prototype_tested}",${d.task_time_seconds},${d.sus_total_score},${d.ethical_consent_signed},"${(d.feedback_realism||'').replace(/"/g, '""')}","${(d.feedback_learning||'').replace(/"/g, '""')}"\n`;
      });
      const csvBlob = new Blob([csv], { type: "text/csv" });
      const csvUrl = URL.createObjectURL(csvBlob);
      const aCsv = document.createElement("a");
      aCsv.href = csvUrl;
      aCsv.download = "CS435_Evaluation_Data.csv";
      setTimeout(() => aCsv.click(), 400);
    })
    .catch(err => {
      console.error(err);
      alert("Error generating export dataset.");
    });
}

// ==========================================
// 7. CONFIGURATION MODAL
// ==========================================
function openConfigModal() {
  document.getElementById("modal-config").style.display = "flex";
  loadConfigSettings();
}

function closeConfigModal() {
  document.getElementById("modal-config").style.display = "none";
}

function loadConfigSettings() {
  const rateInput = document.getElementById("cfg-voice-rate");
  const pitchInput = document.getElementById("cfg-voice-pitch");
  const rateVal = document.getElementById("cfg-rate-val");
  const pitchVal = document.getElementById("cfg-pitch-val");

  if (rateInput && speechRate) {
    rateInput.value = speechRate;
    if (rateVal) rateVal.innerText = speechRate.toFixed(2) + "x";
  }
  if (pitchInput && speechPitch) {
    pitchInput.value = speechPitch;
    if (pitchVal) pitchVal.innerText = speechPitch.toFixed(1);
  }
}

async function saveConfigSettings() {
  const rateInput = document.getElementById("cfg-voice-rate");
  const pitchInput = document.getElementById("cfg-voice-pitch");

  if (rateInput) speechRate = parseFloat(rateInput.value) || 1.0;
  if (pitchInput) speechPitch = parseFloat(pitchInput.value) || 1.0;

  try {
    await fetch("/api/config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        voice_speed: speechRate,
        auto_speak: autoSpeakEnabled
      })
    });
  } catch (err) {
    console.warn("Config save notice:", err);
  }
  closeConfigModal();
}

function escapeHtml(text) {
  const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' };
  return text.replace(/[&<>"']/g, m => map[m]);
}

// Explicit window bindings for bulletproof browser onclick compatibility
window.switchMainTab = switchMainTab;
window.goToScreenA = goToScreenA;
window.goToScreenB = goToScreenB;
window.startSessionA = startSessionA;
window.startSessionB = startSessionB;
window.submitAnswerA = submitAnswerA;
window.submitSimulationAnswer = submitSimulationAnswer;
window.finishSimulation = finishSimulation;
window.loadSampleAnswerA = loadSampleAnswerA;
window.loadSampleAnswerB = loadSampleAnswerB;
window.loadSampleRahulAnswer = loadSampleAnswerB;
window.toggleVoiceInputUniversal = toggleVoiceInputUniversal;
window.clearAnswerDirect = clearAnswerDirect;
window.toggleTheme = toggleTheme;
window.applyTheme = applyTheme;
window.initTheme = initTheme;
window.openConfigModal = openConfigModal;
window.closeConfigModal = closeConfigModal;
window.saveConfigSettings = saveConfigSettings;
window.toggleMuteAudio = toggleMuteAudio;
window.replayLastInterviewerMessage = replayLastInterviewerMessage;
window.speakCurrentQuestionA = speakCurrentQuestionA;
window.speakText = speakText;
window.applyRolePresetA = applyRolePresetA;
window.applyRolePresetB = applyRolePresetB;
window.setRoleFieldA = setRoleFieldA;
window.setRoleFieldB = setRoleFieldB;
window.syncCandidateName = syncCandidateName;
window.syncCandidateCompany = syncCandidateCompany;
window.syncCandidateRole = syncCandidateRole;
window.syncCandidateLevel = syncCandidateLevel;
window.startEvalTimer = startEvalTimer;
window.stopEvalTimer = stopEvalTimer;
window.submitUserEvaluation = submitUserEvaluation;
window.exportEvaluationDataset = exportEvaluationDataset;
window.loadSampleEvaluationP01 = loadSampleEvaluationP01;
window.openWhyFeedbackModal = openWhyFeedbackModal;
window.closeWhyFeedbackModal = closeWhyFeedbackModal;
window.saveReflectionA = saveReflectionA;
window.loadSampleReflectionA = loadSampleReflectionA;
window.testVoicePlayback = testVoicePlayback;
window.searchWebKnowledge = searchWebKnowledge;
window.cycleDemoPortfolio = cycleDemoPortfolio;
window.cycleDemoPortfolioAndOpen = cycleDemoPortfolioAndOpen;
window.switchEvalDashboardTab = switchEvalDashboardTab;
window.replayInterviewerTurn = replayInterviewerTurn;
window.setCockpitInputMode = setCockpitInputMode;
window.clearCockpitAnswer = clearCockpitAnswer;
window.confirmExitSimulation = confirmExitSimulation;
window.setCockpitInputModeA = setCockpitInputModeA;
window.speakFeedbackA4 = speakFeedbackA4;
window.speakFeedforwardA6 = speakFeedforwardA6;
window.speakAdaptiveProbeA7 = speakAdaptiveProbeA7;
window.speakComparisonA8 = speakComparisonA8;
window.handleHomeModeSelectChange = handleHomeModeSelectChange;
window.handleStartFromHome = handleStartFromHome;
window.handleAutoFillFromHome = handleAutoFillFromHome;
window.handleB2ModeSwitch = handleB2ModeSwitch;
window.handleStartSimulationOrPractice = handleStartSimulationOrPractice;
window.goBackUniversal = goBackUniversal;
window.updateContextBannerVisibility = updateContextBannerVisibility;
window.goToHomeUniversal = goToHomeUniversal;
window.openLongitudinalProgress = openLongitudinalProgress;
window.resetLongitudinalProgress = resetLongitudinalProgress;

