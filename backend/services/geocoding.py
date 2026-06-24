import httpx
import logging
import re
from typing import Optional

logger = logging.getLogger("geocoding")


def extract_house_number(query: str, street: str, city: str, neighborhood: str) -> Optional[str]:
    if not query:
        return None
    
    q = query.lower()
    
    # Remove street, city, neighborhood if they exist in the query
    for part in [street, city, neighborhood]:
        if part:
            escaped = re.escape(part.lower())
            q = re.sub(escaped, "", q)
            
    # Find any standalone number-like patterns (e.g. 5, 5א, 12b)
    matches = re.findall(r'\b\d+[a-zA-Z\u0590-\u05fe]?\b', q)
    if matches:
        return matches[0]
    
    # Fallback without word boundaries
    matches_fallback = re.findall(r'\d+[a-zA-Z\u0590-\u05fe]?', q)
    if matches_fallback:
        return matches_fallback[0]
        
    return None


async def geocode_text(address: str) -> Optional[dict]:
    """
    Geocodes an address string using OpenStreetMap Nominatim.
    Returns parsed dictionary of Country, City, Neighborhood, Street, Building,
    or None if lookup fails.
    """
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": address,
        "format": "json",
        "addressdetails": 1,
        "limit": 1,
        "accept-language": "en"
    }
    headers = {
        "User-Agent": "Localis-Community-Bot/1.0 (localis-dev-contact@localis.org)"
    }
    try:
        async with httpx.AsyncClient() as client:
            res = await client.get(url, params=params, headers=headers, timeout=10.0)
            if res.status_code == 200:
                data = res.json()
                if data:
                    res_dict = parse_nominatim_address(data[0].get("address", {}), query=address)
                    res_dict["latitude"] = float(data[0].get("lat")) if data[0].get("lat") else None
                    res_dict["longitude"] = float(data[0].get("lon")) if data[0].get("lon") else None
                    return res_dict
    except Exception as e:
        logger.error(f"Error geocoding text address '{address}': {e}")
    return None

async def reverse_geocode(lat: float, lon: float) -> Optional[dict]:
    """
    Reverse geocodes lat/lon coordinates using OpenStreetMap Nominatim.
    """
    url = "https://nominatim.openstreetmap.org/reverse"
    params = {
        "lat": lat,
        "lon": lon,
        "format": "json",
        "addressdetails": 1,
        "accept-language": "en"
    }
    headers = {
        "User-Agent": "Localis-Community-Bot/1.0 (localis-dev-contact@localis.org)"
    }
    try:
        async with httpx.AsyncClient() as client:
            res = await client.get(url, params=params, headers=headers, timeout=10.0)
            if res.status_code == 200:
                data = res.json()
                if "address" in data:
                    res_dict = parse_nominatim_address(data["address"])
                    res_dict["latitude"] = float(data.get("lat")) if data.get("lat") else lat
                    res_dict["longitude"] = float(data.get("lon")) if data.get("lon") else lon
                    return res_dict
    except Exception as e:
        logger.error(f"Error reverse geocoding ({lat}, {lon}): {e}")
    return None

def parse_nominatim_address(address: dict, query: Optional[str] = None) -> dict:
    """
    Helper to clean and normalize Nominatim address details into hierarchy components:
    Country > City > Neighborhood > Street > Building
    """
    # Country
    country = address.get("country", "")

    # City
    city = address.get("city") or address.get("town") or address.get("village") or address.get("municipality") or ""

    # Neighborhood
    neighborhood = address.get("neighbourhood") or address.get("suburb") or address.get("residential") or address.get("city_district") or ""

    # Street
    street = address.get("road") or address.get("street") or ""

    # Building (usually house number + street name, or block name)
    house_number = address.get("house_number", "")
    if not house_number and street and query:
        extracted = extract_house_number(query, street, city, neighborhood)
        if extracted:
            house_number = extracted

    building = ""
    if house_number and street:
        building = f"{street} {house_number}"
    elif house_number:
        building = f"בניין {house_number}"

    return {
        "country": country.strip(),
        "city": city.strip(),
        "neighborhood": neighborhood.strip(),
        "street": street.strip(),
        "building": building.strip()
    }

