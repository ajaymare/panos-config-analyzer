# CLAUDE.md

## Project Overview

PAN-OS SD-WAN Configuration Parser — a Docker-based Flask tool that parses Palo Alto Panorama/NGFW XML configs (file upload or live API) and generates Excel + HTML dashboard reports with deployment scoring, gap analysis, and multi-config comparison. Output is a ZIP containing both reports.

## Architecture

- **Flask app** (`app.py`): Routes for single/multi-file upload and API input, orchestrates parsing pipeline, returns ZIP (Excel + HTML)
- **Parsers** (`parsers/`): 14 feature-specific modules, each a `BaseParser` subclass with `extract()` method
- **Config Detector** (`parsers/config_detector.py`): Auto-detects Panorama vs NGFW, enumerates templates/device-groups/shared
- **Registry** (`parsers/registry.py`): Auto-discovers all `BaseParser` subclasses via `pkgutil`
- **API Client** (`api_client/connector.py`): pan-os-python SDK wrapper for live device config retrieval
- **Report** (`report/excel_generator.py`): Two report modes, both with Executive Summary sheet:
  - `generate()` — Single config: Executive Summary + Quick Reference + detail sheets + All Features
  - `generate_comparison()` — Multi config: Executive Summary + Comparison Summary + merged detail sheets + All Features
- **HTML Dashboard** (`report/html_dashboard.py`): Self-contained HTML with scorecards, comparison table, category charts, gap analysis
- **Scorer** (`report/scorer.py`): Deployment maturity scoring (Basic/Advanced/Full) with category breakdowns and recommendations
- **Masker** (`report/masker.py`): Sensitive data masking with 6 categories (IPs, hostnames, devices, passwords, certs, network addresses)

## Key Files

- `app.py` — Flask entry point, `/parse` handles both single and multi-file uploads
- `parsers/base.py` — `BaseParser` ABC, `FeatureResult` and `ConfigContainer` dataclasses, shared XML helpers
- `parsers/config_detector.py` — Panorama/NGFW detection, container enumeration (templates, device-groups, shared)
- `report/excel_generator.py` — Single report + comparison report builders with Executive Summary and category grouping
- `report/html_dashboard.py` — Self-contained HTML dashboard (inline CSS, no external deps, works offline)
- `report/scorer.py` — Deployment scoring: `score_config()` and `score_configs()` for maturity grading
- `report/masker.py` — Sensitive data masking engine (IP, hostname, device, password, cert, network categories)
- `report/styles.py` — openpyxl cell styles (header, data, status fills, auto-width)
- `templates/index.html` — Web UI with multi-file upload, file list with remove buttons
- `static/style.css` — CSS with blue/corporate theme

## Build & Deploy

```bash
# Build and push (amd64)
docker buildx build --platform linux/amd64 -t ajaymare/panos-config-analyzer:latest -f Dockerfile . --push

# Run locally (HTTP 8080 + HTTPS 9443)
docker run -d --name panos-parser -p 8080:8080 -p 9443:9443 ajaymare/panos-config-analyzer:latest
```

### HTTPS
- nginx reverse proxy on port 9443 with self-signed certificate (auto-generated on first start)
- gunicorn listens on 127.0.0.1:8080 internally, nginx proxies HTTPS → gunicorn
- Config: `nginx.conf`, entrypoint: `start.sh`

## Development Notes

### Adding a New Parser
1. Create `parsers/new_feature.py`
2. Subclass `BaseParser`, set `FEATURE_NAME` and `SHEET_NAME`
3. Implement `extract(xml_root, containers) -> list[FeatureResult]`
4. The registry auto-discovers it — no other changes needed
5. Add the feature name to `FEATURE_CATEGORIES` in `report/excel_generator.py` for Quick Reference grouping

### XPath Patterns (Actual PAN-OS Structure)
- **SD-WAN profiles** (path quality, traffic distribution, SaaS): Under `device-group/entry/profiles/sdwan-*/entry` and `shared/profiles/sdwan-*/entry`
- **SD-WAN interface profiles**: Under `template/entry/config/devices/entry/vsys/entry/sdwan-interface-profile/entry`
- **SD-WAN link settings**: On interfaces at `network/interface/ethernet/entry/layer3/sdwan-link-settings`
- **SD-WAN policies**: Under `device-group/entry/pre-rulebase/sdwan/rules/entry`
- **VPN topology**: Under `plugins/sd_wan/vpn-cluster/entry` and `plugins/sd_wan/devices/entry` (root level)
- **Routing**: Under `network/virtual-router/entry` and `network/logical-router/entry/vrf/entry`
- **Zones**: Under `vsys/entry/zone/entry`

### Container Model
Config detector creates containers per scope:
- `template` — xml_node points to `template/entry/config`
- `device-group` — xml_node points to `device-group/entry`
- `shared` — xml_node points to `shared`
- `ngfw` — xml_node points to root `config` element

Parsers iterate containers and search relative XPaths. Some parsers (VPN topology) use `xml_root` directly for plugins section.

### Deployment Scoring & Dashboard
- `report/scorer.py` scores configs by counting enabled features out of 14: Basic (1-4), Advanced (5-9), Full (10-14)
- Per-category breakdown (SD-WAN Core, VPN & Topology, Routing, Monitoring, Network Infrastructure)
- Missing features generate actionable recommendations (defined in `RECOMMENDATIONS` dict)
- `report/html_dashboard.py` generates a self-contained HTML file with inline CSS (no JS libs)
- Dashboard sections: scorecards with circular progress, feature comparison table, category bar charts, gap analysis
- `app.py` bundles Excel + HTML into a ZIP via `_create_zip()` before returning to the client

### Sensitive Data Masking
- `report/masker.py` applies masking to `FeatureResult` objects before report generation
- 6 categories: `ip_addresses`, `hostnames`, `devices`, `passwords`, `certificates`, `network`
- UI sends `mask_categories` form field; `app.py` calls `mask_results()` on parsed results
- Column-based matching (maps column names to categories) + regex scanning (IPs, FQDNs)
- Device masking uses consistent mapping (`DEVICE-001`, `DEVICE-002`) across the entire report

### pan-os-python SDK
SDK has no SD-WAN classes. Used only for API connectivity (`xapi.show('/config')`). All extraction uses `xml.etree.ElementTree`.

## Git

- Remote: https://github.com/ajaymare/panos-config-analyzer.git
- Docker image: `ajaymare/panos-config-analyzer:latest` (amd64)
- Author: Ajay Mare (ajaymaray@gmail.com)
