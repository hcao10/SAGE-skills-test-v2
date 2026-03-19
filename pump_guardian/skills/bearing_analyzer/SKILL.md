# Bearing Analyzer Skill

## Skill ID
bearing_analyzer

## Capability
Industrial pump bearing diagnostics using vibration analysis and ISO 10816 severity classification.

## Inputs
- `time` column (seconds)
- `amplitude` column (mm/s)
- equipment id

## Workflow
1. Compute RMS from time-domain vibration amplitude.
2. Execute FFT and detect dominant peak frequency.
3. Estimate likely fault pattern from dominant frequency.
4. Retrieve ISO 10816 class thresholds for severity classification.
5. Render standardized maintenance work order.

## Tools
- `scripts/diag_tool.py` for signal processing.
- `references/ISO_10816.json` for compliance lookup.
- `assets/wo_template.md` for structured work order generation.
