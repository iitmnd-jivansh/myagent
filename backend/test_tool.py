import inspect
from google.genai import live
print("send_realtime_input", inspect.signature(live.AsyncSession.send_realtime_input))
