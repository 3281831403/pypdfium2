<!-- SPDX-FileCopyrightText: 2026 geisserml <geisserml@gmail.com> -->
<!-- SPDX-License-Identifier: CC-BY-4.0 -->

<!-- List character: dash (-) -->

# Changelog for next release
- Remove some copying from autoclose machinery that should be unnecessary but had been retained as an extra precaution in the previous release.
- Added `PdfPage.get_display_size()`, `PdfTextPage.get_rects()` and `PdfTextPage.hit_test()`, providing text rectangles and character lookup in display coordinates (top-left origin, y down, page rotation and CropBox applied), with optional scaling. This makes it straightforward to draw text highlights or locate characters from a click position, without having to convert from PDF canvas units manually.
