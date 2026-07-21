# Clinical Data Generator (v8.1)

> **Automated Synthetic Healthcare Data Pipeline**
> Generates high-fidelity clinical PDFs and FHIR-compliant personas for testing Prior Authorization workflows.

---

## 🌟 Core Features

### 1. Patient Persona Synthesis (FHIR-compliant)
- **Texas-Constrained Demographics**: Restricts all patient names, dates of birth, emergency contacts, hospital facilities, and ZIP codes to realistic values within Texas, USA.
- **Biometric Profiles**: Synthesizes complete patient demographics, physical attributes (height, weight, race, gender), and primary provider details.
- **Structured Clinical State**: Maintains persistent records for medications, allergies, vaccination records, encounters, and diagnoses.

### 2. Clinical Report Synthesis
- **Template-Driven ReportLab PDF Renderer**: Programmatically converts structured case data into medical-grade clinical reports (Consultation Notes, imaging reports, lab results).
- **Medical Content Intensity**: Restricts generation to high-value medical justifications (detailed multi-sentence findings, objective measurements, clinical reasoning), preventing sparse summaries.
- **Coherence Enforcement**: Evaluates cross-document reference consistency. Dates, provider NPIs, and clinical details match the primary persona across all outputs.

### 3. Prior Authorization (PA) & Gap Injection
- **PA Optimization Toggle**: Automatically adjusts clinical details to strengthen the medical justification, raising the approval probability score.
- **Probabilistic Gap Injection System**: When case outcome is set to Denial/Rejection, the system applies a gap injection protocol. It samples 2–4 gap archetypes across 5 clinical dimensions (Profile-Behavior, Temporal-Sequence, Treatment-Escalation, Cross-Document, Policy-Criteria) to construct realistic, hard-to-detect inconsistencies without leaving blank fields.
- **Medications as First-Class Targets**: Automatically intercepts J/Q-prefixed HCPC medication drug codes (e.g. `J0897`, `Q5124`) and routes them to specialized medication prompt structures (step-therapies, failed trials, and lab markers).
- **Supporting Documents Cap**: Intelligently caps supporting documents (e.g., radiology/specialist consults) to a maximum of 5, preserving core documents (PA Requests and Summaries).

### 4. Patient Tracker CSV Exporter
- **Excel-Safe Exporter**: Compiles Prior Authorization metrics for selected patients into a unified 12-column spreadsheet report (`patient_tracker_export.csv`).
- **Formula Injection Protection**: Automatically sanitizes potential formula injection attempts by prepending a single quote (`'`) to values starting with `=`, `+`, `-`, or `@`.
- **Sanitized Multiline Layouts**: Removes all HTML markup tags from cell contents, replacing them with Excel-friendly newlines (`\n`) and plain bullets (`- `).

### 5. Visual Scan Simulation Filter
- **Rasterized Image Filter**: Flat-renders vector PDFs to flat, image-only documents using `PyMuPDF` (`fitz`), Pillow, and NumPy, making them look physically scanned.
- **Adjustable Degradation Artifacts**: Features Light, Medium, and Heavy presets simulating feeding skews, sensor noise, light gradient shadows, lens blur, dust speckles, and aged paper tints.

### 6. Concise Clinical Summary
- Generates a 5-part summary for case evaluators:
  1. **Test Case and Overview** — Basic profile and case description.
  2. **Details from Extraction** — Insurance payer metadata and CPT/ICD code expectations.
  3. **Likelihood without Supporting Documents** — Baseline outcome probability.
  4. **Likelihood PA Score Change** — Impact assessment of each supporting report.
  5. **Overall Summary & Pointers** — Manual verification checklist.

### 7. Multi-User Concurrency
- **Thread-Safe Logging Proxy**: Uses `ThreadSafeStdout` to capture standard print statements and route them to matching `job_id` log buffers for concurrent browser sessions.
- **Patient-Level Isolation**: Restricts concurrent jobs for the same `patient_id` using a registry, preventing race conditions while allowing different patients to compile in parallel.

