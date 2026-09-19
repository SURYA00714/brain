import json
from needle import Needle

def test():
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
    try:
        agent = Needle(tools=tools, system="You are a helpful assistant. Use tools if necessary.", generation=3)
        res = agent.complete("Type Python tutorials")
        print(json.dumps(res, indent=2))
    except Exception as e:
        print("ERROR:", str(e))

if __name__ == "__main__":
    test()
