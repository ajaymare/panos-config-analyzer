"""PAN-OS SD-WAN Configuration Parser — Flask App."""
import json
import os
import signal
import subprocess
import time
import uuid
import xml.etree.ElementTree as ET
import zipfile

from flask import Flask, render_template, request, send_file, jsonify, Response

import config as app_config
from parsers import config_detector, registry
from parsers.base import FeatureResult
from report import excel_generator
from report.html_dashboard import generate_dashboard_fragment
from report.masker import mask_results
from report.migration_dashboard import generate_migration_dashboard_fragment
from scm.ansible_generator import generate_ansible_zip
from scm.mapper import map_results
from scm.migration_report import generate_migration_report
from sizing.calculator import calculate_sizing
from sizing.html_dashboard import generate_sizing_dashboard
from sizing.excel_report import generate_sizing_report
from sizing.rag.retrieval import get_docs_for_sizing_result
from sizing.rag.refresh import auto_refresh_if_stale, refresh_datasheets, get_status as rag_status

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = app_config.MAX_CONTENT_LENGTH

# Auto-refresh PA datasheets in background on startup (non-blocking)
import threading
def _background_rag_init():
    import logging
    logger = logging.getLogger(__name__)
    try:
        auto_refresh_if_stale(max_age_days=30)
    except Exception as e:
        logger.warning("Background RAG init failed (non-fatal): %s", e)

threading.Thread(target=_background_rag_init, daemon=True).start()

# In-memory session cache for parsed results (for Ansible generation)
# Key: session_id, Value: {'configs_data': [...], 'timestamp': float}
_session_cache: dict[str, dict] = {}
_SESSION_TTL = 1800  # 30 minutes


def _cache_cleanup():
    """Remove expired session cache entries."""
    now = time.time()
    expired = [k for k, v in _session_cache.items() if now - v['timestamp'] > _SESSION_TTL]
    for k in expired:
        del _session_cache[k]

# SD-WAN features that are managed by Panorama (not present in NGFW exports)
_PANORAMA_SDWAN_FEATURES = {
    'SD-WAN Interface Profiles', 'App-ID Steering', 'Path Quality Metrics',
    'Bandwidth Monitoring', 'Probe Idle Time', 'Failback Hold Time',
    'Link Remediation (FEC)', 'Packet Duplication',
    'VPN Automation', 'Topology Configured',
    'Hub Capacity', 'Prisma Access Hub',
    'Sub-Second Failover',
    'ADEM Integration', 'SD-WAN Reporting',
    'ZTP Support',
    'BGP AS Control', 'BGP Private AS', 'BGP Security Rule',
    'Multi-VR Support',
    'SD-WAN Security Rules', 'SD-WAN NAT Policies',
    'Custom Applications', 'Template/Stack Mapping',
    'Log Collection',
}


@app.route('/')
def index():
    error = request.args.get('error')
    return render_template('index.html', error=error)


def _extract_versions(xml_root):
    """Extract PAN-OS and SD-WAN plugin versions from XML config."""
    panos_version = xml_root.get('version', '')
    detail_version = xml_root.get('detail-version', '')

    # SD-WAN plugin version: plugins/sd_wan/@version
    sdwan_version = ''
    for path in ['devices/entry/plugins/sd_wan', 'plugins/sd_wan']:
        node = xml_root.find(path)
        if node is not None:
            sdwan_version = node.get('version', '')
            break

    return {
        'panos_version': panos_version,
        'detail_version': detail_version,
        'sdwan_version': sdwan_version,
    }


def _make_session_dir():
    """Create a unique per-request directory for report files."""
    session_id = uuid.uuid4().hex[:12]
    session_dir = os.path.join(app_config.REPORT_DIR, session_id)
    os.makedirs(session_dir, exist_ok=True)
    return session_id, session_dir


