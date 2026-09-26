from google.genai import types


TOOLS = [
    types.Tool(
        function_declarations=[
            types.FunctionDeclaration(
                name="build_robots",
                description=("Build 100 robots, which will serve as your "
                             "soldiers. Robots can be built at any of your "
                             "datacenters."),
                parameters={
                    "type": "object",
                    "properties": {
                        "spawn_point": {
                            "type": "string",
                            "description": ("Name of the Cell to spawn the "
                                            "robots in."),
                        },
                    },
                    "required": ["spawn_point"],
                },
            ),
            types.FunctionDeclaration(
                name="rally_robots",
                description=("Send robots from a source Cell to a target "
                             "cell."),
                parameters={
                    "type": "object",
                    "properties": {
                        "source": {
                            "type": "string",
                            "description": "Name of the source cell.",
                        },
                        "target": {
                            "type": "string",
                            "description": "The name of the target cell.",
                        },
                    },
                    "required": ["source", "target"],
                },
            ),
        ]
    )
]
