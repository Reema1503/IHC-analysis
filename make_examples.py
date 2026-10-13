"""Generate deterministic technical examples. These are not biological controls."""
from pathlib import Path
import numpy as np
from PIL import Image
from skimage.color import hed2rgb

folder = Path(__file__).resolve().parent / 'examples'
folder.mkdir(exist_ok=True)
hed = np.zeros((400, 600, 3), dtype=float)
hed[50:350, 40:280, 2] = .10
hed[50:350, 320:560, 0] = .10
rgb = np.round(np.clip(hed2rgb(hed), 0, 1) * 255).astype(np.uint8)
Image.fromarray(rgb).save(folder / 'synthetic_DAB_and_blue.png')
hed[..., 2] = 0
Image.fromarray(np.round(hed2rgb(hed) * 255).astype(np.uint8)).save(folder / 'synthetic_blue_no_DAB.png')
Image.fromarray(np.full((400, 600, 3), 255, np.uint8)).save(folder / 'synthetic_empty_background.png')
print('Created three synthetic technical examples in examples/. Not biological controls.')
