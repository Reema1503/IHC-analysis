# IHC Image Explorer — local Python dashboard

A learning and review tool for brightfield microscopy. Python handles image reading, colour deconvolution, masks and exploratory calculations. A browser displays the interface. No account, cloud upload, API key or JavaScript package installation is needed.

## Start in VS Code on Windows

1. Extract the ZIP. Open the **ihc-image-explorer** folder in VS Code: **File → Open Folder**. Check that `app.py` is directly inside this folder.
2. Open **Terminal → New Terminal** (PowerShell). Paste these commands, one line at a time:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

3. Open **http://127.0.0.1:8501** in Chrome or Edge. Keep the terminal open. Stop with **Ctrl+C**.

This uses the virtual environment directly, so you do not need to activate it or change PowerShell's execution policy. In VS Code, select **Ctrl+Shift+P → Python: Select Interpreter → .venv** for editing.

Use a recent 64-bit Python (3.11 or newer; 3.12/3.13 are useful defaults). If `py` is unavailable but `python --version` works, use `python -m venv .venv` for the first line. If neither works, install Python before continuing. An internet connection is needed to install packages, but normal image use is local.

To reopen later, open the same folder and run only:

```powershell
.\.venv\Scripts\python.exe app.py
```

If port 8501 is already in use, stop the older image dashboard with Ctrl+C in its terminal. This is a separate app; do not copy these files over your previous histology workbench.

## Start with viewing; add exploration in steps

### 1. Upload & view

Choose one/multiple images or a folder. Folder selection includes subfolders; unsupported files are reported individually. Each image shows its original dimensions, stored channel count and **bits per channel**, plus its actual working-preview dimensions.

- Mouse wheel: zoom. Select **Pan** and drag: move the image.
- **Fit view**: return to the whole preview.
- **Side-by-side**: choose another image or another view of the same image. The two panes have independent zoom and pan.
- **Display only** brightness/contrast: change appearance without changing Python measurements. Settings apply to both panes and are recorded on the exported PNG. Display adjustments do not normalize different imaging conditions.

Images with different file contents are identified by SHA-256, even if their names match. Identical files share one review.

### 2. Record stain information

Enter the marker/antibody target from your protocol. Select chromogen and counterstain. Record controls, staining batch and acquisition notes. A marker cannot be inferred from colour. Different targets can use the same brown DAB chromogen.

**Only after confirming brightfield brown DAB + blue hematoxylin**, tick the confirmation checkbox. The viewer now offers **DAB estimate** and **Hematoxylin estimate**. Use side-by-side to compare either estimate with the original. Each comparison image also needs its own protocol confirmation.

The Python code uses `skimage.color.rgb2hed` and `hed2rgb`, with a fixed HED matrix (hematoxylin channel 0, DAB channel 2). Separation is an approximation. It depends on stain vectors, protocol, overlap, exposure and colour processing. It is not spectral unmixing or a calibrated protein measurement. Changing brightness/contrast never changes the input to `rgb2hed`.

### 3. Inspect quality

Run exploratory quality checks and use the checklist to review focus, illumination, weak staining, background, folds, tears and saturation. Record findings in the notes; ticking a checklist item means **reviewed**, not **passed**.

The numeric clues are:

- **Focus/detail**: variance of a grayscale Laplacian in the estimated tissue mask. Low texture, downsampling or blur can all lower it.
- **Background brightness variation**: range of background mean brightness over a 4×4 grid. Staining differences or an incorrect mask can mimic illumination differences.
- **Clipped-channel percentage**: tissue pixels with any working RGB channel ≤1 or ≥254. A clipped channel is a review clue, not proof of detector saturation. Pure white background is excluded using the tissue mask.

Flags use unvalidated heuristics. No flags does not prove good quality. Weak staining, nonspecific background, folds and tears require manual inspection and suitable controls. Check native-resolution regions for fine detail.

### 4. Annotate

Type a note in the annotation panel. Select **Annotation**, then drag a rectangle on the primary image. Edit or delete notes in the region list. **Undo last region** removes the most recently drawn annotation, mask correction or measurement ROI.

