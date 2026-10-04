from backend.app.safety import check_safety, SAFE_ADVICE

def test_safety_triggers():
    is_unsafe, advice = check_safety("POWER", "Is gas leaking near the unit?", "Does something", "Press it")
    assert is_unsafe is True
    assert advice == SAFE_ADVICE

    is_unsafe, advice = check_safety("E1 error code flashing", "", "Does something", "Press it")
    assert is_unsafe is True
    assert advice == SAFE_ADVICE

    is_unsafe, advice = check_safety("SPARK", "", "", "")
    assert is_unsafe is True

def test_safety_normal():
    is_unsafe, advice = check_safety("FAN SPEED", "How do I make air blow colder?", "Adjusts fan speed", "Press to change speed")
    assert is_unsafe is False
    assert advice == ""
