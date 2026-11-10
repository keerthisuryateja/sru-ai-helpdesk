/* ==========================================================================
   SR University Helpdesk - Voice-First Client Application
   ========================================================================== */

let currentSessionId = localStorage.getItem("sru_session_id") || "sru_" + Date.now().toString(36);
localStorage.setItem("sru_session_id", currentSessionId);

let isRecording = false;
let mediaRecorder = null;
let audioChunks = [];
let webSpeechRecognition = null;
let recognizedLiveTranscript = "";

// DOM Elements
const chatHistoryEl = document.getElementById("chatHistory");
const emptyStateEl = document.getElementById("emptyState");
const textInputEl = document.getElementById("textInput");
const orbContainer = document.getElementById("orbContainer");
const voiceStatusPill = document.getElementById("voiceStatusPill");
const voiceStatusText = document.getElementById("voiceStatusText");
const ttsAudioPlayer = document.getElementById("ttsAudioPlayer");
const themeToggleBtn = document.getElementById("themeToggleBtn");
const sessionIdDisplay = document.getElementById("sessionIdDisplay");
const newChatBtn = document.getElementById("newChatBtn");
const activeProviderBadge = document.getElementById("activeProviderBadge");
const configBtn = document.getElementById("configBtn");
const configModal = document.getElementById("configModal");
const groqKeyInput = document.getElementById("groqKeyInput");
const currentEngineText = document.getElementById("currentEngineText");

sessionIdDisplay.textContent = currentSessionId.slice(-8);

// ==========================================================================
// Theme (Dark / Light)
// ==========================================================================
function initTheme() {
  const savedTheme = localStorage.getItem("sru_theme") || "light";
  document.documentElement.setAttribute("data-theme", savedTheme);
  updateThemeIcon(savedTheme);
}

function toggleTheme() {
  const current = document.documentElement.getAttribute("data-theme") || "light";
  const next = current === "light" ? "dark" : "light";
  document.documentElement.setAttribute("data-theme", next);
  localStorage.setItem("sru_theme", next);
  updateThemeIcon(next);
}

function updateThemeIcon(theme) {
  if (!themeToggleBtn) return;
  if (theme === "dark") {
    themeToggleBtn.innerHTML = `
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/>
      </svg>`;
  } else {
    themeToggleBtn.innerHTML = `
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="12" cy="12" r="4"/>
        <path d="M12 2v2"/><path d="M12 20v2"/><path d="m4.93 4.93 1.41 1.41"/><path d="m17.66 17.66 1.41 1.41"/>
        <path d="M2 12h2"/><path d="M20 12h2"/><path d="m6.34 17.66-1.41 1.41"/><path d="m19.07 4.93-1.41 1.41"/>
      </svg>`;
  }
}

themeToggleBtn.addEventListener("click", toggleTheme);
initTheme();

// ==========================================================================
// AI Engine Configuration (Groq & Providers)
// ==========================================================================
async function checkEngineConfig() {
  try {
    const res = await fetch("/api/config");
    if (!res.ok) return;
    const data = await res.json();
    if (activeProviderBadge) {
      activeProviderBadge.textContent = data.active_provider;
    }
    if (currentEngineText) {
      currentEngineText.textContent = `${data.active_provider} (${data.has_groq ? "Groq Key Configured" : "Local Fallback Ready"})`;
    }
  } catch (e) {
    console.log("Config fetch note:", e);
  }
}

if (configBtn) {
  configBtn.addEventListener("click", () => {
    configModal.classList.add("active");
    checkEngineConfig();
  });
}

function closeConfigModal() {
  configModal.classList.remove("active");
}

async function saveGroqKey(e) {
  e.preventDefault();
  const key = groqKeyInput.value.trim();
  try {
    const res = await fetch("/api/config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ groq_api_key: key })
    });
    const data = await res.json();
    showToast(data.message || "Key saved.");
    closeConfigModal();
    checkEngineConfig();
  } catch (err) {
    showToast("Failed to update configuration", "error");
  }
}

// ==========================================================================
// Session Handling & History
// ==========================================================================
newChatBtn.addEventListener("click", () => {
  currentSessionId = "sru_" + Date.now().toString(36);
  localStorage.setItem("sru_session_id", currentSessionId);
  sessionIdDisplay.textContent = currentSessionId.slice(-8);
  chatHistoryEl.innerHTML = "";
  if (emptyStateEl) {
    chatHistoryEl.appendChild(emptyStateEl);
    emptyStateEl.style.display = "block";
  }
  setOrbState("idle", "Tap Orb to Speak");
  showToast("Started a new dialogue session.");
});

