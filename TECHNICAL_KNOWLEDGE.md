# Technical Knowledge: University Helpdesk AI System

---

## 1. Methodology

### 1.1 Problem Formulation and Objective
The system is designed to resolve informational queries regarding university personnel, administration, student bodies, and digital services via voice and text modalities. The primary operational objectives are:
1. Zero-hallucination factual query response over structured relational campus records.
2. Low-latency voice-to-voice interaction loop (sub-1.5 second target end-to-end response time).
3. Resilient fallback across all critical pipeline segments (ASR/STT, NLP/RAG, and TTS).
4. Direct relational data administration through standard Create, Read, Update, and Delete (CRUD) operations.

---

### 1.2 System Architecture Overview
The architecture is structured as a decoupled multi-tier system:
- **Client Tier**: Web-based single-page application (React 18 SPA / Vanilla JS fallback) providing microphone capture via HTML5 MediaStreams, audio playback via HTML5 Audio elements, and administrative CRUD interfaces.
- **Gateway & Orchestration Tier**: FastAPI ASGI server handling HTTP REST requests, multipart audio ingestion, dialogue session management, and routing.
- **Retrieval-Augmented Generation (RAG) Tier**: Dual-mode engine consisting of an AI-first tool-calling router with a deterministic fallback search engine operating directly over an SQLite relational database.
- **Voice Tier**: Dual-engine Automatic Speech Recognition (Groq Whisper Large v3 with local SpeechRecognition fallback) and a tri-tier cascading Text-to-Speech pipeline (Microsoft Edge Neural TTS, Windows SAPI5/pyttsx3, Kokoro-82M ONNX).
- **Data Persistence Tier**: SQLite relational database accessed via SQLAlchemy Object-Relational Mapping (ORM).

```
                      +------------------------------------------+
                      |         Client Layer (SPA / Admin)       |
                      +------------------------------------------+
                                     |            ^
                    HTTP POST (Text/Audio)   Base64 Audio / JSON
                                     v            |
                      +------------------------------------------+
                      |          FastAPI Application Core        |
                      +------------------------------------------+
                                     |
              +----------------------+----------------------+
              |                                             |
              v                                             v
+-------------------------------+             +-------------------------------+
|         Voice Pipeline        |             |          RAG Engine           |
|                               |             |                               |
| 1. STT: Whisper / Local ASR   |             | 1. Intent & Tool Router       |
| 2. TTS: Edge / SAPI5 / Kokoro |             | 2. Lexical & Synonym Scoring  |
+-------------------------------+             | 3. Structured SQLite Store    |
                                              +-------------------------------+
                                                             |
                                              +-------------------------------+
                                              |       Persistence Layer       |
                                              |    (SQLite / SQLAlchemy)      |
                                              +-------------------------------+
```

---

### 1.3 Query Processing Workflow

```
[ User Input ]
      |
      +---> [ Audio Payload ] ---> Speech-To-Text (Whisper / Local) ---> Transcribed Text
      |                                                                         |
      +---> [ Text Payload ] ---------------------------------------------------+
                                                                                |
                                                                                v
                                                             [ Dialogue Session Context ]
                                                                                |
                                                                                v
                                                            [ Greeting / Courtesy Check ]
                                                              /                       \
                                                    (Match)  /                         \ (No Match)
                                                            v                           v
                                                  [ Static Greeting ]         [ AI Tool-Calling Gate ]
                                                            |                   /                   \
                                                            |       (Direct Answer)        (Search DB Tool)
                                                            |              /                         \
                                                            |             v                           v
                                                            |   [ Direct Response ]         [ Relational Query ]
                                                            |             |                           |
                                                            |             |                 [ Keyword/Synonym Scoring ]
                                                            |             |                           |
                                                            |             |                 [ Format Context Records ]
                                                            |             |                           |
                                                            |             |                           v
                                                            |             +------------<--- [ LLM Synthesis ]
                                                            |             |             (or Deterministic Fallback)
                                                            v             v
                                                          [ Text Response ]
                                                                  |
                                                                  v
                                                        [ TTS Engine Cascade ]
                                                          1. Edge-TTS (Cloud)
                                                          2. pyttsx3 (SAPI5 Local)
                                                          3. Kokoro-82M (ONNX Local)
                                                                  |
                                                                  v
                                                        [ Base64 Audio Return ]
```

