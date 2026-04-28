# PAN-OS SD-WAN Configuration Parser

Docker-based tool with a Flask web UI that parses Palo Alto Panorama/NGFW configurations and generates Excel + HTML dashboard reports of all SD-WAN features — with deployment maturity scoring, gap analysis, and side-by-side comparison. Designed for SEs, PMs, and network engineers.

## Features

- **Multi-Config Comparison**: Upload multiple Panorama and NGFW configs to compare features side-by-side
- **Single Config Analysis**: Upload one XML file for detailed analysis
- **Panorama + NGFW**: Automatically detects config type, enumerates templates, template-stacks, and device-groups
- **Panorama-Managed NGFW Detection**: Detects Panorama-managed NGFWs and correlates SD-WAN features from Panorama config
- **Inline Dashboard**: HTML dashboard renders directly in the web UI after parsing — no separate file download
- **38 SD-WAN Features Tracked**: Comprehensive extraction across 23 parsers covering 7 categories
- **Software Version Detection**: Extracts PAN-OS version and SD-WAN plugin version from configs
- **Deployment Scoring**: Automatic maturity grading based on enabled features (Basic: 0-13, Advanced: 14-26, Full: 27-38)
- **Excel Reports**: Executive Summary with scoring, device-level feature details + Quick Reference + detailed per-feature sheets + comparison views
- **Sensitive Data Masking**: Selectively mask IPs, hostnames, device names, passwords, certificates, and network addresses
- **Multi-User Support**: Per-session isolation — multiple users can parse configs simultaneously
- **HTTPS Support**: Self-signed certificate with nginx reverse proxy on port 9443
- **Dockerized**: Single container, no external dependencies

## 38 Tracked SD-WAN Features (7 Categories)

| Category | Features |
|----------|----------|
| **SD-WAN Core** | SD-WAN Interface Profiles, App-ID Steering, Path Quality Metrics, Bandwidth Monitoring, Probe Idle Time, Failback Hold Time |
| **Traffic Optimization** | Link Remediation (FEC), Packet Duplication |
| **VPN & Topology** | VPN Automation, Topology Configured, Hub Capacity, Prisma Access Hub, Sub-Second Failover, Tunnel Monitor |
| **Routing** | Dynamic Routing, BGP AS Control, BGP Private AS, BGP Timer Profile, BGP Security Rule, BGP Routing Profiles, BGP Dampening, IPv6 Support, Multi-VR Support, Multicast Support, BFD Configuration, Advance Routing |
| **Security & NAT** | SD-WAN Security Rules, SD-WAN NAT Policies |
| **Monitoring & Reporting** | ADEM Integration, SD-WAN Reporting, Log Collection, Device Telemetry, Monitor Profiles |
| **Network Infrastructure** | Sub/Agg Interfaces, Custom Applications, Template/Stack Mapping, Upstream NAT, ZTP Support |

## Quick Start

### Docker Run

```bash
docker run -d --name panos-parser -p 8080:8080 -p 9443:9443 ajaymare/panos-config-analyzer:latest
```

Open `http://localhost:8080` (HTTP) or `https://localhost:9443` (HTTPS) in your browser.

### Docker Build

```bash
docker build -t ajaymare/panos-config-analyzer:latest .
docker run -d --name panos-parser -p 8080:8080 -p 9443:9443 ajaymare/panos-config-analyzer:latest
```

## Usage

### Single Config Analysis

1. Export running config from Panorama or NGFW:
   - **GUI**: Device → Setup → Operations → Export named configuration snapshot
   - **CLI**: `show config running` → save to XML
2. Open `http://localhost:8080`
3. Select one XML file → click "Generate Report"
4. Dashboard displays inline with scorecards, feature summary, and gap analysis
5. Click "Download Excel Report" for the detailed Excel file

### Multi-Config Comparison

