import inspect
from google.genai import types

print("LiveServerToolCall", inspect.signature(types.LiveServerToolCall))
print("FunctionCall", inspect.signature(types.FunctionCall))