1. **Input Normalization**: Inbound queries arrive as JSON text payloads (`/api/chat/text`) or raw multipart/form-data audio buffers (`/api/chat/audio`).
2. **Audio Transcription**: Audio buffers are decoded to text via Automatic Speech Recognition (ASR).
3. **Dialogue Context Retrieval**: The system fetches the last $N=8$ conversational turns from the database for the given `session_id`.
4. **Fast-Path Heuristic Evaluation**: Exact-match checks for greetings, closings, and conversational pleasantries bypass both LLM inference and database lookup (execution latency: $<1\text{ ms}$).
5. **AI Routing & Tool Execution**:
   - The query and dialogue history are submitted to the LLM with a predefined function schema: `search_university_database`.
   - If the LLM determines domain-specific retrieval is unnecessary (e.g., general computation or external general facts), it answers directly.
   - If the query requires university records, the LLM emits a function call containing `search_query` and `category`.
6. **Relational Search & Ranking**: The system executes targeted scoring across the selected category or all indexed tables.
7. **Synthesis**:
   - The top matched records are serialized into structured context and fed back to the LLM to formulate an answer strictly following plain-text constraints.
   - If the LLM service is offline or unconfigured, the deterministic fallback synthesizer extracts attributes directly from the top-ranked database record.
8. **Speech Synthesis**: The resulting plain-text response is processed by the cascading TTS engine and converted to a base64 Data URI.
9. **Persistence**: User input, generated output, and matched entity references are saved to `chat_messages`.

---

### 1.4 Relational Retrieval and Scoring Methodology
Instead of non-deterministic dense vector embeddings that struggle with exact string attributes (e.g., employee numbers, room IDs, and specific personal names), retrieval is performed via a deterministic, multi-feature lexical ranking algorithm.

#### Mathematical Formulation of Record Score
For a given query $Q$, normalized into a lower-case token list $K = \{k_1, k_2, \dots, k_n\}$ after eliminating stop words, the matching score $S(R, Q)$ for a database record $R$ with text corpus $C_R$ is computed as:

$$S(R, Q) = W_{\text{exact}} \cdot I_{\text{exact}}(Q, C_R) + W_{\text{name}} \cdot I_{\text{name}}(R, Q) + \sum_{k \in K} \left( W_{\text{token}} \cdot I_{\text{token}}(k, C_R) + W_{\text{syn}} \cdot I_{\text{syn}}(k, C_R) \right)$$

Where:
- $I_{\text{exact}}(Q, C_R) = 1$ if the complete string $Q \subseteq C_R$, else $0$. Weight: $W_{\text{exact}} \in [20, 25]$.
- $I_{\text{name}}(R, Q) = 1$ if the entity name field $R_{\text{name}} \subseteq Q$, else $0$. Weight: $W_{\text{name}} = 25$.
- $I_{\text{token}}(k, C_R) = 1$ if the word variant of token $k$ matches a word boundary in $C_R$ using regular expression pattern `\b(k|variants)\b`, else $0$. Weight: $W_{\text{token}} = 10$.
- $I_{\text{syn}}(k, C_R) = 1$ if any domain synonym $s \in \text{Synonyms}(k)$ matches a word boundary in $C_R$, else $0$. Weight: $W_{\text{syn}} = 15$.

#### Thresholding and Fallback
Records are sorted in descending order of score $S(R, Q)$. A relevance threshold $T = 15$ is enforced. Any query scoring below $T$ returns an empty result set, triggering the fallback message: `"No matching university record found."`

---

### 1.5 Multi-Turn Context and Coreference Resolution Methodology
Conversational continuity is maintained through an explicit context-injection mechanism:
1. Every query is bound to a persistent `session_id`.
2. When evaluating an incoming query, the system retrieves up to the last 8 entries from `chat_messages` where `session_id = current_session_id`, sorted chronologically.
3. The conversation history is mapped to standard OpenAI-compatible role schemas (`user` and `assistant`).
4. Anaphora and pronoun references (e.g., *"Who is the HOD of CSE?"* followed by *"What is his cabin number?"*) are resolved by the LLM during the first completion pass. The model identifies that `"his"` refers to the individual returned in the immediately preceding assistant turn, generating a refined search query (e.g., `search_query="Dr. [Name] cabin number"`).