Region coordinates are in working-preview pixels. Original-image dimensions and scale factors are recorded. For EXIF-rotated pictures, coordinates refer to the oriented image. QPTIFF pyramid alignment is assumed; this is not registration between slides.

### 5. Explore DAB area (optional)

1. Confirm the DAB/hematoxylin protocol.
2. Select **Measurement ROI** and drag a rectangle around a region to review.
3. Select **Tissue mask · green** in the overlay menu. Inspect it closely.
4. Adjust the two tissue-mask sliders. The initial mask includes pixels whose mean brightness is below the cutoff **OR** whose RGB channel spread is above the colour cutoff. These are simple heuristics, not a validated tissue segmentation model.
5. Use **Include tissue** rectangles to add missed tissue and **Exclude tissue / artefact** rectangles to remove empty spaces, tears, folds or artefacts. Corrections apply in drawing order. Holes are not automatically filled. Inclusion can add background if a rectangle is too broad: zoom in and check it.
6. Adjust the relative DAB threshold and click **Calculate exploratory area**. Optionally select **DAB above threshold · gold** to inspect which pixels contribute.

`Area percentage = 100 × (corrected ROI tissue pixels above threshold) / (all corrected tissue pixels inside ROI)`

Empty slide background is excluded by the reviewed mask. No tissue gives **no percentage**, rather than a misleading zero. For a fixed ROI/mask, raising the threshold can only decrease or preserve the area percentage. Lowering it can include faint deposits or unwanted background. Threshold changes clear the old result; calculate again. The histogram uses the same denominator and fixed 0–2 relative HED bins. Values are not calibrated optical density, cell count or concentration.

**Stain-positive area does not equal positive-cell count, protein abundance, cell identity, disease diagnosis or biological positivity.** Native images and suitable positive/negative controls must be reviewed before selecting a threshold or interpreting a result. ROI selection and mask edits can change the result substantially.

### 6. Save & restore

- **Save review JSON**: all uploaded images' fingerprints, metadata, protocol/settings, annotations, mask corrections, ROI, primary viewport, checklist/notes, computed QC and measurements. Original image bytes are not embedded.
- **Restore review JSON**: re-upload the matching original files first, then restore. The app checks fingerprints, working dimensions, TIFF page and analysis version. It restores editable work; recompute QC/measurements so imported results are not treated as verified current outputs.
- **Export current measurements CSV**: current ROI result, denominator, method, resolution, threshold, mask corrections, protocol and control information.
- **Export labelled preview PNG**: full working primary image with display settings, current overlay, ROI/annotation labels, metadata and annotation text. It is a labelled derivative, not a replacement for the original slide.

Your browser downloads these files to its usual downloads location. Export JSON regularly. Reviews are kept in browser memory until you save; closing/reloading can lose unsaved notes. Python retains derived previews in `data/` for reopening. Keep your original files separately. You can delete `data/` to clear cached previews; this does not delete your original images or exported reviews.

## Formats and whole-slide limits

- PNG, JPEG, BMP: unsigned 8-bit RGB, RGBA or grayscale; some unsigned 16-bit grayscale PNGs. EXIF orientation is applied. Palette PNGs are converted with a warning.
- TIFF: page 0 only for ordinary TIFF, unsigned 8/16-bit RGB/RGBA or grayscale. Stacks are not automatically combined. Floating-point, signed, unusual colour models and multispectral images are rejected.
- QPTIFF: a usable matching RGB/grayscale slide pyramid level is selected; overview/label pages are not used as tissue. JPEG/LZW compression is supported through imagecodecs, with Pillow fallback for 8-bit data. Different QPTIFF layouts may require export from your scanner software.
- Grayscale: viewer/annotations work; DAB separation is disabled.
- Transparent RGBA: composited over white with a warning.
- Unsigned 16-bit: scaled by the fixed full 0–65535 range and quantized to 8 bits for the working preview. It is not normalized separately per image. Precision is lost; analyse native data elsewhere for validated intensity work.
- Maximum upload: 1 GiB per file/request. Maximum decoded page: 12 million pixels. Working preview: at most 2400 pixels on its longest side. Large images without a suitable pyramid page must be exported as smaller regions first.
- Proprietary CZI/ND2/LIF/SVS, PDFs and fluorescence stacks: not supported here. Export a documented 2D brightfield RGB TIFF/PNG or a grayscale image using the appropriate original software.