def _parse_single_xml(file_stream, filename):
    """Parse a single XML file and return results dict."""
    try:
        tree = ET.parse(file_stream)
        xml_root = tree.getroot()
    except ET.ParseError as e:
        raise ValueError(f'Invalid XML in {filename}: {e}')

    config_type = config_detector.get_config_type(xml_root)
    containers = config_detector.detect(xml_root)
    versions = _extract_versions(xml_root)
    panorama_managed = config_detector.is_panorama_managed(xml_root)
    serial = config_detector.get_device_serial(xml_root)

    if not containers:
        raise ValueError(f'No configuration containers found in {filename}')

    all_results = []
    parser_classes = registry.get_parsers()
    for parser_cls in parser_classes:
        parser = parser_cls()
        try:
            results = parser.extract(xml_root, containers)
            all_results.extend(results)
        except Exception as e:
            all_results.append(FeatureResult(
                feature_name=parser.FEATURE_NAME,
                enabled=False,
                summary=f'Parse error: {e}',
                source='Error',
            ))

    return {
        'filename': filename,
        'config_type': config_type,
        'results': all_results,
        'versions': versions,
        'panorama_managed': panorama_managed,
        'serial': serial,
    }


def _mark_panorama_managed(results):
    """Mark disabled SD-WAN features as Panorama-Managed for managed NGFWs."""
    for r in results:
        if not r.enabled and r.feature_name in _PANORAMA_SDWAN_FEATURES:
            r.summary = 'Panorama-Managed'
    return results


def _correlate_with_panorama(ngfw_cfg, panorama_cfg):
    """Enrich NGFW results with Panorama's SD-WAN features.

    For each SD-WAN feature that shows 'Not configured' on the NGFW,
    copy the enabled result from Panorama if available.
    """
    # Build lookup of Panorama's enabled features
    panorama_features = {}
    for r in panorama_cfg['results']:
        if r.enabled and r.feature_name in _PANORAMA_SDWAN_FEATURES:
            if r.feature_name not in panorama_features:
                panorama_features[r.feature_name] = r

    enriched = []
    for r in ngfw_cfg['results']:
        if not r.enabled and r.feature_name in panorama_features:
            # Copy Panorama result, attribute source
            pr = panorama_features[r.feature_name]
            enriched_result = FeatureResult(
                feature_name=pr.feature_name,
                enabled=True,
                summary=pr.summary,
                columns=pr.columns,
                rows=pr.rows,
                source=f'Panorama → {ngfw_cfg["filename"]}',
            )
            enriched.append(enriched_result)
        else:
            enriched.append(r)

    # Copy Panorama's SD-WAN plugin version to NGFW if missing
    ngfw_versions = ngfw_cfg.get('versions') or {}
    pan_versions = panorama_cfg.get('versions') or {}
    if not ngfw_versions.get('sdwan_version') and pan_versions.get('sdwan_version'):
        ngfw_versions['sdwan_version'] = pan_versions['sdwan_version']
        ngfw_cfg['versions'] = ngfw_versions

    ngfw_cfg['results'] = enriched


def _apply_panorama_correlation(configs_data):
    """Apply Panorama correlation to all Panorama-managed NGFWs.

    If a Panorama config is present: correlate NGFW features with Panorama results.
    If no Panorama config: mark SD-WAN features as 'Panorama-Managed'.
    """
    panorama_cfgs = [c for c in configs_data if c['config_type'] == 'panorama']
    ngfw_cfgs = [c for c in configs_data if c['config_type'] == 'ngfw']

    panorama_cfg = panorama_cfgs[0] if panorama_cfgs else None

    for ngfw in ngfw_cfgs:
        if not ngfw.get('panorama_managed'):
            continue

        if panorama_cfg:
            _correlate_with_panorama(ngfw, panorama_cfg)
        else:
            _mark_panorama_managed(ngfw['results'])


