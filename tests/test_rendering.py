# SPDX-FileCopyrightText: 2026 geisserml <geisserml@gmail.com>
# SPDX-License-Identifier: Apache-2.0 OR BSD-3-Clause

import math
import numpy
import warnings
import PIL.Image
import PIL.ImageDraw
import pytest
import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_c
from .conftest import (
    TestFiles,
    PyVersion,
    OutputDir,
    ExpRenderPixels,
    compare_n2,
)

# TODO assert that bitmap and info are consistent


@pytest.fixture
def sample_page():
    pdf = pdfium.PdfDocument(TestFiles.render)
    page = pdf[0]
    yield page

@pytest.fixture
def multipage_doc():
    pdf = pdfium.PdfDocument(TestFiles.multipage)
    yield pdf

def _check_pixels(pil_image, pixels):
    for pos, value in pixels:
        assert pil_image.getpixel(pos) == value


@pytest.mark.parametrize(
    ("name", "crop", "scale", "rotation"),
    [   
        ["01_r0",      (0,   0,   0,   0  ), 0.25, 0,   ],
        ["02_r90",     (0,   0,   0,   0  ), 0.5,  90,  ],
        ["03_r180",    (0,   0,   0,   0  ), 0.75, 180, ],
        ["04_r270",    (0,   0,   0,   0  ), 1,    270, ],
        ["05_cl",      (100, 0,   0,   0  ), 0.5,  0,   ],
        ["06_cb",      (0,   100, 0,   0  ), 0.5,  0,   ],
        ["07_cr",      (0,   0,   100, 0  ), 0.5,  0,   ],
        ["08_ct",      (0,   0,   0,   100), 0.5,  0,   ],
        ["09_r90_cb",  (0,   100,  0,  0  ), 0.5,  90,  ],
        ["10_r180_cr", (0,   0,   100, 0  ), 0.5,  180, ],
        ["11_r270_ct", (0,   0,   0,   100), 0.5,  270, ],
    ]
)
def test_render_page_transform(sample_page, name, crop, scale, rotation):
    pil_image = sample_page.render(
        crop = crop,
        scale = scale,
        rotation = rotation,
    ).to_pil()
    pil_image.save(OutputDir / ("%s.png" % name))
    assert pil_image.mode == "RGB"
    
    c_left, c_bottom, c_right, c_top = [math.ceil(c*scale) for c in crop]
    w = math.ceil(595*scale)
    h = math.ceil(842*scale)
    if rotation in (90, 270):
        w, h = h, w
    
    c_w = w - c_left - c_right
    c_h = h - c_bottom - c_top
    assert pil_image.size == (c_w, c_h)
    
    pixels = []
    for (x, y), value in ExpRenderPixels:
        x, y = round(x*scale), round(y*scale)
        if rotation in (90, 270):
            x, y = y, x
        if rotation == 90:
            x = w-1 - x
        elif rotation == 180:
            x = w-1 - x
            y = h-1 - y
        elif rotation == 270:
            y = h-1 - y
        x -= c_left
        y -= c_top
        if 0 <= x < c_w and 0 <= y < c_h:
            pixels.append( ((x, y), value) )
    
    _check_pixels(pil_image, pixels)


@pytest.mark.parametrize(
    "rev_byteorder", [False, True]
)
def test_render_page_bgrx(rev_byteorder, sample_page):
    pil_image = sample_page.render(
        prefer_bgrx = True,
        rev_byteorder = rev_byteorder,
    ).to_pil()
    assert pil_image.mode == "RGBX"
    exp_pixels = [(pos, (*value, 255)) for pos, value in ExpRenderPixels]
    _check_pixels(pil_image, exp_pixels)


def test_render_page_alpha(sample_page):
    
    pixels = [
        [(0,   0  ), (0,   0,   0,   0  )],
        [(62,  66 ), (0,   0,   0,   186)],
        [(150, 180), (129, 212, 26,  255)],
        [(150, 390), (42,  96,  153, 255)],
        [(150, 570), (128, 0,   128, 255)],
    ]
    kwargs = dict(
        fill_color = (0, 0, 0, 0),
    )
    image = sample_page.render(**kwargs).to_pil()
    image_rev = sample_page.render(**kwargs, rev_byteorder=True).to_pil()
    
    if PyVersion > (3, 6):
        assert image == image_rev
    assert image.mode == "RGBA"
    assert image.size == (595, 842)
    for pos, exp_value in pixels:
        assert image.getpixel(pos) == exp_value
    
    image.save(OutputDir / "colored_alpha.png")


def test_render_page_grey(sample_page):
    kwargs = dict(
        grayscale = True,
        scale = 0.5,
    )
    image = sample_page.render(**kwargs).to_pil()
    image_rev = sample_page.render(**kwargs, rev_byteorder=True).to_pil()
    assert image == image_rev
    assert image.size == (298, 421)
    assert image.mode == "L"
    image.save(OutputDir / "grayscale.png")


