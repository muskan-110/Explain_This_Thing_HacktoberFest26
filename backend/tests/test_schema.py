from backend.app.schemas import ExplainResult, ReadResult

def test_read_result_schema():
    res = ReadResult(label_text="FAN", icon_description="three blades", looks_like="grey round button")
    assert res.label_text == "FAN"

def test_explain_result_schema():
    res = ExplainResult(
        button_name="Fan speed",
        what_it_does="Controls air strength.",
        try_this="Press to cycle modes.",
        confidence="high",
        source="knowledge_base",
        source_ref="notes.md / Fan speed",
        safety_flag=False
    )
    assert res.confidence == "high"
    assert res.source == "knowledge_base"
