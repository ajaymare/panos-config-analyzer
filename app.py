"""PAN-OS SD-WAN Configuration Parser — Flask App."""
import os
import uuid
import xml.etree.ElementTree as ET

from flask import Flask, render_template, request, send_file, jsonify

import config as app_config
from parsers import config_detector, registry
from parsers.base import FeatureResult
from report import excel_generator
from report.html_dashboard import generate_dashboard_fragment
from report.masker import mask_results

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = app_config.MAX_CONTENT_LENGTH

# SD-WAN features that are managed by Panorama (not present in NGFW exports)
_PANORAMA_SDWAN_FEATURES = {
    'SD-WAN Interface Profiles', 'Path Quality Profiles',
    'Traffic Distribution Profiles', 'SD-WAN Policy Rules',
    'VPN Clusters - Topology', 'SaaS Quality Monitoring',
    'Digital Experience Monitoring', 'Link Management',
    'ZTP Support',
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
            )
        else:
            excel_path = excel_generator.generate_comparison(
                configs_data, output_dir=session_dir,
            )

        # Generate dashboard HTML fragment
        dashboard_html = generate_dashboard_fragment(configs_data)

        # Return JSON with dashboard HTML and scoped Excel download URL
        excel_filename = os.path.basename(excel_path)
        return jsonify({
            'dashboard_html': dashboard_html,
            'excel_url': f'/download/{session_id}/{excel_filename}',
            'excel_filename': excel_filename,
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


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
