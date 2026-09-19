import os

files = ["tests/test_planner.py", "tests/test_vision.py", "tests/test_input.py", "tests/test_phase9_3.py", "tests/test_phase9.py", "tests/test_phase8.py", "tests/test_phase12.py"]

for file in files:
    if not os.path.exists(file): continue
    with open(file, "r") as f:
        content = f.read()
    
    # Replace the remaining patch occurrences
    content = content.replace('"brain.requests.post"', '"brain.default_gateway.generate"')
    content = content.replace('"requests.post"', '"brain.default_gateway.generate"')
    
    # Also inject make_mock_response if not already in the file, because we need it for these mocks
    if "make_mock_response" not in content:
        # Not injecting automatically, let's see if we need it
        pass

    with open(file, "w") as f:
        f.write(content)
print("Done fixing patches")
