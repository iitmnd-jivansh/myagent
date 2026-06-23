import os
import requests


GNEWS_API_KEY = "c1e78acd73b05a5987938bf88d20d891"

BASE_URL = "https://gnews.io/api/v4/search"


def get_news(
    topic: str = "general",
    max_results: int = 5
) -> str:
    """Fetches the latest news articles about a specific topic."""

    if not GNEWS_API_KEY:
        return (
            "GNEWS_API_KEY environment "
            "variable not set."
        )

    try:

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

        r.raise_for_status()

        data = r.json()

        articles = data.get(
            "articles",
            []
        )

        if not articles:
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

            title = article.get(
                "title",
                ""
            )

            description = article.get(
                "description",
                ""
            )

            output.append(
                f"""
{i}. {title}

{description}
"""
            )

        return "\n".join(output)

    except Exception as e:

        return (
            f"News lookup failed: "
            f"{str(e)}"
        )