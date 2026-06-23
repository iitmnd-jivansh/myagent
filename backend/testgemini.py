from google import genai

client = genai.Client(api_key="AQ.Ab8RN6J6q2zVLeKzpCbAIel6WnSeKW6eTtxdcsZ5DGWCw5OXKg")


for m in client.models.list():
    print(m.name)
