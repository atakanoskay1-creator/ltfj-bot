"""NOTAC API icin gercekci test ornekleri.

Kullanicinin 2026-09-16'da GitHub Actions'tan attigi gercek
"GET /notam/?location=LTFJ" isteginin GERCEK yanitindaki alan adlari ve
yapisiyla BIREBIR uyumlu, elle olusturulmus ornekler. Gercek NOTAM
numaralari/metinleri kullaniliyor (kamuya acik NOTAM verisi, gizli bir
sey icermez) - sadece id (UUID) alanlari test icin kisaltilmis/uydurma.
"""

RUNWAY_YUZEY_DUZENSIZLIGI = {
    "id": "190a947d-aebc-414b-9ea6-f06bb1fbf7a1",
    "number": "B3455/26",
    "notam_type": "R",
    "affected_fir": "LTBB",
    "series": "B",
    "q_code": "QMRXX",
    "year": "2026",
    "minimum_fl": "000",
    "maximum_fl": "999",
    "schedule": None,
    "lower_limit": None,
    "upper_limit": None,
    "account_id": "LTAAYNYX",
    "status": "active",
    "effective_start": "2026-08-28T07:11:00Z",
    "effective_end": "2026-10-02T16:00:00Z",
    "notam_issued": "2026-08-28T07:15:00Z",
    "notam_updated": "2026-08-28T07:15:00Z",
    "record_created_at": "2026-08-28T07:30:32.771985Z",
    "record_updated_at": "2026-08-28T07:30:03.979035Z",
    "record_archived_at": None,
    "text": "PRESENCE SURFACE IRREGULARITIES ON RWY 06L/24R REDUCING DRIVING \r\nQUALITY.",
    "readings": [
        {
            "short": "Runway 06L/24R has surface irregularities.",
            "long": "Runway 06L/24R has surface irregularities that reduce driving quality, from 28 Aug 2026 07:11 to 2 Oct 2026 16:00 UTC.",
            "generated_at": "2026-08-28T07:32:35Z",
        }
    ],
    "category": {
        "code": "RUNWAY",
        "label": "Runway",
        "description": "Runway closures, works and restrictions",
    },
    "geography": {
        "coordinates": "4054N02919E",
        "radius": "005",
        "radius_nm": 5,
        "latitude": 40.898333,
        "longitude": 29.309167,
        "geojson": {"type": "Point", "coordinates": [29.309167, 40.898333]},
    },
    "location": {
        "id": 41184,
        "code": "LTFJ",
        "icao_code": "LTFJ",
        "iata_code": "SAW",
        "name": "Istanbul Sabiha Gökçen International Airport",
    },
    "location_code": "LTFJ",
    "country": {
        "code": "TR", "name": "Turkey", "continent": "AS", "continent_name": "Asia",
        "url_wiki": "https://en.wikipedia.org/wiki/Turkey",
    },
    "region": {
        "code": "TR-41", "name": "Kocaeli Province", "local_code": "41",
        "continent": "AS", "continent_name": "Asia", "country_code": "TR",
        "url_wiki": "https://en.wikipedia.org/wiki/Kocaeli_Province",
    },
    "tags": [
        {"name": "maintenance", "label": "Maintenance", "description": "Maintenance or work in progress"},
        {"name": "movement-area", "label": "Movement area", "description": "Runway / taxiway / apron (movement area)"},
        {"name": "runway", "label": "Runway", "description": "Runway"},
    ],
    "runway_conditions": None,
    "obstacle": None,
    "affected_elements": [{"ref": "06L/24R", "type": "RWY"}],
}

