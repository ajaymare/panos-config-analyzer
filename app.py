"""PAN-OS SD-WAN Configuration Parser — Flask App."""
import os
import xml.etree.ElementTree as ET

from flask import Flask, render_template, request, send_file, jsonify

import config as app_config
from parsers import config_detector, registry
from report import excel_generator
from report.masker import mask_results
from api_client import connector

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = app_config.MAX_CONTENT_LENGTH


@app.route('/')
def index():
    error = request.args.get('error')
    return render_template('index.html', error=error)


def _parse_single_xml(file_stream, filename):
    """Parse a single XML file and return results dict."""
    try:
        tree = ET.parse(file_stream)
        xml_root = tree.getroot()
    except ET.ParseError as e:
        raise ValueError(f'Invalid XML in {filename}: {e}')

    config_type = config_detector.get_config_type(xml_root)
    containers = config_detector.detect(xml_root)

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
    }


@app.route('/parse', methods=['POST'])
def parse():
    method = request.form.get('method', 'upload')

    try:
        if method == 'upload':
            files = request.files.getlist('config_files')
            if not files or all(f.filename == '' for f in files):
                return 'No file selected', 400

            configs_data = []
            for f in files:
                if f.filename == '':
                    continue
                display_name = os.path.splitext(f.filename)[0]
                config_data = _parse_single_xml(f.stream, display_name)
                configs_data.append(config_data)

            if not configs_data:
                return 'No valid files uploaded', 400

            # Apply masking if requested
            mask_categories = request.form.getlist('mask_categories')
            if mask_categories:
                for cfg in configs_data:
                    cfg['results'] = mask_results(cfg['results'], mask_categories)

            if len(configs_data) == 1:
                # Single file — use existing report
                filepath = excel_generator.generate(
                    configs_data[0]['results'],
                    configs_data[0]['config_type'],
                )
            else:
                # Multiple files — comparison report
                filepath = excel_generator.generate_comparison(configs_data)

        elif method == 'api':
            hostname = request.form.get('hostname', '').strip()
            api_key = request.form.get('api_key', '').strip()
            if not hostname or not api_key:
                return 'Hostname and API key are required', 400

            verify_ssl = 'verify_ssl' in request.form
            try:
                xml_root, device_type = connector.fetch_config(hostname, api_key, verify_ssl)
            except Exception as e:
                return f'API connection failed: {e}', 500

            if xml_root is None:
                return 'Failed to load configuration', 500

            config_type = device_type
            if config_type == 'unknown':
                config_type = config_detector.get_config_type(xml_root)
            containers = config_detector.detect(xml_root)

            if not containers:
                return 'No configuration containers found in XML', 400

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

            filepath = excel_generator.generate(all_results, config_type)
        else:
            return 'Invalid method', 400

        return send_file(
            filepath,
            as_attachment=True,
            download_name=os.path.basename(filepath),
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )

    except ValueError as e:
        return str(e), 400
    except Exception as e:
        return f'Unexpected error: {e}', 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