@pytest.mark.parametrize(
    "fill_color",
    [
        (255, 255, 255, 255),
        (60,  70,  80,  100),
        (255, 255, 255, 255),
        (0,   255, 255, 255),
        (255, 0,   255, 255),
        (255, 255, 0,   255),
    ]
)
def test_render_page_fill_color(fill_color, sample_page):
    kwargs = dict(
        fill_color = fill_color,
        scale = 0.5,
    )
    image = sample_page.render(**kwargs).to_pil()
    image_rev = sample_page.render(**kwargs, rev_byteorder=True).to_pil()
    
    if PyVersion > (3, 6):
        assert image == image_rev
    
    bg_pixel = image.getpixel( (0, 0) )
    if fill_color[3] == 255:
        fill_color = fill_color[:-1]
    assert image.size == (298, 421)
    assert bg_pixel == fill_color


@pytest.mark.parametrize("fill_to_stroke", [False, True])
def test_render_page_colorscheme(fill_to_stroke):
    pdf = pdfium.PdfDocument(TestFiles.render)
    page = pdf[0]
    # from _cli/render.py::SampleTheme
    color_scheme = pdfium.PdfColorScheme(
        path_fill   = (170, 100, 0,   255),  # dark orange
        path_stroke = (0,   150, 255, 255),  # sky blue
        text_fill   = (255, 255, 255, 255),  # white
        text_stroke = (150, 255, 0,   255),  # green
    )
    image = page.render(
        fill_color = (0, 0, 0, 255),
        color_scheme = color_scheme,
        fill_to_stroke = fill_to_stroke,
    ).to_pil()
    assert image.mode == "RGB"
    image.save(OutputDir / f"render_colorscheme_{int(fill_to_stroke)}.png")


@pytest.mark.parametrize("rev_byteorder", [False, True])
def test_render_page_tonumpy(rev_byteorder, sample_page):
    
    bitmap = sample_page.render(
        rev_byteorder = rev_byteorder,
    )
    mode = bitmap.mode
    array = bitmap.to_numpy()
    
    assert isinstance(array, numpy.ndarray)
    assert mode == ("RGB" if rev_byteorder else "BGR")
    
    for (x, y), value in ExpRenderPixels:
        if rev_byteorder:
            assert tuple(array[y][x]) == value
        else:
            assert tuple(array[y][x]) == tuple(reversed(value))


@pytest.mark.parametrize("mode", [None, "lcd", "print"])
def test_render_page_optimization(sample_page, mode):
    pil_image = sample_page.render(
        optimize_mode = mode,
        scale = 0.5,
    ).to_pil()
    assert isinstance(pil_image, PIL.Image.Image)


def test_render_page_noantialias(sample_page):
    pil_image = sample_page.render(
        no_smoothtext  = True,
        no_smoothimage = True,
        no_smoothpath  = True,
        scale = 0.5,
    ).to_pil()
    assert isinstance(pil_image, PIL.Image.Image)


def test_render_pages(multipage_doc):
    for page in multipage_doc:
        image = page.render(
            scale = 0.5,
            grayscale = True,
        ).to_pil()
        assert isinstance(image, PIL.Image.Image)


def test_render_pil_numpy_eq(multipage_doc):
    for page in multipage_doc:
        # render at formats supported by PIL natively (i.e. without copying) so that pil_image and np_array are backed by the same memory
        bitmap = page.render(scale=0.5, rev_byteorder=True, prefer_bgrx=True)
        pil_image = bitmap.to_pil()
        np_array = bitmap.to_numpy()
        assert isinstance(pil_image, PIL.Image.Image)
        assert isinstance(np_array, numpy.ndarray)
        pil_image_from_array = PIL.Image.fromarray(np_array, mode="RGBX")
        assert pil_image == pil_image_from_array


