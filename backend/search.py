import requests


def search_web(query: str) -> str:
    """Searches the web for the given query and returns the answer."""

    try:

        r = requests.get(
            "http://127.0.0.1:8888/search",
            params={
                "q": query,
                "format": "json"
            },
            timeout=20
        )

        r.raise_for_status()

        data = r.json()

        answers = data.get(
            "answers",
            []
        )

        if answers:
            ans = answers[0]["answer"]
            print(f"[SearXNG Live] Query: '{query}' | Information retrieved: {ans}")
            return ans

        print(f"[SearXNG Live] Query: '{query}' | No information found.")
        return None

    except Exception as e:

        print(
            "Search error:",
            e
        )

        return None