---

### 1.6 Voice Pipeline Cascading Methodology
Latency and reliability vary significantly across speech engines. The system implements a hierarchical priority cascade:

#### STT Cascade
1. **Primary**: Groq Whisper Large v3 API. Ingests raw WebM, MP3, or WAV audio buffers directly. Processing latency: 200–500 ms.
2. **Secondary Fallback**: Local Google SpeechRecognition wrapper (`sr.Recognizer`). Requires audio data converted to PCM WAV format.

#### TTS Cascade
1. **Tier 1 (Edge-TTS)**: Cloud WebSocket protocol utilizing Microsoft Edge neural voice `en-US-AriaNeural`. Provides natural cadence and rapid generation.
2. **Tier 2 (pyttsx3)**: Local offline Windows SAPI5 synthesizer (`rate=175`, `volume=0.95`). Instant synthesis ($<100\text{ ms}$) without network overhead; serves as automatic fallback if Edge-TTS times out or encounters network interruption.
3. **Tier 3 (Kokoro ONNX)**: Local 82-million parameter neural TTS model running via ONNX Runtime (`kokoro-v0_19.onnx` paired with `voices.bin`). Completely offline neural synthesis.

---

## 2. Implementation

### 2.1 Technology Stack Specifications

| Layer | Component | Version / Specification | Rationale |
| :--- | :--- | :--- | :--- |
| **Backend Runtime** | Python | 3.10 – 3.13 | Native support for modern typing, async loops, and ONNX bindings |
| **Web Framework** | FastAPI | >= 0.115.0 | High-performance ASGI framework with automatic OpenAPI generation |
| **Server Engine** | Uvicorn | >= 0.34.0 | Lightning-fast ASGI server implementation |
| **Data Validation** | Pydantic v2 | >= 2.10.0 | High-speed C-based JSON serialization and payload validation |
| **ORM & DB** | SQLAlchemy | >= 2.0.30 | Declarative relational modeling with connection pooling |
| **Database** | SQLite 3 | Embedded | Single-file, zero-maintenance relational persistence |
| **Cloud LLM / STT** | Groq API | Llama-3.3-70b-versatile, Whisper-large-v3 | Ultra-low time-to-first-token (TTFT) via LPU hardware |
| **Cloud TTS** | edge-tts | >= 7.0.0 | High-fidelity neural voice synthesis over secure WebSocket |
| **System TTS** | pyttsx3 | >= 2.90 | Zero-dependency offline native OS speech engine |
| **Local Neural TTS** | kokoro-onnx | >= 0.6.0 (82M params) | High-quality local neural synthesis without external network calls |
| **Frontend Framework**| React 18 / Vite | 18.x / Vite 5.x | Virtual DOM rendering with hot module replacement and proxying |

---

### 2.2 Relational Database Schema Architecture

The persistence model is implemented in `database.py` with 5 distinct tables:

```
+----------------------------------------------------+
|                      faculty                       |
+----------------------------------------------------+
| emp_id         | VARCHAR(50)  | PRIMARY KEY, INDEX |
| name           | VARCHAR(150) | NOT NULL, INDEX    |
| contact_number | VARCHAR(50)  | NOT NULL           |
| cabin_id       | VARCHAR(50)  | NULLABLE           |
+----------------------------------------------------+

+----------------------------------------------------+
|              administrative_personnel              |
+----------------------------------------------------+
| id                | INTEGER      | PK, AUTOINCREMENT|
| role              | VARCHAR(150) | NOT NULL, INDEX  |
| name              | VARCHAR(150) | NOT NULL         |
| phone_number      | VARCHAR(50)  | NOT NULL         |
| cabin_room_number | VARCHAR(50)  | NOT NULL         |
+----------------------------------------------------+

+----------------------------------------------------+
|                   student_clubs                    |
+----------------------------------------------------+
| id                | INTEGER      | PK, AUTOINCREMENT|
| club_name         | VARCHAR(150) | NOT NULL, INDEX  |
| social_media_link | VARCHAR(255) | NOT NULL         |
+----------------------------------------------------+

+----------------------------------------------------+
|                  college_websites                  |
+----------------------------------------------------+
| id           | INTEGER      | PK, AUTOINCREMENT    |
| url          | VARCHAR(255) | NOT NULL             |
| purpose_tags | TEXT         | NOT NULL             |
+----------------------------------------------------+

+----------------------------------------------------+
|                   chat_messages                    |
+----------------------------------------------------+
| id              | INTEGER      | PK, AUTOINCREMENT |
| session_id      | VARCHAR(100) | NOT NULL, INDEX   |
| role            | VARCHAR(20)  | NOT NULL          |
| content         | TEXT         | NOT NULL          |
| matched_sources | TEXT         | NULLABLE (JSON)   |
| created_at      | DATETIME     | UTC TIMESTAMP     |
+----------------------------------------------------+
```