@app.route('/parse', methods=['POST'])
def parse():
    try:
        # Create isolated session directory for this request
        session_id, session_dir = _make_session_dir()

        files = request.files.getlist('config_files')
        if not files or all(f.filename == '' for f in files):
            return jsonify({'error': 'No file selected'}), 400

        configs_data = []
        for f in files:
            if f.filename == '':
                continue
            display_name = os.path.splitext(f.filename)[0]
            config_data = _parse_single_xml(f.stream, display_name)
            configs_data.append(config_data)

        if not configs_data:
            return jsonify({'error': 'No valid files uploaded'}), 400

        # Correlate Panorama-managed NGFWs with Panorama config
        _apply_panorama_correlation(configs_data)

        # Apply masking if requested
        mask_categories = request.form.getlist('mask_categories')
        if mask_categories:
            for cfg in configs_data:
                cfg['results'] = mask_results(cfg['results'], mask_categories)

        if len(configs_data) == 1:
            excel_path = excel_generator.generate(
                configs_data[0]['results'],
                configs_data[0]['config_type'],
                versions=configs_data[0].get('versions'),
                output_dir=session_dir,
                filename=configs_data[0]['filename'],
                serial=configs_data[0].get('serial'),
            )
        else:
            excel_path = excel_generator.generate_comparison(
                configs_data, output_dir=session_dir,
            )

        # Generate dashboard HTML fragment
        dashboard_html = generate_dashboard_fragment(configs_data)

        # Cache parsed results for Ansible generation
        _cache_cleanup()
        _session_cache[session_id] = {
            'configs_data': configs_data,
            'timestamp': time.time(),
        }

        # Return JSON with dashboard HTML and scoped Excel download URL
        excel_filename = os.path.basename(excel_path)
        return jsonify({
            'dashboard_html': dashboard_html,
            'excel_url': f'/download/{session_id}/{excel_filename}',
            'excel_filename': excel_filename,
            'session_id': session_id,
        })

    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': f'Unexpected error: {e}'}), 500


@app.route('/download/<session_id>/<filename>')
def download(session_id, filename):
    """Serve an Excel report file scoped to a session directory."""
    # Prevent path traversal
    if '..' in session_id or '..' in filename or '/' in session_id:
        return 'Invalid request', 400

    filepath = os.path.join(app_config.REPORT_DIR, session_id, filename)
    if not os.path.exists(filepath):
        return 'File not found or expired', 404

    return send_file(
        filepath,
        as_attachment=True,
        download_name=filename,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )


@app.route('/parse-migration', methods=['POST'])
def parse_migration():
    """Parse XML configs and generate SCM migration analysis dashboard + Ansible ZIP."""
    try:
        session_id, session_dir = _make_session_dir()

        files = request.files.getlist('config_files')
        if not files or all(f.filename == '' for f in files):
            return jsonify({'error': 'No file selected'}), 400

        configs_data = []
        for f in files:
            if f.filename == '':
                continue
            display_name = os.path.splitext(f.filename)[0]
            config_data = _parse_single_xml(f.stream, display_name)
            configs_data.append(config_data)

        if not configs_data:
            return jsonify({'error': 'No valid files uploaded'}), 400

        _apply_panorama_correlation(configs_data)

        # Collect all results
        all_results = []
        for cfg in configs_data:
            all_results.extend(cfg['results'])

        # Get selected SCM features from form
        selected_features = request.form.getlist('scm_features')
        if not selected_features:
            selected_features = None

        # Get optional SCM credentials from form
        credentials = None
        cid = request.form.get('scm_client_id', '').strip()
        csec = request.form.get('scm_client_secret', '').strip()
        ctsg = request.form.get('scm_tsg_id', '').strip()
        if cid or csec or ctsg:
            credentials = {'client_id': cid, 'client_secret': csec, 'tsg_id': ctsg}

        # Map results to SCM payloads
        mapped = map_results(all_results)
        if selected_features is not None:
            mapped_filtered = {k: v for k, v in mapped.items() if k in selected_features}
        else:
            mapped_filtered = mapped

        # Generate Ansible ZIP
        zip_path = generate_ansible_zip(
            all_results, session_dir,
            selected_features=selected_features,
            credentials=credentials,
        )
        zip_filename = os.path.basename(zip_path)

        # Extract playbooks for in-tool execution
        playbook_dir = os.path.join(session_dir, 'playbooks')
        with zipfile.ZipFile(zip_path, 'r') as zf:
            zf.extractall(playbook_dir)
        # The ZIP has a top-level scm-ansible-playbooks/ prefix
        playbook_root = os.path.join(playbook_dir, 'scm-ansible-playbooks')

        # Generate migration report Excel
        report_bytes = generate_migration_report(
            all_results, selected_features=selected_features, mapped=mapped_filtered,
        )
        report_filename = 'SCM_Migration_Report.xlsx'
        report_path = os.path.join(session_dir, report_filename)
        with open(report_path, 'wb') as rf:
            rf.write(report_bytes)

        # Generate migration dashboard HTML
        dashboard_html = generate_migration_dashboard_fragment(
            all_results,
            selected_features=selected_features,
            mapped=mapped_filtered,
            configs_data=configs_data,
        )

        # Cache for later use (including playbook path for execution)
        _cache_cleanup()
        _session_cache[session_id] = {
            'configs_data': configs_data,
            'playbook_root': playbook_root,
            'timestamp': time.time(),
        }

        return jsonify({
            'dashboard_html': dashboard_html,
            'ansible_url': f'/download-ansible/{session_id}/{zip_filename}',
            'ansible_filename': zip_filename,
            'excel_url': f'/download/{session_id}/{report_filename}',
            'excel_filename': report_filename,
            'session_id': session_id,
        })

    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': f'Unexpected error: {e}'}), 500


