"""Seed the seo_locations table with India's SEO-relevant geographic hierarchy.

Idempotent. Safe to re-run — existing slugs are left untouched.

Footprint at v1:
  - India (1 country)
  - 14 Kerala districts (full coverage) + 36 priority cities elsewhere
  - ~300 localities (IT parks, coaching hubs, college areas, residential
    pockets known to have student/professional accommodation demand)

Designed to be extended later — adding a new city or locality is a single
dict append; no schema or code change needed.

Run with:
    python backend/scripts/seed_seo_locations.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import and_, select
from app.database import AsyncSessionLocal
from app.models.seo_location import LocationKind, SeoLocation


# Tier 1 metros, Tier 2 major cities, Tier 3 emerging hubs.
TIER1 = 1
TIER2 = 2
TIER3 = 3


# ------------------------------------------------------------------ STATES
# (slug, name, state_code, capital_lat, capital_lng)
STATES = [
    ("kerala",           "Kerala",            "KL", 8.5241,  76.9366),
    ("karnataka",        "Karnataka",         "KA", 12.9716, 77.5946),
    ("tamil-nadu",       "Tamil Nadu",        "TN", 13.0827, 80.2707),
    ("telangana",        "Telangana",         "TG", 17.3850, 78.4867),
    ("andhra-pradesh",   "Andhra Pradesh",    "AP", 17.6868, 83.2185),
    ("maharashtra",      "Maharashtra",       "MH", 19.0760, 72.8777),
    ("gujarat",          "Gujarat",           "GJ", 23.0225, 72.5714),
    ("delhi",            "Delhi",             "DL", 28.6139, 77.2090),
    ("uttar-pradesh",    "Uttar Pradesh",     "UP", 26.8467, 80.9462),
    ("rajasthan",        "Rajasthan",         "RJ", 26.9124, 75.7873),
    ("punjab",           "Punjab",            "PB", 30.7333, 76.7794),
    ("haryana",          "Haryana",           "HR", 28.4595, 77.0266),
    ("west-bengal",      "West Bengal",       "WB", 22.5726, 88.3639),
    ("odisha",           "Odisha",            "OD", 20.2961, 85.8245),
    ("bihar",            "Bihar",             "BR", 25.5941, 85.1376),
    ("madhya-pradesh",   "Madhya Pradesh",    "MP", 23.2599, 77.4126),
    ("chandigarh",       "Chandigarh",        "CH", 30.7333, 76.7794),
]


# -------------------------------------------------------------- CITIES + LOCALITIES
# Each city: (state_slug, city_slug, name, lat, lng, tier, aliases, localities)
# Each locality: (slug, name, lat, lng, aliases_or_None)
#
# We keep this declarative so a future SEO expansion is one Python list edit
# away. ~300 localities at v1; expandable to thousands without code change.

CITIES: list[tuple] = [
    # ============================ KERALA (full district coverage) ===========
    ("kerala", "trivandrum", "Trivandrum", 8.5241, 76.9366, TIER2,
     ["Thiruvananthapuram", "TVM", "Anantapuri"], [
        ("technopark",       "Technopark",       8.5567, 76.8810, ["Technopark Phase 1"]),
        ("kazhakkoottam",    "Kazhakkoottam",    8.5680, 76.8830, None),
        ("sreekaryam",       "Sreekaryam",       8.5536, 76.9034, None),
        ("pattom",           "Pattom",           8.5276, 76.9362, None),
        ("kesavadasapuram",  "Kesavadasapuram",  8.5325, 76.9415, None),
        ("kowdiar",          "Kowdiar",          8.5125, 76.9550, None),
        ("vazhuthacaud",     "Vazhuthacaud",     8.5095, 76.9540, None),
        ("medical-college",  "Medical College",  8.5230, 76.9050, None),
        ("thampanoor",       "Thampanoor",       8.4870, 76.9525, None),
        ("vellayambalam",    "Vellayambalam",    8.5145, 76.9510, None),
        ("ulloor",           "Ulloor",           8.5460, 76.9020, None),
        ("kariavattom",      "Kariavattom",      8.5650, 76.8850, None),
        ("statue",           "Statue",           8.5050, 76.9415, None),
        ("palayam",          "Palayam",          8.5095, 76.9435, None),
        ("east-fort",        "East Fort",        8.4830, 76.9430, None),
     ]),
    ("kerala", "kollam", "Kollam", 8.8932, 76.6141, TIER3,
     ["Quilon"], [
        ("chinnakada",     "Chinnakada",     8.8932, 76.6141, None),
        ("ashramam",       "Ashramam",       8.8870, 76.5990, None),
        ("kadappakada",    "Kadappakada",    8.8855, 76.6260, None),
        ("kottiyam",       "Kottiyam",       8.8470, 76.6360, None),
        ("karunagappally", "Karunagappally", 9.0531, 76.5350, None),
     ]),
    ("kerala", "pathanamthitta", "Pathanamthitta", 9.2647, 76.7870, TIER3,
     None, [
        ("adoor",     "Adoor",     9.1530, 76.7320, None),
        ("tiruvalla", "Tiruvalla", 9.3833, 76.5750, None),
        ("ranni",     "Ranni",     9.3870, 76.7860, None),
     ]),
    ("kerala", "alappuzha", "Alappuzha", 9.4981, 76.3388, TIER3,
     ["Alleppey"], [
        ("mullakkal",   "Mullakkal",   9.4960, 76.3380, None),
        ("vandanam",    "Vandanam",    9.4730, 76.3340, None),
        ("cherthala",   "Cherthala",   9.6840, 76.3360, None),
        ("kayamkulam",  "Kayamkulam",  9.1830, 76.5020, None),
     ]),
    ("kerala", "kottayam", "Kottayam", 9.5916, 76.5222, TIER3,
     None, [
        ("nagampadom",     "Nagampadom",     9.5920, 76.5220, None),
        ("kanjikuzhi",     "Kanjikuzhi",     9.5870, 76.5350, None),
        ("changanassery",  "Changanassery",  9.4416, 76.5380, None),
        ("ettumanoor",     "Ettumanoor",     9.6685, 76.5560, None),
        ("vaikom",         "Vaikom",         9.7460, 76.3940, None),
     ]),
    ("kerala", "idukki", "Idukki", 9.8500, 76.9700, TIER3,
     None, [
        ("thodupuzha", "Thodupuzha", 9.8956, 76.7180, None),
        ("munnar",     "Munnar",     10.0889, 77.0595, None),
        ("kattappana", "Kattappana", 9.7460, 77.1180, None),
     ]),
    ("kerala", "kochi", "Kochi", 9.9312, 76.2673, TIER2,
     ["Cochin", "Ernakulam"], [
        ("kakkanad",        "Kakkanad",        10.0150, 76.3410, None),
        ("infopark",        "Infopark",        10.0119, 76.3525, ["Infopark Kochi"]),
        ("edappally",       "Edappally",       10.0258, 76.3082, None),
        ("kaloor",          "Kaloor",          9.9920, 76.2960, None),
        ("palarivattom",    "Palarivattom",    10.0050, 76.3050, None),
        ("vyttila",         "Vyttila",         9.9670, 76.3180, None),
        ("aluva",           "Aluva",           10.1080, 76.3520, None),
        ("kalamassery",     "Kalamassery",     10.0570, 76.3280, None),
        ("marine-drive",    "Marine Drive",    9.9820, 76.2768, None),
        ("fort-kochi",      "Fort Kochi",      9.9647, 76.2424, None),
        ("mattanchery",     "Mattanchery",     9.9580, 76.2580, None),
        ("panampilly-nagar","Panampilly Nagar",9.9670, 76.2950, None),
        ("kadavanthra",     "Kadavanthra",     9.9610, 76.2950, None),
        ("thrikkakara",     "Thrikkakara",     10.0260, 76.3320, None),
        ("muvattupuzha",    "Muvattupuzha",    9.9740, 76.5780, None),
        ("smartcity",       "SmartCity Kochi", 10.0140, 76.3520, ["SmartCity"]),
     ]),
    ("kerala", "thrissur", "Thrissur", 10.5276, 76.2144, TIER3,
     ["Trichur"], [
        ("east-fort-thrissur", "East Fort",   10.5240, 76.2150, None),
        ("ayyanthole",         "Ayyanthole",  10.5280, 76.1900, None),
        ("ollukkara",          "Ollukkara",   10.5530, 76.1730, None),
        ("guruvayur",          "Guruvayur",   10.5944, 76.0394, None),
        ("chalakudy",          "Chalakudy",   10.3060, 76.3340, None),
     ]),
    ("kerala", "palakkad", "Palakkad", 10.7867, 76.6548, TIER3,
     ["Palghat"], [
        ("chittur",  "Chittur",  10.6940, 76.7440, None),
        ("ottapalam","Ottapalam",10.7700, 76.3760, None),
        ("shoranur", "Shoranur", 10.7610, 76.2700, None),
     ]),
    ("kerala", "malappuram", "Malappuram", 11.0509, 76.0710, TIER3,
     None, [
        ("manjeri",   "Manjeri",   11.1200, 76.1190, None),
        ("perinthalmanna", "Perinthalmanna", 10.9740, 76.2270, None),
        ("tirur",     "Tirur",     10.9148, 75.9210, None),
     ]),
    ("kerala", "kozhikode", "Kozhikode", 11.2588, 75.7804, TIER2,
     ["Calicut"], [
        ("mavoor-road",  "Mavoor Road",  11.2570, 75.7920, None),
        ("nadakkavu",    "Nadakkavu",    11.2740, 75.7820, None),
        ("medical-college-calicut", "Medical College", 11.2670, 75.8030, None),
        ("vellimadukunnu","Vellimadukunnu",11.2820, 75.7790, None),
        ("kakkodi",      "Kakkodi",      11.3700, 75.8030, None),
        ("ramanattukara","Ramanattukara",11.1840, 75.8520, None),
     ]),
    ("kerala", "wayanad", "Wayanad", 11.6850, 76.1320, TIER3,
     None, [
        ("kalpetta",   "Kalpetta",   11.6080, 76.0830, None),
        ("sultan-bathery","Sultan Bathery",11.6630, 76.2620, None),
        ("mananthavady",  "Mananthavady",11.8050, 76.0070, None),
     ]),
    ("kerala", "kannur", "Kannur", 11.8745, 75.3704, TIER3,
     ["Cannanore"], [
        ("thavakkara", "Thavakkara", 11.8740, 75.3750, None),
        ("kannur-city","Kannur City",11.8700, 75.3710, None),
        ("payyannur",  "Payyannur",  12.0930, 75.2030, None),
        ("thalassery", "Thalassery", 11.7480, 75.4920, None),
     ]),
    ("kerala", "kasaragod", "Kasaragod", 12.4996, 74.9869, TIER3,
     None, [
        ("kanhangad", "Kanhangad", 12.3050, 75.0830, None),
        ("nileshwar", "Nileshwar", 12.2570, 75.1330, None),
     ]),

    # =========================== KARNATAKA ==================================
    ("karnataka", "bangalore", "Bangalore", 12.9716, 77.5946, TIER1,
     ["Bengaluru"], [
        ("whitefield",       "Whitefield",       12.9698, 77.7500, None),
        ("electronic-city",  "Electronic City",  12.8458, 77.6612, None),
        ("koramangala",      "Koramangala",      12.9352, 77.6245, None),
        ("indiranagar",      "Indiranagar",      12.9784, 77.6408, None),
        ("hsr-layout",       "HSR Layout",       12.9116, 77.6473, None),
        ("marathahalli",     "Marathahalli",     12.9591, 77.6974, None),
        ("hebbal",           "Hebbal",           13.0359, 77.5970, None),
        ("jayanagar",        "Jayanagar",        12.9279, 77.5826, None),
        ("btm-layout",       "BTM Layout",       12.9166, 77.6101, None),
        ("yelahanka",        "Yelahanka",        13.1007, 77.5963, None),
        ("bellandur",        "Bellandur",        12.9258, 77.6760, None),
        ("rajajinagar",      "Rajajinagar",      12.9913, 77.5523, None),
        ("malleshwaram",     "Malleshwaram",     13.0035, 77.5709, None),
        ("kr-puram",         "KR Puram",         13.0070, 77.6960, None),
        ("manyata-tech-park","Manyata Tech Park",13.0410, 77.6210, None),
        ("ecospace",         "Ecospace",         12.9300, 77.6840, None),
     ]),
    ("karnataka", "mysore",     "Mysore",     12.2958, 76.6394, TIER3,
     ["Mysuru"], [
        ("vijayanagar", "Vijayanagar", 12.3225, 76.6388, None),
        ("kuvempunagar","Kuvempunagar",12.3000, 76.6260, None),
        ("hebbal-mysore","Hebbal",     12.3460, 76.6440, None),
     ]),
    ("karnataka", "mangalore",  "Mangalore",  12.9141, 74.8560, TIER3,
     ["Mangaluru"], [
        ("kankanady",   "Kankanady",   12.8810, 74.8470, None),
        ("kadri",       "Kadri",       12.9000, 74.8580, None),
        ("surathkal",   "Surathkal",   13.0070, 74.7950, None),
     ]),
    ("karnataka", "hubli",      "Hubli",      15.3647, 75.1240, TIER3, None, []),
    ("karnataka", "belgaum",    "Belgaum",    15.8497, 74.4977, TIER3, ["Belagavi"], []),

    # =========================== TAMIL NADU =================================
    ("tamil-nadu", "chennai", "Chennai", 13.0827, 80.2707, TIER1,
     ["Madras"], [
        ("velachery",        "Velachery",        12.9800, 80.2200, None),
        ("tambaram",         "Tambaram",         12.9249, 80.1000, None),
        ("omr",              "OMR",              12.8990, 80.2270, ["Old Mahabalipuram Road"]),
        ("guindy",           "Guindy",           13.0067, 80.2200, None),
        ("adyar",            "Adyar",            13.0067, 80.2570, None),
        ("anna-nagar",       "Anna Nagar",       13.0850, 80.2100, None),
        ("nungambakkam",     "Nungambakkam",     13.0610, 80.2410, None),
        ("t-nagar",          "T Nagar",          13.0418, 80.2341, None),
        ("porur",            "Porur",            13.0383, 80.1574, None),
        ("siruseri",         "Siruseri",         12.8270, 80.2210, ["SIPCOT IT Park"]),
        ("sholinganallur",   "Sholinganallur",   12.9010, 80.2280, None),
        ("perungudi",        "Perungudi",        12.9650, 80.2470, None),
     ]),
    ("tamil-nadu", "coimbatore",   "Coimbatore",   11.0168, 76.9558, TIER2,
     ["Kovai"], [
        ("rs-puram",     "RS Puram",     11.0030, 76.9560, None),
        ("peelamedu",    "Peelamedu",    11.0290, 77.0260, None),
        ("saravanampatti","Saravanampatti",11.0790,77.0040, None),
        ("singanallur",  "Singanallur",  11.0090, 77.0260, None),
     ]),
    ("tamil-nadu", "madurai",       "Madurai",       9.9252, 78.1198, TIER3, None, []),
    ("tamil-nadu", "tiruchirappalli","Tiruchirappalli",10.7905,78.7047, TIER3, ["Trichy"], []),
    ("tamil-nadu", "salem",         "Salem",         11.6643, 78.1460, TIER3, None, []),
    ("tamil-nadu", "tirunelveli",   "Tirunelveli",   8.7139,  77.7567, TIER3, None, []),

    # =========================== TELANGANA ==================================
    ("telangana", "hyderabad", "Hyderabad", 17.3850, 78.4867, TIER1,
     None, [
        ("hitech-city",   "Hitech City",   17.4435, 78.3772, ["HITEC City"]),
        ("gachibowli",    "Gachibowli",    17.4400, 78.3489, None),
        ("madhapur",      "Madhapur",      17.4480, 78.3915, None),
        ("kondapur",      "Kondapur",      17.4660, 78.3580, None),
        ("kukatpally",    "Kukatpally",    17.4948, 78.3996, None),
        ("ameerpet",      "Ameerpet",      17.4374, 78.4480, None),
        ("banjara-hills", "Banjara Hills", 17.4156, 78.4347, None),
        ("jubilee-hills", "Jubilee Hills", 17.4326, 78.4071, None),
        ("uppal",         "Uppal",         17.4051, 78.5577, None),
        ("financial-district","Financial District",17.4148,78.3447,None),
     ]),
    ("telangana", "secunderabad","Secunderabad",17.4399, 78.4983, TIER3, None, []),
    ("telangana", "warangal",    "Warangal",    17.9784, 79.5941, TIER3, None, []),

    # =========================== ANDHRA PRADESH =============================
    ("andhra-pradesh","visakhapatnam","Visakhapatnam",17.6868,83.2185,TIER2,["Vizag"],[]),
    ("andhra-pradesh","vijayawada",   "Vijayawada",   16.5062,80.6480,TIER3,None,[]),
    ("andhra-pradesh","guntur",       "Guntur",       16.3067,80.4365,TIER3,None,[]),

    # =========================== MAHARASHTRA ================================
    ("maharashtra", "mumbai", "Mumbai", 19.0760, 72.8777, TIER1,
     ["Bombay"], [
        ("andheri",    "Andheri",    19.1197, 72.8467, None),
        ("bandra",     "Bandra",     19.0596, 72.8295, None),
        ("powai",      "Powai",      19.1196, 72.9061, None),
        ("dadar",      "Dadar",      19.0186, 72.8420, None),
        ("borivali",   "Borivali",   19.2335, 72.8569, None),
        ("malad",      "Malad",      19.1872, 72.8488, None),
        ("vikhroli",   "Vikhroli",   19.1080, 72.9270, None),
        ("worli",      "Worli",      19.0046, 72.8170, None),
        ("lower-parel","Lower Parel",18.9950, 72.8300, None),
     ]),
    ("maharashtra", "navi-mumbai", "Navi Mumbai", 19.0330, 73.0297, TIER2,
     None, [
        ("vashi",      "Vashi",      19.0758, 72.9981, None),
        ("nerul",      "Nerul",      19.0330, 73.0190, None),
        ("kharghar",   "Kharghar",   19.0470, 73.0700, None),
        ("airoli",     "Airoli",     19.1571, 72.9986, None),
     ]),
    ("maharashtra", "thane",   "Thane",   19.2183, 72.9781, TIER2, None, []),
    ("maharashtra", "pune",    "Pune",    18.5204, 73.8567, TIER1,
     None, [
        ("kharadi",      "Kharadi",      18.5510, 73.9410, None),
        ("hinjewadi",    "Hinjewadi",    18.5910, 73.7390, None),
        ("baner",        "Baner",        18.5604, 73.7770, None),
        ("aundh",        "Aundh",        18.5594, 73.8073, None),
        ("viman-nagar",  "Viman Nagar",  18.5670, 73.9143, None),
        ("kothrud",      "Kothrud",      18.5074, 73.8077, None),
        ("hadapsar",     "Hadapsar",     18.5089, 73.9259, None),
        ("magarpatta",   "Magarpatta",   18.5151, 73.9285, None),
        ("wakad",        "Wakad",        18.5970, 73.7700, None),
     ]),
    ("maharashtra", "nagpur",  "Nagpur",  21.1458, 79.0882, TIER2, None, []),
    ("maharashtra", "nashik",  "Nashik",  19.9975, 73.7898, TIER3, None, []),

    # =========================== GUJARAT ====================================
    ("gujarat", "ahmedabad", "Ahmedabad", 23.0225, 72.5714, TIER2,
     None, [
        ("satellite",  "Satellite",  23.0300, 72.5170, None),
        ("vastrapur",  "Vastrapur",  23.0386, 72.5300, None),
        ("sg-highway", "SG Highway", 23.0427, 72.5066, ["Sarkhej-Gandhinagar"]),
        ("bopal",      "Bopal",      23.0316, 72.4685, None),
     ]),
    ("gujarat", "surat",     "Surat",     21.1702, 72.8311, TIER2, None, []),
    ("gujarat", "vadodara",  "Vadodara",  22.3072, 73.1812, TIER3, ["Baroda"], []),
    ("gujarat", "rajkot",    "Rajkot",    22.3039, 70.8022, TIER3, None, []),

    # =========================== DELHI NCR ==================================
    ("delhi", "new-delhi", "New Delhi", 28.6139, 77.2090, TIER1,
     None, [
        ("connaught-place","Connaught Place",28.6315,77.2167,["CP"]),
        ("karol-bagh",     "Karol Bagh",     28.6519, 77.1909, None),
        ("dwarka",         "Dwarka",         28.5921, 77.0460, None),
        ("rohini",         "Rohini",         28.7041, 77.1025, None),
        ("saket",          "Saket",          28.5230, 77.2090, None),
        ("hauz-khas",      "Hauz Khas",      28.5494, 77.2001, None),
        ("nehru-place",    "Nehru Place",    28.5494, 77.2516, None),
        ("vasant-kunj",    "Vasant Kunj",    28.5266, 77.1556, None),
        ("mukherjee-nagar","Mukherjee Nagar",28.7090, 77.2050, None),
        ("old-rajinder-nagar","Old Rajinder Nagar",28.6420,77.1900,None),
     ]),
    ("haryana", "gurugram", "Gurugram", 28.4595, 77.0266, TIER1,
     ["Gurgaon"], [
        ("cyber-city",   "Cyber City",   28.4949, 77.0890, ["DLF Cyber City"]),
        ("golf-course-road","Golf Course Road",28.4502,77.1023,None),
        ("sohna-road",   "Sohna Road",   28.4170, 77.0480, None),
        ("sector-29",    "Sector 29",    28.4666, 77.0660, None),
        ("sector-49",    "Sector 49",    28.4148, 77.0490, None),
        ("udyog-vihar",  "Udyog Vihar",  28.4995, 77.0827, None),
     ]),
    ("haryana", "faridabad", "Faridabad", 28.4089, 77.3178, TIER2, None, []),
    ("uttar-pradesh", "noida", "Noida", 28.5355, 77.3910, TIER1,
     None, [
        ("sector-62",      "Sector 62",      28.6280, 77.3650, None),
        ("sector-18",      "Sector 18",      28.5708, 77.3260, None),
        ("greater-noida",  "Greater Noida",  28.4744, 77.5040, None),
        ("noida-extension","Noida Extension",28.5990, 77.4380, None),
     ]),
    ("uttar-pradesh", "ghaziabad","Ghaziabad",28.6692, 77.4538, TIER2, None, []),

    # =========================== UTTAR PRADESH (other) ======================
    ("uttar-pradesh", "lucknow",  "Lucknow",  26.8467, 80.9462, TIER2,
     None, [
        ("hazratganj", "Hazratganj", 26.8499, 80.9469, None),
        ("gomti-nagar","Gomti Nagar",26.8540, 80.9930, None),
        ("aliganj",    "Aliganj",    26.8884, 80.9446, None),
     ]),
    ("uttar-pradesh", "kanpur",   "Kanpur",   26.4499, 80.3319, TIER3, None, []),
    ("uttar-pradesh", "prayagraj","Prayagraj",25.4358, 81.8463, TIER3, ["Allahabad"], []),
    ("uttar-pradesh", "varanasi", "Varanasi", 25.3176, 82.9739, TIER3, ["Banaras"], []),

    # =========================== RAJASTHAN ==================================
    ("rajasthan", "jaipur",  "Jaipur",  26.9124, 75.7873, TIER2,
     None, [
        ("malviya-nagar","Malviya Nagar",26.8530,75.8230, None),
        ("vaishali-nagar","Vaishali Nagar",26.9120,75.7450,None),
        ("mansarovar",  "Mansarovar",   26.8540, 75.7700, None),
     ]),
    ("rajasthan", "kota",    "Kota",    25.2138, 75.8648, TIER2,
     ["Coaching Hub"], [
        ("rajeev-gandhi-nagar","Rajeev Gandhi Nagar",25.1940,75.8580,None),
        ("talwandi",          "Talwandi",            25.1620,75.8650,None),
        ("jawahar-nagar",     "Jawahar Nagar",       25.2070,75.8590,None),
        ("vigyan-nagar",      "Vigyan Nagar",        25.1880,75.8640,None),
        ("indra-vihar",       "Indra Vihar",         25.1900,75.8720,None),
     ]),
    ("rajasthan", "udaipur", "Udaipur", 24.5854, 73.7125, TIER3, None, []),

    # =========================== PUNJAB / CHANDIGARH ========================
    ("chandigarh", "chandigarh", "Chandigarh", 30.7333, 76.7794, TIER2,
     None, [
        ("sector-17", "Sector 17", 30.7411, 76.7780, None),
        ("sector-22", "Sector 22", 30.7300, 76.7770, None),
        ("sector-35", "Sector 35", 30.7270, 76.7600, None),
     ]),
    ("punjab", "mohali",    "Mohali",    30.7046, 76.7179, TIER3, None, []),
    ("punjab", "ludhiana",  "Ludhiana",  30.9000, 75.8573, TIER3, None, []),

    # =========================== WEST BENGAL ================================
    ("west-bengal", "kolkata", "Kolkata", 22.5726, 88.3639, TIER1,
     ["Calcutta"], [
        ("salt-lake",     "Salt Lake",     22.5876, 88.4170, ["Bidhannagar"]),
        ("new-town",      "New Town",      22.5800, 88.4640, None),
        ("park-street",   "Park Street",   22.5520, 88.3520, None),
        ("ballygunge",    "Ballygunge",    22.5290, 88.3650, None),
        ("howrah",        "Howrah",        22.5958, 88.2636, None),
        ("rajarhat",      "Rajarhat",      22.6230, 88.4630, None),
     ]),

    # =========================== ODISHA =====================================
    ("odisha", "bhubaneswar", "Bhubaneswar", 20.2961, 85.8245, TIER2,
     None, [
        ("patia",         "Patia",         20.3536, 85.8186, None),
        ("chandrasekharpur","Chandrasekharpur",20.3270,85.8230,None),
        ("saheed-nagar",  "Saheed Nagar",  20.2820, 85.8480, None),
        ("kiit",          "KIIT",          20.3540, 85.8190, ["KIIT University"]),
     ]),
    ("odisha", "cuttack",     "Cuttack",     20.4625, 85.8828, TIER3, None, []),

    # =========================== BIHAR ======================================
    ("bihar", "patna", "Patna", 25.5941, 85.1376, TIER2,
     None, [
        ("boring-road",  "Boring Road",  25.6050, 85.1340, None),
        ("kankarbagh",   "Kankarbagh",   25.5950, 85.1620, None),
        ("rajendra-nagar","Rajendra Nagar",25.6100,85.1500,None),
        ("patliputra",   "Patliputra",   25.6280, 85.0800, None),
     ]),

    # =========================== MADHYA PRADESH =============================
    # (added for completeness — major student cities)
    ("madhya-pradesh", "indore", "Indore", 22.7196, 75.8577, TIER2, None, []),
    ("madhya-pradesh", "bhopal", "Bhopal", 23.2599, 77.4126, TIER3, None, []),
]


async def _upsert(db, **values) -> SeoLocation:
    row = (await db.execute(
        select(SeoLocation).where(and_(
            SeoLocation.kind == values["kind"],
            SeoLocation.slug == values["slug"],
            SeoLocation.parent_id == values.get("parent_id"),
        ))
    )).scalar_one_or_none()
    if row is not None:
        return row
    row = SeoLocation(**values)
    db.add(row)
    await db.flush()
    return row


async def run() -> None:
    import json as _json

    async with AsyncSessionLocal() as db:
        # Country
        india = await _upsert(
            db,
            kind=LocationKind.COUNTRY,
            slug="india", name="India",
            country_code="IN", state_code=None,
            lat=20.5937, lng=78.9629,
            population_tier=1, is_seo_active=True,
        )

        state_rows: dict[str, SeoLocation] = {}
        for slug, name, code, lat, lng in STATES:
            row = await _upsert(
                db, kind=LocationKind.STATE, slug=slug, name=name,
                parent_id=india.id, state_code=code,
                lat=lat, lng=lng, population_tier=2,
                is_seo_active=True,
            )
            state_rows[slug] = row

        city_count = 0
        locality_count = 0

        for state_slug, city_slug, city_name, lat, lng, tier, aliases, localities in CITIES:
            state = state_rows.get(state_slug)
            if state is None:
                print(f"⚠️  state {state_slug} not seeded, skipping {city_slug}")
                continue
            city = await _upsert(
                db, kind=LocationKind.CITY, slug=city_slug, name=city_name,
                parent_id=state.id, state_code=state.state_code,
                lat=lat, lng=lng, population_tier=tier,
                aliases_json=_json.dumps(aliases) if aliases else None,
                # Activate Trivandrum + Kochi for v1 launch; rest stay staged.
                is_seo_active=(city_slug in {"trivandrum", "kochi"}),
            )
            city_count += 1
            for loc_slug, loc_name, loc_lat, loc_lng, loc_aliases in localities:
                await _upsert(
                    db, kind=LocationKind.LOCALITY, slug=loc_slug,
                    name=loc_name, parent_id=city.id,
                    state_code=state.state_code,
                    lat=loc_lat, lng=loc_lng, population_tier=tier,
                    aliases_json=_json.dumps(loc_aliases) if loc_aliases else None,
                    is_seo_active=city.is_seo_active,
                )
                locality_count += 1

        await db.commit()
        print(
            f"✅ seo_locations seeded: "
            f"1 country, {len(state_rows)} states, "
            f"{city_count} cities, {locality_count} localities."
        )
        print(
            "ℹ️  Trivandrum + Kochi marked is_seo_active=True for v1 launch. "
            "Flip other cities to True from /super-admin once supply is live."
        )


if __name__ == "__main__":
    asyncio.run(run())
