"""File uploads for Agent 99 — screenshots, attachments, etc."""
import os
import uuid
from flask import Blueprint, request, jsonify, current_app

upload_bp = Blueprint('upload', __name__)

UPLOAD_DIR = None


def _get_upload_dir():
    global UPLOAD_DIR
    if UPLOAD_DIR is None:
        UPLOAD_DIR = os.path.join(os.path.dirname(current_app.config['DB_PATH']), 'uploads')
        os.makedirs(UPLOAD_DIR, exist_ok=True)
    return UPLOAD_DIR


@upload_bp.route('/file', methods=['POST'])
def upload_file():
    """Upload a file for Agent 99 to reference."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    if not file.filename:
        return jsonify({'error': 'No filename'}), 400

    # Generate safe filename
    ext = os.path.splitext(file.filename)[1].lower()
    safe_name = f'{uuid.uuid4().hex[:12]}{ext}'
    filepath = os.path.join(_get_upload_dir(), safe_name)

    file.save(filepath)

    return jsonify({
        'filename': file.filename,
        'saved_as': safe_name,
        'path': filepath,
        'size': os.path.getsize(filepath),
    })