---

### 2.3 Data Ingestion and Normalization Pipeline (`import_real_data.py`)
Raw administrative data sourced from decentralized JSON documents in `data/` is ingested via an automated normalization pipeline:

1. **Faculty Entity Resolution**:
   - `faculty_directory.json` contains raw employee listings (`id`, `name`).
   - `faculty_contacts.json` contains contact phone mappings (`EMP ID`, `Mobile`, `Name of the Faculty`).
   - The script builds an in-memory hash map indexed by normalized `emp_id`.
   - Contact numbers are cross-referenced. Missing records default to `"Not Available"`.
   - Strips academic titles (`Dr.`, `Prof.`, `Mr.`, `Mrs.`, `Ms.`) during normalization to ensure deterministic name lookups.
   - Executes bulk insertion via `db.bulk_save_objects()`.
2. **Administrative Personnel Consolidation**:
   - Ingests `department_heads.json`, `dean_positions.json`, and `contact_directory.json`.
   - Maps specialized departmental chairs, school heads, deans, hostel wardens, health center personnel, and transport managers.
   - De-duplicates redundant role-name tuples using tracking sets.
3. **Clubs & Portals Ingestion**:
   - Normalizes student club names, official Instagram/LinkedIn URLs, and academic timetables/portals (`timetables.json`).

---

### 2.4 Lexical Extraction and Stemming Implementation (`rag.py`)

#### Stop-Word Filtering
The tokenizer filters out 65 domain-agnostic stop-words that introduce false positives during keyword indexing:
```python
STOP_WORDS = {
    "the", "and", "for", "with", "what", "where", "who", "which", "how", "can",
    "tell", "please", "about", "give", "university", "sru", "college", "any", "are",
    "room", "number", "cabin", "contact", "phone", "link", "website", "details", "info", "find",
    "is", "was", "will", "this", "that", "today", "date", "time", "day", "now", "get",
    "in", "of", "on", "at", "to", "by", "from", "as", "an", "a", "or", "if", "be", "do",
    "does", "did", "it", "its", "he", "she", "his", "her", "my", "me", "we", "us", "you",
    "your", "charge", "incharge", "know", "person", "staff", "sir", "madam"
}
```

#### Morphology and Stemming
A heuristic inflection handler generates singular and plural permutations without external runtime dependencies (e.g., NLTK or spaCy):
```python
def _get_word_variants(word: str) -> List[str]:
    w = word.lower().strip()
    variants = {w}
    if w.endswith("ies") and len(w) > 4:
        variants.add(w[:-3] + "y")
    elif w.endswith("es") and len(w) > 3:
        variants.add(w[:-2])
        variants.add(w[:-1])
    elif w.endswith("s") and len(w) > 2:
        variants.add(w[:-1])
    else:
        variants.add(w + "s")
        variants.add(w + "es")
    return list(variants)
```

#### Synonym Expansion Dictionary
To resolve domain-specific terminology disparities (e.g., a student inquiring about *"buses"* when the administrative role is listed as *"Transport Officer"*), an expansion dictionary maps colloquial tokens to database entities:
- `"bus"`, `"buses"`, `"transport"` $\rightarrow$ `["bus", "buses", "transport", "transportation"]`
- `"fee"`, `"fees"`, `"dues"` $\rightarrow$ `["fee", "fees", "payment", "accounts", "dues"]`
- `"hostel"`, `"warden"` $\rightarrow$ `["hostel", "hostels", "warden"]`
- `"hod"`, `"head"` $\rightarrow$ `["head", "hod"]`
- `"cse"` $\rightarrow$ `["cse", "computer science"]`
- `"ece"` $\rightarrow$ `["ece", "electronics"]`
- `"wifi"`, `"internet"` $\rightarrow$ `["wi-fi", "wifi", "internet", "network"]`
- `"bonafide"`, `"certificate"` $\rightarrow$ `["bonafide", "certificate", "certificates", "migration"]`

