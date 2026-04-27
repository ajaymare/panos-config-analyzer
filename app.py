"""PAN-OS SD-WAN Configuration Parser — Flask App."""
import os
import uuid
import xml.etree.ElementTree as ET

from flask import Flask, render_template, request, send_file, jsonify

import config as app_config
from parsers import config_detector, registry
from report import excel_generator
from report.html_dashboard import generate_dashboard_fragment
from report.masker import mask_results
from api_client import connector

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = app_config.MAX_CONTENT_LENGTH


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
            from parsers.base import FeatureResult
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
    }


@app.route('/parse', methods=['POST'])
def parse():
    method = request.form.get('method', 'upload')

    try:
        # Create isolated session directory for this request
        session_id, session_dir = _make_session_dir()

        if method == 'upload':
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

        elif method == 'api':
            hostname = request.form.get('hostname', '').strip()
            api_key = request.form.get('api_key', '').strip()
            if not hostname or not api_key:
                return jsonify({'error': 'Hostname and API key are required'}), 400

            verify_ssl = 'verify_ssl' in request.form
            try:
                xml_root, device_type = connector.fetch_config(hostname, api_key, verify_ssl)
            except Exception as e:
                return jsonify({'error': f'API connection failed: {e}'}), 500

            if xml_root is None:
                return jsonify({'error': 'Failed to load configuration'}), 500

            config_type = device_type
            if config_type == 'unknown':
                config_type = config_detector.get_config_type(xml_root)
            containers = config_detector.detect(xml_root)
            versions = _extract_versions(xml_root)

            if not containers:
                return jsonify({'error': 'No configuration containers found in XML'}), 400

            all_results = []
            parser_classes = registry.get_parsers()
            for parser_cls in parser_classes:
                parser = parser_cls()
                try:
                    results = parser.extract(xml_root, containers)
                    all_results.extend(results)
                except Exception as e:
                    from parsers.base import FeatureResult
                    all_results.append(FeatureResult(
                        feature_name=parser.FEATURE_NAME,
                        enabled=False,
                        summary=f'Parse error: {e}',
                        source='Error',
                    ))

            # Apply masking if requested
            mask_categories = request.form.getlist('mask_categories')
            if mask_categories:
                all_results = mask_results(all_results, mask_categories)

            excel_path = excel_generator.generate(
                all_results, config_type, versions=versions, output_dir=session_dir,
            )
            configs_data = [{
                'filename': hostname,
                'config_type': config_type,
                'results': all_results,
                'versions': versions,
            }]
        else:
            return jsonify({'error': 'Invalid method'}), 400

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
