# CLAUDE.md

## Project Overview

PAN-OS SD-WAN Configuration Parser — a Docker-based Flask tool that parses Palo Alto Panorama/NGFW XML configs (file upload or live API) and generates Excel reports of all SD-WAN features.

## Architecture

- **Flask app** (`app.py`): Routes for upload/API input, orchestrates parsing pipeline, returns Excel download
- **Parsers** (`parsers/`): 14 feature-specific modules, each a `BaseParser` subclass with `extract()` method
- **Config Detector** (`parsers/config_detector.py`): Auto-detects Panorama vs NGFW, enumerates templates/device-groups
- **Registry** (`parsers/registry.py`): Auto-discovers all `BaseParser` subclasses via `pkgutil`
- **API Client** (`api_client/connector.py`): pan-os-python SDK wrapper for live device config retrieval
- **Report** (`report/`): openpyxl-based Excel generator with summary + detail sheets

## Key Files

- `app.py` — Flask entry point, `/parse` route ties parsers to Excel generator
- `parsers/base.py` — `BaseParser` ABC, `FeatureResult` dataclass, shared XML helpers
- `parsers/config_detector.py` — Panorama/NGFW detection, `ConfigContainer` objects
- `report/excel_generator.py` — Builds workbook with summary sheet + per-feature detail sheets
- `report/styles.py` — openpyxl cell styles (header, data, status fills, auto-width)

## Build & Deploy

```bash
# Build
docker build -t panos-sdwan-parser:latest .

# Run
docker run -d --name panos-parser -p 8080:8080 panos-sdwan-parser:latest
```

## Development Notes

### Adding a New Parser
1. Create `parsers/new_feature.py`
2. Subclass `BaseParser`, set `FEATURE_NAME` and `SHEET_NAME`
3. Implement `extract(xml_root, containers) -> list[FeatureResult]`
4. The registry auto-discovers it — no other changes needed

### XPath Patterns
- NGFW: `.//devices/entry/network/...` or `.//devices/entry/plugins/sd_wan/...`
- Panorama templates: `.//template/entry/config/devices/entry/...`
- Device groups (policies): `.//pre-rulebase/...` and `.//post-rulebase/...`

### pan-os-python SDK
SDK has no SD-WAN classes. Used only for API connectivity (`xapi.show('/config')`). All extraction uses `xml.etree.ElementTree`.
