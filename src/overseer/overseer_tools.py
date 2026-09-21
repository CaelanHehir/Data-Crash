from google.genai import types


TOOLS = [
    types.Tool(
        function_declarations=[
            types.FunctionDeclaration(
                name="move_player",
                description="Move the player in a particular direction.",
                parameters={
                    "type": "object",
                    "properties": {
                        "direction": {
                            "type": "string",
                            "description": "Direction to move: north, south, \
                                            east, or west.",
                        },
                        "distance": {
                            "type": "integer",
                            "description": "Number of units to move.",
                        },
                    },
                    "required": ["direction", "distance"],
                },
            ),
            types.FunctionDeclaration(
                name="attack",
                description="Attack a specified target.",
                parameters={
                    "type": "object",
                    "properties": {
                        "target": {
                            "type": "string",
                            "description": "The name of the target to attack.",
                        },
                    },
                    "required": ["target"],
                },
            ),
        ]
    )
]
