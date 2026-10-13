# Verification report — IHC Image Explorer v1.0

## Completed

- Six automated regression tests passed: stain channel mapping and threshold monotonicity; ROI tissue denominator; include/exclude mask correction order; empty-background/blue-only behaviour; confirmation-gated server routes and PNG overlays; unsupported/grayscale inputs; unsigned-16-bit scaling and ordinary multi-page TIFF handling.
- The attached **original HE62 800_Scan1.qptiff** was submitted through the Flask upload route. Reading and original-preview serving succeeded. The selected slide page was 4, excluding overview/label pages. Original metadata and working-preview dimensions matched expectations. Exploratory QC returned successfully. Its SHA-256 was identical before and after processing; the original was not modified. No DAB interpretation was made for this unconfirmed slide.
- scikit-image's **512 × 512 original reference IHC image** was uploaded through the same route. Confirmed DAB/hematoxylin estimates, ROI area calculation and PNG stain routes returned successfully. This is a published learning example, not an experimental control for the supplied slide.
- Deterministic synthetic DAB-like, hematoxylin-only and empty-background fixtures verify expected numerical behaviour. With a fixed mask and ROI, increasing the threshold did not increase selected area. Removing all ROI tissue returned no percentage.
- Browser JavaScript passed `node --check` syntax validation. Python/server functions were exercised with Flask's HTTP test client.

## Not established

- No interactive browser automation was available; mouse/touch rendering, zoom/pan, file downloads and JSON restore were not end-to-end browser-tested. UI handlers and JavaScript syntax were checked, but this is a verification limit.
- The Windows installation commands were prepared but could not be executed in this Linux environment.
- No matched original biological positive or negative/no-primary controls were supplied. Synthetic examples are not substitutes. No staining threshold, tissue-mask accuracy, cell detection, biological positivity, protein abundance or measurement reliability has been validated.
- Full-resolution tiled slide navigation is not implemented. Whole-slide outputs and QC are preview-resolution estimates. Fine structures require native-resolution ROI exports.

Research review and experiment-specific validation remain necessary before relying on measurements.
