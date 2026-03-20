# What is an industrial “Skill”?

## Skill bundle layout (mapped to this demo)

### `SKILL.md` (core instructions)

Markdown that defines **when** the skill should activate, expected inputs/outputs, and which tools it coordinates.  
Example intent: *“When RMS vibration velocity trends up with bearing-band energy concentration, activate bearing diagnostics.”*

### `scripts/` (executable logic)

Python/TS (or other) code for **deterministic computation** and **local tool execution**.  
In this repo, `diag_tool.py` performs RMS + FFT + peak detection—something a generic LLM should not “guess.”

### `references/` (grounding assets)

Manuals (PDF), fault tables (Excel), JSON standards like **ISO 10816**, SOP snippets, etc.  
The agent retrieves these **just-in-time** instead of stuffing entire documents into the prompt up front.

### `assets/` (output templates)

Standardized work orders / safety reports to match **enterprise format and auditability**.  
`wo_template.md` is an example asset.

---

## Progressive disclosure & efficiency

A common anti-pattern is putting *all possible engineering knowledge* into one giant prompt: **slow, expensive, brittle**.  
A skill architecture typically:

1. Loads **metadata only** at startup (name, short capability, trigger hints).
2. On a matching request/alarm, loads **SKILL.md → scripts → references → templates** on demand.

For large industrial datasets, **code execution / tool runs** move heavy work out of the model context. Teams often see **large reductions** in wasted tokens/latency when replacing “prompt-only omniscience” with “metadata + on-demand assets + tools” (exact savings depend on workload).

---

## Industrial adoption: effectiveness *and* efficiency

Industrial buyers usually evaluate agents on two axes:

1. **Effectiveness**: can it **reliably** solve the problem under constraints (repeatable, traceable, auditable)?
2. **Efficiency**: does it reduce total cost—time, compute, human coordination, downtime risk?

Surveys (e.g., McKinsey/Deloitte 2024–2025 themes) note many organizations use AI, but fewer capture outsized value without **workflow redesign**.  
Skills + templates + evidence chains are how demos become **operable systems**.

> *It’s not just about capability — it’s about whether it can deliver results reliably and at a reasonable cost.*
