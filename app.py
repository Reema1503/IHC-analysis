"""Run: python app.py. Local Flask server, image calculations stay on this computer."""
from pathlib import Path
import io
import json
import os
import uuid
from threading import RLock
import numpy as np
from PIL import Image
from flask import Flask, request, jsonify, render_template, send_file
from werkzeug.exceptions import HTTPException
from analysis import read_image, stain_channels, stain_preview, tissue_mask, measure, quality, SUPPORTED

ROOT = Path(__file__).resolve().parent
DATA = Path(os.environ.get('IHC_DATA_DIR', ROOT / 'data'))
DATA.mkdir(parents=True, exist_ok=True)
app = Flask(__name__)
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
app.config['MAX_CONTENT_LENGTH'] = 1024 * 1024 * 1024  # 1 GiB/request
lock = RLock()


def catalog():
    return [json.loads(p.read_text(encoding='utf-8')) for p in sorted(DATA.glob('*/meta.json'))]


def image_data(image_id):
    if len(image_id) != 64 or any(c not in '0123456789abcdef' for c in image_id):
        raise ValueError('Invalid image ID.')
    folder = DATA / image_id
    if not (folder / 'meta.json').exists():
        raise ValueError('Upload this original image first.')
    meta = json.loads((folder / 'meta.json').read_text(encoding='utf-8'))
    with Image.open(folder / 'original.png') as pil:
        rgb = np.array(pil.convert('RGB'))
    return folder, meta, rgb


def ensure_stains(folder, meta, rgb, mode='dab'):
    if not meta['is_rgb']:
        raise ValueError('Stain separation requires an RGB brightfield image.')
    if mode not in {'he', 'dab'}:
        raise ValueError('Select H&E or DAB + hematoxylin and confirm the protocol.')
    cache = folder / f'{mode}_v11.npy'
    if not cache.exists():
        with lock:
            if not cache.exists():
                stains = stain_channels(rgb, mode)
                channels = [('hematoxylin', 0), ('eosin', 1)] if mode == 'he' else [('hematoxylin', 0), ('dab', 2)]
                for name, index in channels:
                    Image.fromarray(stain_preview(stains, index, mode)).save(folder / f'{mode}_v11_{name}.png')
                np.save(cache, stains)
    return np.load(cache, mmap_mode='r')


def png_response(array):
    stream = io.BytesIO()
    Image.fromarray(array).save(stream, format='PNG')
    stream.seek(0)
    return send_file(stream, mimetype='image/png')


def confirmed_mode(settings):
    if settings.get('confirmed') is not True:
        raise ValueError('Select your staining mode and tick protocol confirmation first.')
    staining = settings.get('staining')
    # Compatibility with v1 DAB settings; H&E must be explicitly selected in v1.1.
    if staining == 'H&E':
        return 'he'
    if staining in {None, 'DAB + hematoxylin'} and settings.get('chromogen') == 'DAB (brown)' and settings.get('counterstain') == 'Hematoxylin (blue)':
        return 'dab'
    raise ValueError('Only confirmed H&E or DAB + hematoxylin supports separation.')


@app.errorhandler(Exception)
def error(e):
    if isinstance(e, HTTPException):
        return jsonify(error='Upload is over 1 GiB; use a smaller exported region.' if e.code == 413 else e.description), e.code
    app.logger.error('%s: %s', type(e).__name__, e)
    return jsonify(error=str(e)), 400


@app.get('/')
def home():
    return render_template('index.html')


@app.get('/api/images')
def images():
    return jsonify(catalog())


@app.post('/api/upload')
def upload():
    file = request.files.get('file')
    if file is None:
        raise ValueError('Choose an image file.')
    name = file.filename or 'unnamed'
    suffix = Path(name).suffix.lower()
    if suffix not in SUPPORTED:
        raise ValueError(f'{name}: unsupported format. Use PNG/JPEG/BMP/TIFF or RGB QPTIFF. Convert CZI/ND2/LIF/SVS, PDF and fluorescence stacks first.')
    temp = DATA / (uuid.uuid4().hex + suffix)
    file.save(temp)
    try:
        rgb, meta = read_image(temp, name)
        image_id = meta['sha256']
        meta['id'] = image_id
        folder = DATA / image_id
        folder.mkdir(exist_ok=True)
        with lock:
            Image.fromarray(rgb).save(folder / 'original.png')
            (folder / 'meta.json').write_text(json.dumps(meta, indent=2), encoding='utf-8')
        # Original uploads are left with the researcher. Only derived previews are retained here.
        return jsonify(meta)
    finally:
        temp.unlink(missing_ok=True)


@app.get('/api/image/<image_id>/<kind>')
def image_preview(image_id, kind):
    folder, meta, rgb = image_data(image_id)
    if kind == 'original':
        return send_file(folder / 'original.png', mimetype='image/png')
    if kind not in {'dab', 'hematoxylin', 'eosin'}:
        raise ValueError('Unknown preview type.')
    if request.args.get('confirmed') != 'yes':
        raise ValueError('Confirm your staining protocol before stain separation.')
    mode = request.args.get('mode', 'dab')
    if mode not in {'he', 'dab'} or kind not in ({'hematoxylin', 'eosin'} if mode == 'he' else {'hematoxylin', 'dab'}):
        raise ValueError('This stain preview is not available for the selected protocol.')
    ensure_stains(folder, meta, rgb, mode)
    return send_file(folder / f'{mode}_v11_{kind}.png', mimetype='image/png')


@app.post('/api/analyze/<image_id>')
def analyze(image_id):
    folder, meta, rgb = image_data(image_id)
    settings = request.get_json()
    if not isinstance(settings, dict):
        raise ValueError('Settings must be an object.')
    qc, _ = quality(rgb, settings)
    result = {'quality': qc, 'measurement': None}
    if settings.get('measure'):
        mode = confirmed_mode(settings)
        settings = {**settings, 'stain_mode': mode}
        hed = ensure_stains(folder, meta, rgb, mode)
        measurement, _, _ = measure(rgb, hed, settings)
        result['measurement'] = measurement
    return jsonify(result)


@app.post('/api/overlay/<image_id>')
def overlay(image_id):
    folder, meta, rgb = image_data(image_id)
    settings = request.get_json()
    if not isinstance(settings, dict):
        raise ValueError('Settings must be an object.')
    kind = settings.get('overlay', 'tissue')
    if kind == 'tissue':
        mask = tissue_mask(rgb, settings)
        colour = [35, 210, 157]
    elif kind == 'saturation':
        _, mask = quality(rgb, settings)
        colour = [255, 0, 170]
    elif kind == 'positive':
        mode = confirmed_mode(settings)
        settings = {**settings, 'stain_mode': mode}
        hed = ensure_stains(folder, meta, rgb, mode)
        _, _, mask = measure(rgb, hed, settings)
        colour = [255, 180, 0]
    else:
        raise ValueError('Unknown overlay.')
    rgba = np.zeros((*rgb.shape[:2], 4), dtype=np.uint8)
    rgba[mask, :3] = colour
    rgba[mask, 3] = 110
    return png_response(rgba)


if __name__ == '__main__':
    print('Open http://127.0.0.1:8503')
    app.run(host='127.0.0.1', port=8503, debug=False, threaded=True)
