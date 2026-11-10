import React, { useState, useEffect, useRef } from 'react';
import {
  Mic,
  Send,
  Volume2,
  VolumeX,
  RefreshCw,
  Sun,
  Moon,
  Database,
  Bot,
  Plus,
  Edit2,
  Trash2,
  Search,
  X,
  CheckCircle2,
  AlertCircle,
  Info,
  Calendar,
  Lock,
  LogOut,
  KeyRound,
  Eye,
  EyeOff,
  ShieldCheck,
  Copy,
  Check,
  Sparkles,
  ExternalLink,
  Mail,
  GraduationCap,
  Building,
  Coins,
  PartyPopper,
  Radio
} from 'lucide-react';
import ThreeOrb from './ThreeOrb';
import { sound } from './audioFeedback';

const PROMPT_CATEGORIES = [
  { id: 'featured', label: 'Featured', icon: Sparkles },
  { id: 'faculty', label: 'Faculty & Offices', icon: GraduationCap },
  { id: 'campus', label: 'Campus & Hostels', icon: Building },
  { id: 'coins', label: 'SSM Coins & Fees', icon: Coins },
  { id: 'clubs', label: 'Fests & Clubs', icon: PartyPopper }
];

const PROMPTS_BY_CATEGORY = {
  featured: [
    "How to earn Alpha and Sigma coins in SSM?",
    "What can I redeem SSM coins for?",
    "What are the hostel fees and room options?",
    "What is the minimum attendance requirement?",
    "Cabin room and email of buses in-charge",
    "Official tuition fee payment link"
  ],
  faculty: [
    "Who is the Vice Chancellor of SR University?",
    "Who is Dr. Sridhar Chinthala?",
    "Who is the Dean of Computer Science?",
    "Where is the Controller of Examinations located?",
    "How to reach the Registrar Office?"
  ],
  campus: [
    "What are the hostel out-pass rules and curfew timings?",
    "What are the Central Library operating hours?",
    "What sports and gym facilities are open to students?",
    "Where is the campus Health and Medical Centre located?",
    "What is the highest placement package achieved?"
  ],
  coins: [
    "What causes penalty coin deductions in SSM?",
    "What are the SSM badges and leaderboard levels?",
    "How do students redeem coins for stationary and cafeteria?",
    "What merit scholarships are offered at SR University?",
    "What is the process to apply for fee concession?"
  ],
  clubs: [
    "Tell me about Google Developer Student Club (GDSC)",
    "What technical and robotics clubs exist at SRU?",
    "What are the major annual cultural fests (Spark)?",
    "How do I join the coding and AI hackathon team?",
    "How do students register a new club on campus?"
  ]
};


