# PAN-OS SD-WAN Configuration Parser

Docker-based tool with a Flask web UI that parses Palo Alto Panorama/NGFW configurations and generates an Excel report of all SD-WAN features — enabled/disabled status with detailed configuration breakdowns. Supports uploading multiple configs for side-by-side comparison analysis.

## Features

- **Multi-Config Comparison**: Upload multiple Panorama and NGFW configs to compare features side-by-side
- **Single Config Analysis**: Upload one XML or connect to a live device via PAN-OS API
- **Panorama + NGFW**: Automatically detects config type, enumerates templates, template-stacks, and device-groups
- **14 SD-WAN Feature Parsers**: Comprehensive extraction of all SD-WAN related configuration
- **Excel Reports**: Quick Reference summary, detailed per-feature sheets, and comparison views
- **Sensitive Data Masking**: Selectively mask IPs, hostnames, device names, passwords, certificates, and network addresses
- **HTTPS Support**: Self-signed certificate with nginx reverse proxy on port 9443
- **Dockerized**: Single container, no external dependencies

## SD-WAN Features Parsed

| Feature | Description |
|---------|-------------|
| SD-WAN Interface Profiles | Link type, tag, bandwidth, path monitoring |
| Path Quality Profiles | SLA thresholds: latency, jitter, packet loss |
| Traffic Distribution | Algorithms: best-available, top-down, weighted |
| SD-WAN Policy Rules | App-ID based path selection with traffic distribution |
| VPN/IPSec Tunnels | IKE gateways, IPSec tunnels, crypto profiles |
| VPN Clusters / Topology | Cluster config, hub/branch devices, BGP, site info |
| Routing (BGP/OSPF/ECMP) | Virtual routers, logical routers, VRFs, ECMP |
| Policy-Based Forwarding | PBF rules with nexthop, monitoring |
| QoS Profiles | QoS profiles and interface bindings |
| Link Management | SD-WAN link settings on interfaces, gateways |
| SaaS Quality Monitoring | Adaptive/static monitoring, probe intervals |
| Digital Experience Monitoring | DEM probes and autonomous DEM |
| Zones & Interfaces | Zones, ethernet, tunnel, aggregate, cellular interfaces |
| Certificate Profiles | CA certs, CRL/OCSP settings |

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
3. Select one XML file → click "Parse Configuration"
4. Excel report downloads automatically

### Multi-Config Comparison

1. Export configs from multiple devices (Panorama + NGFWs)
2. Open `http://localhost:8080`
3. Select multiple XML files → click "Compare N Configurations"
4. Comparison report downloads with side-by-side feature analysis
5. Use the X button to remove individual files before submitting

### Mask Sensitive Information

Before parsing, optionally enable masking to redact sensitive data from the report:
- **IP Addresses** — All IPs replaced with `x.x.x.x`
- **Hostnames & FQDNs** — DNS names replaced with `***.***`
- **Device Names & Serials** — Consistently replaced with `DEVICE-001`, `DEVICE-002`, etc.
- **Passwords & Keys** — Pre-shared keys, API keys replaced with `********`
- **Certificates** — CA certificate names redacted
- **Network Addresses** — Subnets, BGP AS numbers, interface names masked

Use "Select All" to enable all categories, or pick individual ones.

### Connect via API

1. Generate an API key:
   ```bash
   curl -k -X GET 'https://<host>/api/?type=keygen&user=admin&password=admin'
   ```
2. Open `http://localhost:8080`
3. Select "Connect via API" tab → enter hostname and API key → click "Connect & Parse"
4. Excel report downloads automatically

## Excel Report Format

### Single Config Report
- **Quick Reference**: All 14 features grouped by category with Enabled/Disabled status, color-coded headers
- **Detail Sheets**: One sheet per feature with full configuration data, auto-filter, and Source column
- **All Features**: Split into Enabled and Disabled sections with counts

### Multi-Config Comparison Report
- **Comparison Summary**: Features as rows, each config gets Status + Summary columns side-by-side with green/red color coding and per-config totals
- **Detail Sheets**: All data from all configs merged per feature with Config File and Source columns
- **All Features**: Enabled/Disabled split across all configs with Config File column

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
│   └── *.py                # 14 feature parsers
├── api_client/
│   └── connector.py        # pan-os-python SDK wrapper
├── report/
│   ├── excel_generator.py  # Single + comparison report generation
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
- pan-os-python — PAN-OS API connectivity
- lxml — XML parsing
- gunicorn — Production WSGI server
- nginx — HTTPS reverse proxy with self-signed certificate
