import os
import requests


GNEWS_API_KEY = "c1e78acd73b05a5987938bf88d20d891"

BASE_URL = "https://gnews.io/api/v4/search"


def get_news(
    topic: str = "general",
    max_results: int = 5
) -> str:
    """Fetches the latest news articles about a specific topic."""
    print("=" * 50)
    print(f"[NEWS] News lookup request")
    print(f"[NEWS]   Topic: '{topic}'")
    print(f"[NEWS]   Max results: {max_results}")
    print("=" * 50)

    if not GNEWS_API_KEY:
        print(f"[NEWS] ❌ GNEWS_API_KEY not set!")
        return (
            "GNEWS_API_KEY environment "
            "variable not set."
        )

    try:
        print(f"[NEWS]   Calling GNews API...")
        print(f"[NEWS]   URL: {BASE_URL}")
        print(f"[NEWS]   Params: q='{topic}', lang=en, max={max_results}")

        r = requests.get(
            BASE_URL,
            params={
                "q": topic,
                "lang": "en",
                "max": max_results,
                "token": GNEWS_API_KEY
            },
            timeout=15
        )

        print(f"[NEWS]   GNews API response status: {r.status_code}")

        r.raise_for_status()

        data = r.json()

        articles = data.get(
            "articles",
            []
        )

        article_count = len(articles)
        print(f"[NEWS]   Articles found: {article_count}")

        if not articles:
            print(f"[NEWS]   No articles found for topic '{topic}'.")
            print("=" * 50)
            return (
                f"No news found for "
                f"'{topic}'."
            )

        output = [
            f"Latest news about {topic}:"
        ]

        for i, article in enumerate(
            articles,
            start=1
        ):
            title = article.get("title", "")
            description = article.get("description", "")
            source = article.get("source", {}).get("name", "Unknown")
            published = article.get("publishedAt", "Unknown")

            print(f"[NEWS]   Article {i}:")
            print(f"[NEWS]     Title: {title}")
            print(f"[NEWS]     Source: {source}")
            print(f"[NEWS]     Published: {published}")
            print(f"[NEWS]     Description: {description[:100]}...")

            output.append(
                f"""
{i}. {title}

{description}
"""
            )

        print(f"[NEWS] ✅ Successfully retrieved {article_count} articles for '{topic}'")
        print("=" * 50)

        return "\n".join(output)

    except Exception as e:
        print(f"[NEWS] ❌ News lookup failed with error: {e}")
        print("=" * 50)
        return (
            f"News lookup failed: "
            f"{str(e)}"
        )