async function loadSessionHistory() {
  try {
    const res = await fetch(`/api/chat/history/${currentSessionId}`);
    if (!res.ok) return;
    const messages = await res.json();
    if (messages.length > 0 && emptyStateEl) {
      emptyStateEl.style.display = "none";
    }
    messages.forEach((msg) => {
      appendMessage(msg.role, msg.content, msg.matched_sources, false);
    });
  } catch (err) {
    console.error("Failed to load history:", err);
  }
}

// ==========================================================================
// Voice Orb States & Animations
// ==========================================================================
function setOrbState(state, statusMessage) {
  orbContainer.classList.remove("recording", "speaking", "thinking");
  voiceStatusPill.classList.remove("recording");

  if (state === "recording") {
    orbContainer.classList.add("recording");
    voiceStatusPill.classList.add("recording");
  } else if (state === "speaking") {
    orbContainer.classList.add("speaking");
  }

  if (statusMessage) {
    voiceStatusText.textContent = statusMessage;
  }
}

ttsAudioPlayer.addEventListener("play", () => {
  setOrbState("speaking", "SRU AI Speaking...");
});

ttsAudioPlayer.addEventListener("ended", () => {
  setOrbState("idle", "Tap Orb to Speak");
});

ttsAudioPlayer.addEventListener("pause", () => {
  setOrbState("idle", "Tap Orb to Speak");
});

// ==========================================================================
// Chat UI Rendering
// ==========================================================================
function appendMessage(role, text, sources = [], playAudioNow = false, audioUri = "") {
  if (emptyStateEl && emptyStateEl.style.display !== "none") {
    emptyStateEl.style.display = "none";
  }

  const row = document.createElement("div");
  row.className = `message-row ${role}`;

  const label = document.createElement("div");
  label.className = "message-label";
  label.textContent = role === "user" ? "You" : "SRU AI Assistant";
  row.appendChild(label);

  const bubble = document.createElement("div");
  bubble.className = "message-bubble";
  bubble.textContent = text;

  // Add source tags & details if available
  if (role === "assistant" && sources && sources.length > 0) {
    const srcBox = document.createElement("div");
    srcBox.className = "sources-accordion";

    sources.forEach((s) => {
      const tag = document.createElement("span");
      tag.className = "badge";

      const sType = s.type || (s.emp_id ? "Faculty" : (s.role ? "Administrative" : (s.club_name ? "Club" : "Website")));
      if (sType.includes("Faculty")) tag.classList.add("badge-blue");
      else if (sType.includes("Admin")) tag.classList.add("badge-amber");
      else if (sType.includes("Club")) tag.classList.add("badge-purple");
      else tag.classList.add("badge-green");

      tag.textContent = s.title || sType;
      srcBox.appendChild(tag);
    });
    bubble.appendChild(srcBox);
  }

  // Audio replay button for assistant response
  if (role === "assistant" && audioUri) {
    const audioBar = document.createElement("div");
    audioBar.className = "message-audio-action";

    const replayBtn = document.createElement("button");
    replayBtn.className = "btn btn-outline btn-sm";
    replayBtn.innerHTML = `
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M15.54 8.46a5 5 0 0 1 0 7.07"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14"/></svg>
      Play Kokoro Voice
    `;
    replayBtn.onclick = () => playAudio(audioUri);
    audioBar.appendChild(replayBtn);
    bubble.appendChild(audioBar);
  }

  row.appendChild(bubble);
  chatHistoryEl.appendChild(row);
  chatHistoryEl.scrollTop = chatHistoryEl.scrollHeight;

  if (playAudioNow && audioUri) {
    playAudio(audioUri);
  }
}

function playAudio(audioUri) {
  if (!audioUri) return;
  ttsAudioPlayer.src = audioUri;
  ttsAudioPlayer.play().catch((e) => console.log("Audio playback note:", e));
}

// ==========================================================================
// Query Submissions (Text & Voice)
// ==========================================================================
async function submitTextQuery(query) {
  if (!query || !query.trim()) return;
  const cleanQuery = query.trim();
  textInputEl.value = "";

  appendMessage("user", cleanQuery);
  setOrbState("idle", "Searching university records...");

  // Show typing indicator
  const loadingRow = document.createElement("div");
  loadingRow.className = "message-row assistant";
  loadingRow.id = "tempLoading";
  loadingRow.innerHTML = `
    <div class="message-label">SRU AI Assistant</div>
    <div class="message-bubble" style="color: var(--text-secondary);">
      Consulting university database records...
    </div>
  `;
  chatHistoryEl.appendChild(loadingRow);
  chatHistoryEl.scrollTop = chatHistoryEl.scrollHeight;

  try {
    const res = await fetch("/api/chat/text", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        query: cleanQuery,
        session_id: currentSessionId,
        synthesize_voice: true
      })
    });

    const data = await res.json();
    loadingRow.remove();

    if (res.ok) {
      appendMessage("assistant", data.text, data.sources, true, data.audio);
    } else {
      setOrbState("idle", "Tap Orb to Speak");
      appendMessage("assistant", "Error: " + (data.detail || "Server error"));
    }
  } catch (err) {
    loadingRow.remove();
    setOrbState("idle", "Tap Orb to Speak");
    appendMessage("assistant", "Network error connecting to university server.");
    console.error(err);
  }
}