@app.route('/generate-ansible/<session_id>', methods=['POST'])
def generate_ansible(session_id):
    """Generate Ansible playbook ZIP from cached parsed results."""
    if '..' in session_id or '/' in session_id:
        return jsonify({'error': 'Invalid session'}), 400

    _cache_cleanup()
    cached = _session_cache.get(session_id)
    if not cached:
        return jsonify({'error': 'Session expired. Please re-upload and parse your config files.'}), 404

    try:
        # Collect all FeatureResults across all configs
        all_results = []
        for cfg in cached['configs_data']:
            all_results.extend(cfg['results'])

        # Get selected features from request body (if provided)
        selected_features = None
        if request.is_json and request.json:
            selected_features = request.json.get('selected_features')

        session_dir = os.path.join(app_config.REPORT_DIR, session_id)
        os.makedirs(session_dir, exist_ok=True)

        zip_path = generate_ansible_zip(
            all_results, session_dir,
            selected_features=selected_features,
        )
        zip_filename = os.path.basename(zip_path)

        return jsonify({
            'ansible_url': f'/download-ansible/{session_id}/{zip_filename}',
            'ansible_filename': zip_filename,
        })
    except Exception as e:
        return jsonify({'error': f'Failed to generate Ansible playbooks: {e}'}), 500


@app.route('/download-ansible/<session_id>/<filename>')
def download_ansible(session_id, filename):
    """Serve an Ansible playbook ZIP file scoped to a session directory."""
    if '..' in session_id or '..' in filename or '/' in session_id:
        return 'Invalid request', 400

    filepath = os.path.join(app_config.REPORT_DIR, session_id, filename)
    if not os.path.exists(filepath):
        return 'File not found or expired', 404

    return send_file(
        filepath,
        as_attachment=True,
        download_name=filename,
        mimetype='application/zip',
    )


def _get_playbook_root(session_id: str) -> str | None:
    """Resolve playbook root directory for a session (works across workers)."""
    playbook_root = os.path.join(app_config.REPORT_DIR, session_id, 'playbooks', 'scm-ansible-playbooks')
    if os.path.isdir(playbook_root):
        return playbook_root
    # Also check session cache (same worker)
    cached = _session_cache.get(session_id)
    if cached and 'playbook_root' in cached and os.path.isdir(cached['playbook_root']):
        return cached['playbook_root']
    return None


