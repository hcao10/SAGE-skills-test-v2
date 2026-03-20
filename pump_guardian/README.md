# PumpGuardian - Industrial Pump Bearing Diagnostic Agent

PumpGuardian is a production-style demo showing the difference between:

- **General AI** (guessing, unstructured)
- **Skill Agent** (tool-driven, traceable, standard-compliant)

## Features

- Dual mode comparison (`General AI` vs `Skill Agent`)
- Progressive disclosure (load skill assets on demand)
- Local tool execution (`diag_tool.py` RMS + FFT + peak detection)
- ISO 10816 reference retrieval and evidence display
- Structured maintenance work order generation
- Markdown export
- Synthetic vibration data generator (default 81 Hz fault pattern)
- Live right-panel agent trace animation
- **MiniMax** real LLM calls for narrative contrast (optional API key)
- **Chinese / English** UI language toggle (LLM prompts follow UI language)
- **LLM raw I/O column** (chat-style + optional JSON payload) for side-by-side comparison
- **Sample CSV** under `data/samples/` (download button in the app)
- **Skill playbook** expander (progressive disclosure / industrial ROI narrative)

## MiniMax configuration

You can configure the API in **any** of these ways (first match wins; existing OS env vars are never overwritten):

1. **`.env` file** (recommended for local dev)  
   Create `pump_guardian/.env` next to `app.py` (copy from `env.sample`). It is loaded automatically from that folder even if your shell `cwd` is elsewhere.

2. **Streamlit `secrets.toml`**  
   Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and fill in values. On each run, secrets are merged into the process environment if the variable is not already set.

3. **Shell / CI environment variables**  
   Same names as below.

Variables:

- `MINIMAX_API_KEY` — required for live LLM responses
- `MINIMAX_API_BASE` — optional, default `https://api.minimax.io`  
  If you use `https://api.minimax.io/v1` as the host prefix, that also works.
- `MINIMAX_MODEL` — optional, default `MiniMax-M2.5` (matches model id / name you provided)

**Using `uv`:** no extra steps — activate the venv (or `uv run`) and run Streamlit as usual; `.env` and `secrets.toml` behave the same.

**If the UI still says the key is missing**

- Put `.env` or `.streamlit/secrets.toml` inside **`pump_guardian/`** (same folder as `app.py`), not only the repo root.
- If you run `streamlit run pump_guardian/app.py` from a **parent** directory, Streamlit’s built-in `st.secrets` may not read `pump_guardian/.streamlit/secrets.toml` — this project **also** loads that path explicitly; still prefer placing files under `pump_guardian/` as above.
- Variable name must be exactly `MINIMAX_API_KEY` (no spaces around `=` in `.env`).
- In the app **sidebar**, use “Session API key” once to verify, or enable “Show whether API key is loaded”.

**Behavior**

- **General AI**: calls MiniMax with a *deliberately data-poor* prompt (no CSV numbers, no FFT, no ISO). You see a generic narrative vs the industrial pipeline.
- **Skill Agent**: runs the full local skill pipeline first, then optionally calls MiniMax to summarize the *grounded* metrics (only if `MINIMAX_API_KEY` is set).

## Project Structure

```text
pump_guardian/
|
|-- app.py
|-- requirements.txt
|
|-- core/
|   |-- router.py
|   |-- trace.py
|   |-- skill_loader.py
|   |-- workorder.py
|   |-- minimax_client.py
|   |-- i18n.py
|   |-- config.py
|   |-- llm_parse.py
|
|-- docs/
|   |-- skill_playbook_zh.md
|   |-- skill_playbook_en.md
|
|-- skills/
|   |-- bearing_analyzer/
|       |-- SKILL.md
|       |-- scripts/
|       |   |-- diag_tool.py
|       |-- references/
|       |   |-- ISO_10816.json
|       |-- assets/
|           |-- wo_template.md
|
|-- data/
|   |-- generator.py
|   |-- samples/
|       |-- bearing_fault_81hz_demo.csv
|
|-- README.md
```

## Run

From the `pump_guardian` directory:

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Demo Notes

- If no CSV is uploaded, the app generates a synthetic vibration signal with:
  - 81 Hz bearing fault baseline
  - random noise
  - optional harmonic
- CSV format must include:
  - `time`
  - `amplitude`

## Expected Comparison

- **General AI**: generic LLM narrative + **raw request/response** panel; **no local tool pipeline**.  
  If the model *happens* to emit parseable JSON spectrum / markdown-like work order text, the UI will render it (heuristic); otherwise it shows **explicit “not produced”** states to contrast with the skill path.
- **Skill Agent**: full **tool + reference + template** pipeline (traceable), FFT + ISO evidence + standardized work order, plus an optional grounded LLM summary in the LLM column.