def test_render_new():
    pdf = pdfium.PdfDocument.new()
    page = pdf.new_page(50, 100)
    bitmap = page.render()


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_render_to_canvas_size(sample_page, rotation):
    for size in [(512, 512), (300, 500), (500, 300), (1, 1)]:
        bitmap = sample_page.render_to_canvas(*size, rotation=rotation)
        assert (bitmap.width, bitmap.height) == size
        assert bitmap.to_pil().size == size


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_render_to_canvas_identity(sample_page, rotation):
    # canvas at the page's native pixel size with matching rotation must be
    # pixel-identical to a plain render() call
    ref_bitmap = sample_page.render(scale=1, rotation=rotation)
    canvas_bitmap = sample_page.render_to_canvas(
        ref_bitmap.width, ref_bitmap.height,
        rotation = rotation,
    )
    assert (canvas_bitmap.width, canvas_bitmap.height) == (ref_bitmap.width, ref_bitmap.height)
    assert canvas_bitmap.mode == ref_bitmap.mode
    assert bytes(canvas_bitmap.buffer) == bytes(ref_bitmap.buffer)


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_render_to_canvas_margins(sample_page, rotation):
    fill_color = (230, 230, 230, 255)
    bitmap = sample_page.render_to_canvas(512, 512, rotation=rotation, fill_color=fill_color)
    pil_image = bitmap.to_pil()
    # with contain-fitting, the canvas corners always fall into the margins
    for pos in [(0, 0), (511, 0), (0, 511), (511, 511)]:
        assert pil_image.getpixel(pos) == fill_color[:-1]
    # known page content must appear at the translated canvas position
    # (ExpRenderPixels are bitmap positions at scale 1, rotation 0)
    posconv = bitmap.get_posconv(sample_page)
    page_h = sample_page.get_height()
    for (x, y), value in ExpRenderPixels[1:]:
        canvas_pos = posconv.to_bitmap(x, page_h - y)
        assert pil_image.getpixel(canvas_pos) == value


def test_render_to_canvas_fill_alpha(sample_page):
    fill_color = (60, 70, 80, 100)
    bitmap = sample_page.render_to_canvas(700, 900, fill_color=fill_color)
    assert bitmap.mode == "BGRA"
    pil_image = bitmap.to_pil()
    assert pil_image.mode == "RGBA"
    assert pil_image.getpixel( (0, 0) ) == fill_color


def test_render_to_canvas_rev_byteorder(sample_page):
    fill_color = (60, 70, 80, 255)
    bitmap = sample_page.render_to_canvas(700, 900, fill_color=fill_color)
    bitmap_rev = sample_page.render_to_canvas(700, 900, fill_color=fill_color, rev_byteorder=True)
    assert bitmap.mode == "BGR"
    assert bitmap_rev.mode == "RGB"
    assert bitmap.to_pil().getpixel( (0, 0) ) == fill_color[:-1]
    assert bitmap.to_pil() == bitmap_rev.to_pil()


def test_render_to_canvas_invalid(sample_page):
    for size in [(0, 100), (100, 0), (-1, 100), (100, -1)]:
        with pytest.raises(ValueError, match="Invalid canvas size"):
            sample_page.render_to_canvas(*size)


SynthRects = [
    # (x, y, w, h) in PDF canvas units (origin bottom left), RGB color
    ( (20,  60, 40, 30), (255, 0,   0  ) ),
    ( (120, 10, 50, 40), (0,   0,   255) ),
]

@pytest.fixture
def synth_page():
    pdf = pdfium.PdfDocument.new()
    page = pdf.new_page(200, 100)
    for (x, y, w, h), (r, g, b) in SynthRects:
        raw_rect = pdfium_c.FPDFPageObj_CreateNewRect(x, y, w, h)
        assert raw_rect
        ok = pdfium_c.FPDFPageObj_SetFillColor(raw_rect, r, g, b, 255)
        assert ok
        ok = pdfium_c.FPDFPath_SetDrawMode(raw_rect, pdfium_c.FPDF_FILLMODE_WINDING, False)
        assert ok
        page.insert_obj( pdfium.PdfObject(raw_rect, pdf=pdf) )
    page.gen_content()
    yield page


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_render_to_canvas_posconv(synth_page, rotation):

    W, H = synth_page.get_size()
    CW, CH = 512, 512
    bitmap = synth_page.render_to_canvas(CW, CH, rotation=rotation)
    assert (bitmap.width, bitmap.height) == (CW, CH)
    posconv = bitmap.get_posconv(synth_page)
    pil_image = bitmap.to_pil()

    # scale of the contain-fitting, for pixel<->canvas-unit conversions
    eff_w, eff_h = (H, W) if rotation in (90, 270) else (W, H)
    scale = min(CW/eff_w, CH/eff_h)

    for (x, y, w, h), color in SynthRects:
        page_center = (x + w/2, y + h/2)
        # the rect's color block must appear at the translated canvas position
        canvas_pos = posconv.to_bitmap(*page_center)
        assert pil_image.getpixel(canvas_pos) == color
        # round trip back to page coordinates, with at most 1px error
        rt_page = posconv.to_page(*canvas_pos)
        for rt_coord, exp_coord in zip(rt_page, page_center):
            assert abs(rt_coord - exp_coord) * scale == pytest.approx(0, abs=1)

    # canvas corners fall into the margins, i.e. outside the page
    corner_page = posconv.to_page(0, 0)
    assert not (0 <= corner_page[0] <= W and 0 <= corner_page[1] <= H)



