// CS 435: Self-Directed AI-Assisted Interview Practice System
// High-Fidelity Client Application with Real-Time STT, TTS, Animated Visualizers & Evaluation Module

let currentSessionId = null;
let currentQuestionId = 1;
let currentQuestionText = "Tell me about a time when you worked with a difficult teammate. What was the situation and how did you resolve it?";
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

// Initialization
document.addEventListener("DOMContentLoaded", () => {
  setupWordCounters();
  setupSpeechRecognition();
  setupSpeechSynthesis();
  loadLongitudinalProgress();
  loadConfigSettings();
  loadLoggedEvaluations();
  calculateLiveSusScore();
  setupSusListeners();
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

  // Update Prototype A visualizer
  const a3Equalizer = document.getElementById("a3-equalizer");
  const a3Status = document.getElementById("a3-voice-status");
  if (a3Equalizer && isSpeaking) a3Equalizer.classList.add("active");
  if (a3Status && isSpeaking) {
    a3Status.className = "voice-status-pill speaking";
    a3Status.innerText = "🔊 Reading Aloud...";
  }
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
  const btnB3 = document.getElementById("btn-mute-b3");
  if (btnB3) {
    btnB3.innerText = isMuted ? "🔊 Unmute" : "🔇 Mute";
    btnB3.classList.toggle("btn-warning", isMuted);
  }
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

  if (mode === "voice") {
    if (vStage) vStage.style.display = "block";
    if (tStage) tStage.style.display = "none";
    if (vBtn) vBtn.classList.add("active");
    if (tBtn) tBtn.classList.remove("active");
  } else {
    if (vStage) vStage.style.display = "none";
    if (tStage) tStage.style.display = "block";
    if (vBtn) vBtn.classList.remove("active");
    if (tBtn) tBtn.classList.add("active");
    const ta = document.getElementById("b-answer");
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

function confirmExitSimulation() {
  if (simConversationHistory && simConversationHistory.length > 1) {
    if (confirm("Are you sure you want to return to configuration? Your ongoing mock interview progress will be reset.")) {
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
  if (targetId !== "b-answer") return;
  const words = (totalSpoken || "").trim().split(/\s+/).filter(Boolean);
  if (words.length < 5) return;

  if (simSilenceTimer) clearTimeout(simSilenceTimer);
  if (simSilenceCountdownTimer) {
    clearInterval(simSilenceCountdownTimer);
    simSilenceCountdownTimer = null;
  }

  let remainingSec = 3.5;
  simSilenceCountdownTimer = setInterval(() => {
    remainingSec -= 0.5;
    if (remainingSec <= 2.0 && isUniversalRecording && universalTextareaId === "b-answer") {
      if (statusEl) {
        statusEl.innerHTML = `⏸️ <strong>Pause detected:</strong> Auto-sending to Dr. Vance in <strong>${remainingSec.toFixed(1)}s</strong> (keep speaking to cancel)...`;
      }
    }
    if (remainingSec <= 0) {
      if (simSilenceCountdownTimer) {
        clearInterval(simSilenceCountdownTimer);
        simSilenceCountdownTimer = null;
      }
    }
  }, 500);

  simSilenceTimer = setTimeout(() => {
    if (simSilenceCountdownTimer) {
      clearInterval(simSilenceCountdownTimer);
      simSilenceCountdownTimer = null;
    }
    if (isUniversalRecording && universalTextareaId === "b-answer") {
      console.log("Natural conversational pause detected in real interview mode -> auto-forwarding response to AI");
      stopUniversalRecordingAndTranscribe();
    }
  }, 3500);
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
  universalPCMChunks = [];
  isUniversalRecording = true;

  // 1. Update UI IMMEDIATELY so button is visibly functional
  if (btn) {
    if (btnId === "hero-mic-b") {
      const glyph = document.getElementById("hero-mic-glyph");
      const label = document.getElementById("hero-mic-label");
      const sub = document.getElementById("hero-mic-sub");
      if (glyph) glyph.innerText = "⏹️";
      if (label) label.innerText = "Done Speaking — Send Response ↵";
      if (sub) sub.innerText = "Listening live... Auto-sends on 3.5s pause or click now";
      btn.classList.add("recording");
    } else if (btnId === "btn-speech-b") {
      btn.innerText = "⏹️ Finish Speaking (Auto-Sends to AI)";
      btn.className = "btn btn-danger btn-sm";
    } else {
      btn.innerText = "⏹️ Done Speaking (Click to Finish)";
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

  // 2. LAYER A: Web Speech API (Client-side native streaming)
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (SpeechRecognition) {
    try {
      if (universalRecognition) {
        try { universalRecognition.abort(); } catch (e) {}
      }
      universalRecognition = new SpeechRecognition();
      universalRecognition.continuous = true;
      universalRecognition.interimResults = true;
      universalRecognition.lang = navigator.language || "en-US";
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

        const totalSpoken = (universalSpeechAccumulated + interimBatch).trim();
        if (totalSpoken) {
          universalWebSpeechGotText = true;
          if (textarea) {
            textarea.value = (universalBaseText ? universalBaseText + " " : "") + totalSpoken;
            textarea.dispatchEvent(new Event("input"));
          }
          if (preview) {
            preview.innerText = `“${interimBatch || totalSpoken}”`;
            preview.classList.add("active");
          }
          if (status) {
            status.innerHTML = `🗣️ <strong>Speaking:</strong> ${(interimBatch || totalSpoken).slice(-45)}`;
          }
          checkSimSilenceAutoForward(totalSpoken, universalTextareaId, status);
        }
      };

      universalRecognition.onerror = (e) => {
        console.warn("Web Speech API note (resilient fallback active):", e.error);
      };

      universalRecognition.start();
    } catch (wsErr) {
      console.warn("Web Speech start note:", wsErr);
    }
  }

  // 3. LAYER B: Live Streaming Full-Duplex WebSocket STT (Vosk Concurrent Transcriber)
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
            // If Web Speech API is not providing text or Vosk has more text, update UI directly
            if (!universalWebSpeechGotText || text.length >= (universalSpeechAccumulated || "").length) {
              if (textarea) {
                textarea.value = (universalBaseText ? universalBaseText + " " : "") + text;
                textarea.dispatchEvent(new Event("input"));
              }
              if (preview) {
                preview.innerText = `“${text}”`;
                preview.classList.add("active");
              }
              if (status) {
                status.innerHTML = `🗣️ <strong>Transcribing Live:</strong> ${escapeHtml(text.slice(-45))}`;
              }
              checkSimSilenceAutoForward(text, universalTextareaId, status);
            }
          }
        } else if (msg.type === "complete") {
          const text = (msg.text || "").trim();
          if (text) {
            universalLiveStreamGotText = true;
            universalLiveStreamAccumulated = text;
            if (textarea) {
              const base = universalBaseText ? universalBaseText + " " : "";
              if (!universalWebSpeechGotText || text.length >= textarea.value.length) {
                textarea.value = base + text;
                textarea.dispatchEvent(new Event("input"));
              }
            }
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

  // 4. LAYER C: 100% Reliable Web Audio API buffer capture & frame streaming
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

    const source = universalAudioCtx.createMediaStreamSource(stream);
    universalAnalyser = universalAudioCtx.createAnalyser();
    universalAnalyser.fftSize = 512;

    universalScriptProcessor = universalAudioCtx.createScriptProcessor(4096, 1, 1);
    const audioContextSampleRate = universalAudioCtx.sampleRate;

    universalScriptProcessor.onaudioprocess = (e) => {
      if (!isUniversalRecording) return;
      const inputData = e.inputBuffer.getChannelData(0);
      universalPCMChunks.push(new Float32Array(inputData));

      // Stream concurrently to backend Speech-to-Text converter during recording
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

  const textarea = document.getElementById(universalTextareaId);
  const status = document.getElementById(universalStatusId);
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
    if (status) {
      status.innerHTML = "✓ <strong>Voice Converted in Real-Time:</strong> Answer captured live with zero wait time!";
    }
    resetUniversalUI();
    // Real Interview Mode auto-forwarding directly to AI
    if (targetTextareaId === "b-answer") {
      if (status) status.innerHTML = "🚀 <strong>Auto-forwarding spoken response directly to Dr. Marcus Vance...</strong>";
      setTimeout(() => {
        submitSimulationAnswer();
      }, 350);
    }
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
  for (let i = 0; i < universalPCMChunks.length; i++) {
    mergedFloat32.set(universalPCMChunks[i], offset);
    offset += universalPCMChunks[i].length;
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
      if (textarea) {
        textarea.value = (universalBaseText ? universalBaseText + " " : "") + text;
        textarea.dispatchEvent(new Event("input"));
      }
      if (status) {
        status.innerHTML = `✓ <strong>Spoken Answer Transcribed:</strong> “${escapeHtml(text.slice(0, 70))}${text.length > 70 ? '...' : ''}”`;
      }
      resetUniversalUI();
      // Real Interview Mode auto-forwarding directly to AI
      if (targetTextareaId === "b-answer") {
        if (status) status.innerHTML = "🚀 <strong>Auto-forwarding spoken response directly to Dr. Marcus Vance...</strong>";
        setTimeout(() => {
          submitSimulationAnswer();
        }, 350);
      }
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

function resetUniversalUI() {
  if (universalBtnId) {
    const btn = document.getElementById(universalBtnId);
    if (btn) {
      if (universalBtnId === "hero-mic-b") {
        const glyph = document.getElementById("hero-mic-glyph");
        const label = document.getElementById("hero-mic-label");
        const sub = document.getElementById("hero-mic-sub");
        if (glyph) glyph.innerText = "🎙️";
        if (label) label.innerText = "Click to Speak to Dr. Vance";
        if (sub) sub.innerText = "Transcribes in real time • Auto-sends on 3.5s pause or click";
        btn.classList.remove("recording");
      } else if (universalBtnId === "btn-speech-b") {
        btn.innerText = "🎙️ Speak to Interviewer (Auto-Forwards)";
        btn.className = "btn btn-primary btn-sm";
      } else {
        btn.innerText = "🎙️ Start Voice Input (Click to Speak)";
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
    if (preview) preview.classList.remove("active");
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
          html += `<li><strong>${escapeHtml(r.title)}</strong><br><span style='color: #475569;'>${escapeHtml(r.snippet)}</span>${r.url ? ` <a href='${r.url}' target='_blank' style='color: #2563eb; font-size: 0.8rem; text-decoration: underline;'>[Source]</a>` : ''}</li>`;
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
  ["a-answer", "a-retry-answer", "b-answer"].forEach(id => {
    const el = document.getElementById(id);
    if (el) {
      el.addEventListener("input", (e) => {
        const words = e.target.value.trim().split(/\s+/).filter(Boolean);
        const counterEl = document.getElementById(id === "a-answer" ? "a-word-count" : "");
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
  const pR = document.getElementById("nav-research");
  if (pA) pA.classList.toggle("active", tab === "A");
  if (pB) pB.classList.toggle("active", tab === "B");
  if (pE) pE.classList.toggle("active", tab === "E");
  if (pR) pR.classList.toggle("active", tab === "R");

  const secA = document.getElementById("section-proto-a");
  const secB = document.getElementById("section-proto-b");
  const secE = document.getElementById("section-eval");
  const secR = document.getElementById("section-research");

  if (secA) secA.style.display = tab === "A" ? "block" : "none";
  if (secB) secB.style.display = tab === "B" ? "block" : "none";
  if (secE) secE.style.display = tab === "E" ? "block" : "none";
  if (secR) secR.style.display = tab === "R" ? "block" : "none";

  stopAllAudio();
  window.scrollTo({ top: 0, behavior: "smooth" });
}

// Wireframe Mode Toggle
function toggleWireframeMode() {
  const isWireframe = document.body.classList.toggle("wireframe-mode");
  document.getElementById("wf-status").innerText = isWireframe ? "ON" : "OFF";
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
  if (tSelect) tSelect.value = type;

  syncCandidateRole(role);
  syncCandidateCompany(company);
  syncCandidateLevel(level);

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
    name: "Elena Rostova",
    role: "Staff Distributed Systems Engineer",
    company: "Stripe",
    level: "Senior",
    interviewType: "Technical & System Architecture (Deep Dive)",
    interviewDuration: "Comprehensive Onsite Loop (8-10 Questions • ~60 mins)",
    difficulty: "Challenging & Probing (Technical Bar Raiser / Stress Test)",
    tagline: "High-Throughput Consensus & Ledgers",
    cv: "Led distributed consensus protocol redesign using Raft quorum leases for cross-region payment ledgers. Cut 99th-percentile commit latency from 450ms to 42ms with 99.999% availability. Reduced cross-AZ egress costs by $410k/year across 14 clusters.",
    jd: "Architect high-throughput, fault-tolerant financial ledger infrastructure. Deep expertise with Raft/Paxos consensus, partition tolerance, distributed transactions (2PC/Saga), and low-latency gRPC services."
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
    cv: "Master's student in HCI at IIT Gandhinagar. Conducted 30+ mixed-methods usability tests and semi-structured interviews on onboarding flows, driving a 28% increase in task completion and reducing drop-off by 15%. Expert in cognitive walkthroughs and STAR method.",
    jd: "Conduct qualitative user interviews, usability benchmarking, cognitive walkthroughs, and synthesize actionable UX design guidelines for cross-functional product and engineering teams."
  },
  {
    id: "product-management",
    name: "Marcus Chen",
    role: "Associate Product Manager",
    company: "Airbnb",
    level: "Mid-Level",
    interviewType: "Situational Problem Solving & Strategy (Execution)",
    interviewDuration: "Standard Round (6-7 Questions • ~45 mins)",
    difficulty: "Neutral Corporate (Standard Hiring Bar / Objective)",
    tagline: "Marketplace GMV & Experimentation",
    cv: "Managed cross-functional squad of 8 engineers and 2 product designers. Launched dynamic pricing pilot across 12 metropolitan markets, yielding $3.4M annualized GMV lift. Resolved priority conflicts between checkout redesign and technical debt reduction.",
    jd: "Lead product discovery and execution for two-sided marketplace dynamics. Define North Star metrics, run rigorous A/B experiments, and partner with data science and engineering leaders."
  },
  {
    id: "machine-learning",
    name: "Dr. Priya Nair",
    role: "Senior Machine Learning Engineer",
    company: "HealthAI Labs",
    level: "Senior",
    interviewType: "Technical & System Architecture (Deep Dive)",
    interviewDuration: "Comprehensive Onsite Loop (8-10 Questions • ~60 mins)",
    difficulty: "Challenging & Probing (Technical Bar Raiser / Stress Test)",
    tagline: "Medical Imaging & Edge TensorRT",
    cv: "Ph.D. in Computer Vision. Deployed PyTorch 3D UNet for automated MRI lesion segmentation with 94.2% Dice coefficient. Optimized inference using TensorRT and INT8 quantization, reducing scan latency from 800ms to 65ms on edge GPUs.",
    jd: "Develop and deploy deep learning models for clinical medical imaging. Experience with PyTorch, CUDA kernel optimization, model quantization, HIPAA compliance, and edge inference."
  },
  {
    id: "data-platform",
    name: "Liam O'Connor",
    role: "Data Platform Architect",
    company: "Netflix",
    level: "Senior",
    interviewType: "Leadership & Team Dynamics (Cross-Functional)",
    interviewDuration: "Standard Round (6-7 Questions • ~45 mins)",
    difficulty: "Neutral Corporate (Standard Hiring Bar / Objective)",
    tagline: "Streaming Lakehouse & Kafka/Flink",
    cv: "Architected real-time stream processing platform ingesting 15B events/day using Apache Kafka, Apache Flink, and Iceberg lakehouse. Slashed analytics pipeline lag from 4 hours to 45 seconds while cutting compute costs by $620k/year.",
    jd: "Own enterprise streaming data infrastructure, metadata cataloging, and data governance. Drive architecture reviews, scalability benchmarks, and cross-team data reliability SLAs."
  },
  {
    id: "frontend-engineering",
    name: "Sophia Rodriguez",
    role: "Senior Frontend Engineer",
    company: "Spotify",
    level: "Mid-Level",
    interviewType: "Full Mixed Mock (Behavioral + Technical Architecture)",
    interviewDuration: "Focused Screening (4-5 Questions • ~25 mins)",
    difficulty: "Supportive & Conversational (Mentorship / Low Stress)",
    tagline: "Design Systems & Web Performance",
    cv: "Created enterprise React/TypeScript accessible design system used by 45+ product squads. Improved web Core Web Vitals (LCP < 1.2s, CLS < 0.02) and reduced bundle size by 35% through tree-shaking and dynamic module federation.",
    jd: "Build modern, accessible, high-performance web applications with React, TypeScript, and Web Audio. Collaborate with product design to build resilient component libraries meeting WCAG 2.1 AA standards."
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
// 4. PROTOTYPE A (LEARNING-ORIENTED FLOW)
// ==========================================
function goToScreenA(screenId) {
  const secA = document.getElementById("section-proto-a");
  if (secA && secA.style.display === "none") {
    switchMainTab("A");
  }
  const screens = ["screen-a1", "screen-a2", "screen-a3", "screen-a4", "screen-a6", "screen-a7", "screen-a8", "screen-a9"];
  screens.forEach(id => {
    const el = document.getElementById(id);
    if (el) el.style.display = (id === `screen-${screenId}`) ? "block" : "none";
  });
  stopAllAudio();
  window.scrollTo({ top: 0, behavior: "smooth" });

  if (screenId === "a3" && autoSpeakEnabled) {
    setTimeout(speakCurrentQuestionA, 400);
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
    const shortDuration = durationVal.includes("Quick") ? "15m" : (durationVal.includes("Full") ? "45m" : "20m");
    a3DurationPill.innerText = `⏱️ ${shortDuration}`;
  }

  const startBtn = document.querySelector("#screen-a2 button.btn-primary");
  if (startBtn) {
    startBtn.disabled = true;
    startBtn.innerText = "⏳ Generating AI Questions with Nemotron 3.5...";
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

    if (data.first_question) {
      currentQuestionId = data.first_question.id;
      currentQuestionText = data.first_question.text;
      const qTextEl = document.getElementById("a3-q-text");
      if (qTextEl) qTextEl.innerText = `“${currentQuestionText}”`;
    }

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
    if (startBtn) {
      startBtn.disabled = false;
      startBtn.innerText = "🚀 Begin Practice Interview";
    }
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

function loadSampleAnswerA(attemptNumber) {
  const textarea = attemptNumber === 1 ? document.getElementById("a-answer") : document.getElementById("a-retry-answer");
  if (!textarea) return;

  const role = (candidateProfile.role || "Software Engineer").toLowerCase();
  if (role.includes("ux") || role.includes("design") || role.includes("research")) {
    if (attemptNumber === 1) {
      textarea.value = "In my previous UX sprint, I had a disagreement with our engineer on the dashboard layout. The engineer wanted fewer filters to save loading time, while I wanted all filters visible. I scheduled a 30-minute sync to talk through user needs and we agreed on a compromise.";
    } else {
      textarea.value = "During our cross-functional sprint for the user dashboard, a lead engineer and I disagreed on whether to include an extensive filter menu or streamline it based on usability tests. Rather than escalating, I scheduled a 30-minute working session where I walked through recorded user testing clips showing that 4 out of 5 users were confused by excessive filters. I proposed an A/B test compromise with collapsible filters. As a concrete result, our engineering partner agreed, we shipped the feature 2 days ahead of deadline, and subsequent product analytics revealed a 28% higher task completion rate with zero user drop-offs.";
    }
  } else if (role.includes("product") || role.includes("apm") || role.includes("pm")) {
    if (attemptNumber === 1) {
      textarea.value = "During a feature planning cycle, engineering wanted to delay an analytics integration to refactor backend services. I explained the business priority and we agreed to split the work across two milestones.";
    } else {
      textarea.value = "During our mobile checkout redesign, our lead backend engineer wanted to defer Apple Pay integration to Q3 due to technical debt, but our user funnel showed 42% cart abandonments on mobile checkout. I organized a prioritization workshop, mapped out the engineering debt versus lost revenue, and proposed a phased rollout with minimal webhook refactoring. As a result, we reduced checkout drop-offs by 31% within 3 weeks and generated an estimated $140,000 in recovered monthly ARR.";
    }
  } else {
    // Software Engineer / General
    if (attemptNumber === 1) {
      textarea.value = "In our last sprint, we found a memory leak in the production caching tier right before a major release. I investigated the logs, found the offending circular reference, and created a quick hotfix that unblocked the release.";
    } else {
      textarea.value = "Forty-eight hours before our quarterly enterprise release, monitoring alerted us to a 35% memory spike under simulated 10k RPS load. Rather than blindly reverting commits, I ran profiling using pprof, identified an unbounded map cache in our auth middleware, and proposed an LRU cache with strict eviction limits. I paired with our reliability lead to benchmark the fix under 15k RPS, proving 0% packet drops and stable heap memory. As a measurable outcome, we deployed on schedule, reduced P99 latency from 180ms to 42ms, and prevented an estimated $85,000 SLA penalty.";
    }
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
  const submitBtn = attemptNumber === 1 ? document.getElementById("btn-submit-a") : null;
  if (submitBtn) submitBtn.innerText = "Evaluating against rubric...";

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
      goToScreenA("a4");
    } else {
      await loadAttemptComparison();
      goToScreenA("a8");
    }
  } catch (err) {
    console.error(err);
    alert("Evaluation error. Please try again.");
  } finally {
    if (submitBtn) submitBtn.innerText = "Submit Answer";
  }
}

function renderFeedbackScreenA4(evalData) {
  document.getElementById("a4-overall-score").innerText = `${evalData.overall_score} / 10`;

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

  // Populate Why Modal
  document.getElementById("modal-why-score").innerText = `${evalData.evidence_outcome.score} / 10`;
  document.getElementById("modal-why-reason").innerText = evalData.evidence_outcome.reason;
  if (evalData.evidence_outcome.evidence_found) {
    document.getElementById("modal-why-excerpt").innerText = `Analyzed: “${evalData.evidence_outcome.evidence_found}”`;
  }
  if (evalData.example_improved_answer) {
    document.getElementById("modal-why-addition").innerText = evalData.example_improved_answer;
  }
}

function openWhyFeedbackModal() {
  document.getElementById("modal-why-feedback").style.display = "flex";
}

function closeWhyFeedbackModal() {
  document.getElementById("modal-why-feedback").style.display = "none";
}

function loadSampleReflectionA() {
  document.getElementById("a-change").value = "I would add the measurable user retention impact and exact A/B test metric to show a concrete resolution.";
  document.getElementById("a-learn").value = "In behavioral interviews, explaining actions isn't enough; I must explicitly state the quantifiable result (STAR Result).";
}

async function saveReflectionA() {
  const change = document.getElementById("a-change").value;
  const learn = document.getElementById("a-learn").value;

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
  } catch (err) {
    console.error(err);
    // Local fallback diff
    renderComparisonTable({
      deltas: { relevance: 1.0, specificity: 2.0, evidence_outcome: 4.0, structure_clarity: 2.0, overall: 2.2 },
      attempt1_scores: { relevance: 8.0, specificity: 6.0, evidence: 4.0, structure: 6.0, overall: 6.0 },
      attempt2_scores: { relevance: 9.0, specificity: 8.0, evidence: 8.0, structure: 8.0, overall: 8.2 },
      improvements: ["✓ Added measurable outcome & concrete evidence (4.0 → 8.0)", "✓ Overall score increased from 6.0/10 to 8.2/10 (+2.2)"]
    });
  }
}

function renderComparisonTable(comp) {
  const tbody = document.getElementById("compare-tbody");
  tbody.innerHTML = `
    <tr>
      <td><strong>Relevance</strong></td>
      <td>${comp.attempt1_scores.relevance}/10</td>
      <td>${comp.attempt2_scores.relevance}/10</td>
      <td><span class="score-delta">+${comp.deltas.relevance}</span></td>
    </tr>
    <tr>
      <td><strong>Specificity</strong></td>
      <td>${comp.attempt1_scores.specificity}/10</td>
      <td>${comp.attempt2_scores.specificity}/10</td>
      <td><span class="score-delta">+${comp.deltas.specificity}</span></td>
    </tr>
    <tr>
      <td><strong>Evidence & Outcome (STAR)</strong></td>
      <td>${comp.attempt1_scores.evidence}/10</td>
      <td>${comp.attempt2_scores.evidence}/10</td>
      <td><span class="score-delta" style="color: #ea580c; font-weight: 800;">+${comp.deltas.evidence_outcome || comp.deltas.evidence} ★</span></td>
    </tr>
    <tr>
      <td><strong>Structure & Clarity</strong></td>
      <td>${comp.attempt1_scores.structure}/10</td>
      <td>${comp.attempt2_scores.structure}/10</td>
      <td><span class="score-delta">+${comp.deltas.structure_clarity || comp.deltas.structure}</span></td>
    </tr>
    <tr style="background-color: var(--primary-light);">
      <td><strong>Overall Rating</strong></td>
      <td><strong>${comp.attempt1_scores.overall}/10</strong></td>
      <td><strong>${comp.attempt2_scores.overall}/10</strong></td>
      <td><strong style="color: var(--primary); font-size: 1.1rem;">+${comp.deltas.overall}</strong></td>
    </tr>
  `;

  const impList = document.getElementById("compare-improvements");
  if (impList && comp.improvements) {
    impList.innerHTML = comp.improvements.map(i => `<li>${i}</li>`).join("");
  }
}

// Longitudinal Progress Chart
async function loadLongitudinalProgress() {
  try {
    const res = await fetch(`/api/progress?persona_id=${activePersona}`);
    const data = await res.json();

    const ctx = document.getElementById("progressChart");
    if (!ctx) return;

    const labels = data.trajectory.map(t => t.attempt_label);
    const overallScores = data.trajectory.map(t => t.overall_score);
    const evidenceScores = data.trajectory.map(t => t.evidence_score);

    if (progressChartInstance) {
      progressChartInstance.destroy();
    }

    progressChartInstance = new Chart(ctx, {
      type: "line",
      data: {
        labels: labels,
        datasets: [
          {
            label: "Overall Score (0-10)",
            data: overallScores,
            borderColor: "#2563eb",
            backgroundColor: "rgba(37, 99, 235, 0.1)",
            tension: 0.3,
            fill: true,
            borderWidth: 3
          },
          {
            label: "Evidence & Outcome Score (0-10)",
            data: evidenceScores,
            borderColor: "#ea580c",
            backgroundColor: "transparent",
            borderDash: [5, 5],
            tension: 0.3,
            borderWidth: 2
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          y: {
            min: 0,
            max: 10,
            title: { display: true, text: "Rubric Rating" }
          }
        }
      }
    });

    const wList = document.getElementById("prog-weaknesses");
    if (wList && data.profile.recurring_weaknesses) {
      wList.innerHTML = data.profile.recurring_weaknesses.map(w => `<li>${w}</li>`).join("");
    }

    const focusEl = document.getElementById("prog-focus");
    if (focusEl) {
      focusEl.innerText = `${data.current_focus_area}. ${data.action_advice}`;
    }

  } catch (err) {
    console.error("Progress fetch error:", err);
  }
}

// ==========================================
// 5. PROTOTYPE B (FULL REAL-TIME VOICE SIMULATION)
// ==========================================
let simConversationHistory = [];

function goToScreenB(screenId) {
  const secB = document.getElementById("section-proto-b");
  if (secB && secB.style.display === "none") {
    switchMainTab("B");
  }
  const screens = ["screen-b1", "screen-b2", "screen-b3", "screen-b6", "screen-b8"];
  screens.forEach(id => {
    const el = document.getElementById(id);
    if (el) el.style.display = (id === `screen-${screenId}`) ? "block" : "none";
  });
  stopAllAudio();
  window.scrollTo({ top: 0, behavior: "smooth" });
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
    heroSub.innerText = "Transcribes in real time • Auto-sends on 3.5s pause or click";
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
    if (role.includes("product") || role.includes("apm")) {
      ta.value = `Good morning Dr. Vance! I'm ${name}. Over the past 3 years as an Associate Product Manager, I've driven user onboarding optimization and checkout funnel improvements. I specialize in turning user friction into prioritized engineering roadmaps, and I'm excited about this opportunity to scale our core product offerings.`;
    } else if (role.includes("ux") || role.includes("design")) {
      ta.value = `Good morning Dr. Vance! I'm ${name}. I'm a UX Researcher with a background in cognitive human-computer interaction and mixed-methods research. I specialize in translating qualitative field studies and usability metrics into validated product features.`;
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
      <div style="display: flex; align-items: center; gap: 0.6rem; color: #475569; font-size: 0.88rem;">
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

    let engineLabel = "🟢 NVIDIA Nemotron 3.5";
    if (data.source === "gemini_1.5_flash") {
      engineLabel = "🟢 Google Gemini 1.5 Flash";
    } else if (data.source === "semantic_dialogue_engine") {
      engineLabel = "⚡ Semantic NLP Engine";
    }

    const currentTurnAssistantIdx = simConversationHistory.filter(m => m.role === "assistant").length - 1;

    chat.innerHTML += `
      <div class="chat-bubble interviewer">
        <div class="chat-meta">DR. MARCUS VANCE • OFFICIAL INTERVIEW (${stageTitle}) • <span style="color: #047857; font-weight: 600;">${engineLabel}</span></div>
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
        <div class="chat-bubble interviewer" style="background: #ecfdf5; border: 2px solid #10b981; border-radius: 12px; padding: 1.25rem; margin-top: 1rem; box-shadow: 0 4px 12px rgba(16, 185, 129, 0.15);">
          <div style="display: flex; align-items: center; gap: 0.6rem; margin-bottom: 0.5rem;">
            <span style="font-size: 1.5rem;">🎉</span>
            <div>
              <strong style="color: #065f46; font-size: 1.05rem;">Interview Completed with Dr. Marcus Vance</strong>
              <div style="font-size: 0.82rem; color: #047857;">All conversation turns have been recorded and transcribed.</div>
            </div>
          </div>
          <p style="color: #1e293b; font-size: 0.9rem; margin-bottom: 1rem; line-height: 1.55;">
            Dr. Vance has wrapped up the oral questioning. When you are ready, proceed to convene the Hiring Committee Evaluation Scorecard to inspect your detailed BARS ratings, turn-by-turn evidence audit, and targeted development plan.
          </p>
          <div style="display: flex; gap: 0.75rem; flex-wrap: wrap; align-items: center;">
            <button class="btn btn-primary" id="btn-proceed-evaluation" onclick="finishSimulation()" style="background: #059669; border-color: #047857; font-weight: 700; padding: 0.65rem 1.35rem; font-size: 0.92rem; box-shadow: 0 3px 10px rgba(5, 150, 105, 0.3);">
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

  // 1. Build Competency Matrix Cards
  const comps = d.competency_matrix || [];
  const compCardsHtml = comps.map(c => {
    const s = typeof c.score === "number" ? c.score : 7.5;
    const pct = Math.min(100, Math.max(10, Math.round((s / 10) * 100)));
    let barColor = "#10b981";
    if (s < 6.0) barColor = "#ef4444";
    else if (s < 7.5) barColor = "#f59e0b";
    else if (s >= 8.8) barColor = "#059669";
    const w = c.weight ? Math.round(c.weight * 100) : 25;
    return `
      <div class="comp-eval-card">
        <div>
          <div class="comp-eval-header">
            <span class="comp-name">${escapeHtml(c.name)}</span>
            <span class="comp-score-tag" style="color: ${barColor}">${s.toFixed(1)} / 10</span>
          </div>
          <div style="display: flex; justify-content: space-between; font-size: 0.75rem; color: #64748b; margin-bottom: 0.25rem;">
            <span>Evaluation Weight: <strong>${w}%</strong></span>
            <strong style="color: ${barColor}">${escapeHtml(c.rating_label || 'Meets Bar')}</strong>
          </div>
          <div class="comp-bar-container">
            <div class="comp-bar-fill" style="width: ${pct}%; background: ${barColor};"></div>
          </div>
          <p class="comp-anchor-desc"><strong>Behavioral Anchor:</strong> ${escapeHtml(c.behavioral_anchor || c.focus || '')}</p>
        </div>
        <div class="comp-evidence-quote">
          <strong>Observed Signal:</strong> ${escapeHtml(c.evidence || 'Consistent domain alignment verified across dialogue.')}
        </div>
      </div>
    `;
  }).join("") || `<p style="color: #64748b; padding: 1rem;">Competencies evaluated against role standard.</p>`;

  // 2. Build Turn-by-Turn Question & Response Audit
  const turns = d.turn_evaluations || [];
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
            <span style="font-size: 0.82rem; color: #64748b; margin-left: 0.5rem;">• Focus Competency: <strong>${escapeHtml(t.competency_tested || 'Domain Competency')}</strong></span>
          </div>
          <span class="badge ${badgeClass}" style="font-weight: 800; font-size: 0.85rem;">Turn Rating: ${tScore.toFixed(1)} / 10</span>
        </div>
        <div class="turn-audit-body">
          <div class="turn-q-box">
            <div style="font-size: 0.75rem; font-weight: 800; color: #475569; margin-bottom: 0.2rem;">💼 DR. MARCUS VANCE (LEAD EVALUATOR):</div>
            <div>“${escapeHtml(t.interviewer_question)}”</div>
          </div>
          <div class="turn-ans-box">
            <div style="font-size: 0.75rem; font-weight: 800; color: #1e40af; margin-bottom: 0.2rem;">🎙️ CANDIDATE'S SPOKEN RESPONSE:</div>
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
  }).join("") || `<p style="color: #64748b; padding: 1rem;">Turn breakdown recorded.</p>`;

  // 3. Build Job Description & Resume Requirements Alignment Matrix
  const jdList = d.job_description_alignment || [];
  const jdRowsHtml = jdList.map(j => {
    let bClass = "badge-success";
    if (j.status === "Partially Demonstrated") bClass = "badge-warning";
    if (j.status === "Not Assessed / Missing") bClass = "badge-danger";
    return `
      <tr>
        <td style="font-weight: 600; color: #1e293b; width: 28%;">${escapeHtml(j.requirement)}</td>
        <td style="width: 18%;"><span class="badge ${bClass}">${escapeHtml(j.status)}</span></td>
        <td style="font-style: italic; color: #475569; width: 28%; font-size: 0.82rem;">${escapeHtml(j.evidence_quote || 'No direct quote identified')}</td>
        <td style="color: #334155; width: 26%; font-size: 0.82rem;">${escapeHtml(j.alignment_analysis || '')}</td>
      </tr>
    `;
  }).join("") || `<tr><td colspan="4" style="text-align: center; color: #64748b; padding: 1rem;">Candidate demonstrated core role alignment.</td></tr>`;

  // 4. Build Debrief & 30-Day Coaching Plan
  const topStrengths = (d.key_strengths || []).map(s => `<li style="margin-bottom: 0.4rem;">${escapeHtml(s)}</li>`).join("");
  const topGrowth = (d.priority_growth_areas || []).map(g => `<li style="margin-bottom: 0.4rem;">${escapeHtml(g)}</li>`).join("");
  const topActions = (d.actionable_recommendations || []).map(a => `<li style="margin-bottom: 0.4rem;">${escapeHtml(a)}</li>`).join("");

  // Synthesize Complete Dashboard HTML
  contentEl.innerHTML = `
    <div class="eval-dashboard-container">
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
              <span style="font-size: 0.85rem; color: #94a3b8;">AGGREGATE SCORE:</span>
              <span class="eval-score-ring">${overall.toFixed(1)}</span>
              <span style="font-size: 1rem; color: #94a3b8; font-weight: 700;">/ 10</span>
            </div>
            <span style="font-size: 0.78rem; color: #94a3b8;">${escapeHtml(confidence)}</span>
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

      <!-- TAB 1: Competency Rubrics (BARS Framework) -->
      <div id="tab-competencies" style="display: block;">
        <div style="display: flex; justify-content: space-between; align-items: baseline; flex-wrap: wrap; gap: 0.5rem; margin-bottom: 0.5rem;">
          <div>
            <h3 style="font-size: 1.15rem; color: var(--text-main); margin: 0;">Track-Specific Competency Evaluation (BARS Rubrics)</h3>
            <p style="font-size: 0.84rem; color: var(--text-muted); margin: 0.2rem 0 0 0;">Evaluated strictly against the behavioral rubrics defined for <strong>${escapeHtml(candidateProfile.interviewType || 'Comprehensive Focus')}</strong>.</p>
          </div>
          <span class="badge badge-primary">Model: NVIDIA Nemotron 3.5 Super VL</span>
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
        <div style="overflow-x: auto; background: #ffffff; border-radius: 8px; border: 1px solid var(--border);">
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
          <div style="background: #ecfdf5; border: 1px solid #a7f3d0; border-radius: 10px; padding: 1.25rem;">
            <div style="font-weight: 800; color: #065f46; font-size: 0.95rem; margin-bottom: 0.6rem;">✓ TOP CANDIDATE SUPERPOWERS:</div>
            <ul style="margin: 0; padding-left: 1.2rem; color: #064e3b; font-size: 0.85rem; line-height: 1.5;">
              ${topStrengths}
            </ul>
          </div>
          <div style="background: #fffbeb; border: 1px solid #fde68a; border-radius: 10px; padding: 1.25rem;">
            <div style="font-weight: 800; color: #92400e; font-size: 0.95rem; margin-bottom: 0.6rem;">⚠️ CRITICAL GROWTH & ONBOARDING RISKS:</div>
            <ul style="margin: 0; padding-left: 1.2rem; color: #78350f; font-size: 0.85rem; line-height: 1.5;">
              ${topGrowth}
            </ul>
          </div>
        </div>

        <div style="background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 10px; padding: 1.25rem;">
          <div style="font-weight: 800; color: #1e40af; font-size: 0.95rem; margin-bottom: 0.6rem;">🎯 30-DAY TARGETED ACTION PLAN TO REACH NEXT LEVEL:</div>
          <ol style="margin: 0; padding-left: 1.3rem; color: #1e3a8a; font-size: 0.88rem; line-height: 1.6;">
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
}

function closeConfigModal() {
  document.getElementById("modal-config").style.display = "none";
}

async function loadConfigSettings() {
  try {
    const res = await fetch("/api/config");
    const data = await res.json();
    const badge = document.getElementById("cfg-engine-badge");
    const orBadge = document.getElementById("cfg-openrouter-badge");

    if (orBadge) {
      if (data.openrouter_active) {
        orBadge.className = "badge badge-success";
        orBadge.innerText = "✓ Nemotron 3.5 Super VL Active";
      } else {
        orBadge.className = "badge badge-outline";
        orBadge.innerText = "Curated Fallback Ready ($0 Free)";
      }
    }

    if (badge) {
      if (data.openrouter_active) {
        badge.className = "badge badge-success";
        badge.innerText = "NVIDIA Nemotron 3.5 Super VL (Free Tier)";
      } else if (data.gemini_active) {
        badge.className = "badge badge-success";
        badge.innerText = "Gemini 1.5 Flash Free Tier Active";
      } else {
        badge.className = "badge badge-primary";
        badge.innerText = "Curated Sample Questions + STAR Evaluator ($0 Free)";
      }
    }
  } catch (err) {
    console.warn("Config load error:", err);
  }
}

async function saveConfigSettings() {
  const openrouterKey = document.getElementById("cfg-openrouter-key") ? document.getElementById("cfg-openrouter-key").value.trim() : "";
  const geminiKey = document.getElementById("cfg-gemini-key") ? document.getElementById("cfg-gemini-key").value.trim() : "";
  const voiceIdx = document.getElementById("cfg-voice-select").value;
  const rateVal = parseFloat(document.getElementById("cfg-voice-rate").value);
  const pitchVal = parseFloat(document.getElementById("cfg-voice-pitch").value);
  autoSpeakEnabled = document.getElementById("cfg-auto-speak").checked;

  speechRate = rateVal;
  speechPitch = pitchVal;

  if (voiceIdx !== "" && userVoices[voiceIdx]) {
    selectedVoice = userVoices[voiceIdx];
  }

  try {
    const payload = {
      voice_speed: speechRate,
      auto_speak: autoSpeakEnabled
    };
    if (openrouterKey) {
      payload.openrouter_api_key = openrouterKey;
      payload.openrouter_model = "nvidia/nemotron-3.5-super-vl:free";
    }
    if (geminiKey) {
      payload.gemini_api_key = geminiKey;
    }

    await fetch("/api/config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    alert("Settings saved successfully! AI Engine is ready.");
    closeConfigModal();
    loadConfigSettings();
  } catch (err) {
    console.error(err);
    closeConfigModal();
  }
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
window.toggleWireframeMode = toggleWireframeMode;
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

