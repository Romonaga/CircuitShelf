from backend.services.openai_assist_utils import parse_json_object


def test_parse_json_object_accepts_fenced_json():
    parsed = parse_json_object(
        """```json
        {"componentName": "MCP23017", "pinout": {"pins": [{"pin": "1", "label": "GPB4"}]}}
        ```"""
    )

    assert parsed["componentName"] == "MCP23017"
    assert parsed["pinout"]["pins"][0]["label"] == "GPB4"


def test_parse_json_object_extracts_embedded_json_object():
    parsed = parse_json_object('Here is the result: {"quality": "good", "useful": true}')

    assert parsed == {"quality": "good", "useful": True}
