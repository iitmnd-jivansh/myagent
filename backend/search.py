import requests


def search_web(query: str) -> str:
    """Searches the web for the given query and returns the answer."""
    print("=" * 50)
    print(f"[SEARCH] Web search request")
    print(f"[SEARCH]   Query: '{query}'")
    print(f"[SEARCH]   SearXNG endpoint: http://127.0.0.1:8888/search")
    print("=" * 50)

    try:
        print(f"[SEARCH]   Calling SearXNG API...")

        r = requests.get(
            "http://127.0.0.1:8888/search",
            params={
                "q": query,
                "format": "json"
            },
            timeout=20
        )

        print(f"[SEARCH]   SearXNG response status: {r.status_code}")

        r.raise_for_status()

        data = r.json()

        answers = data.get(
            "answers",
            []
        )

        if answers:
            ans = answers[0]["answer"]
            print(f"[SEARCH] ✅ Search result found:")
            print(f"[SEARCH]   Answer ({len(ans)} chars): {ans[:200]}...")
            print(f"[SEARCH]   Query: '{query}' | Information retrieved successfully")
            print("=" * 50)
            return ans

        print(f"[SEARCH]   No answers found in SearXNG response.")
        print(f"[SEARCH]   Available keys in response: {list(data.keys())}")
        print(f"[SEARCH]   Query: '{query}' | No information found.")
        print("=" * 50)
        return None

    except requests.exceptions.Timeout:
        print(f"[SEARCH] ❌ SearXNG request timed out after 20s")
        print(f"[SEARCH]   Is SearXNG running on http://127.0.0.1:8888?")
        print("=" * 50)
        return None

    except requests.exceptions.ConnectionError as e:
        print(f"[SEARCH] ❌ Connection error: {e}")
        print(f"[SEARCH]   SearXNG may not be running. Start with: searxng-run")
        print("=" * 50)
        return None

    except Exception as e:
        print(f"[SEARCH] ❌ Search error: {e}")
        print("=" * 50)
        return None