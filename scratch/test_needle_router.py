import json
from models.needle_router import Needle2Router

def test():
    router = Needle2Router()
    tools = [
        {
            "name": "TYPE_TEXT",
            "description": "Type some text.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"}
                }
            }
        },
        {
            "name": "OPEN_APP",
            "description": "Open an application.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"}
                }
            }
        }
    ]
    res = router.route_tool("Type Python tutorials", tools)
    print(json.dumps(res, indent=2))

if __name__ == "__main__":
    test()
