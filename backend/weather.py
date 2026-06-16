import requests


def get_coordinates(city):

    r = requests.get(
        "https://geocoding-api.open-meteo.com/v1/search",
        params={
            "name": city,
            "count": 1,
            "language": "en",
            "format": "json"
        },
        timeout=10
    )

    r.raise_for_status()

    data = r.json()

    results = data.get(
        "results",
        []
    )

    if not results:
        return None

    return {
        "name": results[0]["name"],
        "latitude": results[0]["latitude"],
        "longitude": results[0]["longitude"],
        "country": results[0]["country"]
    }


def get_weather(city):

    location = get_coordinates(city)

    if not location:
        return "Location not found."

    r = requests.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": location["latitude"],
            "longitude": location["longitude"],
            "current": [
                "temperature_2m",
                "relative_humidity_2m",
                "apparent_temperature",
                "weather_code",
                "wind_speed_10m"
            ]
        },
        timeout=10
    )

    r.raise_for_status()

    data = r.json()

    current = data["current"]

    return f"""
Weather for {location['name']}, {location['country']}

Temperature: {current['temperature_2m']}°C
Feels Like: {current['apparent_temperature']}°C
Humidity: {current['relative_humidity_2m']}%
Wind Speed: {current['wind_speed_10m']} km/h
"""