# SPDX-FileCopyrightText: 2026 geisserml <geisserml@gmail.com>
# SPDX-License-Identifier: Apache-2.0 OR BSD-3-Clause

import math
import pytest
import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_c
from .conftest import TestFiles, OutputDir


def test_boxes():
    
    pdf = pdfium.PdfDocument(TestFiles.render)
    index = 0
    page = pdf[index]
    assert page.get_size() == pdf.get_page_size(index) == (595, 842)
    assert page.get_mediabox() == (0, 0, 595, 842)
    assert isinstance(page, pdfium.PdfPage)
    
    test_cases = [
        ("media", (0,  0,  612, 792)),
        ("media", (0,  0,  595, 842)),
        ("crop",  (10, 10, 585, 832)),
        ("bleed", (20, 20, 575, 822)),
        ("trim",  (30, 30, 565, 812)),
        ("art",   (40, 40, 555, 802)),
    ]
    
    for mn, exp_box in test_cases:
        getattr(page, f"set_{mn}box")(*exp_box)
        box = getattr(page, f"get_{mn}box")()
        assert pytest.approx(box) == exp_box


def test_mediabox_fallback():
    pdf = pdfium.PdfDocument(TestFiles.box_fallback)
    page = pdf[0]
    assert page.get_mediabox() == (0, 0, 612, 792)


def test_rotation():
    pdf = pdfium.PdfDocument.new()
    page = pdf.new_page(500, 800)
    for r in (90, 180, 270, 0):
        page.set_rotation(r)
        assert page.get_rotation() == r


@pytest.mark.parametrize(
    "rotation,cropbox,exp_size",
    [
        (0,   None,             (595.30, 841.89)),
        (90,  None,             (841.89, 595.30)),
        (180, None,             (595.30, 841.89)),
        (270, None,             (841.89, 595.30)),
        (0,   (50, 60, 500, 700), (450, 640)),
        (90,  (50, 60, 500, 700), (640, 450)),
        (180, (50, 60, 500, 700), (450, 640)),
        (270, (50, 60, 500, 700), (640, 450)),
    ]
)
def test_get_display_size(rotation, cropbox, exp_size):
    pdf = pdfium.PdfDocument(TestFiles.text)
    page = pdf[0]
    if cropbox:
        page.set_cropbox(*cropbox)
    page.set_rotation(rotation)

    w, h = page.get_display_size()
    assert (w, h) == pytest.approx(exp_size, abs=0.01)

    scale = 2
    ws, hs = page.get_display_size(scale=scale)
    assert (ws, hs) == pytest.approx((exp_size[0]*scale, exp_size[1]*scale), abs=0.01)

    # consistency with the bitmap produced by render()
    bitmap = page.render(scale=scale)
    assert (bitmap.width, bitmap.height) == (math.ceil(ws), math.ceil(hs))


def test_page_labels():
    # incidentally, it happens that this TOC test file also has page labels
    pdf = pdfium.PdfDocument(TestFiles.toc_viewmodes)
    exp_labels = ["i", "ii", "appendix-C", "appendix-D", "appendix-E", "appendix-F", "appendix-G", "appendix-H"]
    assert exp_labels == [pdf.get_page_label(i) for i in range(len(pdf))]


def test_flatten():
    pdf = pdfium.PdfDocument(TestFiles.forms)
    pdf.init_forms()
    page = pdf[0]
    rc = page.flatten()
    assert rc == pdfium_c.FLATTEN_SUCCESS
    pdf.save(OutputDir / "flattened.pdf")


def test_posconv():
    pdf = pdfium.PdfDocument.new()
    W, H = 100, 150
    page = pdf.new_page(W, H)
    posconv = pdfium.PdfPosConv(page, (0, 0, W, H, 0))
    page_corners = [
        (0, 0),  # bottom left == origin
        (W, 0),  # bottom right
        (0, H),  # top left
        (W, H),  # top right
    ]
    # bitmaps use top-left as origin
    bmp_corners = [posconv.to_bitmap(x, y) for x, y in page_corners]
    exp_bmp_corners = [(x, H-y) for x, y in page_corners]
    assert bmp_corners == exp_bmp_corners
    reverse_page_corners = [posconv.to_page(x, y) for x, y in bmp_corners]
    assert reverse_page_corners == page_corners
