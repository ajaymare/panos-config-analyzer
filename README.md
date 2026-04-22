# PAN-OS SD-WAN Configuration Parser

Docker-based tool with a Flask web UI that parses Palo Alto Panorama/NGFW configurations and generates an Excel report of all SD-WAN features — enabled/disabled status with detailed configuration breakdowns.

## Features

- **Dual Input**: Upload XML config file or connect to a live device via PAN-OS API
- **Panorama + NGFW**: Automatically detects config type, enumerates templates, template-stacks, and device-groups
- **14 SD-WAN Feature Parsers**: Comprehensive extraction of all SD-WAN related configuration
- **Excel Report**: Summary sheet (Enabled/Disabled per feature) + detailed per-feature sheets with full config parameters
- **Dockerized**: Single container, no external dependencies

## SD-WAN Features Parsed

| Feature | Description |
|---------|-------------|
| SD-WAN Interface Profiles | Link type, tag, bandwidth, path monitoring |
| Path Quality Profiles | SLA thresholds: latency, jitter, packet loss |
| Traffic Distribution | Algorithms: best-available, top-down, weighted |
| SD-WAN Policy Rules | App-ID based path selection, error correction |
| VPN/IPSec Tunnels | IKE gateways, IPSec tunnels, crypto profiles |
| VPN Clusters / Topology | Hub-spoke, full mesh topology definitions |
| Routing (BGP/OSPF/ECMP) | Virtual routers, logical routers, VRFs, ECMP |
| Policy-Based Forwarding | PBF rules with nexthop, monitoring |
| QoS Profiles | QoS profiles and interface bindings |
| Link Management | Link tags, ISP settings, monitoring probes |
| SaaS Quality Monitoring | SaaS app probes, thresholds |
| Digital Experience Monitoring | DEM probes and autonomous DEM |
| Zones & Interfaces | Zones, ethernet, tunnel interfaces |
| Certificate Profiles | CA certs, CRL/OCSP settings |

## Quick Start

### Docker Run

```bash
docker run -d --name panos-parser -p 8080:8080 panos-sdwan-parser:latest
```

Open `http://localhost:8080` in your browser.

### Docker Build

```bash
docker build -t panos-sdwan-parser:latest .
docker run -d --name panos-parser -p 8080:8080 panos-sdwan-parser:latest
```

## Usage

### Upload XML Config

1. Export running config from Panorama or NGFW:
   - **GUI**: Device → Setup → Operations → Export named configuration snapshot
   - **CLI**: `show config running` → save to XML
2. Open `http://localhost:8080`
3. Select "Upload XML File" tab → choose your XML file → click "Parse Configuration"
4. Excel report downloads automatically

### Connect via API

1. Generate an API key:
   ```bash
   curl -k -X GET 'https://<host>/api/?type=keygen&user=admin&password=admin'
   ```
2. Open `http://localhost:8080`
3. Select "Connect via API" tab → enter hostname and API key → click "Connect & Parse"
4. Excel report downloads automatically

## Excel Report Format

- **Summary Sheet**: All 14 features listed with Enabled/Disabled status, summary count, and source (NGFW / template name / device-group name)
- **Detail Sheets**: One sheet per feature with full configuration columns, auto-filter, and formatted cells

## Project Structure

```
parser/
├── app.py                  # Flask routes
├── config.py               # App configuration
├── requirements.txt        # Python dependencies
├── Dockerfile
├── parsers/                # Feature extraction modules
│   ├── base.py             # BaseParser ABC + FeatureResult
│   ├── config_detector.py  # Panorama vs NGFW detection
│   ├── registry.py         # Auto-discovers all parsers
│   └── *.py                # 14 feature parsers
├── api_client/
│   └── connector.py        # pan-os-python SDK wrapper
├── report/
│   ├── excel_generator.py  # openpyxl workbook builder
│   └── styles.py           # Cell formatting
├── templates/
│   └── index.html          # Web UI
└── static/
    └── style.css
```

## Dependencies

- Flask — Web framework
- openpyxl — Excel generation
- pan-os-python — PAN-OS API connectivity
- lxml — XML parsing
- gunicorn — Production WSGI server
