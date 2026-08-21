# PAN-OS SD-WAN Toolkit

Docker-based web application for Palo Alto Networks SD-WAN professionals. Five integrated tools: Configuration Analysis with deployment scoring, SCM Migration with Terraform HCL generation, Firewall Sizing Calculator with hardware and VM-Series recommendations, POC Config Generator with Ansible/Terraform output, and SD-WAN Advisor for competitive positioning.

## Five Modes

### 1. Configuration Analysis
Upload Panorama or NGFW XML configs to generate deployment reports with maturity scoring, gap analysis, and multi-config comparison.

- **38 SD-WAN features tracked** across 7 categories (23 parsers)
- Deployment scoring: Basic (0-13), Advanced (14-26), Full (27-38)
- Inline HTML dashboard + downloadable Excel report
- Multi-config side-by-side comparison
- Panorama-managed NGFW detection and correlation
- PAN-OS and SD-WAN plugin version extraction
- Sensitive data masking (IPs, hostnames, devices, passwords, certs, networks)

### 2. Generate SCM Config
Convert PAN-OS SD-WAN configurations to Terraform HCL targeting the `paloaltonetworks/scm` provider for deployment to Strata Cloud Manager.

- Migration readiness analysis with feature-by-feature compatibility
- Terraform HCL generation for 15 SD-WAN object types using the SCM Terraform provider
- Direct deploy-to-SCM from the web UI: `terraform init`, `plan`, `apply`, `destroy` with live terminal output
- Migration report with supported/unsupported feature breakdown
- Generated `.tf` files: provider config, variables, per-feature resource definitions, outputs

### 3. Sizing Calculator
Input site requirements and get PA firewall model recommendations for SD-WAN deployments.

- **Hardware**: 21 PA models across 7 series (PA-400 through PA-7000)
- **VM-Series**: 7 VM models (VM-50 through VM-1000-HV)
- **Security features** that affect sizing: Threat Prevention, SSL Decryption, URL Filtering, WildFire, DNS Security
- Separate Hub and Branch recommendations with up to 2 alternative options per role from different series
- **SD-WAN-specific specs**: Policy rules, virtual interfaces, security zones, virtual routers per model
- **Device Comparison Tool**: Side-by-side comparison of recommended models with ability to add any PA/VM model from the full catalog, with best-value highlighting
- ISP-based tunnel calculation (Private: 1-to-1, Public: 1-to-many)
- 30% minimum headroom enforcement on all sizing requirements
- TAC recommended PAN-OS version per model series
- Licensing recommendations (auto-suggests BPLA bundle for 3+ security features)
- Full device specs: throughput, sessions, tunnels, ports, form factor, HA support
- Downloadable Excel report with model comparison sheet
- **Datasheet References (RAG)**: Auto-fetches and indexes official PA datasheets, surfaces relevant excerpts alongside sizing recommendations

### 4. POC Config Generator
Step-by-step wizard to generate SD-WAN proof-of-concept deployment packages with maximum feature coverage from minimal input.

- **Dual target**: Panorama (Ansible playbooks) or SCM (Terraform HCL)
- **5-question wizard**: target, connectivity, topology, bandwidth — auto-generates everything else
- **Auto-configured features**: 3 Path Quality Profiles (RealTime/Business/Default), 3 Traffic Distribution Profiles (TopDown/BestPath/BestPath+FEC), 3 SD-WAN Policy Rules (VoiceVideo/BusinessApps/Default), Security Zones, VPN Cluster, BGP Routing, Interface Profiles
- **Panorama output**: Ansible playbooks using `paloaltonetworks.panos.panos_config_element` with per-feature roles and master playbook
- **SCM output**: Terraform HCL using `paloaltonetworks/scm` provider with zones, profiles, and SD-WAN rules
- Downloadable ZIP with deployment-ready config and Quick Start guide

