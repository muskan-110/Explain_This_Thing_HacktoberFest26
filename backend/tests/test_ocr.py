import pytest
from PIL import Image, ImageDraw, ImageFont

from backend.app.ocr import choose_label_at, read_label_at


def box(text, x0, y0, x1, y1, score=0.99):
    return {"text": text, "score": score, "x0": x0, "y0": y0, "x1": x1, "y1": y1}


ITEMS = [
    box("FAN", 200, 170, 280, 205),
    box("HUMIDITY", 300, 350, 410, 385),
    box("SLEEP", 300, 480, 410, 515),
    box("TIME", 440, 350, 550, 385),
]


def test_tap_inside_a_label_returns_that_label():
    assert choose_label_at(ITEMS, 350, 365) == "HUMIDITY"


def test_tap_just_above_the_label_still_counts():
    assert choose_label_at(ITEMS, 350, 345) == "HUMIDITY"


def test_tap_on_an_icon_only_button_returns_none():
    # the button between FAN and TIME has no text; the nearest label is far away
    assert choose_label_at(ITEMS, 480, 190) is None


def test_neighbouring_button_is_never_chosen():
    assert choose_label_at(ITEMS, 350, 440) is None    # in the gap between HUMIDITY and SLEEP


def test_low_confidence_and_symbol_only_text_is_ignored():
    items = [box("HUM1D1TY", 300, 350, 410, 385, score=0.2), box("---", 300, 350, 410, 385)]
    assert choose_label_at(items, 350, 365) is None


def test_real_engine_reads_a_drawn_label():
    pytest.importorskip("rapidocr")
    img = Image.new("RGB", (500, 300), "white")
    d = ImageDraw.Draw(img)
    d.text((150, 110), "TIMER", fill="black", font=ImageFont.load_default(size=60))
    got = read_label_at(img, 0.5, 0.5)
    assert got is not None and "TIM" in got.upper()


def _microwave_panel():
    """Layout of the MICROWAVE + GRILL row on the user's microwave panel (one box per text line)."""
    return [
        # left button: MICROWAVE / POWER LEVEL
        box("MICROWAVE", 155, 210, 314, 253), box("POWER LEVEL", 145, 246, 320, 284),
        # centre button: MICROWAVE / + / GRILL
        box("MICROWAVE", 340, 205, 490, 235), box("+", 405, 236, 425, 254), box("GRILL", 367, 256, 463, 296),
        # right button: MICROWAVE / + / CONVECTION
        box("MICROWAVE", 511, 190, 676, 234), box("+", 580, 236, 600, 252), box("CONVECTION", 509, 249, 681, 293),
        # row above and row below
        box("KEEP", 366, 36, 462, 77), box("WARM", 362, 72, 469, 113),
        box("GRILL", 184, 400, 285, 441),
    ]


def test_multi_line_label_is_joined_into_one_button_label():
    items = _microwave_panel()
    assert choose_label_at(items, 412, 245) == "MICROWAVE + GRILL"        # tap on the "+" between the lines
    assert choose_label_at(items, 415, 220) == "MICROWAVE + GRILL"        # tap on the top word
    assert choose_label_at(items, 415, 280) == "MICROWAVE + GRILL"        # tap on the bottom word


def test_neighbouring_buttons_are_not_merged_into_the_label():
    items = _microwave_panel()
    assert choose_label_at(items, 600, 215) == "MICROWAVE + CONVECTION"
    assert choose_label_at(items, 230, 230) == "MICROWAVE POWER LEVEL"
    assert choose_label_at(items, 230, 420) == "GRILL"                    # single-line button two rows down
    assert choose_label_at(items, 415, 90) == "KEEP WARM"


def test_real_engine_reads_a_two_line_label_as_one():
    pytest.importorskip("rapidocr")
    img = Image.new("RGB", (600, 400), "black")
    d = ImageDraw.Draw(img)
    f = ImageFont.load_default(size=56)
    d.text((120, 90), "MICROWAVE", fill="white", font=f)
    d.text((200, 155), "GRILL", fill="white", font=f)
    got = read_label_at(img, 0.5, 0.40)
    assert got is not None and "MICROWAVE" in got.upper() and "GRILL" in got.upper()
