import requests


def get_coordinates(city):
    print("─" * 50)
    print(f"[WEATHER] Geocoding request for city: '{city}'")
    print(f"[WEATHER]   Calling Open-Meteo Geocoding API...")

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

    print(f"[WEATHER]   Geocoding API status: {r.status_code}")

    r.raise_for_status()

    data = r.json()

    results = data.get(
        "results",
        []
    )

    if not results:
        print(f"[WEATHER] ❌ Location '{city}' not found in geocoding API.")
        print("─" * 50)
        return None

    location = {
        "name": results[0]["name"],
        "latitude": results[0]["latitude"],
        "longitude": results[0]["longitude"],
        "country": results[0]["country"]
    }

    print(f"[WEATHER]   Found location: {location['name']}, {location['country']}")
    print(f"[WEATHER]   Coordinates: {location['latitude']}, {location['longitude']}")
    print("─" * 50)

    return location


def get_weather(city: str) -> str:
    """Returns the current weather conditions for the specified city."""
    print("=" * 50)
    print(f"[WEATHER] Weather lookup request")
    print(f"[WEATHER]   City: '{city}'")
    print("=" * 50)

    location = get_coordinates(city)

    if not location:
        print(f"[WEATHER] ❌ Cannot fetch weather: location not found.")
        print("=" * 50)
        return "Location not found."

    print(f"[WEATHER]   Fetching weather data from Open-Meteo forecast API...")
    print(f"[WEATHER]   Parameters: temperature, humidity, feels-like, wind, weather_code")

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

    print(f"[WEATHER]   Forecast API status: {r.status_code}")
    r.raise_for_status()

    data = r.json()

    current = data["current"]

    result = f"""
Weather for {location['name']}, {location['country']}

Temperature: {current['temperature_2m']}°C
Feels Like: {current['apparent_temperature']}°C
Humidity: {current['relative_humidity_2m']}%
Wind Speed: {current['wind_speed_10m']} km/h
"""

    print(f"[WEATHER] ✅ Weather data retrieved:")
    print(f"[WEATHER]   Location: {location['name']}, {location['country']}")
    print(f"[WEATHER]   Temperature: {current['temperature_2m']}°C")
    print(f"[WEATHER]   Feels Like: {current['apparent_temperature']}°C")
    print(f"[WEATHER]   Humidity: {current['relative_humidity_2m']}%")
    print(f"[WEATHER]   Wind Speed: {current['wind_speed_10m']} km/h")
    print("=" * 50)

    return result