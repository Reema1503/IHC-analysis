"""Image loading and exploratory calculations. No display adjustments enter analysis."""
from pathlib import Path
import hashlib
import re
import numpy as np
from PIL import Image, ImageDraw, ImageOps
from scipy import ndimage as ndi
from skimage.color import rgb2hed, hed2rgb, separate_stains, combine_stains, rgb_from_hed
import tifffile

# TIFF containers can advertise a giant page 0 even when only a small page is read.
# Disable Pillow's metadata-only alarm; enforce our own limits before every decode.
Image.MAX_IMAGE_PIXELS = None
MAX_DECODE_PIXELS = 12_000_000
MAX_SIDE = 2400
SUPPORTED = {'.png', '.jpg', '.jpeg', '.tif', '.tiff', '.qptiff', '.bmp'}


def file_hash(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def read_image(path, name=None):
    """Choose a safe slide pyramid page; never decode a giant full-resolution page."""
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED:
        raise ValueError('Supported: PNG, JPEG, BMP, TIFF and RGB QPTIFF. Convert proprietary formats (CZI, ND2, LIF, SVS), PDFs or fluorescence stacks to a 2D image first.')
    warnings, pages, protocol = [], [], ''
    page_index = 0
    if suffix in {'.tif', '.tiff', '.qptiff'}:
        with tifffile.TiffFile(path) as tf:
            first = tf.pages[0]
            original_h, original_w = first.imagelength, first.imagewidth
            channels = int(first.samplesperpixel)
            bits = first.bitspersample
            bits = int(bits[0] if isinstance(bits, tuple) else bits)
            dtype = str(first.dtype)
            original_photo = first.photometric.name
            desc = first.description or ''
            study = re.search(r'<StudyName>(.*?)</StudyName>', desc)
            protocol = study.group(1) if study else ''
            choices = []
            for i, page in enumerate(tf.pages):
                w, h = page.imagewidth, page.imagelength
                kind = re.search(r'<ImageType>(.*?)</ImageType>', page.description or '')
                kind = kind.group(1) if kind else 'TIFF page'
                pages.append({'page': i, 'width': w, 'height': h, 'type': kind})
                same_aspect = abs(w / h - original_w / original_h) < .02 * original_w / original_h
                # Only QPTIFF pages explicitly belonging to the slide pyramid are eligible.
                eligible = i == 0 or (suffix == '.qptiff' and kind in {'ReducedResolution', 'Thumbnail'} and same_aspect and page.photometric == first.photometric)
                if eligible and w * h <= MAX_DECODE_PIXELS:
                    choices.append((w * h, i))
            if not choices:
                raise ValueError('Image is too large for this preview app and has no usable small RGB pyramid page. Export a region or downsampled TIFF/PNG (at most 12 million pixels) from your slide software. The full slide was not decoded.')
            page_index = max(choices)[1]
            page = tf.pages[page_index]
            if page.photometric.name not in {'RGB', 'MINISBLACK'}:
                raise ValueError('This TIFF has an unsupported colour model. Export an RGB brightfield image or a grayscale 2D image first.')
            if page.dtype.kind != 'u' or page.dtype.itemsize not in {1, 2}:
                raise ValueError('Only unsigned 8-bit and 16-bit TIFF pixels are supported. Export with a documented intensity range first.')
            if page.samplesperpixel not in {1, 3, 4}:
                raise ValueError('Multispectral TIFF is not an RGB brightfield image. Export a documented RGB image; channels will not be guessed.')
            try:
                array = page.asarray()
            except (ValueError, RuntimeError) as e:
                # Pillow can decode JPEG/LZW TIFF when imagecodecs is unavailable.
                if page.dtype.itemsize != 1:
                    raise ValueError('Install imagecodecs to read this compressed TIFF.') from e
                with Image.open(path) as pil:
                    pil.seek(page_index)
                    array = np.array(pil)
            if page.planarconfig == 2 and array.ndim == 3 and array.shape[0] == page.samplesperpixel:
                array = np.moveaxis(array, 0, -1)
            if array.ndim not in {2, 3} or (array.ndim == 3 and array.shape[-1] not in {3, 4}):
                raise ValueError('Only a single 2D grayscale/RGB/RGBA page is supported.')
            if len(tf.pages) > 1 and suffix != '.qptiff':
                warnings.append('Multi-page TIFF: only page 0 is loaded. Other pages are not assumed to be pyramid levels or combined.')
            if page_index != 0:
                warnings.append(f'Whole-slide preview uses TIFF page {page_index}; zoom magnifies this preview, not native slide pixels.')
    else:
        with Image.open(path) as pil:
            original_w, original_h = pil.size
            if original_w * original_h > MAX_DECODE_PIXELS:
                raise ValueError('Image exceeds 12 million pixels. Export a smaller region before uploading.')
            mode = pil.mode
            channels = len(pil.getbands())
            bits = 16 if mode.startswith('I;16') else 8
            dtype = 'uint16' if bits == 16 else 'uint8'
            original_photo = mode
            if mode == 'I' or mode == 'F':
                raise ValueError('Floating-point or signed images need an explicit intensity range. Export unsigned 8/16-bit data first.')
            pil = ImageOps.exif_transpose(pil)
            if pil.size != (original_w, original_h):
                warnings.append('EXIF orientation applied; coordinates and original dimensions refer to the oriented image.')
                original_w, original_h = pil.size
            if mode == 'P':
                warnings.append('Palette image converted to RGB for display. Confirm that it is an original brightfield image before analysis.')
                pil = pil.convert('RGB')
            elif mode not in {'L', 'RGB', 'RGBA'} and not mode.startswith('I;16'):
                raise ValueError(f'Unsupported image mode {mode}. Export RGB, RGBA or grayscale first.')
            array = np.array(pil)
    is_rgb = array.ndim == 3 and array.shape[-1] in {3, 4}
    if array.dtype == np.uint16:
        warnings.append('16-bit values are scaled by the full 0–65535 range to an 8-bit working preview. No per-image contrast normalization. Measurements use this quantized preview, not native 16-bit pixels.')
        array = np.round(array.astype(np.float32) / 65535 * 255).astype(np.uint8)
    if array.dtype != np.uint8:
        raise ValueError('Unsupported decoded pixel type; export an unsigned 8/16-bit image.')
    if not is_rgb:
        array = np.repeat(array[..., None], 3, axis=2)
        warnings.append('Grayscale image: viewing and annotations work; stain separation is disabled.')
    elif array.shape[-1] == 4:
        alpha = array[..., 3:4].astype(np.float32) / 255
        array = np.round(array[..., :3] * alpha + 255 * (1 - alpha)).astype(np.uint8)
        warnings.append('Transparency composited over white for the working image.')
    loaded_h, loaded_w = array.shape[:2]
    pil = Image.fromarray(array)
    pil.thumbnail((MAX_SIDE, MAX_SIDE), Image.Resampling.LANCZOS)
    rgb = np.array(pil)
    wh, ww = rgb.shape[:2]
    if (ww, wh) != (original_w, original_h):
        warnings.append('All masks, QC and area estimates use the working preview. Fine cells, small tears and pale tissue can be missed. Export a native-resolution region for detailed review.')
    meta = {'filename': name or path.name, 'original_width': original_w, 'original_height': original_h,
            'channels': channels, 'bit_depth_per_channel': bits, 'dtype': dtype,
            'colour_model': original_photo, 'page': page_index, 'pages': pages,
            'decoded_width': loaded_w, 'decoded_height': loaded_h,
            'working_width': ww, 'working_height': wh, 'is_rgb': is_rgb,
            'scale_x': original_w / ww, 'scale_y': original_h / wh,
            'scanner_study_name': protocol, 'warnings': warnings,
            'sha256': file_hash(path), 'analysis_version': '1.0'}
    return rgb, meta


# H&E basis: fixed normalized H/E vectors, plus an orthogonal residual direction.
# The residual is neither DAB nor a third biological stain.
RGB_FROM_HE = np.array(rgb_from_hed, dtype=float, copy=True)
RGB_FROM_HE[:2] /= np.linalg.norm(RGB_FROM_HE[:2], axis=1, keepdims=True)
RGB_FROM_HE[2] = np.cross(RGB_FROM_HE[0], RGB_FROM_HE[1])
RGB_FROM_HE[2] /= np.linalg.norm(RGB_FROM_HE[2])
HE_FROM_RGB = np.linalg.inv(RGB_FROM_HE)


def stain_channels(rgb, mode='dab'):
    if mode == 'he':
        return separate_stains(rgb, HE_FROM_RGB).astype(np.float32)
    if mode != 'dab':
        raise ValueError('Unknown stain mode.')

    """Fixed scikit-image HED basis; H=0, DAB=2. Values are relative, not calibrated."""
    return np.maximum(rgb2hed(rgb), 0).astype(np.float32)


def stain_preview(hed, index, mode='dab'):
    separated = np.zeros_like(hed)
    separated[..., index] = hed[..., index]
    reconstructed = combine_stains(separated, RGB_FROM_HE) if mode == 'he' else hed2rgb(separated)
    return np.round(np.clip(reconstructed, 0, 1) * 255).astype(np.uint8)


def rectangle_mask(shape, rect):
    mask = np.zeros(shape, dtype=bool)
    if not isinstance(rect, dict):
        raise ValueError('Draw a measurement ROI first.')
    vals = [float(rect.get(k, 0)) for k in ['x', 'y', 'w', 'h']]
    if not np.all(np.isfinite(vals)):
        raise ValueError('Invalid rectangle coordinates.')
    x, y, w, h = vals
    if w <= 0 or h <= 0:
        raise ValueError('Rectangle must have a positive width and height.')
    height, width = shape
    left, right = max(0, int(np.floor(x))), min(width, int(np.ceil(x + w)))
    top, bottom = max(0, int(np.floor(y))), min(height, int(np.ceil(y + h)))
    mask[top:bottom, left:right] = True
    return mask


def tissue_mask(rgb, settings):
    """Initial mask: sufficiently dark OR coloured; no hole-filling of empty spaces."""
    brightness = rgb.mean(axis=2)
    colour_spread = rgb.max(axis=2).astype(float) - rgb.min(axis=2).astype(float)
    mask = (brightness < float(settings.get('tissue_brightness', 215))) | (colour_spread > float(settings.get('tissue_colour', 25)))
    for correction in settings.get('corrections', []):
        selected = rectangle_mask(mask.shape, correction)
        if correction.get('kind') == 'include':
            mask[selected] = True
        elif correction.get('kind') == 'exclude':
            mask[selected] = False
    return mask


def measure(rgb, stains, settings):
    mode = settings.get('stain_mode', 'dab')
    channel = settings.get('measure_channel', 'hematoxylin' if mode == 'he' else 'dab')
    allowed = {'he': {'hematoxylin': 0, 'eosin': 1}, 'dab': {'hematoxylin': 0, 'dab': 2}}
    if mode not in allowed or channel not in allowed[mode]:
        raise ValueError('The selected channel does not belong to the confirmed staining mode.')
    values = stains[..., allowed[mode][channel]]
    threshold = float(settings.get('threshold', .05))
    if not np.isfinite(threshold) or not 0 <= threshold <= 2:
        raise ValueError('Stain threshold must be 0 to 2.')
    mask = tissue_mask(rgb, settings)
    roi = rectangle_mask(mask.shape, settings.get('roi'))
    denominator = mask & roi
    above_mask = denominator & (values > threshold)
    total, above = int(denominator.sum()), int(above_mask.sum())
    hist, edges = np.histogram(values[denominator], bins=40, range=(0, 2))
    mean = float(values[denominator].mean()) if total else None
    return {'tissue_pixels': total, 'area_above_threshold_pixels': above,
            'area_above_threshold_pct': 100 * above / total if total else None,
            'threshold': threshold, 'histogram_counts': hist.tolist(),
            'histogram_edges': edges.tolist(), 'mean_relative_stain': mean,
            'dab_mean_relative': mean if channel == 'dab' else None,
            'channel': channel, 'stain_mode': mode,
            'resolution': 'working preview pixels; not cell counts or protein abundance',
            'method': ('fixed normalized H&E + orthogonal residual basis' if mode == 'he' else 'fixed scikit-image HED') + '; ' + channel + '; strictly greater than threshold'}, mask, above_mask


def quality(rgb, settings):
    mask = tissue_mask(rgb, settings)
    gray = rgb.mean(axis=2).astype(float) / 255
    lap = ndi.laplace(gray)
    tissue_n = int(mask.sum())
    # Saturation in tissue only; white slide background is not an automatic alarm.
    clipped = mask & ((rgb.min(axis=2) <= 1) | (rgb.max(axis=2) >= 254))
    focus = float(lap[mask].var()) if tissue_n else None
    tile_means = []
    for ys in np.array_split(np.arange(rgb.shape[0]), 4):
        for xs in np.array_split(np.arange(rgb.shape[1]), 4):
            tile, tm = gray[np.ix_(ys, xs)], mask[np.ix_(ys, xs)]
            if (~tm).sum() > 100:
                tile_means.append(float(tile[~tm].mean()))
    illumination = float(np.ptp(tile_means)) if len(tile_means) > 1 else None
    return {'focus_laplacian_variance': focus, 'background_tile_brightness_range': illumination,
            'tissue_clipped_pct': float(clipped.sum() / tissue_n * 100) if tissue_n else None,
            'tissue_pixels': tissue_n,
            'review_flags': [s for condition, s in [
                (focus is not None and focus < .0001, 'Possible low detail/blur: inspect a native-resolution region. Low texture can also cause this.'),
                (illumination is not None and illumination > .08, 'Possible uneven background brightness: review illumination, staining and tissue-mask errors.'),
                (tissue_n > 0 and clipped.sum() / tissue_n > .01, 'Possible clipped channels in tissue: inspect saturation overlay; coloured tissue or mask errors can contribute.'),
                (tissue_n == 0, 'No tissue selected by the initial mask. Adjust settings or include tissue manually.')
            ] if condition]}, clipped