RUNWAY_KAPANIS = {
    "id": "8f9209b8-706f-48bd-9ddd-cd1af0f77ddc",
    "number": "B7835/25",
    "notam_type": "N",
    "affected_fir": "LTBB",
    "series": "B",
    "q_code": "QMRLC",
    "year": "2025",
    "minimum_fl": "000",
    "maximum_fl": "999",
    "schedule": None,
    "lower_limit": None,
    "upper_limit": None,
    "account_id": "LTAAYNYX",
    "status": "active",
    "effective_start": "2026-03-29T23:00:00Z",
    "effective_end": "2026-10-24T01:59:00Z",
    "notam_issued": "2025-09-30T12:18:00Z",
    "notam_updated": "2025-09-30T12:19:00Z",
    "record_created_at": "2026-07-22T16:56:54.080303Z",
    "record_updated_at": "2026-07-22T16:56:54.080303Z",
    "record_archived_at": None,
    "text": (
        "SABIHA GOKCEN AD,\nRWY 06L/24R SHALL BE TEMPORARILY CLSD TO DEP AND ARR TFC DUE TO \n"
        "RWY MAINTENANCE AS FOLLOWING DATES AND TIMES."
    ),
    "readings": [
        {
            "short": "Runway 06L/24R is temporarily closed for maintenance.",
            "long": "Runway 06L/24R is temporarily closed to departing and arriving traffic due to runway maintenance during scheduled times between 29 March and 24 October 2026.",
            "generated_at": "2026-07-25T17:59:43Z",
        }
    ],
    "category": {"code": "RUNWAY", "label": "Runway", "description": "Runway closures, works and restrictions"},
    "geography": {
        "coordinates": "4054N02919E", "radius": "005", "radius_nm": 5,
        "latitude": 40.9, "longitude": 29.316667,
        "geojson": {"type": "Point", "coordinates": [29.316667, 40.9]},
    },
    "location": {
        "id": 41184, "code": "LTFJ", "icao_code": "LTFJ", "iata_code": "SAW",
        "name": "Istanbul Sabiha Gökçen International Airport",
    },
    "location_code": "LTFJ",
    "country": {"code": "TR", "name": "Turkey", "continent": "AS", "continent_name": "Asia",
                "url_wiki": "https://en.wikipedia.org/wiki/Turkey"},
    "region": {"code": "TR-41", "name": "Kocaeli Province", "local_code": "41",
               "continent": "AS", "continent_name": "Asia", "country_code": "TR",
               "url_wiki": "https://en.wikipedia.org/wiki/Kocaeli_Province"},
    "tags": [
        {"name": "maintenance", "label": "Maintenance", "description": "Maintenance or work in progress"},
        {"name": "runway", "label": "Runway", "description": "Runway"},
    ],
    "runway_conditions": None,
    "obstacle": None,
    "affected_elements": [{"ref": "06L/24R", "type": "RWY"}],
}

# Baska bir lokasyon icin (LTFJ filtresinin gercekten calistigini test etmek icin)
BASKA_LOKASYON = {**RUNWAY_YUZEY_DUZENSIZLIGI, "id": "farkli-lokasyon-id",
                   "location_code": "LTBA",
                   "location": {**RUNWAY_YUZEY_DUZENSIZLIGI["location"], "code": "LTBA", "icao_code": "LTBA"}}

# Zorunlu olmayan alanlarin (category, tags, readings, affected_elements) HEPSI
# eksik/None oldugu minimal bir kayit - defansif .get() kullanimini test eder.
MINIMAL_KAYIT = {
    "id": "minimal-id-0001",
    "number": "M0001/26",
    "notam_type": "N",
    "status": "active",
    "effective_start": "2026-01-01T00:00:00Z",
    "effective_end": "2026-01-02T00:00:00Z",
    "notam_issued": "2026-01-01T00:00:00Z",
    "notam_updated": "2026-01-01T00:00:00Z",
    "record_updated_at": "2026-01-01T00:00:00Z",
    "text": "MINIMAL NOTAM TEXT.",
    "location_code": "LTFJ",
    # category, tags, readings, affected_elements, location BILEREK YOK
}

GECERSIZ_KAYIT_ID_YOK = {"number": "NOID/26", "status": "active", "location_code": "LTFJ"}

STANDART_YANIT = {
    "count": 2,
    "next": None,
    "previous": None,
    "results": [RUNWAY_YUZEY_DUZENSIZLIGI, RUNWAY_KAPANIS],
}