@app.route('/playbook-list/<session_id>')
def playbook_list(session_id):
    """List available playbooks for a session."""
    if '..' in session_id or '/' in session_id:
        return jsonify({'error': 'Invalid session'}), 400

    playbook_root = _get_playbook_root(session_id)
    if not playbook_root:
        return jsonify({'error': 'Session expired. Please re-upload your config.'}), 404

    playbooks = sorted(
        f for f in os.listdir(playbook_root)
        if f.endswith('.yml') and not f.startswith('.')
    )
    return jsonify({'playbooks': playbooks})


@app.route('/run-playbook/<session_id>', methods=['POST'])
def run_playbook(session_id):
    """Run one or more Ansible playbooks sequentially and stream output via SSE."""
    if '..' in session_id or '/' in session_id:
        return jsonify({'error': 'Invalid session'}), 400

    playbook_root = _get_playbook_root(session_id)
    if not playbook_root:
        return jsonify({'error': 'Session expired. Please re-upload your config.'}), 404

    cached = _session_cache.get(session_id) or {}

    data = request.get_json(force=True)
    creds = data.get('credentials', {})

    # Accept single playbook or list of playbooks
    playbooks = data.get('playbooks', [])
    if not playbooks:
        single = data.get('playbook', '')
        if single:
            playbooks = [single]
    if not playbooks:
        return jsonify({'error': 'No playbooks specified'}), 400

    # Validate all playbook names
    for pb in playbooks:
        if not pb or '..' in pb or '/' in pb:
            return jsonify({'error': f'Invalid playbook name: {pb}'}), 400
        if not os.path.isfile(os.path.join(playbook_root, pb)):
            return jsonify({'error': f'Playbook not found: {pb}'}), 404

    # Validate credentials
    client_id = creds.get('client_id', '').strip()
    client_secret = creds.get('client_secret', '').strip()
    tsg_id = creds.get('tsg_id', '').strip()
    if not client_id or not client_secret or not tsg_id:
        return jsonify({'error': 'All SCM credentials (Client ID, Client Secret, TSG ID) are required.'}), 400

    # Write credentials to the playbook working directory
    import yaml
    creds_path = os.path.join(playbook_root, 'group_vars', 'all', 'scm_credentials.yml')
    creds_data = {
        'scm_client_id': client_id,
        'scm_client_secret': client_secret,
        'scm_tsg_id': tsg_id,
        'scm_auth_url': 'https://auth.apps.paloaltonetworks.com/am/oauth2/access_token',
        'scm_base_url': 'https://api.sase.paloaltonetworks.com',
    }
    with open(creds_path, 'w') as cf:
        yaml.dump(creds_data, cf, default_flow_style=False)

    def generate():
        """SSE generator that runs playbooks sequentially and streams output."""
        total = len(playbooks)
        for idx, playbook in enumerate(playbooks, 1):
            # Send playbook start event
            yield f'event: playbook_start\ndata: {json.dumps({"playbook": playbook, "index": idx, "total": total})}\n\n'

            try:
                proc = subprocess.Popen(
                    ['ansible-playbook', '-i', 'inventory/hosts.yml', playbook, '-v'],
                    cwd=playbook_root,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    env={**os.environ, 'ANSIBLE_FORCE_COLOR': '0', 'PYTHONUNBUFFERED': '1'},
                )
                cached['process'] = proc

                for line in iter(proc.stdout.readline, ''):
                    escaped = json.dumps(line.rstrip('\n'))
                    yield f'data: {escaped}\n\n'

                proc.wait()
                exit_code = proc.returncode

                yield f'event: playbook_end\ndata: {json.dumps({"playbook": playbook, "index": idx, "total": total, "exit_code": exit_code})}\n\n'

                # Stop running remaining playbooks if one fails
                if exit_code != 0:
                    yield f'data: {json.dumps(f"Playbook {playbook} failed — stopping queue.")}\n\n'
                    yield f'event: done\ndata: {json.dumps({"exit_code": exit_code, "stopped_at": playbook})}\n\n'
                    return

            except FileNotFoundError:
                yield f'data: {json.dumps("ERROR: ansible-playbook not found.")}\n\n'
                yield f'event: done\ndata: {json.dumps({"exit_code": 127})}\n\n'
                return
            except Exception as e:
                yield f'data: {json.dumps(f"ERROR: {str(e)}")}\n\n'
                yield f'event: done\ndata: {json.dumps({"exit_code": 1})}\n\n'
                return
            finally:
                cached.pop('process', None)

        # All playbooks completed successfully
        yield f'event: done\ndata: {json.dumps({"exit_code": 0})}\n\n'

    return Response(generate(), mimetype='text/event-stream',
                    headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})