1. Export configs from multiple devices (Panorama + NGFWs)
2. Open `http://localhost:8080`
3. Select multiple XML files → click "Compare N Configurations"
4. Comparison dashboard displays inline with side-by-side scoring and feature comparison
5. Click "Download Excel Report" for the detailed comparison Excel
6. Use the X button to remove individual files before submitting

### Panorama-Managed NGFW Configs

NGFW configs exported from Panorama-managed devices don't contain SD-WAN configuration locally — it's pushed from Panorama. The tool handles this automatically:

- **NGFW uploaded alone**: SD-WAN features show as "Panorama-Managed" (amber) instead of "Not configured" (red)
- **NGFW + Panorama uploaded together**: SD-WAN features from Panorama are correlated and attributed to each NGFW device, giving a complete picture

### Mask Sensitive Information

Before parsing, optionally enable masking to redact sensitive data from the report:
- **IP Addresses** — All IPs replaced with `x.x.x.x`
- **Hostnames & FQDNs** — DNS names replaced with `***.***`
- **Device Names & Serials** — Consistently replaced with `DEVICE-001`, `DEVICE-002`, etc.
- **Passwords & Keys** — Pre-shared keys, API keys replaced with `********`
- **Certificates** — CA certificate names redacted
- **Network Addresses** — Subnets, BGP AS numbers, interface names masked

Use "Select All" to enable all categories, or pick individual ones.

## Report Output

The inline dashboard displays immediately after parsing. The Excel report is available via download button.

### Inline Dashboard
- **Deployment Scorecards**: Per-config cards with maturity level (Basic/Advanced/Full), circular progress, device name, PAN-OS and SD-WAN plugin versions
- **Feature Comparison Table**: All 38 features grouped by 7 categories — green checkmark (enabled), amber diamond (Panorama-Managed), red X (missing). Topology Configured shows actual type (Full Mesh / Hub-Spoke)
- **Category Bar Charts**: Horizontal bars showing coverage percentage per category per config
- **Gap Analysis**: Missing features with actionable recommendations for each config

### Excel Report

#### Single Config
- **Executive Summary**: KPI scorecard (maturity level, score, enabled/gaps), device name with serial, category coverage with progress bars, compact feature status by category, prioritized recommendations with business impact
- **Quick Reference**: All 38 features grouped by 7 categories with one row per device/source per feature
- **Detail Sheets**: One sheet per feature with full configuration data
- **All Features**: Split into Enabled and Disabled sections with counts

#### Multi-Config Comparison
- **Executive Summary**: Side-by-side deployment scoring across all configs
- **Comparison Summary**: Features as rows, per-config Status + Summary columns
- **Detail Sheets**: Merged data from all configs per feature
- **All Features**: Enabled/Disabled split across all configs

## Project Structure

```
parser/
├── app.py                  # Flask routes (single + multi-file)
├── config.py               # App configuration
├── requirements.txt        # Python dependencies
├── Dockerfile
├── nginx.conf              # HTTPS reverse proxy config (port 9443)
├── start.sh                # Entrypoint: generates self-signed cert, starts gunicorn + nginx
├── parsers/                # Feature extraction modules
│   ├── base.py             # BaseParser ABC + FeatureResult
│   ├── config_detector.py  # Panorama vs NGFW detection
│   ├── registry.py         # Auto-discovers all parsers
│   └── *.py                # 23 feature parsers (38 tracked features)
├── api_client/
│   └── connector.py        # pan-os-python SDK wrapper
├── report/
│   ├── excel_generator.py  # Single + comparison report generation
│   ├── html_dashboard.py   # Self-contained HTML dashboard generator
│   ├── scorer.py           # Deployment maturity scoring engine
│   ├── masker.py           # Sensitive data masking engine
│   └── styles.py           # Cell formatting
├── templates/
│   └── index.html          # Web UI with multi-file upload
└── static/
    └── style.css
```

## Dependencies

- Flask — Web framework
- openpyxl — Excel generation
- lxml — XML parsing
- gunicorn — Production WSGI server
- nginx — HTTPS reverse proxy with self-signed certificate
