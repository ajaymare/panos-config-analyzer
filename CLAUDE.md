# CLAUDE.md

## Project Overview

PAN-OS SD-WAN Configuration Parser — a Docker-based Flask tool that parses Palo Alto Panorama/NGFW XML configs (file upload or live API) and generates Excel reports + inline HTML dashboard with deployment scoring, gap analysis, and multi-config comparison. Supports Panorama-managed NGFW correlation and multi-user concurrent access.

## Architecture

- **Flask app** (`app.py`): Routes for single/multi-file upload, orchestrates parsing pipeline, returns JSON (dashboard HTML + Excel download URL)
- **Parsers** (`parsers/`): 23 feature-specific modules (38 tracked features), each a `BaseParser` subclass with `extract()` method
- **Config Detector** (`parsers/config_detector.py`): Auto-detects Panorama vs NGFW, enumerates templates/device-groups/shared, detects Panorama-managed NGFWs
- **Registry** (`parsers/registry.py`): Auto-discovers all `BaseParser` subclasses via `pkgutil`
- **Report** (`report/excel_generator.py`): Two report modes, both with Executive Summary sheet:
  - `generate()` — Single config: Executive Summary + Quick Reference + detail sheets + All Features
  - `generate_comparison()` — Multi config: Executive Summary + Comparison Summary + merged detail sheets + All Features
- **HTML Dashboard** (`report/html_dashboard.py`): Inline dashboard fragment with scorecards, comparison table, category charts, gap analysis
- **Scorer** (`report/scorer.py`): Deployment maturity scoring (Basic/Advanced/Full) with category breakdowns, Panorama-managed feature tracking, and recommendations
- **Masker** (`report/masker.py`): Sensitive data masking with 6 categories (IPs, hostnames, devices, passwords, certs, network addresses)

## Key Files

- `app.py` — Flask entry point, `/parse` (file upload only) returns JSON (dashboard HTML + Excel URL), `/download/<session>/<file>` serves Excel
- `parsers/base.py` — `BaseParser` ABC, `FeatureResult` and `ConfigContainer` dataclasses, shared XML helpers
- `parsers/config_detector.py` — Panorama/NGFW detection, container enumeration, `is_panorama_managed()`, `get_device_serial()`, `get_managed_serials()`
- `report/excel_generator.py` — Single report + comparison report builders with Executive Summary and category grouping
- `report/html_dashboard.py` — Inline dashboard fragment (`generate_dashboard_fragment()`) + standalone HTML (`generate_dashboard()`)
- `report/scorer.py` — Deployment scoring: `score_config()` and `score_configs()`, tracks `panorama_managed_features` separately
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

### 38 Tracked Features (7 Categories)
Features are defined in `FEATURE_CATEGORIES` in `report/excel_generator.py`. Categories: SD-WAN Core (6), Traffic Optimization (2), VPN & Topology (6), Routing (12), Security & NAT (2), Monitoring & Reporting (5), Network Infrastructure (5).

### Enhanced Parser Sub-Features
Many parsers emit multiple `FeatureResult` objects — a primary feature plus sub-features for scoring:
- **VPN Topology** (`VPN Automation`): + Topologies Supported, Hub Capacity, Prisma Access Hub, Sub-Second Failover, BGP AS Control, BGP Private AS, BGP Security Rule, Multi-VR Support
- **Routing** (`Dynamic Routing`): + BGP Timer Profile, IPv6 Support, Multicast Support, BFD Configuration, BGP Dampening, BGP Routing Profiles
- **SD-WAN Interface Profiles**: + Bandwidth Monitoring, Probe Idle Time, Failback Hold Time
- **Traffic Distribution**: + Link Remediation (FEC), Packet Duplication
- **VPN Tunnels**: + Tunnel Monitor
- **Link Management**: + Upstream NAT
- **Device Telemetry**: + Advance Routing

### Summary Format
Parser summaries use `"Source: Entry1, Entry2"` format (set in `_make_result()` in `base.py`). Quick Reference shows one row per source/device per feature. Executive Summary and dashboard Feature Details tables include a Device column showing the config filename.

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

### Inline Dashboard & Scoring
- `/parse` returns JSON: `{ dashboard_html, excel_url, excel_filename }`
- Dashboard HTML fragment is injected inline in the web UI — no separate file download
- Excel report served via `/download/<session_id>/<filename>` with per-session isolation
- `report/scorer.py` scores configs by counting enabled features out of 38: Basic (0-13), Advanced (14-26), Full (27-38)
- Per-category breakdown (SD-WAN Core, Traffic Optimization, VPN & Topology, Routing, Security & NAT, Monitoring & Reporting, Network Infrastructure)
- Panorama-managed features tracked separately — count toward score, shown in amber
- Three status indicators in dashboard: green checkmark (enabled), amber diamond (Panorama-Managed), red X (missing)
- Software version info (PAN-OS version, SD-WAN plugin version) shown in scorecards and Excel

### Panorama-Managed NGFW Handling
- `config_detector.is_panorama_managed()` checks for `panorama/local-panorama/panorama-server` in NGFW config
- `config_detector.get_device_serial()` extracts serial from `mgt-config/devices/entry`
- `config_detector.get_managed_serials()` lists SD-WAN device serials from Panorama's `plugins/sd_wan/devices`
- NGFW uploaded alone: SD-WAN features marked "Panorama-Managed" instead of "Not configured"
- NGFW + Panorama uploaded together: `_correlate_with_panorama()` copies Panorama's SD-WAN results to NGFW with source "Panorama → {device}"
- `_PANORAMA_SDWAN_FEATURES` in `app.py` defines which features are Panorama-managed (interface profiles, policies, VPN topology, ZTP, etc.)

### Multi-User Isolation
- Each `/parse` request creates a unique session directory under `REPORT_DIR/<uuid>/`
- Excel files are scoped to the session directory
- Download URLs include session ID: `/download/<session_id>/<filename>`

### Sensitive Data Masking
- `report/masker.py` applies masking to `FeatureResult` objects before report generation
- 6 categories: `ip_addresses`, `hostnames`, `devices`, `passwords`, `certificates`, `network`
- UI sends `mask_categories` form field; `app.py` calls `mask_results()` on parsed results
- Column-based matching (maps column names to categories) + regex scanning (IPs, FQDNs)
- Device masking uses consistent mapping (`DEVICE-001`, `DEVICE-002`) across the entire report

## Git

- Remote: https://github.com/ajaymare/panos-config-analyzer.git
- Docker image: `ajaymare/panos-config-analyzer:latest` (amd64)
- Author: Ajay Mare (ajaymaray@gmail.com)