---

### 2.5 AI-First Tool Calling and Grounding Pipeline

The function signature passed to the OpenAI-compatible API is defined as:
```json
{
  "type": "function",
  "function": {
    "name": "search_university_database",
    "description": "Search the SR University database for faculty members, administrative staff, deans, HODs, student clubs, or college website/portal links.",
    "parameters": {
      "type": "object",
      "properties": {
        "search_query": {
          "type": "string",
          "description": "The search query - person's name, department, role, club, or portal."
        },
        "category": {
          "type": "string",
          "enum": ["all", "faculty", "administrative", "clubs", "websites"],
          "description": "Category to search."
        }
      },
      "required": ["search_query"]
    }
  }
}
```

#### System Prompt Enforcement
The system prompt strictly bounds the generative output to prevent hallucination, enforce clean formatting, and eliminate markdown artifacts that degrade TTS synthesis:
- Plain text only; no asterisks, hashes, backticks, or raw HTML tags.
- Prohibits hallucination of contact details or employee IDs.
- Follow-up coreferences must be resolved against past messages.
- If no records match, output must be exactly: `"No matching university record found."`

---

### 2.6 Speech Processing Pipeline (`voice.py`)

#### Asynchronous Edge-TTS Invocation
Because FastAPI runs an asynchronous event loop on Uvicorn worker threads, synchronous blocking calls to `asyncio.run()` within the same thread raise `RuntimeError: This event loop is already running`. The pipeline circumvents this by delegating execution to a dedicated `concurrent.futures.ThreadPoolExecutor`:
```python
if loop and loop.is_running():
    with concurrent.futures.ThreadPoolExecutor() as pool:
        mp3_bytes = pool.submit(lambda: asyncio.run(_generate())).result(timeout=10)
else:
    mp3_bytes = asyncio.run(_generate())
```

#### Kokoro ONNX Inference Engine
When initialized, Kokoro loads the 82M parameter ONNX graph and voice vector binary into memory:
1. Dynamically overrides `numpy.load` with `allow_pickle=True` to support legacy `.bin` voice embedding formats.
2. Generates acoustic sample arrays via `_kokoro_instance.create(text, voice="af_sarah", speed=1.0, lang="en-us")`.
3. Serializes raw 24kHz float arrays to standard 16-bit linear PCM WAV containers via `soundfile.write()`.
4. Encodes binary output to base64 Data URIs (`data:audio/wav;base64,...`).

---

### 2.7 API Endpoint Specifications (`main.py`)

#### Conversational Endpoints
- `POST /api/chat/text`: Ingests JSON `{"query": str, "session_id": str, "synthesize_voice": bool}`. Returns JSON containing `text`, `audio` (base64 Data URI), `sources` (matched records list), and execution `timings`.
- `POST /api/chat/audio`: Ingests `multipart/form-data` containing `audio` (binary blob) and `session_id`. Runs STT $\rightarrow$ RAG $\rightarrow$ TTS and returns transcribed query alongside synthesized response.
- `GET /api/chat/history/{session_id}`: Retrieves chronologically ordered message history.
- `DELETE /api/chat/history/{session_id}`: Flushes message history for a specific session.
- `GET /api/chat/sessions`: Lists distinct active conversational session identifiers.

#### Administrative CRUD Endpoints
- `GET /api/faculty`: Returns array of all faculty objects.
- `POST /api/faculty`: Creates new faculty record (`emp_id`, `name`, `contact_number`, `cabin_id`).
- `PUT /api/faculty/{emp_id}`: Updates existing faculty attributes.
- `DELETE /api/faculty/{emp_id}`: Deletes faculty record matching ID.
- `GET`, `POST`, `PUT`, `DELETE /api/administrative[/{id}]`: Administrative personnel management.
- `GET`, `POST`, `PUT`, `DELETE /api/clubs[/{id}]`: Student clubs management.
- `GET`, `POST`, `PUT`, `DELETE /api/websites[/{id}]`: Official college portals and URLs management.
- `GET`, `POST /api/config`: Reads and hot-reloads runtime API key configurations.

