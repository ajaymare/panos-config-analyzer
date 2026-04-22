"""PAN-OS SD-WAN Configuration Parser — Flask App."""
import os
import xml.etree.ElementTree as ET

from flask import Flask, render_template, request, send_file, redirect, url_for

import config as app_config
from parsers import config_detector, registry
from report import excel_generator
from api_client import connector

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = app_config.MAX_CONTENT_LENGTH


@app.route('/')
def index():
    error = request.args.get('error')
    return render_template('index.html', error=error)


@app.route('/parse', methods=['POST'])
def parse():
    xml_root = None
    config_type = 'unknown'

    method = request.form.get('method', 'upload')

    try:
        if method == 'upload':
            f = request.files.get('config_file')
            if not f or f.filename == '':
                return redirect(url_for('index', error='No file selected'))

            # Parse XML
            try:
                tree = ET.parse(f.stream)
                xml_root = tree.getroot()
            except ET.ParseError as e:
                return redirect(url_for('index', error=f'Invalid XML: {e}'))

        elif method == 'api':
            hostname = request.form.get('hostname', '').strip()
            api_key = request.form.get('api_key', '').strip()
            if not hostname or not api_key:
                return redirect(url_for('index', error='Hostname and API key are required'))

            verify_ssl = 'verify_ssl' in request.form
            try:
                xml_root, device_type = connector.fetch_config(hostname, api_key, verify_ssl)
                config_type = device_type
            except Exception as e:
                return redirect(url_for('index', error=f'API connection failed: {e}'))
        else:
            return redirect(url_for('index', error='Invalid method'))

        if xml_root is None:
            return redirect(url_for('index', error='Failed to load configuration'))

        # Detect config type and get containers
        if config_type == 'unknown':
            config_type = config_detector.get_config_type(xml_root)
        containers = config_detector.detect(xml_root)

        if not containers:
            return redirect(url_for('index', error='No configuration containers found in XML'))

        # Run all parsers
        all_results = []
        parser_classes = registry.get_parsers()
        for parser_cls in parser_classes:
            parser = parser_cls()
            try:
                results = parser.extract(xml_root, containers)
                all_results.extend(results)
            except Exception as e:
                # Add a failed result for this parser
                from parsers.base import FeatureResult
                all_results.append(FeatureResult(
                    feature_name=parser.FEATURE_NAME,
                    enabled=False,
                    summary=f'Parse error: {e}',
                    source='Error',
                ))

        # Generate Excel report
        filepath = excel_generator.generate(all_results, config_type)

        # Return as download
        return send_file(
            filepath,
            as_attachment=True,
            download_name=os.path.basename(filepath),
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )

    except Exception as e:
        return redirect(url_for('index', error=f'Unexpected error: {e}'))


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