---

## 🏗️ System Architecture & Technology Stack

### Core Principle: Single Source of Truth
All documents derive from `patient_state`, a canonical patient data model loaded from UAT Excel definitions, state managers, and database layers. This prevents timeline drift and inconsistent demographics.

### Technology Stack
- **Backend Orchestrator**: Python 3.10+
- **Web App API Layer**: Flask REST API (integrated with Swagger OpenAPI documentation)
- **PDF Layout Engines**: ReportLab PDF library
- **PDF Post-Processing**: PyMuPDF (`fitz`), Pillow, and NumPy (Visual Scan filter)
- **Medical Code Search**: Tavily Search Engine API (retrieves CPT/ICD code descriptions)
- **LLM Pipeline Clients**: OpenAI (`gpt-4o`, `gpt-4o-mini`) & Vertex AI (`gemini-2Pro`, `gemini-2Flash`)

### Decoupled Storage Layer
Supports two repository backends toggled via `PATIENT_STORAGE_BACKEND`:
1. **JSON Backend**: (Default) Saves data to `src/core/patients_db.json`.
2. **PostgreSQL Backend**: Optimizes reads/writes using B-tree indices on patient names/dates of birth and a GIN index on `persona_data` (JSONB). Initialized via schema DDL at `src/core/schema.sql`.

### Directory Structure
```text
pdgenerator/
├── cred/                       # Credentials & environment configuration (.env)
├── core/                       # Reference case data (Excel plan, code maps)
├── config/                     # Externalized rules & pattern configurations
├── templates/                  # PDF layouts and planner rule schemas
├── generated_output/           # Generated files (gitignored)
│   ├── patient-data/           # Per-patient documents and folders
│   ├── archive/                # Archived/past generated versions
│   ├── logs/                   # Log streams and history logs
│   ├── metadata/               # Patient text records (-record.txt)
│   ├── summary/                # Dedicated clinical summary PDFs
│   └── debug/                  # Debug patient_state JSON logs
├── ui/
│   └── index.html              # Interactive dark web interface (Material You)
├── src/
│   ├── ai/                     # LLM client, prompts, models, and Tavily search
│   ├── core/                   # Patient DB, state, and config setup
│   ├── data/                   # Excel loaders, history tracking, records
│   ├── doc_generation/         # PDF planner, validator, and tracker exporters
│   ├── utils/                  # Date parsing, versioning, and purge managers
│   ├── cli.py                  # Terminal interactive entrypoint
│   └── workflow.py             # Core pipeline orchestrator
├── api_server.py               # Flask REST API (port 410)
├── run.py                      # Interactive CLI launcher
├── compact_patient_data.py     # Log and history compaction CLI
└── remove_persona.py           # Deep persona removal utility
```

### Core File Reference
- `src/workflow.py` — Orchestrates data load, LLM calls, document validation, and PDF output.
- `src/utils/purge_manager.py` — Cleans up folders, records, and database rows.
- `src/doc_generation/patient_tracker_export.py` — Formats and writes the CSV export.
- `src/ai/client.py` — Handles API interfaces with OpenAI and Vertex AI.
- `src/ai/prompts.py` — Central prompt definitions and gap archetype pools.

---

## ⚙️ Setup & Execution

### 1. Prerequisites
- Python 3.10+
- OpenAI API Key **or** Google Cloud Vertex AI credentials

### 2. Platform-Independent Launch
Launch scripts are provided for automatic installation and bootstrapping:
- **Web UI Mode**:
  - **Windows**: Run `run_api.bat`
  - **macOS / Linux**: Run `chmod +x run_api.sh && ./run_api.sh`
- **CLI Mode**:
  - **Windows**: Run `run.bat`
  - **macOS / Linux**: Run `chmod +x run.sh && ./run.sh`
  - **Direct (Any OS)**: `python run.py`