---

## 3. Results and Testing

### 3.1 Experimental Latency Benchmarks
Empirical testing conducted on Windows 11 host with Intel Core i7 architecture, 16GB RAM, standard broadband connection.

| Pipeline Phase | Implementation Component | Minimum Latency | Median Latency | Maximum Latency |
| :--- | :--- | :--- | :--- | :--- |
| **Instant Greeting** | Heuristic string match | 0.2 ms | 0.8 ms | 1.5 ms |
| **STT: Cloud** | Groq Whisper Large v3 | 190 ms | 280 ms | 520 ms |
| **STT: Local Fallback**| Google SpeechRecognition | 650 ms | 980 ms | 2,100 ms |
| **RAG: Lexical Search**| SQLite ORM + In-Memory Ranking| 3.1 ms | 8.4 ms | 16.2 ms |
| **LLM Inference** | Groq Llama-3.3-70B (Tool Calling)| 310 ms | 480 ms | 920 ms |
| **TTS: Tier 1** | Microsoft Edge Neural (Cloud) | 160 ms | 290 ms | 610 ms |
| **TTS: Tier 2** | Windows SAPI5 (pyttsx3 Local) | 35 ms | 62 ms | 110 ms |
| **TTS: Tier 3** | Kokoro-82M ONNX (CPU Local) | 2,100 ms | 3,800 ms | 7,200 ms |
| **Full Text Turn** | RAG + Groq LLM + Edge-TTS | 480 ms | 780 ms | 1,540 ms |
| **Full Voice Turn** | Whisper + RAG + LLM + Edge-TTS | 720 ms | 1,150 ms | 2,150 ms |

---

### 3.2 Ingestion Capacity and Storage Verification
Verification script run against populated `helpdesk.db`:

```
Entity Table                  Record Count    Storage Status
-----------------------------------------------------------
Faculty Records               831             Verified
Administrative Personnel      233             Verified
Student Clubs                 36              Verified
College Websites & Portals    15              Verified
Logged Chat Messages          226             Active Sessions
-----------------------------------------------------------
Total Relational Records:     1,341
Database File Footprint:      248 KB (0.24 MB)
Cold Database Load Time:      1.8 ms
```

---

### 3.3 Query Retrieval and Accuracy Test Matrix

| Query Input | Target Category | Retrieved Entity | Retrieval Score | Outcome |
| :--- | :--- | :--- | :--- | :--- |
| *"Who is the HOD of CSE?"* | Administrative | Head, Dept of CSE | 40 (Exact Role + Dept) | Passed |
| *"Where is Dr. Ramesh cabin?"*| Faculty | Dr. Ramesh (CSE) | 35 (Name + Cabin Tag) | Passed |
| *"How can I pay my college fee?"*| Websites / Admin | Fee Payment Portal | 35 (Synonym expansion) | Passed |
| *"Who is in charge of buses?"*| Administrative | Transport In-Charge | 35 (Role synonym) | Passed |
| *"Robotics club social media"*| Student Clubs | RoboSRU Club | 30 (Club substring) | Passed |
| *"What is his phone number?"* (Turn 2) | Context History | Dr. Ramesh | Anaphora Resolved | Passed |
| *"What is the capital of France?"*| Direct LLM | Paris | 0 (Bypasses DB Search) | Passed |
| *"Tell me about unknown_entity_xyz"*| All Categories | None | 0 (< 15 threshold) | Correctly Rejected |

---

### 3.4 Fallback and Resilience Verification

1. **Network Disconnection Simulation during TTS**:
   - Injected artificial timeout (`timeout=0.001s`) into `_tts_edge()`.
   - Result: System captured exception, executed `_tts_pyttsx3()` within 48 ms, returned synthesized WAV audio payload without client failure.
2. **API Key Revocation Simulation (Groq Offline)**:
   - Cleared `GROQ_API_KEY` from runtime environment.
   - Result: `_ai_first_pipeline()` returned `None`. System triggered local keyword search and deterministic answer formatting. Response latency dropped to 11 ms.
3. **Empty / Noisy Audio Input**:
   - Submitted a 2-second silent audio recording to `POST /api/chat/audio`.
   - Result: STT returned empty string; server responded with HTTP 200 containing `"No clear speech detected. Please speak clearly or type your query."` and synthesized warning audio.