### 5. SD-WAN Advisor
Guided wizard for sales teams to generate competitive positioning recommendations — PAN-OS SD-WAN vs Prisma SD-WAN.

- **7-step wizard**: existing PA investment, competitor displacement, deployment scale, security model, management preference, key priorities, review & generate
- **Weighted scoring engine**: 6 categories (Existing Investment, Security Model, Management, Deployment Scale, Competitive Fit, Priority Alignment) with configurable weights
- Recommendation with confidence score and per-category rationale
- Side-by-side PAN-OS vs Prisma score bars
- Feature comparison table (10 rows)
- Competitive displacement talking points (Fortinet, Cisco Viptela, Cisco Meraki, VeloCloud, Silver Peak)
- Downloadable Excel report with Executive Summary, Scoring Breakdown, Feature Comparison, and Next Steps

## Quick Start

```bash
docker run -d --name panos-sdwan-toolkit -p 8080:8080 -p 9443:9443 ajaymare/panos-sdwan-toolkit:latest
```

Open `https://localhost:9443` (HTTPS) or `http://localhost:8080` (HTTP).

### Build from Source

```bash
docker build -t ajaymare/panos-sdwan-toolkit:latest .
docker run -d --name panos-sdwan-toolkit -p 8080:8080 -p 9443:9443 ajaymare/panos-sdwan-toolkit:latest
```

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

## Sizing Calculator Details

### Supported PA Hardware Models (21 Models)

| Series | Models | Role |
|--------|--------|------|
| PA-400 | PA-410, PA-440, PA-450, PA-460 | Branch |
| PA-500 | PA-540, PA-560 | Branch |
| PA-800 | PA-820, PA-850 | Branch |
| PA-1400 | PA-1410, PA-1420 | Branch / Hub |
| PA-3400 | PA-3410, PA-3420, PA-3430, PA-3440 | Hub |
| PA-5400 | PA-5410, PA-5420, PA-5430, PA-5440 | Hub |
| PA-7000 | PA-7050, PA-7080 | Hub |

### Supported VM-Series Models

| Model | vCPU | Role |
|-------|------|------|
| VM-50 | 2 | Branch (lab/micro-branch) |
| VM-100 | 2 | Branch |
| VM-200 | 2 | Branch |
| VM-300 | 4 | Branch / Hub |
| VM-500 | 8 | Branch / Hub |
| VM-700 | 16 | Hub |
| VM-1000-HV | 16+ | Hub |

### SD-WAN Specific Device Capabilities

Each model includes SD-WAN-specific specs used for sizing decisions:
- **SD-WAN Policy Rules**: Max number of SD-WAN rules supported
- **SD-WAN Virtual Interfaces**: Max virtual interfaces for SD-WAN tunnels
- **Max Security Zones**: Zone capacity for segmentation
- **Max Virtual Routers**: VR capacity for multi-VRF deployments

### Security Features and Throughput Impact

| Feature | Impact | Throughput Metric Used |
|---------|--------|----------------------|
| Threat Prevention | High | Threat Prevention throughput |
| SSL Decryption | High | SSL Decryption throughput (lowest) |
| URL Filtering | Medium | Licensing only |
| WildFire | Medium | Licensing only |
| DNS Security | Low | Licensing only |

### Tunnel Calculation Logic

- **Private ISP** (MPLS/P2P): 1-to-1 tunnels per matching hub link
- **Public ISP** (Internet): 1-to-many tunnels to every hub public link on every hub
- No branch-to-branch tunnels

## Usage

### Configuration Analysis

1. Export running config: Device > Setup > Operations > Export named configuration snapshot (or CLI: `show config running`)
2. Select "Generate Report" on the landing page
3. Upload one or multiple XML files
4. Dashboard displays inline; click "Download Excel Report" for details

### SCM Migration

1. Select "Generate SCM Config" on the landing page
2. Upload Panorama XML config
3. Select SD-WAN objects to migrate
4. Review migration dashboard, download Terraform config, or deploy directly to SCM via `terraform apply`