### 3. Manual Installation (If scripts fail)
```bash
# Clone the repository
cd pdgenerator

# Initialize virtual environment
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 4. Configuration Setup (`cred/.env`)
Copy the template configuration file:
```bash
# Mac/Linux
cp cred/.env.example cred/.env

# Windows
copy cred\.env.example cred\.env
```
Fill in the credentials in `cred/.env`:
```ini
LLM_PROVIDER=openai # openai or vertexai
OPENAI_API_KEY=your_openai_api_key_here

# For Vertex AI:
GCP_PROJECT_ID=your_gcp_project_id_here
GOOGLE_APPLICATION_CREDENTIALS=./cred/gcp_auth_key.json

OUTPUT_DIR=./generated_output
API_PORT=410
ENABLE_WEB_SEARCH=true
TAVILY_API_KEY=your_tavily_api_key_here

# Database backend selection:
PATIENT_STORAGE_BACKEND=json # json or postgres
DB_SCHEMA=pdgenerator
```

### 5. Interactive CLI Launcher
Run `python run.py` to open the terminal-based interactive CLI:
- **`[Patient ID]`**: Runs generation for a single patient (e.g. `210`).
- **`[ID]-[feedback]`**: Runs generation with specific guidance (e.g. `225-use kidney transplant`).
- **`[ID],[ID],[ID]`**: Batch mode for specific IDs (e.g. `221,222,223`).
- **`*`**: Compiles missing patients from the Excel plan.
- **`q`** / **`exit`**: Exits CLI.

### 6. Standalone CLI Utilities

#### Persona Removal CLI
To completely wipe out all generated history, document folders, and database entries for a specific patient:
```bash
python remove_persona.py <Patient_ID>
# Bypass manual confirmation:
python remove_persona.py -f <Patient_ID>
```

#### Patient Data Compaction CLI
To reduce token history, feedback, and database size for patient runs:
```bash
# Compact a single patient
python compact_patient_data.py --patient-id 225

# Compact all patients and keep only the last 3 history entries
python compact_patient_data.py --all --history-entries 3
```

#### Database Migration CLI
To transfer records between JSON and PostgreSQL storage backends:
```bash
# Migrate JSON database to PostgreSQL database
python migrate_json_to_postgres.py --strategy update

# Reverse migrate PostgreSQL database to JSON file
python migrate_postgres_to_json.py --strategy skip
```
*Strategies supported: `update` (overwrite), `skip` (do not replace), `fail` (abort on duplicate).*

---

## 🚀 Web UI & API Reference

Access the interface in your browser by opening `ui/index.html` (runs locally, connects to the local API server).

### API Server Management
```bash
# Start Flask API server (runs on port 410 by default)
python -m api_server

# Stop the server on port 410
lsof -i :410
kill -9 <PID>
```

### API Endpoints
Full Swagger OpenAPI interactive documentation is available at:
👉 **[http://localhost:410/apidocs](http://localhost:410/apidocs)**

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| GET | `/api/status` | Server status |
| GET | `/api/patients` | Retrieve patient checklist |
| GET | `/api/patient/<id>` | Fetch active patient profile |
| POST | `/api/generate` | Synthesize single patient documents |
| POST | `/api/generate_all` | Trigger queue-based batch generation |
| POST | `/api/cancel/<job_id>` | Abort run and rollback changes |
| POST | `/api/purge` | Purge databases/files (supports batch `patient_ids`) |
| POST | `/api/template/save` | Save a document as a baseline template |
| POST | `/api/patient_tracker_export` | Compile metrics CSV tracker |
| GET | `/api/job/<job_id>?since=N` | Poll logs dynamically |
| GET | `/api/output/<patient_id>` | Fetch list of generated PDFs |
| GET | `/api/download/<id>/<type>/<file>`| Open PDF inline in browser |

---

## 📝 License
Proprietary / Internal Use Only.
