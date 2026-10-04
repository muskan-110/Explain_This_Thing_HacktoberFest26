from backend.app.textutils import has_devanagari, meaningful_tokens, heading_matches_read, find_matching_chunk


def test_has_devanagari():
    assert has_devanagari("यह बटन हवा तेज़ करता है")
    assert has_devanagari("Fan का काम")
    assert not has_devanagari("This button controls the fan")
    assert not has_devanagari("")
    assert not has_devanagari(None)


def test_tokens_drop_generic_words():
    assert meaningful_tokens("blue button with fan blades") == ["fan", "blades"]
    assert meaningful_tokens("ON/OFF") == []


def test_heading_matches_label():
    assert heading_matches_read("Fan speed", "FAN SPEED", "blue fan icon")
    assert heading_matches_read("Mode Selection", "MODE", "")
    assert heading_matches_read("Temperature", "TEMP", "")


def test_unknown_label_does_not_match_other_headings():
    for heading in ["Fan speed", "Timer", "Mode Selection", "Power Button"]:
        assert not heading_matches_read(heading, "IONIZER", "air purifier with wavy lines")


def test_icon_fallback_only_when_label_has_no_words():
    assert heading_matches_read("Power Button", "ON/OFF", "power circle with line")
    assert not heading_matches_read("Power Button", "IONIZER", "power circle with line")


def test_find_matching_chunk_prefers_score_order_and_respects_min_score():
    chunks = [
        {"heading": "Mode Selection", "score": 0.70},
        {"heading": "Fan speed", "score": 0.62},
        {"heading": "Timer", "score": 0.30},
    ]
    assert find_matching_chunk(chunks, "FAN SPEED", "") == 1
    assert find_matching_chunk(chunks, "TIMER", "", min_score=0.40) is None
    assert find_matching_chunk(chunks, "IONIZER", "") is None


def test_plus_and_minus_match_a_temperature_heading_but_nothing_else():
    assert heading_matches_read("Temperature Adjustment", "+", "plus sign")
    assert heading_matches_read("Temperature Adjustment", "-", "minus sign")
    assert not heading_matches_read("Fan speed", "+", "plus sign")
    assert not heading_matches_read("Timer", "-", "")


def test_filler_try_this_is_detected():
    from backend.app.textutils import try_this_is_filler
    assert try_this_is_filler("I'm not sure, but you can press it to start.", "MICROWAVE + CONVECTION")
    assert try_this_is_filler("I am not sure what to do with this button.", "CLEAN BY STEAMING")
    assert try_this_is_filler("Press it and see what happens.", "TURBO")
    assert try_this_is_filler("Press it to start.", "MICROWAVE + GRILL")        # label never says START
    assert try_this_is_filler("", "TURBO")
    assert try_this_is_filler("\u092f\u0939 \u092c\u091f\u0928 \u0926\u092c\u093e\u0915\u0930 \u0926\u0947\u0916\u0947\u0902 \u0914\u0930 \u0926\u0947\u0916\u0947\u0902 \u0915\u094d\u092f\u093e \u0939\u094b\u0924\u093e \u0939\u0948\u0964", "Reheat")


def test_good_try_this_is_kept():
    from backend.app.textutils import try_this_is_filler
    assert not try_this_is_filler("Press it again and again to go from low to high.", "FAN SPEED")
    assert not try_this_is_filler("Press it to start cooking.", "START EXPRESS COOKING")
    assert not try_this_is_filler("Press it, then choose how long you want.", "TIMER")