### Sizing Calculator

1. Select "Sizing Calculator" on the landing page
2. Enter deployment details: hub/branch count, bandwidth, sessions, ISP links
3. Toggle security features (Threat Prevention, SSL Decryption, etc.)
4. Configure HA requirements
5. Click "Calculate Sizing" for recommendations with rationale
6. Use the Device Comparison tool to compare recommended models against any other PA/VM model

### POC Config Generator

1. Select "POC Config Generator" on the landing page
2. Choose deployment target: Panorama or SCM
3. Enter Panorama IP (or SCM folder for SCM target)
4. Select hub count, branch count, WAN link type, and bandwidth
5. Review auto-configured features and click "Generate"
6. Download the ZIP (Ansible playbooks or Terraform HCL)

### SD-WAN Advisor

1. Select "SD-WAN Advisor" on the landing page
2. Answer questions about existing PA investment, competitor, scale, security, management, and priorities
3. Review the recommendation with confidence score and per-category breakdown
4. Download the Excel report for stakeholder distribution

## Project Structure

```
panos-sdwan-toolkit/
├── app.py                     # Flask routes
├── config.py                  # App configuration
├── Dockerfile
├── nginx.conf                 # HTTPS reverse proxy (port 9443)
├── start.sh                   # Entrypoint script
├── parsers/                   # 23 feature extraction modules
│   ├── base.py                # BaseParser ABC + FeatureResult
│   ├── config_detector.py     # Panorama vs NGFW detection
│   ├── registry.py            # Auto-discovers all parsers
│   └── *.py                   # Feature parsers
├── report/
│   ├── excel_generator.py     # Single + comparison reports
│   ├── html_dashboard.py      # Inline HTML dashboard
│   ├── migration_dashboard.py # SCM migration dashboard
│   ├── scorer.py              # Deployment maturity scoring
│   ├── masker.py              # Sensitive data masking
│   └── styles.py              # Excel cell formatting
├── scm/
│   ├── mapper.py              # PAN-OS to SCM config mapping
│   ├── terraform_generator.py # Terraform HCL generation (paloaltonetworks/scm provider)
│   └── migration_report.py    # Migration report generation
├── sizing/
│   ├── models.py              # PA + VM-Series specs (21 PA + 7 VM), licensing data
│   ├── calculator.py          # Sizing algorithm with series-based options
│   ├── html_dashboard.py      # Sizing dashboard HTML + device comparison tool
│   ├── excel_report.py        # Sizing Excel report
│   └── rag/                   # Datasheet RAG pipeline
│       ├── sources.py         # PA datasheet URL registry
│       ├── refresh.py         # Auto-fetch and refresh datasheets
│       ├── ingest.py          # PDF parsing and chunking
│       ├── store.py           # ChromaDB vector store
│       └── retrieval.py       # Query and retrieve relevant excerpts
├── poc/
│   ├── generator.py           # POC ZIP generation (Ansible + Terraform)
│   ├── templates.py           # PAN-OS XML element builders
│   └── html_dashboard.py      # POC results dashboard
├── advisor/
│   ├── engine.py              # Scoring algorithm, competitive data, feature comparison
│   ├── html_dashboard.py      # Advisor results dashboard
│   └── excel_report.py        # Advisor Excel report
├── templates/
│   └── index.html             # Web UI (landing page + 5 mode wizards)
└── static/
    └── style.css
```

## Dependencies

- Flask, gunicorn -- Web framework and WSGI server
- openpyxl -- Excel report generation
- lxml -- XML parsing
- PyYAML -- YAML serialization
- chromadb -- Vector store for datasheet RAG
- pdfplumber -- PDF text extraction
- duckduckgo-search -- Datasheet URL discovery
- nginx -- HTTPS reverse proxy with self-signed certificate
