import os

test_files = [
    "tests/test_planner.py",
    "tests/test_input.py",
    "tests/test_phase9_3.py",
    "tests/test_vision.py",
]

for file in test_files:
    if not os.path.exists(file): continue
    with open(file, "r") as f:
        content = f.read()

    if "make_mock_response" in content:
        # replace make_mock_response definition
        old_def = """def make_mock_response(text):
    mock = MagicMock()
    mock.status_code = 200
    mock.raise_for_status.return_value = None
    mock.json.return_value = {"response": text}
    return mock"""
        new_def = """def make_mock_response(text):
    from models.gateway import ModelResponse
    return ModelResponse(text=text, model="mock", provider="mock", success=True)"""
        content = content.replace(old_def, new_def)
    
    # replace patches
    content = content.replace('@patch("brain.requests.post")', '@patch("brain.default_gateway.generate")')
    
    with open(file, "w") as f:
        f.write(content)
    print(f"Fixed {file}")