def test_render_with_stream_read():
    stream = open(TestFiles.multipage, "rb")
    pdf = pdfium.PdfDocument(stream)
    page = pdf[0]
    bitmap = page.render()


@pytest.mark.parametrize(
    ("with_forms", "exp_color"),
    [
        (False, (255, 255, 255)),
        (True, (0, 51, 113)),
    ]
)
def test_render_form(with_forms, exp_color):
    
    pdf = pdfium.PdfDocument(TestFiles.forms)
    if with_forms:
        pdf.init_forms()
    
    if with_forms:
        assert isinstance(pdf.formenv, pdfium.PdfFormEnv)
    else:
        assert pdf.formenv is None
    
    page = pdf[0]
    image = page.render(
        may_draw_forms = with_forms,
    ).to_pil()
    
    assert image.getpixel( (190, 190) ) == exp_color
    assert image.getpixel( (190, 430) ) == exp_color
    assert image.getpixel( (190, 480) ) == exp_color


def test_numpy_nocopy(sample_page):
    bitmap = sample_page.render(scale=0.1)
    array = bitmap.to_numpy()
    assert (bitmap.width, bitmap.height) == (60, 85)
    val_a, val_b = 255, 123
    assert array[0][0][0] == val_a
    bitmap.buffer[0] = val_b
    assert array[0][0][0] == val_b
    array[0][0][0] = val_a
    assert bitmap.buffer[0] == val_a


@pytest.mark.parametrize(
    ("bitmap_format", "rev_byteorder", "is_referenced"),
    [
        (pdfium_c.FPDFBitmap_BGR,  False, False),
        (pdfium_c.FPDFBitmap_BGR,  True,  False),
        (pdfium_c.FPDFBitmap_BGRA, False, False),
        (pdfium_c.FPDFBitmap_BGRA, True,  True),
        (pdfium_c.FPDFBitmap_BGRx, False, False),
        (pdfium_c.FPDFBitmap_BGRx, True,  True),
        (pdfium_c.FPDFBitmap_Gray, False, True),
    ]
)
def test_pil_nocopy_where_possible(bitmap_format, rev_byteorder, is_referenced, sample_page):
    
    bitmap = sample_page.render(
        scale = 0.1,
        rev_byteorder = rev_byteorder,
        force_bitmap_format = bitmap_format,
    )
    pil_image = bitmap.to_pil()
    assert pil_image.size == (60, 85)
    
    val_a, val_b = 255, 123
    if bitmap.n_channels == 4:
        pixel_a = (val_a, 255, 255, 255)
        pixel_b = (val_b, 255, 255, 255)
    elif bitmap.n_channels == 3:
        pixel_a = (val_a, 255, 255)
        pixel_b = (val_b, 255, 255)
    elif bitmap.n_channels == 1:
        pixel_a = val_a
        pixel_b = val_b
    else:
        assert False
    
    assert pil_image.getpixel((0, 0)) == pixel_a
    bitmap.buffer[0] = val_b
    
    if is_referenced:
        
        # changes to the buffer are reflected in the image
        assert pil_image.getpixel((0, 0)) == pixel_b
        
        # changes to the image are reflected in the buffer, since we set `.readonly = False` on after image init
        pil_image.putpixel((0, 0), pixel_a)
        assert pil_image.getpixel((0, 0)) == pixel_a
        assert bitmap.buffer[0] == val_a
        
    else:
        if pil_image.getpixel((0, 0)) == pixel_b:
            warnings.warn(f"PIL now references {bitmap.mode} mode bitmaps.")
        else:
            assert pil_image.getpixel((0, 0)) == pixel_a


def test_draw_image_borders():
    # this demonstrates posconv functionality in the form of an embedder test
    # see test_page::test_posconv for a more unittest-like example
    
    pdf = pdfium.PdfDocument(TestFiles.images)
    page = pdf[0]
    images = list( page.get_objects(filter=[pdfium_c.FPDF_PAGEOBJ_IMAGE]) )
    pdf_qpl = [i.get_quad_points() for i in images]
    
    bitmap = page.render(scale=1)
    posconv = bitmap.get_posconv(page)
    pil_image = bitmap.to_pil()
    bitmap_qpl  = [[posconv.to_bitmap(x, y) for x, y in qps] for qps in pdf_qpl]
    
    reverse_qpl = [[posconv.to_page(x, y) for x, y in qps] for qps in bitmap_qpl]
    for qps_a, qps_b in zip(pdf_qpl, reverse_qpl):
        compare_n2(qps_a, qps_b)
    
    draw = PIL.ImageDraw.Draw(pil_image)
    GREEN = (50, 200, 10)
    for qps in bitmap_qpl:
        draw.polygon(qps, outline=GREEN, width=3)
    
    pil_image.save(OutputDir/"image_borders.png")