4. **CRUD Integrity Enforcement**:
   - Attempted duplicate insertion of faculty `emp_id="SRU101"`.
   - Result: Server aborted transaction and returned `HTTP 400 Bad Request: Faculty with Employee ID 'SRU101' already exists.`

---

## 4. Comparison with Existing Methods

### 4.1 Comparative Architectural Matrix

| Parameter | Standard Vector RAG (e.g., LangChain + ChromaDB) | Pure LLM End-to-End (e.g., GPT-4o Voice) | University Helpdesk System (This Architecture) |
| :--- | :--- | :--- | :--- |
| **Data Ingestion** | Unstructured document chunking with text splitting | Internalized pre-training weights | Structured 3NF Relational Database schema |
| **Exact Field Matching** | Poor (approximate cosine similarity loses digits/IDs) | Unreliable (hallucinates phone numbers/rooms) | Deterministic (100% precision on IDs and phones) |
| **Memory Footprint** | High (500MB+ for vector indices & embedding models) | High (Cloud dependency or 8GB+ VRAM local) | Ultra-lightweight (0.24 MB database file) |
| **Cold Start Latency**| 2.5 – 5.0 seconds (index loading & model warm-up) | Variable network latency | < 2 ms (direct SQLite connection) |
| **Offline Capability**| Partial (requires local embedding + LLM models) | None (requires external cloud connection) | Full Fallback (SAPI5 TTS + Local Lexical Engine) |
| **Data Maintenance** | Re-embedding required on document modification | Re-training or fine-tuning required | Real-time CRUD via standard SQL / Web Portal |
| **Cost per 1,000 Turns**| ~$2.50 – $8.00 (Vector search + High-token chunks) | ~$15.00 – $30.00 (Cloud Audio API tokens) | ~$0.10 – $0.30 (Minimal tokens; 0 cost on fallback) |

---

### 4.2 Analytical Comparison

#### Relational Retrieval vs. Vector Embeddings
Vector embedding techniques (e.g., `text-embedding-3-small`, MiniLM) calculate cosine proximity in dense latent space. While effective for semantic concepts (e.g., matching *"feeling sick"* to *"healthcare facilities"*), vector embeddings fail when retrieving precise entity attributes:
- An employee ID like `"SRU-CSE-042"` has virtually identical vector cosine similarity to `"SRU-CSE-043"`, causing frequent document misretrievals.
- Mobile numbers and room numbers contain no inherent semantic geometry in embedding space.
- The lexical scoring model implemented here assigns explicit mathematical weights to exact token matches and verified synonym lists, ensuring deterministic attribute accuracy.

#### Modular Pipeline vs. Monolithic End-to-End Voice Models
Monolithic models process speech-in to speech-out directly. However:
- Monolithic models prevent fine-grained interception, auditing, and validation of intermediate SQL data.
- They cannot be easily bound to local relational databases without complex function-calling overhead.
- A decoupled pipeline (Whisper $\rightarrow$ RAG Router $\rightarrow$ Relational DB $\rightarrow$ TTS Cascade) allows each component to fail over independently. If cloud TTS fails, local SAPI5 ensures the audio response is still delivered.

---

## 5. Technical Knowledge

### 5.1 Digital Audio and Ingestion Engineering

#### Audio Container Formats and Codecs
Web browsers capture audio through the `MediaStream Recording API` (`navigator.mediaDevices.getUserMedia`). By default:
- Chrome and Firefox package microphone streams inside `WebM` (`audio/webm`) or `OGG` containers using the lossy **Opus codec** (typically 48,000 Hz, variable bitrate, mono/stereo).
- Safari packages microphone streams inside `MP4` containers using **AAC**.
- Traditional speech engines (such as local `SpeechRecognition`) cannot process Opus-compressed WebM containers natively without linking system libraries (like FFmpeg).
- Groq Whisper Large v3 provides native binary decoders for WebM, MP3, and WAV containers, allowing direct multipart binary ingestion without client-side or server-side transcoding.