function handleTextSubmit(e) {
  e.preventDefault();
  submitTextQuery(textInputEl.value);
}

function askQuickPrompt(promptText) {
  submitTextQuery(promptText);
}

// ==========================================================================
// Voice Orb Interaction (Recording & Transcription)
// ==========================================================================
function toggleVoiceInteraction() {
  if (isRecording) {
    stopRecording();
  } else {
    startRecording();
  }
}

async function startRecording() {
  audioChunks = [];
  recognizedLiveTranscript = "";

  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    mediaRecorder = new MediaRecorder(stream);

    mediaRecorder.ondataavailable = (e) => {
      if (e.data.size > 0) audioChunks.push(e.data);
    };

    mediaRecorder.onstop = async () => {
      stream.getTracks().forEach((track) => track.stop());
      const audioBlob = new Blob(audioChunks, { type: "audio/wav" });
      await processRecordedAudio(audioBlob);
    };

    mediaRecorder.start();
    isRecording = true;
    setOrbState("recording", "Listening... Speak your query now.");

    // Web Speech API for instant live recognition
    const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (SpeechRec) {
      webSpeechRecognition = new SpeechRec();
      webSpeechRecognition.continuous = false;
      webSpeechRecognition.interimResults = true;
      webSpeechRecognition.lang = "en-US";

      webSpeechRecognition.onresult = (event) => {
        const transcript = Array.from(event.results)
          .map((res) => res[0].transcript)
          .join("");
        recognizedLiveTranscript = transcript;
        if (transcript) {
          voiceStatusText.textContent = `"${transcript}"`;
        }
      };

      webSpeechRecognition.onerror = (e) => {
        console.log("WebSpeech note:", e.error);
      };

      webSpeechRecognition.start();
    }
  } catch (err) {
    console.error("Microphone error:", err);
    showToast("Microphone access unavailable. You can use the text box below.", "error");
    setOrbState("idle", "Tap Orb to Speak");
    isRecording = false;
  }
}

function stopRecording() {
  if (mediaRecorder && mediaRecorder.state !== "inactive") {
    mediaRecorder.stop();
  }
  if (webSpeechRecognition) {
    try { webSpeechRecognition.stop(); } catch (e) {}
  }
  isRecording = false;
  setOrbState("idle", "Processing speech...");
}

async function processRecordedAudio(audioBlob) {
  if (recognizedLiveTranscript && recognizedLiveTranscript.trim()) {
    submitTextQuery(recognizedLiveTranscript.trim());
    return;
  }

  const formData = new FormData();
  formData.append("audio", audioBlob, "query.wav");
  formData.append("session_id", currentSessionId);

  const loadingRow = document.createElement("div");
  loadingRow.className = "message-row assistant";
  loadingRow.innerHTML = `
    <div class="message-label">SRU AI Assistant</div>
    <div class="message-bubble" style="color: var(--text-secondary);">
      Processing voice input...
    </div>
  `;
  chatHistoryEl.appendChild(loadingRow);
  chatHistoryEl.scrollTop = chatHistoryEl.scrollHeight;

  try {
    const res = await fetch("/api/chat/audio", {
      method: "POST",
      body: formData
    });
    const data = await res.json();
    loadingRow.remove();

    if (res.ok) {
      if (data.query) {
        appendMessage("user", data.query);
      }
      appendMessage("assistant", data.text, data.sources, true, data.audio);
    } else {
      setOrbState("idle", "Tap Orb to Speak");
      appendMessage("assistant", "Voice transcription note: " + (data.detail || "Unable to transcribe"));
    }
  } catch (err) {
    loadingRow.remove();
    setOrbState("idle", "Tap Orb to Speak");
    appendMessage("assistant", "Network error processing voice audio.");
    console.error(err);
  }
}

// ==========================================================================
// Toast Utility
// ==========================================================================
function showToast(message, type = "info") {
  const container = document.getElementById("toastContainer");
  if (!container) return;

  const toast = document.createElement("div");
  toast.className = "toast";
  toast.innerHTML = `
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
    <span>${message}</span>
  `;
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = "0";
    setTimeout(() => toast.remove(), 300);
  }, 3500);
}

// Initial setup
checkEngineConfig();
loadSessionHistory();