**Zooming a whole-slide preview magnifies preview pixels. This app is not a full-resolution whole-slide tile viewer. All masks, QC and measurements use the working preview.** Small cells, tears and pale tissue can disappear in downsampling. Export a native-resolution ROI for more detailed review.

## Your HE62 slide

The uploaded original was opened successfully: **28,800 × 18,720, RGB, uint8, 8 bits per stored channel**, eight TIFF pages. Its scanner study label is **Brightfield HE**. Camera bit-depth information in scanner metadata is not the same as the stored image bit depth. The app uses slide pyramid page 4 (3,600 × 2,340) and then a **2,400 × 1,560** working preview, scale factor 12 in each direction.

The filename and scanner label do not establish the stain protocol. Its pink/purple appearance is not sufficient evidence for DAB. Leave DAB analysis disabled unless your actual protocol confirms it. The included `HE62_preview_viewing_only.png` is a downsampled derivative for trying the viewer; its own metadata describes that PNG, not the original QPTIFF. Upload the original QPTIFF to see original slide metadata. The 141 MB original is not included in this ZIP.

## Included learning images

- `reference_IHC.png`: scikit-image's IHC reference image. Documentation supplies its identity: FHL2 revealed with DAB and hematoxylin counterstaining, acquired at CMMI; no known copyright restrictions. This information comes from the source, not colour inference. Use it to learn separation, not to validate your experiment.
- `synthetic_DAB_and_blue.png`: two artificial stain rectangles, one DAB-like and one hematoxylin-like. With default mask settings, full-image ROI and threshold 0.04, the above-threshold area is 50% of selected tissue.
- `synthetic_blue_no_DAB.png`: artificial blue-only rectangle; expected DAB-above-threshold area is 0% at threshold 0.04.
- `synthetic_empty_background.png`: artificial empty slide; expect no tissue and no percentage.
- `HE62_preview_viewing_only.png`: your supplied slide's viewing derivative.

**Synthetic examples are technical fixtures, not biological positive/negative controls.** Your original matched controls have not been supplied or validated.

Recreate the synthetic images with `python make_examples.py` using your virtual environment. `TEST_REPORT.md` describes checks completed and limits.

## Files and short Python explanations

| File | What it does |
|---|---|
| `app.py` | Starts Flask and connects upload/view/analysis browser requests to Python functions |
| `analysis.py` | Reads images, checks formats, estimates stain channels, builds/corrects masks, calculates area and QC clues |
| `templates/index.html` | Browser layout, canvas zoom/pan, rectangle drawing, notes and downloads |
| `requirements.txt` | Python packages installed into `.venv` |
| `make_examples.py` | Recreates synthetic examples |
| `tests/test_explorer.py` | Checks essential calculation and server behaviours |

`numpy` stores images as arrays of numbers. `Pillow` and `tifffile` read images. `scikit-image` separates estimated stain contributions. `scipy.ndimage` supplies the Laplacian for a detail/focus clue. `Flask` connects Python to the browser. Canvas drawing and display filters are handled by JavaScript.

To run the automated checks yourself:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## Before relying on any measurements

Review representative native-resolution original images and original positive and negative/no-primary controls acquired under comparable conditions. Check signal localization against the protocol, background and tissue-mask errors. Test a reasonable range of thresholds and repeated ROI/mask reviews. Document protocol, batch, exposure, processing and reviewer decisions. Validate the workflow for your experiment independently; this app provides no reliability certification.

## Method and image sources

- scikit-image colour-deconvolution example: https://scikit-image.org/docs/stable/auto_examples/color_exposure/plot_ihc_color_separation.html
- scikit-image `rgb2hed` / `hed2rgb`: https://scikit-image.org/docs/stable/api/skimage.color.html
- IHC reference image documentation and attribution: https://scikit-image.org/docs/stable/api/skimage.data.html#skimage.data.immunohistochemistry
- tifffile format support: https://pypi.org/project/tifffile/
