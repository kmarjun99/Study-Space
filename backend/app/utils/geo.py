import math

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great circle distance between two points 
    on the earth (specified in decimal degrees)
    Returns distance in Kilometers
    """
    if lat1 is None or lon1 is None or lat2 is None or lon2 is None:
        return float('inf')

    # Convert decimal degrees to radians 
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])

    # Haversine formula 
    dlon = lon2 - lon1 
    dlat = lat2 - lat1 
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a)) 
    r = 6371 # Radius of earth in kilometers. Use 3956 for miles
    return c * r

def sort_by_proximity(user_lat: float, user_lon: float, items: list) -> list:
    """
    Sorts a list of objects (dicts or models) by distance to user.
    Objects must have 'latitude' and 'longitude' attributes.
    Adds a '_distance' attribute to the object/dict.
    """
    for item in items:
        # Check if item is dict or object
        i_lat = item.get('latitude') if isinstance(item, dict) else getattr(item, 'latitude', None)
        i_lon = item.get('longitude') if isinstance(item, dict) else getattr(item, 'longitude', None)
        
        dist = haversine_distance(user_lat, user_lon, i_lat, i_lon)
        
        if isinstance(item, dict):
            item['_distance'] = dist
        else:
            setattr(item, '_distance', dist)
            
    return sorted(items, key=lambda x: x['_distance'] if isinstance(x, dict) else getattr(x, '_distance'))
