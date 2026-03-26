"""Restaurant collection runner (Places API).

Location and zone settings are loaded from zone_config.py.
To collect a different area, edit only zone_config.py."""
import os
import googlemaps
import pandas as pd
import time
from pathlib import Path
from dotenv import load_dotenv

# Zone settings from zone_config (lat/lng, sub-areas, radius, output suffix, text queries)
from zone_config import get_zones, ZONE_RADIUS, OUTPUT_SUFFIX, TEXT_QUERIES

PROJECT_ROOT = Path(__file__).parent.parent
ENV_FILE = PROJECT_ROOT / ".env"

load_dotenv(dotenv_path=ENV_FILE)

API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
if not API_KEY:
    raise ValueError(
        "GOOGLE_MAPS_API_KEY is not set.\n"
        "Create a .env file at the project root and set the API key.\n"
        f"Expected path: {ENV_FILE}"
    )

OUTPUT_DIR = Path(__file__).parent / "Data1_Information(R_Info)"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
gmaps = googlemaps.Client(key=API_KEY)

# Zone grid from zone_config
ZONES = get_zones()

# Cost-control flags
CHECK_BUSINESS_STATUS = False  # True: verify business status (extra cost); False: skip (cheaper)
TEXT_SEARCH_ENABLED = True  # Text Search on/off (billable when on)

res_list = []
collected_place_ids = set()
api_call_count = {"nearby": 0, "text": 0, "details": 0}

# Collect per grid zone (Nearby Search)
for zone in ZONES:
    zone_name = zone["name"]
    location = (zone["lat"], zone["lng"])
    zone_count = 0

    try:
        places_result = gmaps.places_nearby(
            location=location,
            radius=ZONE_RADIUS,
            type='restaurant'
        )
        api_call_count["nearby"] += 1
    except Exception:
        continue

    page_count = 1
    next_page_token = places_result.get('next_page_token')

    while True:
        for place in places_result.get('results', []):
            place_id = place.get('place_id')

            if place_id in collected_place_ids:
                continue

            if CHECK_BUSINESS_STATUS:
                try:
                    place_details = gmaps.place(
                        place_id=place_id,
                        fields=['business_status']
                    )
                    api_call_count["details"] += 1
                    business_status = place_details.get('result', {}).get('business_status')
                    if business_status != 'OPERATIONAL':
                        continue
                except Exception:
                    pass

            res_list.append({
                "restaurant_id": place_id,
                "district": zone_name,
                "r_name": place.get('name'),
                "r_latitude": place.get('geometry', {}).get('location', {}).get('lat'),
                "r_longitude": place.get('geometry', {}).get('location', {}).get('lng'),
                "rating": place.get('rating'),
                "category": place.get('types', [None])[0] if place.get('types') else None,
                "address": place.get('vicinity') or place.get('formatted_address')
            })

            collected_place_ids.add(place_id)
            zone_count += 1
            time.sleep(0.1)

        if not next_page_token or page_count >= 3:
            break

        time.sleep(2)
        try:
            places_result = gmaps.places_nearby(
                location=location,
                radius=ZONE_RADIUS,
                type='restaurant',
                page_token=next_page_token
            )
            api_call_count["nearby"] += 1
            next_page_token = places_result.get('next_page_token')
            page_count += 1
        except Exception:
            break

    print(f"[{zone_name}] {zone_count} places")

# Extra collection via Text Search (TEXT_QUERIES from zone_config)
text_query_count = 0
queries_to_use = TEXT_QUERIES if TEXT_SEARCH_ENABLED else []

for query in queries_to_use:
    try:
        places_result = gmaps.places(query=query)
        api_call_count["text"] += 1
        next_page_token = places_result.get('next_page_token')
        page_count = 1

        while True:
            for place in places_result.get('results', []):
                place_id = place.get('place_id')

                if place_id in collected_place_ids:
                    continue

                if CHECK_BUSINESS_STATUS:
                    try:
                        place_details = gmaps.place(
                            place_id=place_id,
                            fields=['business_status']
                        )
                        api_call_count["details"] += 1
                        if place_details.get('result', {}).get('business_status') != 'OPERATIONAL':
                            continue
                    except Exception:
                        pass

                res_list.append({
                    "restaurant_id": place_id,
                    "district": OUTPUT_SUFFIX,
                    "r_name": place.get('name'),
                    "r_latitude": place.get('geometry', {}).get('location', {}).get('lat'),
                    "r_longitude": place.get('geometry', {}).get('location', {}).get('lng'),
                    "rating": place.get('rating'),
                    "category": place.get('types', [None])[0] if place.get('types') else None,
                    "address": place.get('formatted_address')
                })

                collected_place_ids.add(place_id)
                text_query_count += 1
                time.sleep(0.1)

            if not next_page_token or page_count >= 3:
                break

            time.sleep(2)
            try:
                places_result = gmaps.places(query=query, page_token=next_page_token)
                api_call_count["text"] += 1
                next_page_token = places_result.get('next_page_token')
                page_count += 1
            except Exception:
                break

        time.sleep(0.5)
    except Exception as e:
        print(f"Text search error: {e}")

if text_query_count > 0:
    print(f"Text search added: {text_query_count} places")

df = pd.DataFrame(res_list)
df = df.drop_duplicates(subset=['restaurant_id'], keep='first')

output_path = OUTPUT_DIR / f"restaurants_{OUTPUT_SUFFIX}.csv"
df.to_csv(output_path, index=False, encoding="utf-8-sig")

total_api_calls = api_call_count["nearby"] + api_call_count["text"] + api_call_count["details"]
estimated_cost = (api_call_count["nearby"] * 0.032) + (api_call_count["text"] * 0.032) + (api_call_count["details"] * 0.017)

print(f"Saved: {output_path} (total {len(df)} restaurants)")
print(
    f"API calls — Nearby: {api_call_count['nearby']}, Text: {api_call_count['text']}, "
    f"Details: {api_call_count['details']}, total: {total_api_calls}"
)
print(f"Estimated cost: ${estimated_cost:.2f}")