@app.route('/stop-playbook/<session_id>', methods=['POST'])
def stop_playbook(session_id):
    """Stop a running Ansible playbook."""
    if '..' in session_id or '/' in session_id:
        return jsonify({'error': 'Invalid session'}), 400

    cached = _session_cache.get(session_id)
    if not cached:
        return jsonify({'error': 'Session not found'}), 404

    proc = cached.get('process')
    if proc and proc.poll() is None:
        proc.send_signal(signal.SIGTERM)
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        return jsonify({'stopped': True})

    return jsonify({'stopped': False, 'message': 'No running playbook'})


@app.route('/refresh-datasheets', methods=['POST'])
def refresh_docs():
    """Manually trigger re-fetch of all PA datasheets."""
    try:
        result = refresh_datasheets()
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/datasheet-status')
def datasheet_status():
    """Return current datasheet ingestion status."""
    try:
        return jsonify(rag_status())
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/calculate-sizing', methods=['POST'])
def sizing():
    """Calculate PA firewall sizing recommendation for SD-WAN deployment."""
    try:
        session_id, session_dir = _make_session_dir()

        inputs = {
            'num_hubs': int(request.form.get('num_hubs', 1)),
            'num_branches': int(request.form.get('num_branches', 1)),
            'hub_public_isps': int(request.form.get('hub_public_isps', 1)),
            'hub_private_isps': int(request.form.get('hub_private_isps', 0)),
            'branch_public_isps': int(request.form.get('branch_public_isps', 1)),
            'branch_private_isps': int(request.form.get('branch_private_isps', 0)),
            'hub_bandwidth_mbps': int(request.form.get('hub_bandwidth_mbps', 1000)),
            'branch_bandwidth_mbps': int(request.form.get('branch_bandwidth_mbps', 100)),
            'hub_sessions': int(request.form.get('hub_sessions', 500000)),
            'branch_sessions': int(request.form.get('branch_sessions', 50000)),
            'threat_prevention': request.form.get('threat_prevention') == 'yes',
            'ssl_decryption': request.form.get('ssl_decryption') == 'yes',
            'url_filtering': request.form.get('url_filtering') == 'yes',
            'wildfire': request.form.get('wildfire') == 'yes',
            'dns_security': request.form.get('dns_security') == 'yes',
            'hub_ha': request.form.get('hub_ha') == 'yes',
            'branch_ha_count': int(request.form.get('branch_ha_count', 0)),
            'vm_series': request.form.get('vm_series') == 'yes',
        }

        result = calculate_sizing(inputs)

        # Retrieve relevant datasheet snippets for recommended models
        doc_refs = get_docs_for_sizing_result(result)
        result['doc_references'] = doc_refs

        dashboard_html = generate_sizing_dashboard(result)
        excel_path = generate_sizing_report(result, output_dir=session_dir)
        excel_filename = os.path.basename(excel_path)

        return jsonify({
            'dashboard_html': dashboard_html,
            'excel_url': f'/download/{session_id}/{excel_filename}',
            'excel_filename': excel_filename,
            'session_id': session_id,
        })

    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': f'Unexpected error: {e}'}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