export default function App() {
  const [activeView, setActiveView] = useState(() => {
    if (typeof window !== 'undefined') {
      return window.location.pathname.startsWith('/admin') ? 'admin' : 'chat';
    }
    return 'chat';
  });

  useEffect(() => {
    const handleLocationChange = () => {
      if (typeof window !== 'undefined') {
        setActiveView(window.location.pathname.startsWith('/admin') ? 'admin' : 'chat');
      }
    };
    window.addEventListener('popstate', handleLocationChange);
    return () => window.removeEventListener('popstate', handleLocationChange);
  }, []);
  const [theme, setTheme] = useState(() => localStorage.getItem('sru_theme') || 'light');
  const [sessionId, setSessionId] = useState(() => localStorage.getItem('sru_session_id') || 'sru_' + Date.now().toString(36));
  const [messages, setMessages] = useState([]);
  const [inputQuery, setInputQuery] = useState('');
  const [orbState, setOrbState] = useState('idle'); // 'idle' | 'recording' | 'thinking' | 'speaking'
  const [statusText, setStatusText] = useState('Tap Orb to Speak');

  // Audio player & recording refs
  const audioPlayerRef = useRef(new Audio());
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const chatScrollRef = useRef(null);
  const recognitionRef = useRef(null);
  const voiceConversationRef = useRef(false); // Track if in voice conversation mode

  const silenceTimerRef = useRef(null);

  // Audio FX & UI Enhancements
  const [soundFxEnabled, setSoundFxEnabled] = useState(() => localStorage.getItem('sru_sound_fx') !== 'false');
  const [activePromptCategory, setActivePromptCategory] = useState('featured');
  const [copiedMsgId, setCopiedMsgId] = useState(null);
  const [recordingSeconds, setRecordingSeconds] = useState(0);
  const inputRef = useRef(null);

  useEffect(() => {
    sound.enabled = soundFxEnabled;
  }, [soundFxEnabled]);

  // Live recording seconds counter
  useEffect(() => {
    let interval = null;
    if (orbState === 'recording') {
      setRecordingSeconds(0);
      interval = setInterval(() => {
        setRecordingSeconds((prev) => prev + 1);
      }, 1000);
    } else {
      setRecordingSeconds(0);
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [orbState]);

  // Unified Portal Authentication (Persisted in localStorage)
  const [authToken, setAuthToken] = useState(() => localStorage.getItem('sru_auth_token') || localStorage.getItem('sru_admin_token') || '');
  const [authRole, setAuthRole] = useState(() => localStorage.getItem('sru_auth_role') || (localStorage.getItem('sru_admin_token') ? 'admin' : '')); // 'user' | 'admin'
  const [loginRoleTab, setLoginRoleTab] = useState('user'); // 'user' | 'admin'
  const [authPasswordInput, setAuthPasswordInput] = useState('');
  const [authLoading, setAuthLoading] = useState(false);
  const [authError, setAuthError] = useState('');
  const [showAuthPassword, setShowAuthPassword] = useState(false);

  // Admin Data Management State
  const [adminTab, setAdminTab] = useState('faculty');
  const [adminRecords, setAdminRecords] = useState([]);
  const [adminCounts, setAdminCounts] = useState({ faculty: 0, administrative: 0, clubs: 0, websites: 0 });
  const [searchFilter, setSearchFilter] = useState('');
  const [crudModalOpen, setCrudModalOpen] = useState(false);
  const [editingRecord, setEditingRecord] = useState(null);
  const [formData, setFormData] = useState({});

  const handleUnifiedLogin = async (e) => {
    if (e) e.preventDefault();
    if (!authPasswordInput.trim()) return;
    setAuthLoading(true);
    setAuthError('');
    try {
      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          password: authPasswordInput.trim(),
          role: loginRoleTab
        })
      });
      const data = await res.json();
      if (res.ok && data.token) {
        localStorage.setItem('sru_auth_token', data.token);
        localStorage.setItem('sru_auth_role', data.role);
        if (data.role === 'admin') {
          localStorage.setItem('sru_admin_token', data.token);
        }
        setAuthToken(data.token);
        setAuthRole(data.role);
        setAuthPasswordInput('');
        setAuthError('');
        if (data.role === 'admin' && window.location.pathname.startsWith('/admin')) {
          setActiveView('admin');
        } else {
          setActiveView('chat');
        }
      } else {
        setAuthError(data.detail || 'Incorrect password for selected portal.');
      }
    } catch (err) {
      setAuthError('Unable to connect to authentication service.');
    } finally {
      setAuthLoading(false);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('sru_auth_token');
    localStorage.removeItem('sru_auth_role');
    localStorage.removeItem('sru_admin_token');
    localStorage.removeItem('sru_voice_token');
    setAuthToken('');
    setAuthRole('');
    setAuthPasswordInput('');
    setAuthError('');
    setActiveView('chat');
    // Stop any active audio
    audioPlayerRef.current.pause();
    audioPlayerRef.current.currentTime = 0;
    if (window.speechSynthesis) window.speechSynthesis.cancel();
    setOrbState('idle');
    setStatusText('Tap Orb to Speak');
  };

  const [continuousMode, setContinuousMode] = useState(() => localStorage.getItem('sru_continuous_mode') === 'true');
  const continuousModeRef = useRef(continuousMode);
  const startVoiceRecordingRef = useRef(null);
  const isTogglingVoiceRef = useRef(false);
  const userStoppedRef = useRef(false);

  // In-app Delete Confirmation Modal State
  const [deleteModal, setDeleteModal] = useState({
    open: false,
    recordId: null,
    recordName: '',
    tab: 'faculty'
  });
  const [isDeleting, setIsDeleting] = useState(false);

  // No-op toast helper so no intrusive popup notifications appear
  const addToast = () => {};

  const toggleTheme = () => {
    setTheme(theme === 'light' ? 'dark' : 'light');
  };

  const handleContinuousToggle = (enabled) => {
    setContinuousMode(enabled);
    voiceConversationRef.current = enabled;
  };

  // Theme synchronization
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('sru_theme', theme);
  }, [theme]);

  // Sync continuousMode ref and storage
  useEffect(() => {
    continuousModeRef.current = continuousMode;
    localStorage.setItem('sru_continuous_mode', continuousMode);
  }, [continuousMode]);

  // Initial load
  useEffect(() => {
    fetchHistory(sessionId);
    fetchAdminCounts();

    const player = audioPlayerRef.current;
    player.onplay = () => {
      setOrbState('speaking');
      setStatusText('Speaking...');
    };
    player.onended = () => {
      // Auto-continue listening only if user explicitly turned on continuous mode
      if (continuousModeRef.current) {
        setOrbState('idle');
        setStatusText('Listening again...');
        setTimeout(() => {
          if (continuousModeRef.current && audioPlayerRef.current.paused) {
            startVoiceRecordingRef.current?.();
          }
        }, 350);
      } else {
        setOrbState('idle');
        setStatusText('Tap Orb to Speak');
      }
    };
    player.onpause = () => {
      setOrbState('idle');
      setStatusText('Tap Orb to Speak');
    };
  }, []);

  // Auto-scroll chat stream
  useEffect(() => {
    if (chatScrollRef.current) {
      chatScrollRef.current.scrollTop = chatScrollRef.current.scrollHeight;
    }
  }, [messages, orbState]);

  // Fetch admin records when switching tabs in admin view
  useEffect(() => {
    if (activeView === 'admin') {
      fetchAdminRecords(adminTab);
      fetchAdminCounts();
    }
  }, [activeView, adminTab]);

  // Verify authentication token validity on load
  useEffect(() => {
    if (authToken) {
      fetch('/api/auth/verify', {
        headers: { Authorization: `Bearer ${authToken}` }
      })
        .then((res) => {
          if (!res.ok) {
            handleLogout();
          } else {
            res.json().then((data) => {
              if (data.role && data.role !== authRole) {
                setAuthRole(data.role);
                localStorage.setItem('sru_auth_role', data.role);
              }
            });
          }
        })
        .catch(() => {});
    }
  }, [authToken]);

  // =========================================================================
  // API Calls & Chat Logic (Instant Text + Async Audio)
  // =========================================================================

  const fetchHistory = async (sess) => {
    try {
      const res = await fetch(`/api/chat/history/${sess}`);
      if (res.ok) {
        const data = await res.json();
        setMessages(data);
      }
    } catch (e) {
      console.error(e);
    }
  };

  const startNewDialogue = () => {
    const newId = 'sru_' + Date.now().toString(36);
    setSessionId(newId);
    localStorage.setItem('sru_session_id', newId);
    setMessages([]);
    setOrbState('idle');
    setStatusText('Tap Orb to Speak');
    voiceConversationRef.current = false;
    // Stop any playing audio
    audioPlayerRef.current.pause();
    audioPlayerRef.current.currentTime = 0;
    addToast('Dialogue context reset. Started fresh session.', 'info', 'Session Reset');
  };

  const playVoiceAudio = (audioUri) => {
    if (!audioUri) return;
    const player = audioPlayerRef.current;
    player.src = audioUri;
    player.play().catch((err) => console.log('Audio playback note:', err));
  };

  const speakWithBrowserSpeech = (text) => {
    if (!window.speechSynthesis) return false;
    try {
      window.speechSynthesis.cancel();
      const cleanSpeech = text
        .replace(/https?:\/\/[^\s]+/g, 'the link on screen')
        .replace(/[*_#`~]/g, '')
        .replace(/[()]/g, '')
        .trim();
      if (!cleanSpeech) return false;

      const utterance = new SpeechSynthesisUtterance(cleanSpeech);
      utterance.rate = 1.05;
      utterance.pitch = 1.0;

      const voices = window.speechSynthesis.getVoices();
      const naturalVoice = voices.find(
        (v) => (v.name.includes('Natural') || v.name.includes('Google') || v.name.includes('Aria') || v.name.includes('Zira') || v.name.includes('Samantha')) && v.lang.startsWith('en')
      ) || voices.find((v) => v.lang.startsWith('en'));
      if (naturalVoice) utterance.voice = naturalVoice;

      setOrbState('speaking');
      setStatusText('Speaking...');

      utterance.onend = () => {
        setOrbState('idle');
        if (continuousModeRef.current) {
          setStatusText('Listening again...');
          setTimeout(() => {
            if (continuousModeRef.current && (audioPlayerRef.current?.paused ?? true)) {
              startVoiceRecordingRef.current?.();
            }
          }, 350);
        } else {
          setStatusText('Tap Orb to Speak');
        }
      };

      utterance.onerror = () => {
        setOrbState('idle');
        setStatusText('Tap Orb to Speak');
      };

      window.speechSynthesis.speak(utterance);
      return true;
    } catch (e) {
      console.log('Browser speech synthesis error:', e);
      return false;
    }
  };

  const fetchAndPlayTts = async (text, msgId) => {
    try {
      const headers = authToken ? { Authorization: `Bearer ${authToken}` } : {};
      const res = await fetch(`/api/tts?text=${encodeURIComponent(text)}`, { headers });
      if (res.ok) {
        const data = await res.json();
        if (data.audio) {
          // Attach audio to message for future replay
          setMessages((prev) =>
            prev.map((m) => (m.id === msgId ? { ...m, audio: data.audio } : m))
          );
          playVoiceAudio(data.audio);
        }
      }
    } catch (err) {
      console.log('TTS fetch error:', err);
    }
  };

  const cleanAssistantText = (txt) => {
    if (!txt) return '';
    const urls = [];
    const masked = txt.replace(/https?:\/\/[^\s]+/g, (u) => {
      urls.push(u);
      return `@@@URLTOKEN${urls.length - 1}@@@`;
    });
    const stripped = masked.replace(/[\*#`]/g, '').replace(/(^|\s)_|_(?=\s|$|[.,!?])/g, '$1');
    return stripped.replace(/@@@URLTOKEN(\d+)@@@/g, (_, idx) => urls[idx]).trim();
  };

  const handleSendQuery = async (queryText, fromVoice = false) => {
    const q = queryText || inputQuery;
    if (!q || !q.trim()) {
      addToast('Please enter a question or tap the voice orb to speak.', 'warning', 'Empty Query');
      return;
    }
    const clean = q.trim();
    setInputQuery('');

    // Track whether this was a voice-initiated query
    if (fromVoice) {
      voiceConversationRef.current = true;
    }

    // 1. Append user message immediately
    const userMsg = { id: Date.now(), role: 'user', content: clean };
    setMessages((prev) => [...prev, userMsg]);

    setOrbState('thinking');
    setStatusText('Checking...');

    const botMsgId = Date.now() + 1;

    try {
      // Ultra-fast text response with 0ms audio blocking
      const wantVoice = fromVoice || (continuousModeRef.current && voiceConversationRef.current);
      const res = await fetch('/api/chat/text', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: clean,
          session_id: sessionId,
          synthesize_voice: false
        })
      });

      const data = await res.json();
      if (res.ok) {
        const cleanText = cleanAssistantText(data.text);
        const botMsg = {
          id: botMsgId,
          role: 'assistant',
          content: cleanText,
          audio: data.audio || null,
          sources: data.sources || []
        };
        // Display answer immediately!
        setMessages((prev) => [...prev, botMsg]);
        sound.playMessagePing();

        if (data.audio) {
          playVoiceAudio(data.audio);
        } else if (wantVoice) {
          // Play instant voice with zero network lag
          const spoke = speakWithBrowserSpeech(cleanText);
          if (!spoke) {
            setOrbState('idle');
            setStatusText('Tap Orb to Speak');
            fetchAndPlayTts(cleanText, botMsgId);
          }
        } else {
          setOrbState('idle');
          setStatusText('Tap Orb to Speak');
        }
      } else {
        setOrbState('idle');
        setStatusText('Tap Orb to Speak');
        setMessages((prev) => [
          ...prev,
          { id: botMsgId, role: 'assistant', content: data.detail || 'Service error.' }
        ]);
        addToast(data.detail || 'Error getting response from assistant.', 'error', 'Chat Error');
      }
    } catch (err) {
      console.error(err);
      setOrbState('idle');
      setStatusText('Tap Orb to Speak');
      setMessages((prev) => [
        ...prev,
        { id: botMsgId, role: 'assistant', content: 'Network error connecting to university server.' }
      ]);
      addToast('Network error connecting to university server.', 'error', 'Connection Error');
    }
  };

  // =========================================================================
  // Voice Recognition & Recording
  // =========================================================================

  const toggleVoiceRecording = () => {
    if (isTogglingVoiceRef.current) return;
    isTogglingVoiceRef.current = true;
    setTimeout(() => { isTogglingVoiceRef.current = false; }, 350);

    if (orbState === 'recording') {
      stopVoiceRecording();
    } else if (orbState === 'speaking') {
      // Stop playback and end voice conversation mode
      voiceConversationRef.current = false;
      audioPlayerRef.current.pause();
      audioPlayerRef.current.currentTime = 0;
      if (window.speechSynthesis) window.speechSynthesis.cancel();
      setOrbState('idle');
      setStatusText('Tap Orb to Speak');
    } else {
      userStoppedRef.current = false;
      startVoiceRecording();
    }
  };

  const startVoiceRecording = async () => {
    startVoiceRecordingRef.current = startVoiceRecording;
    userStoppedRef.current = false;

    // 1. Native Web Speech API (Chrome, Edge, Opera, Android browsers)
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (SpeechRecognition) {
      try {
        if (recognitionRef.current) {
          try { recognitionRef.current.abort(); } catch (e) {}
        }

        const recognition = new SpeechRecognition();
        recognition.lang = 'en-US';
        recognition.continuous = true;
        recognition.interimResults = true;

        let finalTranscript = '';

        recognition.onstart = () => {
          setOrbState('recording');
          setStatusText('Listening... Speak now');
          sound.playMicStart();
        };

        recognition.onresult = (event) => {
          let interim = '';
          for (let i = event.resultIndex; i < event.results.length; ++i) {
            if (event.results[i].isFinal) {
              finalTranscript += event.results[i][0].transcript;
            } else {
              interim += event.results[i][0].transcript;
            }
          }
          const heard = (finalTranscript || interim).trim();
          if (heard) {
            setStatusText(`Hearing: "${heard.slice(0, 36)}${heard.length > 36 ? '...' : ''}"`);
            
            // Clear previous silence timer
            if (silenceTimerRef.current) clearTimeout(silenceTimerRef.current);
            // Auto-stop after 1.4s of silence once words are spoken
            silenceTimerRef.current = setTimeout(() => {
              if (recognitionRef.current && (finalTranscript || interim).trim() && !userStoppedRef.current) {
                userStoppedRef.current = true;
                sound.playMicStop();
                setStatusText('Got it! Responding...');
                setOrbState('thinking');
                try {
                  recognitionRef.current.stop();
                } catch (e) {}
              }
            }, 1400);
          }
        };

        recognition.onerror = (e) => {
          console.warn('SpeechRecognition error:', e.error);
          if (silenceTimerRef.current) clearTimeout(silenceTimerRef.current);
          if (e.error === 'no-speech') {
            // Keep listening peacefully without flipping states or looping
            return;
          }
          if (e.error === 'not-allowed') {
            alert('Microphone access was denied. Please allow microphone permissions in your browser.');
            setOrbState('idle');
            setStatusText('Tap Orb to Speak');
            voiceConversationRef.current = false;
            return;
          }
          setOrbState('idle');
          setStatusText('Tap Orb to Speak');
        };

        recognition.onend = () => {
          if (silenceTimerRef.current) clearTimeout(silenceTimerRef.current);
          const queryToSubmit = finalTranscript.trim();
          if (queryToSubmit) {
            setOrbState('thinking');
            setStatusText('Checking answer...');
            voiceConversationRef.current = true;
            handleSendQuery(queryToSubmit, true);
          } else {
            // Clean exit to idle without looping
            setOrbState('idle');
            setStatusText('Tap Orb to Speak');
          }
        };

        recognitionRef.current = recognition;
        recognition.start();
        return;
      } catch (err) {
        console.warn('SpeechRecognition startup error, trying MediaRecorder:', err);
      }
    }

    // 2. MediaRecorder Fallback (Records WebM and uploads to Groq Whisper)
    audioChunksRef.current = [];
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      mediaRecorderRef.current = recorder;

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) audioChunksRef.current.push(e.data);
      };

      recorder.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        const blob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
        await processAudioBlob(blob);
      };

      recorder.start();
      setOrbState('recording');
      setStatusText('Listening... Speak now');
      sound.playMicStart();
    } catch (err) {
      console.error('Microphone error:', err);
      addToast('Microphone access was denied or is unavailable. Please use the text input below.', 'error', 'Microphone Error', 5000);
      setOrbState('idle');
      setStatusText('Tap Orb to Speak');
    }
  };

  const stopVoiceRecording = () => {
    userStoppedRef.current = true;
    sound.playMicStop();
    if (silenceTimerRef.current) clearTimeout(silenceTimerRef.current);
    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch (e) {}
    }
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop();
    }
    setOrbState('thinking');
    setStatusText('Processing...');
  };

  const processAudioBlob = async (blob) => {
    const formData = new FormData();
    formData.append('audio', blob, 'recording.webm');
    formData.append('session_id', sessionId);

    try {
      const headers = authToken ? { Authorization: `Bearer ${authToken}` } : {};
      const res = await fetch('/api/chat/audio', {
        method: 'POST',
        headers,
        body: formData
      });

      const data = await res.json();
      if (res.ok) {
        if (data.query && !data.query.includes('(Audio captured')) {
          setMessages((prev) => [...prev, { id: Date.now(), role: 'user', content: data.query }]);
        }
        const cleanText = cleanAssistantText(data.text);
        const botMsg = {
          id: Date.now() + 1,
          role: 'assistant',
          content: cleanText,
          audio: data.audio
        };
        setMessages((prev) => [...prev, botMsg]);
        sound.playMessagePing();
        voiceConversationRef.current = true;
        if (data.audio) {
          playVoiceAudio(data.audio);
        } else {
          setOrbState('idle');
          setStatusText('Tap Orb to Speak');
        }
      } else {
        setOrbState('idle');
        setStatusText('Tap Orb to Speak');
      }
    } catch (err) {
      console.error(err);
      setOrbState('idle');
      setStatusText('Tap Orb to Speak');
    }
  };

  // Global Keyboard Shortcuts (Space to talk, Esc to stop, / to focus)
  useEffect(() => {
    const handleKeyDown = (e) => {
      const activeEl = document.activeElement;
      const isInput =
        activeEl &&
        (activeEl.tagName === 'INPUT' ||
          activeEl.tagName === 'TEXTAREA' ||
          activeEl.isContentEditable);

      if (e.key === ' ' && !isInput && activeView === 'chat' && authToken) {
        e.preventDefault();
        toggleVoiceRecording();
      } else if (e.key === 'Escape') {
        if (orbState === 'speaking' || orbState === 'recording') {
          e.preventDefault();
          stopVoiceRecording();
          audioPlayerRef.current.pause();
          if (window.speechSynthesis) window.speechSynthesis.cancel();
          setOrbState('idle');
          setStatusText('Tap Orb to Speak');
        }
      } else if (e.key === '/' && !isInput && activeView === 'chat') {
        e.preventDefault();
        if (inputRef.current) inputRef.current.focus();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [orbState, activeView, authToken]);

  const copyMessageText = (text, id) => {
    if (navigator.clipboard) {
      navigator.clipboard.writeText(text);
      setCopiedMsgId(id);
      setTimeout(() => setCopiedMsgId(null), 2000);
      if (soundFxEnabled) sound.playMessagePing();
    }
  };

  // =========================================================================
  // Admin Data CRUD
  // =========================================================================

  const fetchAdminCounts = async () => {
    try {
      const [fac, adm, clb, web, knw] = await Promise.all([
        fetch('/api/faculty').then((r) => r.json()),
        fetch('/api/administrative').then((r) => r.json()),
        fetch('/api/clubs').then((r) => r.json()),
        fetch('/api/websites').then((r) => r.json()),
        fetch('/api/knowledge').then((r) => r.json())
      ]);
      setAdminCounts({
        faculty: fac.length || 0,
        administrative: adm.length || 0,
        clubs: clb.length || 0,
        websites: web.length || 0,
        knowledge: knw.length || 0
      });
    } catch (e) {
      console.error(e);
    }
  };

  const fetchAdminRecords = async (tab) => {
    let ep = '/api/faculty';
    if (tab === 'administrative') ep = '/api/administrative';
    else if (tab === 'clubs') ep = '/api/clubs';
    else if (tab === 'websites') ep = '/api/websites';
    else if (tab === 'knowledge') ep = '/api/knowledge';

    try {
      const res = await fetch(ep);
      if (res.ok) {
        const data = await res.json();
        setAdminRecords(data);
      }
    } catch (e) {
      console.error(e);
    }
  };

  const openAddRecordModal = () => {
    setEditingRecord(null);
    setFormData(adminTab === 'knowledge' ? { category: 'fees' } : {});
    setCrudModalOpen(true);
  };

  const openEditRecordModal = (rec) => {
    setEditingRecord(rec);
    setFormData({ ...rec });
    setCrudModalOpen(true);
  };

  const handleSaveRecord = async (e) => {
    e.preventDefault();
    let url = '';
    let method = editingRecord ? 'PUT' : 'POST';

    if (adminTab === 'faculty') {
      url = editingRecord ? `/api/faculty/${encodeURIComponent(editingRecord.emp_id)}` : '/api/faculty';
    } else if (adminTab === 'administrative') {
      url = editingRecord ? `/api/administrative/${editingRecord.id}` : '/api/administrative';
    } else if (adminTab === 'clubs') {
      url = editingRecord ? `/api/clubs/${editingRecord.id}` : '/api/clubs';
    } else if (adminTab === 'websites') {
      url = editingRecord ? `/api/websites/${editingRecord.id}` : '/api/websites';
    } else if (adminTab === 'knowledge') {
      url = editingRecord ? `/api/knowledge/${editingRecord.id}` : '/api/knowledge';
    }

    try {
      const res = await fetch(url, {
        method,
        headers: {
          'Content-Type': 'application/json',
          ...(authToken ? { Authorization: `Bearer ${authToken}` } : {})
        },
        body: JSON.stringify(formData)
      });
      if (res.status === 401) {
        handleLogout();
        addToast('Admin session expired or unauthorized. Please log in again.', 'error', 'Session Expired');
        return;
      }
      if (res.ok) {
        setCrudModalOpen(false);
        await fetchAdminRecords(adminTab);
        await fetchAdminCounts();
        const recLabel = formData.name || formData.club_name || formData.url || formData.title || 'Record';
        addToast(
          editingRecord ? `Changes saved for "${recLabel}".` : `Added "${recLabel}" to database successfully.`,
          'success',
          editingRecord ? 'Record Updated' : 'Record Created'
        );
      } else {
        const err = await res.json().catch(() => ({}));
        addToast(err.detail || 'Error saving record to database.', 'error', 'Save Error');
      }
    } catch (err) {
      console.error(err);
      addToast('Network error saving record.', 'error', 'Network Error');
    }
  };

  const promptDeleteRecord = (rec) => {
    const id = rec.emp_id || rec.id;
    const name = rec.name || rec.club_name || rec.url || rec.title || `ID ${id}`;
    setDeleteModal({
      open: true,
      recordId: id,
      recordName: name,
      tab: adminTab
    });
  };

  const executeDeleteRecord = async () => {
    if (!deleteModal.recordId) return;
    const { recordId, recordName, tab } = deleteModal;
    setIsDeleting(true);

    let url = `/api/faculty/${encodeURIComponent(recordId)}`;
    if (tab === 'administrative') url = `/api/administrative/${recordId}`;
    else if (tab === 'clubs') url = `/api/clubs/${recordId}`;
    else if (tab === 'websites') url = `/api/websites/${recordId}`;
    else if (tab === 'knowledge') url = `/api/knowledge/${recordId}`;

    try {
      const res = await fetch(url, {
        method: 'DELETE',
        headers: {
          ...(authToken ? { Authorization: `Bearer ${authToken}` } : {})
        }
      });
      if (res.status === 401) {
        handleLogout();
        addToast('Admin session expired or unauthorized. Please log in again.', 'error', 'Session Expired');
        return;
      }
      if (res.ok) {
        setDeleteModal({ open: false, recordId: null, recordName: '', tab: 'faculty' });
        await fetchAdminRecords(tab);
        await fetchAdminCounts();
        addToast(`Permanently deleted "${recordName}" from database.`, 'delete', 'Record Deleted');
      } else {
        const err = await res.json().catch(() => ({}));
        addToast(err.detail || 'Failed to delete record from database.', 'error', 'Delete Error');
      }
    } catch (err) {
      console.error(err);
      addToast('Network error while deleting record.', 'error', 'Network Error');
    } finally {
      setIsDeleting(false);
    }
  };


  // Filtered records in Admin view
  const filteredRecords = adminRecords.filter((r) => {
    const q = searchFilter.toLowerCase().trim();
    if (!q) return true;
    return Object.values(r).some((val) => {
      if (typeof val === 'string') return val.toLowerCase().includes(q);
      if (Array.isArray(val)) return val.join(' ').toLowerCase().includes(q);
      return false;
    });
  });

  return (
    <div className="app-shell">
      {/* Top Header */}
      <header className="app-header">
        <div
          className="brand-section"
          style={{ cursor: activeView === 'admin' ? 'pointer' : 'default' }}
          onClick={() => {
            if (activeView === 'admin') {
              window.history.pushState({}, '', '/');
              setActiveView('chat');
            }
          }}
        >
          <img src="/sru_logo.png" alt="SRU Logo" className="brand-logo-img" />
          <div className="brand-info">
            <h1>SR University</h1>
            <p>{activeView === 'admin' ? 'Database Administration' : 'Voice Assistant'}</p>
          </div>
        </div>

        <div className="header-controls">
          {authToken && (
            <>
              <span
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 5,
                  fontSize: '0.74rem',
                  padding: '3px 9px',
                  borderRadius: 12,
                  backgroundColor: authRole === 'admin' ? 'rgba(37, 99, 235, 0.12)' : 'rgba(16, 185, 129, 0.12)',
                  color: authRole === 'admin' ? '#2563eb' : '#059669',
                  fontWeight: 600
                }}
              >
                {authRole === 'admin' ? <ShieldCheck size={12} /> : <Bot size={12} />}
                {authRole === 'admin' ? 'Administrator' : 'Student / User'}
              </span>

              {authRole === 'admin' && activeView === 'admin' && (
                <a
                  href="/"
                  onClick={(e) => {
                    e.preventDefault();
                    window.history.pushState({}, '', '/');
                    setActiveView('chat');
                  }}
                  className="btn btn-outline btn-sm"
                  style={{ textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: '0.78rem' }}
                >
                  <Bot size={13} />
                  Voice Assistant
                </a>
              )}

              {authRole === 'admin' && activeView === 'chat' && (
                <a
                  href="/admin"
                  onClick={(e) => {
                    e.preventDefault();
                    window.history.pushState({}, '', '/admin');
                    setActiveView('admin');
                  }}
                  className="btn btn-outline btn-sm"
                  style={{ textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: '0.78rem' }}
                >
                  <Database size={13} />
                  Admin Portal
                </a>
              )}

              <button
                onClick={handleLogout}
                className="btn btn-outline btn-sm"
                style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: '0.78rem', color: 'var(--destructive)', borderColor: 'var(--border-color)' }}
                title="Log out of session"
              >
                <LogOut size={13} />
                Log Out
              </button>
            </>
          )}

          {/* Tactile Sound FX Toggle */}
          <button
            className="btn btn-outline btn-icon"
            onClick={() => {
              const nextVal = !soundFxEnabled;
              setSoundFxEnabled(nextVal);
              sound.enabled = nextVal;
              localStorage.setItem('sru_sound_fx', nextVal ? 'true' : 'false');
              if (nextVal) sound.playMessagePing();
            }}
            title={soundFxEnabled ? "Mute tactile sound effects" : "Enable tactile sound effects"}
          >
            {soundFxEnabled ? <Volume2 size={14} /> : <VolumeX size={14} />}
          </button>

          {/* Theme Toggle Button */}
          <button
            className="btn btn-outline btn-icon"
            onClick={toggleTheme}
            title="Toggle theme"
          >
            {theme === 'light' ? <Moon size={14} /> : <Sun size={14} />}
          </button>
        </div>
      </header>

      {/* Main 100vh Body - Zero Vertical Scrolling */}
      {!authToken ? (
        /* Unified Portal Login Screen */
        <main className="main-stage" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: 'calc(100vh - 65px)' }}>
          <section
            style={{
              maxWidth: 440,
              width: '100%',
              margin: 'auto',
              padding: '2.5rem 2rem',
              background: 'var(--card-bg, #ffffff)',
              border: '1px solid var(--border-color, #e2e8f0)',
              borderRadius: 18,
              boxShadow: '0 20px 45px -15px rgba(0,0,0,0.12)',
              textAlign: 'center'
            }}
          >
            <div
              style={{
                width: 62,
                height: 62,
                borderRadius: '50%',
                background: 'linear-gradient(135deg, #1e3a8a, #2563eb)',
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#fff',
                marginBottom: '1rem',
                boxShadow: '0 8px 18px -4px rgba(37,99,235,0.35)'
              }}
            >
              <ShieldCheck size={30} />
            </div>

            <h2 style={{ fontSize: '1.3rem', fontWeight: 700, margin: '0 0 0.35rem 0', color: 'var(--text-primary)' }}>
              SR University Portal
            </h2>
            <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', margin: '0 0 1.4rem 0' }}>
              Unified Access for AI Voice Assistant and Administration
            </p>

            {/* Role Switcher Tabs */}
            <div
              style={{
                display: 'flex',
                padding: 4,
                backgroundColor: 'var(--bg-secondary, #f1f5f9)',
                borderRadius: 10,
                marginBottom: '1.25rem'
              }}
            >
              <button
                type="button"
                onClick={() => { setLoginRoleTab('user'); setAuthError(''); }}
                style={{
                  flex: 1,
                  padding: '8px 12px',
                  border: 'none',
                  borderRadius: 8,
                  fontSize: '0.82rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                  backgroundColor: loginRoleTab === 'user' ? '#2563eb' : 'transparent',
                  color: loginRoleTab === 'user' ? '#ffffff' : 'var(--text-secondary)',
                  transition: 'all 0.2s ease',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: 6
                }}
              >
                <Bot size={14} />
                Student / User
              </button>
              <button
                type="button"
                onClick={() => { setLoginRoleTab('admin'); setAuthError(''); }}
                style={{
                  flex: 1,
                  padding: '8px 12px',
                  border: 'none',
                  borderRadius: 8,
                  fontSize: '0.82rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                  backgroundColor: loginRoleTab === 'admin' ? '#2563eb' : 'transparent',
                  color: loginRoleTab === 'admin' ? '#ffffff' : 'var(--text-secondary)',
                  transition: 'all 0.2s ease',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: 6
                }}
              >
                <Database size={14} />
                Administrator
              </button>
            </div>

            <p style={{ fontSize: '0.76rem', color: 'var(--text-muted)', textAlign: 'left', margin: '0 0 0.85rem 0', lineHeight: 1.4 }}>
              {loginRoleTab === 'admin'
                ? 'Enter master administrator password to modify faculty, administrative offices, websites, and knowledge records.'
                : 'Enter user access password to unlock voice assistant and conversational campus helpdesk.'}
            </p>

            {authError && (
              <div
                style={{
                  padding: '0.65rem 0.85rem',
                  backgroundColor: 'rgba(239, 68, 68, 0.1)',
                  border: '1px solid rgba(239, 68, 68, 0.3)',
                  borderRadius: 8,
                  color: '#ef4444',
                  fontSize: '0.8rem',
                  marginBottom: '1rem',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  textAlign: 'left'
                }}
              >
                <AlertCircle size={15} style={{ flexShrink: 0 }} />
                <span>{authError}</span>
              </div>
            )}

            <form onSubmit={handleUnifiedLogin} style={{ display: 'flex', flexDirection: 'column', gap: '1rem', textAlign: 'left' }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 600, marginBottom: 6, color: 'var(--text-secondary)' }}>
                  {loginRoleTab === 'admin' ? 'Master Admin Password' : 'User Access Password'}
                </label>
                <div style={{ position: 'relative' }}>
                  <input
                    type={showAuthPassword ? "text" : "password"}
                    value={authPasswordInput}
                    onChange={(e) => setAuthPasswordInput(e.target.value)}
                    placeholder={loginRoleTab === 'admin' ? 'Enter admin password...' : 'Enter user password...'}
                    autoFocus
                    className="form-control"
                    style={{
                      width: '100%',
                      padding: '0.65rem 2.5rem 0.65rem 0.85rem',
                      fontSize: '0.88rem',
                      borderRadius: 8,
                      border: '1px solid var(--border-color, #cbd5e1)',
                      background: 'var(--bg-primary, #ffffff)',
                      color: 'var(--text-primary)',
                      boxSizing: 'border-box'
                    }}
                  />
                  <button
                    type="button"
                    onClick={() => setShowAuthPassword(!showAuthPassword)}
                    tabIndex={-1}
                    style={{
                      position: 'absolute',
                      right: 8,
                      top: '50%',
                      transform: 'translateY(-50%)',
                      background: 'none',
                      border: 'none',
                      color: 'var(--text-secondary)',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      padding: 4
                    }}
                    title={showAuthPassword ? "Hide password" : "Show password"}
                  >
                    {showAuthPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>
              </div>

              <button
                type="submit"
                className="btn btn-primary"
                disabled={authLoading || !authPasswordInput.trim()}
                style={{
                  padding: '0.7rem',
                  fontWeight: 600,
                  fontSize: '0.88rem',
                  borderRadius: 8,
                  display: 'inline-flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: 8,
                  cursor: authLoading ? 'not-allowed' : 'pointer'
                }}
              >
                {authLoading ? (
                  <>
                    <RefreshCw size={14} className="spin" />
                    Signing In...
                  </>
                ) : (
                  <>
                    <KeyRound size={15} />
                    {loginRoleTab === 'admin' ? 'Unlock Admin Portal' : 'Enter Voice Assistant'}
                  </>
                )}
              </button>
            </form>
          </section>
        </main>
      ) : activeView === 'chat' ? (
        <main className="main-stage">
          {/* Left Stage: Voice Orb Centerpiece */}
          <section className="voice-stage-left">
            {/* 3D WebGL Living Reactive Core */}
            <div
              className="orb-3d-wrapper"
              onClick={toggleVoiceRecording}
              title="Click 3D Core to Speak or Interrupt"
            >
              <div className={`orb-ambient-glow ${orbState}`} />
              <ThreeOrb state={orbState} size={250} />
            </div>

            {/* Voice Status Pill with Live Duration Timer */}
            <div className={`status-pill ${orbState === 'recording' ? 'recording' : ''}`}>
              <div className="dot"></div>
              <span>
                {orbState === 'recording' && recordingSeconds > 0
                  ? `Listening (0:${recordingSeconds < 10 ? '0' : ''}${recordingSeconds})...`
                  : statusText}
              </span>
              <div className="waveform-bars">
                <div className="waveform-bar"></div>
                <div className="waveform-bar"></div>
                <div className="waveform-bar"></div>
                <div className="waveform-bar"></div>
              </div>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px', marginTop: '0.25rem' }}>
              <button
                className={`btn ${orbState === 'recording' ? 'btn-primary' : orbState === 'speaking' ? 'btn-destructive' : 'btn-outline'} btn-sm`}
                onClick={toggleVoiceRecording}
                style={{ minWidth: 105, gap: '6px' }}
              >
                {orbState === 'recording' ? (
                  <>
                    <CheckCircle2 size={13} />
                    Done (Send)
                  </>
                ) : orbState === 'speaking' ? (
                  <>
                    <Volume2 size={13} />
                    Interrupt
                  </>
                ) : (
                  <>
                    <Mic size={13} />
                    Speak
                  </>
                )}
              </button>

              <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.68rem', color: 'var(--text-muted)', marginTop: '0.1rem' }}>
                <span className="kbd-hint">Space</span>
                <span>to talk</span>
                <span style={{ opacity: 0.4 }}>•</span>
                <span className="kbd-hint">Esc</span>
                <span>to stop</span>
              </div>

              <label
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  fontSize: '0.72rem',
                  color: 'var(--text-secondary)',
                  cursor: 'pointer',
                  userSelect: 'none',
                  marginTop: '0.2rem'
                }}
                title="When enabled, the assistant automatically listens for your next question after it finishes speaking"
              >
                <input
                  type="checkbox"
                  checked={continuousMode}
                  onChange={(e) => handleContinuousToggle(e.target.checked)}
                  style={{ accentColor: '#2563eb', cursor: 'pointer' }}
                />
                Auto-listen (Continuous)
              </label>
            </div>
          </section>

          {/* Right Stage: Contextual Dialogue Stream */}
          <section className="chat-stage-right">
            <div className="chat-stage-header">
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <span style={{ width: 6, height: 6, borderRadius: '50%', backgroundColor: '#10b981' }}></span>
                <span>Session: <strong>{sessionId.slice(-6)}</strong></span>
              </div>
              <button className="btn btn-outline btn-sm" onClick={startNewDialogue} title="Reset dialogue">
                <RefreshCw size={11} />
                Reset
              </button>
            </div>

            {/* Internal Scroll ONLY */}
            <div className="chat-scroll-area" ref={chatScrollRef}>
              {messages.length === 0 ? (
                <div style={{ margin: 'auto', textAlign: 'center', color: 'var(--text-secondary)' }}>
                  <p style={{ fontSize: '0.82rem' }}>
                    Ask about faculty, offices, fees, rules, scholarships, fests, or campus facilities.
                  </p>
                </div>
              ) : (
                messages.map((m) => (
                  <div key={m.id} className={`message-card ${m.role}`}>
                    <span className="message-sender">{m.role === 'user' ? 'You' : 'SRU AI'}</span>
                    <div className="message-content-box">
                      {m.content}

                      {/* Message Actions: Audio replay & Copy */}
                      {m.role === 'assistant' && (
                        <div className="msg-actions">
                          <button
                            className="btn btn-outline btn-icon btn-sm"
                            onClick={() => {
                              if (m.audio) {
                                playVoiceAudio(m.audio);
                              } else {
                                const spoke = speakWithBrowserSpeech(m.content);
                                if (!spoke) {
                                  fetchAndPlayTts(m.content, m.id);
                                }
                              }
                            }}
                            title="Play Voice"
                            style={{ width: 26, height: 26 }}
                          >
                            <Volume2 size={13} />
                          </button>

                          <button
                            className={`msg-action-btn ${copiedMsgId === m.id ? 'copied' : ''}`}
                            onClick={() => copyMessageText(m.content, m.id)}
                            title="Copy answer to clipboard"
                          >
                            {copiedMsgId === m.id ? <Check size={12} /> : <Copy size={12} />}
                            <span>{copiedMsgId === m.id ? 'Copied' : 'Copy'}</span>
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                ))
              )}
            </div>

            {/* Bottom Dock: Filterable Categorized Chips + Input */}
            <div className="chat-bottom-dock">
              {/* Category Filter Tabs */}
              <div className="category-filter-bar">
                {PROMPT_CATEGORIES.map((cat) => {
                  const Icon = cat.icon;
                  return (
                    <button
                      key={cat.id}
                      className={`category-tab-btn ${activePromptCategory === cat.id ? 'active' : ''}`}
                      onClick={() => setActivePromptCategory(cat.id)}
                    >
                      <Icon size={12} style={{ marginRight: 4, verticalAlign: 'middle' }} />
                      {cat.label}
                    </button>
                  );
                })}
              </div>

              {/* Active Category Chips */}
              <div className="chips-slider">
                {(PROMPTS_BY_CATEGORY[activePromptCategory] || []).map((prompt, idx) => (
                  <button
                    key={idx}
                    className="quick-prompt-chip"
                    onClick={() => handleSendQuery(prompt)}
                  >
                    {prompt}
                  </button>
                ))}
              </div>

              <form
                className="input-dock-form"
                onSubmit={(e) => {
                  e.preventDefault();
                  handleSendQuery();
                }}
              >
                <input
                  ref={inputRef}
                  type="text"
                  className="input-dock-field"
                  placeholder="Ask a question or press [Space] to speak... (Press [/] to focus)"
                  value={inputQuery}
                  onChange={(e) => setInputQuery(e.target.value)}
                />
                <button type="submit" className="btn btn-primary btn-icon" style={{ width: 28, height: 28 }} title="Send">
                  <Send size={12} />
                </button>
              </form>
            </div>
          </section>
        </main>
      ) : authRole === 'admin' ? (
        /* Admin Management View */
        <main className="main-stage">
          <section className="admin-view-panel">
            <div className="admin-top-bar">
              <div className="admin-category-tabs">
                <button
                  className={`admin-cat-btn ${adminTab === 'faculty' ? 'active' : ''}`}
                  onClick={() => setAdminTab('faculty')}
                >
                  Faculty ({adminCounts.faculty})
                </button>
                <button
                  className={`admin-cat-btn ${adminTab === 'administrative' ? 'active' : ''}`}
                  onClick={() => setAdminTab('administrative')}
                >
                  Administrative ({adminCounts.administrative})
                </button>
                <button
                  className={`admin-cat-btn ${adminTab === 'knowledge' ? 'active' : ''}`}
                  onClick={() => setAdminTab('knowledge')}
                >
                  Knowledge ({adminCounts.knowledge})
                </button>
                <button
                  className={`admin-cat-btn ${adminTab === 'clubs' ? 'active' : ''}`}
                  onClick={() => setAdminTab('clubs')}
                >
                  Clubs ({adminCounts.clubs})
                </button>
                <button
                  className={`admin-cat-btn ${adminTab === 'websites' ? 'active' : ''}`}
                  onClick={() => setAdminTab('websites')}
                >
                  Websites ({adminCounts.websites})
                </button>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <div style={{ position: 'relative' }}>
                  <Search size={13} style={{ position: 'absolute', left: 8, top: 9, color: 'var(--text-muted)' }} />
                  <input
                    type="text"
                    placeholder="Search records..."
                    className="form-control"
                    style={{ paddingLeft: '1.75rem', height: 32, fontSize: '0.78rem' }}
                    value={searchFilter}
                    onChange={(e) => setSearchFilter(e.target.value)}
                  />
                </div>
                <button className="btn btn-primary btn-sm" onClick={openAddRecordModal}>
                  <Plus size={12} />
                  Add
                </button>
                <button
                  className="btn btn-outline btn-sm"
                  onClick={handleLogout}
                  style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: '0.78rem', color: 'var(--destructive)', borderColor: 'var(--border-color)' }}
                  title="End admin session"
                >
                  <LogOut size={13} />
                  Log Out
                </button>
              </div>
            </div>

            {/* Admin Records Table */}
            <div className="admin-table-wrapper">
              <table className="admin-data-table">
                <thead>
                  {adminTab === 'faculty' && (
                    <tr>
                      <th style={{ width: 130 }}>Employee ID</th>
                      <th>Faculty Name</th>
                      <th>Email</th>
                      <th>Cabin ID</th>
                      <th style={{ width: 100, textAlign: 'right' }}>Actions</th>
                    </tr>
                  )}
                  {adminTab === 'administrative' && (
                    <tr>
                      <th>Role</th>
                      <th>Name</th>
                      <th>Email</th>
                      <th>Cabin</th>
                      <th style={{ width: 100, textAlign: 'right' }}>Actions</th>
                    </tr>
                  )}
                  {adminTab === 'knowledge' && (
                    <tr>
                      <th style={{ width: 140 }}>Category</th>
                      <th style={{ width: 220 }}>Title</th>
                      <th>Content Preview</th>
                      <th style={{ width: 180 }}>Tags</th>
                      <th style={{ width: 100, textAlign: 'right' }}>Actions</th>
                    </tr>
                  )}
                  {adminTab === 'clubs' && (
                    <tr>
                      <th>Club Name</th>
                      <th>Social Link</th>
                      <th style={{ width: 100, textAlign: 'right' }}>Actions</th>
                    </tr>
                  )}
                  {adminTab === 'websites' && (
                    <tr>
                      <th style={{ width: 220 }}>URL</th>
                      <th>Purpose Tags</th>
                      <th style={{ width: 100, textAlign: 'right' }}>Actions</th>
                    </tr>
                  )}
                </thead>
                <tbody>
                  {filteredRecords.length === 0 ? (
                    <tr>
                      <td colSpan={5} style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-secondary)' }}>
                        No records found.
                      </td>
                    </tr>
                  ) : (
                    filteredRecords.map((r) => {
                      if (adminTab === 'faculty') {
                        return (
                          <tr key={r.emp_id}>
                            <td><span className="badge badge-faculty">{r.emp_id}</span></td>
                            <td><strong>{r.name}</strong></td>
                            <td>{r.email ? <a href={`mailto:${r.email}`} style={{ color: '#2563eb' }}>{r.email}</a> : <span style={{ color: 'var(--text-muted)' }}>—</span>}</td>
                            <td>{r.cabin_id ? <code>{r.cabin_id}</code> : <span style={{ color: 'var(--text-muted)' }}>—</span>}</td>
                            <td style={{ textAlign: 'right' }}>
                              <button className="btn btn-outline btn-sm" onClick={() => openEditRecordModal(r)} style={{ marginRight: 4 }} title="Edit Record">
                                <Edit2 size={11} />
                              </button>
                              <button className="btn btn-outline btn-sm" style={{ color: 'var(--destructive)' }} onClick={() => promptDeleteRecord(r)} title="Delete Record">
                                <Trash2 size={11} />
                              </button>
                            </td>
                          </tr>
                        );
                      } else if (adminTab === 'administrative') {
                        return (
                          <tr key={r.id}>
                            <td><span className="badge badge-admin">{r.role}</span></td>
                            <td><strong>{r.name}</strong></td>
                            <td>{r.email ? <a href={`mailto:${r.email}`} style={{ color: '#2563eb' }}>{r.email}</a> : <span style={{ color: 'var(--text-muted)' }}>—</span>}</td>
                            <td><code>{r.cabin_room_number}</code></td>
                            <td style={{ textAlign: 'right' }}>
                              <button className="btn btn-outline btn-sm" onClick={() => openEditRecordModal(r)} style={{ marginRight: 4 }} title="Edit Record">
                                <Edit2 size={11} />
                              </button>
                              <button className="btn btn-outline btn-sm" style={{ color: 'var(--destructive)' }} onClick={() => promptDeleteRecord(r)} title="Delete Record">
                                <Trash2 size={11} />
                              </button>
                            </td>
                          </tr>
                        );
                      } else if (adminTab === 'knowledge') {
                        return (
                          <tr key={r.id}>
                            <td><span className="badge badge-knowledge" style={{ textTransform: 'capitalize' }}>{r.category}</span></td>
                            <td><strong>{r.title}</strong></td>
                            <td style={{ maxWidth: 360, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={r.content}>
                              {r.content}
                            </td>
                            <td><span className="badge badge-web" style={{ fontSize: '0.72rem' }}>{r.tags}</span></td>
                            <td style={{ textAlign: 'right' }}>
                              <button className="btn btn-outline btn-sm" onClick={() => openEditRecordModal(r)} style={{ marginRight: 4 }} title="Edit Record">
                                <Edit2 size={11} />
                              </button>
                              <button className="btn btn-outline btn-sm" style={{ color: 'var(--destructive)' }} onClick={() => promptDeleteRecord(r)} title="Delete Record">
                                <Trash2 size={11} />
                              </button>
                            </td>
                          </tr>
                        );
                      } else if (adminTab === 'clubs') {
                        return (
                          <tr key={r.id}>
                            <td><span className="badge badge-club">{r.club_name}</span></td>
                            <td><a href={r.social_media_link} target="_blank" rel="noreferrer" style={{ color: '#2563eb' }}>{r.social_media_link}</a></td>
                            <td style={{ textAlign: 'right' }}>
                              <button className="btn btn-outline btn-sm" onClick={() => openEditRecordModal(r)} style={{ marginRight: 4 }} title="Edit Record">
                                <Edit2 size={11} />
                              </button>
                              <button className="btn btn-outline btn-sm" style={{ color: 'var(--destructive)' }} onClick={() => promptDeleteRecord(r)} title="Delete Record">
                                <Trash2 size={11} />
                              </button>
                            </td>
                          </tr>
                        );
                      } else {
                        return (
                          <tr key={r.id}>
                            <td><a href={r.url} target="_blank" rel="noreferrer" style={{ color: '#2563eb', fontWeight: 600 }}>{r.url}</a></td>
                            <td><span className="badge badge-web">{r.purpose_tags}</span></td>
                            <td style={{ textAlign: 'right' }}>
                              <button className="btn btn-outline btn-sm" onClick={() => openEditRecordModal(r)} style={{ marginRight: 4 }} title="Edit Record">
                                <Edit2 size={11} />
                              </button>
                              <button className="btn btn-outline btn-sm" style={{ color: 'var(--destructive)' }} onClick={() => promptDeleteRecord(r)} title="Delete Record">
                                <Trash2 size={11} />
                              </button>
                            </td>
                          </tr>
                        );
                      }
                    })
                  )}
                </tbody>
              </table>
            </div>
          </section>
        </main>
      ) : (
        /* Student/User attempted to access /admin */
        <main className="main-stage" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: 'calc(100vh - 65px)' }}>
          <section style={{ maxWidth: 440, padding: '2.5rem 2rem', textAlign: 'center', background: 'var(--card-bg, #ffffff)', borderRadius: 16, border: '1px solid var(--border-color, #e2e8f0)', boxShadow: '0 15px 35px -10px rgba(0,0,0,0.1)' }}>
            <div style={{ width: 56, height: 56, borderRadius: '50%', background: 'rgba(245, 158, 11, 0.12)', color: '#d97706', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', marginBottom: '1rem' }}>
              <AlertCircle size={30} />
            </div>
            <h3 style={{ margin: '0 0 0.5rem 0', fontSize: '1.15rem', fontWeight: 700 }}>Administrator Access Required</h3>
            <p style={{ fontSize: '0.84rem', color: 'var(--text-secondary)', margin: '0 0 1.5rem 0', lineHeight: 1.5 }}>
              You are currently signed in as <strong>Student / User</strong>. Only administrators can view and manage university database records.
            </p>
            <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'center' }}>
              <button
                className="btn btn-primary btn-sm"
                onClick={() => {
                  window.history.pushState({}, '', '/');
                  setActiveView('chat');
                }}
              >
                Return to Assistant
              </button>
              <button className="btn btn-outline btn-sm" onClick={handleLogout}>
                Sign Out / Switch Role
              </button>
            </div>
          </section>
        </main>
      )}

      {/* CRUD Modal for Admin */}
      {crudModalOpen && (
        <div className="modal-overlay">
          <div className="modal-dialog">
            <div className="modal-header">
              <h3 style={{ margin: 0, fontSize: '0.95rem', fontWeight: 700 }}>
                {editingRecord ? 'Edit Record' : 'Add Record'}
              </h3>
              <button className="btn btn-outline btn-icon" onClick={() => setCrudModalOpen(false)}>
                <X size={13} />
              </button>
            </div>
            <form onSubmit={handleSaveRecord}>
              <div className="modal-body">
                {adminTab === 'faculty' && (
                  <>
                    <div className="form-field">
                      <label className="form-label">Employee ID *</label>
                      <input
                        type="text"
                        className="form-control"
                        required
                        disabled={!!editingRecord}
                        value={formData.emp_id || ''}
                        onChange={(e) => setFormData({ ...formData, emp_id: e.target.value })}
                        placeholder="e.g. SRU-CSE-101"
                      />
                    </div>
                    <div className="form-field">
                      <label className="form-label">Faculty Name *</label>
                      <input
                        type="text"
                        className="form-control"
                        required
                        value={formData.name || ''}
                        onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                        placeholder="e.g. Dr. A. Ramesh Babu"
                      />
                    </div>
                    <div className="form-field">
                      <label className="form-label">Email Address</label>
                      <input
                        type="email"
                        className="form-control"
                        value={formData.email || ''}
                        onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                        placeholder="e.g. faculty.name@sru.edu.in"
                      />
                    </div>
                    <div className="form-field">
                      <label className="form-label">Cabin ID / Room</label>
                      <input
                        type="text"
                        className="form-control"
                        value={formData.cabin_id || ''}
                        onChange={(e) => setFormData({ ...formData, cabin_id: e.target.value })}
                        placeholder="e.g. Block-I, Room 102 (optional, defaults to null)"
                      />
                    </div>
                  </>
                )}

                {adminTab === 'administrative' && (
                  <>
                    <div className="form-field">
                      <label className="form-label">Role *</label>
                      <input
                        type="text"
                        className="form-control"
                        required
                        value={formData.role || ''}
                        onChange={(e) => setFormData({ ...formData, role: e.target.value })}
                        placeholder="e.g. Buses In-Charge"
                      />
                    </div>
                    <div className="form-field">
                      <label className="form-label">Officer Name *</label>
                      <input
                        type="text"
                        className="form-control"
                        required
                        value={formData.name || ''}
                        onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                        placeholder="e.g. Mr. Ch. Venkat Narayana"
                      />
                    </div>
                    <div className="form-field">
                      <label className="form-label">Email Address</label>
                      <input
                        type="email"
                        className="form-control"
                        value={formData.email || ''}
                        onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                        placeholder="e.g. officer@sru.edu.in"
                      />
                    </div>
                    <div className="form-field">
                      <label className="form-label">Cabin / Room *</label>
                      <input
                        type="text"
                        className="form-control"
                        required
                        value={formData.cabin_room_number || ''}
                        onChange={(e) => setFormData({ ...formData, cabin_room_number: e.target.value })}
                        placeholder="e.g. Cabin T-102"
                      />
                    </div>
                  </>
                )}

                {adminTab === 'knowledge' && (
                  <>
                    <div className="form-field">
                      <label className="form-label">Category *</label>
                      <select
                        className="form-control"
                        required
                        value={formData.category || 'fees'}
                        onChange={(e) => setFormData({ ...formData, category: e.target.value })}
                      >
                        <option value="fees">Fees</option>
                        <option value="scholarships">Scholarships</option>
                        <option value="gamification_ssm">Gamification (SSM Coins & Badges)</option>
                        <option value="academics">Academics</option>
                        <option value="permissions">Permissions & Gate Pass</option>
                        <option value="campus_life">Campus Life & Fests</option>
                        <option value="placements">Placements</option>
                        <option value="facilities">Facilities</option>
                        <option value="rules">Rules & Discipline</option>
                      </select>
                    </div>
                    <div className="form-field">
                      <label className="form-label">Title *</label>
                      <input
                        type="text"
                        className="form-control"
                        required
                        value={formData.title || ''}
                        onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                        placeholder="e.g. B.Tech Tuition Fee Structure"
                      />
                    </div>
                    <div className="form-field">
                      <label className="form-label">Content *</label>
                      <textarea
                        className="form-control"
                        required
                        rows={5}
                        value={formData.content || ''}
                        onChange={(e) => setFormData({ ...formData, content: e.target.value })}
                        placeholder="Detailed rules, fee amounts, policies..."
                      />
                    </div>
                    <div className="form-field">
                      <label className="form-label">Search Tags *</label>
                      <input
                        type="text"
                        className="form-control"
                        required
                        value={formData.tags || ''}
                        onChange={(e) => setFormData({ ...formData, tags: e.target.value })}
                        placeholder="e.g. tuition, btech fees, semester"
                      />
                    </div>
                  </>
                )}

                {adminTab === 'clubs' && (
                  <>
                    <div className="form-field">
                      <label className="form-label">Club Name *</label>
                      <input
                        type="text"
                        className="form-control"
                        required
                        value={formData.club_name || ''}
                        onChange={(e) => setFormData({ ...formData, club_name: e.target.value })}
                        placeholder="e.g. RoboSRU - Robotics Club"
                      />
                    </div>
                    <div className="form-field">
                      <label className="form-label">Social Media Link *</label>
                      <input
                        type="url"
                        className="form-control"
                        required
                        value={formData.social_media_link || ''}
                        onChange={(e) => setFormData({ ...formData, social_media_link: e.target.value })}
                        placeholder="https://instagram.com/sru_robotics"
                      />
                    </div>
                  </>
                )}

                {adminTab === 'websites' && (
                  <>
                    <div className="form-field">
                      <label className="form-label">Portal URL *</label>
                      <input
                        type="url"
                        className="form-control"
                        required
                        value={formData.url || ''}
                        onChange={(e) => setFormData({ ...formData, url: e.target.value })}
                        placeholder="https://feepay.sru.edu.in"
                      />
                    </div>
                    <div className="form-field">
                      <label className="form-label">Purpose Tags *</label>
                      <input
                        type="text"
                        className="form-control"
                        required
                        value={formData.purpose_tags || ''}
                        onChange={(e) => setFormData({ ...formData, purpose_tags: e.target.value })}
                        placeholder="e.g. tuition fees, fee payment"
                      />
                    </div>
                  </>
                )}
              </div>

              <div className="modal-footer">
                <button type="button" className="btn btn-outline btn-sm" onClick={() => setCrudModalOpen(false)}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary btn-sm">
                  Save
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {deleteModal.open && (
        <div className="modal-overlay" onClick={() => !isDeleting && setDeleteModal({ ...deleteModal, open: false })}>
          <div className="modal-dialog" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 430 }}>
            <div className="modal-header">
              <h3 style={{ margin: 0, fontSize: '0.95rem', fontWeight: 700, color: 'var(--destructive)' }}>
                Delete Database Record
              </h3>
              <button
                className="btn btn-outline btn-icon"
                onClick={() => setDeleteModal({ ...deleteModal, open: false })}
                disabled={isDeleting}
                title="Close"
              >
                <X size={13} />
              </button>
            </div>
            <div className="modal-body" style={{ textAlign: 'center', padding: '1.5rem 1.25rem' }}>
              <div className="delete-confirm-icon" style={{ margin: '0 auto 1rem auto' }}>
                <Trash2 size={22} />
              </div>
              <h4 style={{ margin: '0 0 0.5rem 0', fontSize: '1rem', fontWeight: 600 }}>
                Confirm Permanent Deletion
              </h4>
              <p style={{ margin: 0, fontSize: '0.84rem', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                Are you sure you want to delete <strong>{deleteModal.recordName}</strong> ({deleteModal.recordId}) from the database? This action cannot be undone.
              </p>
            </div>
            <div className="modal-footer" style={{ justifyContent: 'flex-end', gap: '0.5rem' }}>
              <button
                type="button"
                className="btn btn-outline btn-sm"
                onClick={() => setDeleteModal({ ...deleteModal, open: false })}
                disabled={isDeleting}
              >
                Cancel
              </button>
              <button
                type="button"
                className="btn btn-destructive btn-sm"
                onClick={executeDeleteRecord}
                disabled={isDeleting}
                style={{ minWidth: 110 }}
              >
                {isDeleting ? 'Deleting...' : 'Delete Record'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