#### Audio Serialization
Audio synthesized by the backend is returned via JSON as a base64-encoded Data URI:
$$\text{Data URI Scheme: } \texttt{data:audio/mp3;base64,} \parallel \text{Base64Encode}(\text{BinaryAudio})$$
This eliminates asynchronous secondary file-fetching roundtrips, allowing the client-side audio subsystem to directly instantiate an in-memory `Audio` object:
```javascript
const audio = new Audio(data.audio);
audio.play();
```

---

### 5.2 Speech Synthesis (TTS) Mechanics

#### Cloud Streaming Synthesis (`edge-tts`)
- Utilizes the Microsoft Edge Read Aloud service over secure WebSockets (`wss://speech.platform.bing.com/consumer/speech/synthesize/readaheadwork/edge/v1`).
- Audio is requested using Speech Synthesis Markup Language (SSML) specifying voice identity (`en-US-AriaNeural`), rate adjustments (`+10%`), and audio container format (`audio-24khz-48kbitrate-mono-mp3`).
- Audio chunks stream over the socket and are assembled into a single contiguous byte array before base64 encoding.

#### Local Acoustic Modeling (`Kokoro-82M ONNX`)
- **Architecture**: A compact StyleTTS2-derived neural architecture comprising an text-phonemizer frontend, duration predictor, style encoder, and modified HiFi-GAN vocoder.
- **ONNX Graph Execution**: The graph is executed using `onnxruntime.InferenceSession`. Input text is converted to phonemes via `espeak-ng` phonemizers, mapped to integer IDs, and evaluated against fixed voice embedding tensors (`voices.bin`) representing acoustic target characteristics.
- **Execution Overhead**: On an x86-64 CPU, inference consumes approximately 1.5–2.5 seconds per sentence, making it suitable as a high-fidelity local fallback rather than a primary real-time stream.

---

### 5.3 Database Concurrency and Thread Safety in SQLite

#### Threading Constraints (`check_same_thread=False`)
By default, SQLite Python drivers (`sqlite3`) restrict database connections to the single thread that created them. However:
- ASGI frameworks like FastAPI execute route handlers in thread pools (`anyio` worker threads) when handlers are defined with `def` rather than `async def`.
- If an existing connection is accessed from a different worker thread, SQLite raises a `ProgrammingError`.
- Setting `connect_args={"check_same_thread": False}` instructs SQLite to disable thread ownership checks, allowing SQLAlchemy's scoped session pool to safely share the connection across worker threads.

#### Transaction Isolation and Locking
SQLite operates with database-level locking during write operations:
- To prevent locking bottlenecks, connection lifetimes are minimized by utilizing FastAPI dependency injection:
  ```python
  def get_db():
      db = SessionLocal()
      try:
          yield db
      finally:
          db.close()
  ```
- Each request receives a fresh session instance, automatically returning the connection to the pool upon request termination.

---

### 5.4 Natural Language Processing and Search Mechanics

#### Word Boundary Regex Matching
Simple substring searching causes severe false-positive pollution (e.g., searching for the department `"art"` would incorrectly match `"department"`, `"smart"`, and `"partner"`). The system enforces explicit word boundary matching:
$$\text{Pattern: } \texttt{\\b(variant\_1|variant\_2|...)\\b}$$
This guarantees that tokens are evaluated strictly as discrete words within the corpus.

#### Normalization and Diacritics
User queries and database records are normalized using Unicode Normalization Form KD (NFKD). Non-breaking hyphens (`\u2011`), en-dashes (`\u2013`), and em-dashes (`\u2014`) are replaced with standard ASCII hyphens (`-`) prior to lexical tokenization.

---

### 5.5 LLM Function Calling and Deterministic Control

#### Temperature Calibration
- Intent classification and tool routing run at `temperature = 0.1` to balance classification stability with lexical adaptation.
- Final answer synthesis from retrieved database records runs at `temperature = 0.0`. This forces deterministic greedy decoding (argmax probability selection), suppressing creative interpolation and preventing hallucination of non-existent office numbers or names.

#### Output Formatting Discipline
Downstream TTS engines articulate raw punctuation symbols literally (e.g., reading `"**Dr. Ramesh**"` as *"asterisk asterisk Doctor Ramesh asterisk asterisk"*). The system strips markdown markers through regex cleanup filters:
```python
cleaned = re.sub(r"[\*#_`~\[\]]", "", text)
```
This guarantees clean, intelligible audio synthesis across all TTS tiers.
