import os
import tempfile

UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', tempfile.gettempdir())
MAX_CONTENT_LENGTH = 100 * 1024 * 1024  # 100MB max upload
REPORT_DIR = os.path.join(UPLOAD_FOLDER, 'reports')
os.makedirs(REPORT_DIR, exist_ok=True)
