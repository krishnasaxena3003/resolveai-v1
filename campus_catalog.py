"""AKGEC public place and academic department catalog.

Coordinates are point locations (not surveyed building footprints). Sources and
confidence are kept alongside each row so the map never implies field survey.
"""
from datetime import datetime, timezone

VERIFIED_AT = "2026-11-01"
DEPARTMENTS = (
    "Applied Sciences & Humanities",
    "Computer Science and Engineering",
    "Information Technology",
    "Electronics and Communication Engineering",
    "Mechanical Engineering",
    "Civil Engineering",
    "Electrical and Electronics Engineering",
    "Master of Computer Applications",
)
DEPARTMENT_ALIASES = {
    "applied sciences": "Applied Sciences & Humanities",
    "applied science": "Applied Sciences & Humanities",
    "cse": "Computer Science and Engineering",
    "computer science": "Computer Science and Engineering",
    "it": "Information Technology",
    "ece": "Electronics and Communication Engineering",
    "en/ec": "Electronics and Communication Engineering",
    "mechanical": "Mechanical Engineering", "mech": "Mechanical Engineering",
    "civil": "Civil Engineering", "eee": "Electrical and Electronics Engineering",
    "mca": "Master of Computer Applications",
}

GOOGLE = "https://www.google.com/maps/search/?api=1&query={lat}%2C{lon}"
OFFICIAL_TOUR = "https://www.akgec.ac.in/about/infrastructure-visual-tour/academic-complex/"
LIBRARY_SOURCE = "https://www.akgec.ac.in/central-library/"
IT_LABS_SOURCE = "https://www.akgec.ac.in/it-labs/"
MCA_SOURCE = "https://www.akgec.ac.in/departments/master-of-computer-applications/"
CSE_GEOTAG_SOURCE = "https://www.akgec.ac.in/wp-content/uploads/2022/11/4.1.1GEOTAGGED_CSELABS.pdf"
IT_GEOTAG_SOURCE = "https://www.akgec.ac.in/wp-content/uploads/2022/11/4.1.1_GOETAGGED_IT-LABORATORIES.pdf"
DEPARTMENTAL_LIBRARY_SOURCE = "https://www.akgec.ac.in/wp-content/uploads/2022/11/Departmental-Library.pdf"
LIBRARY_GEOTAG_SOURCE = "https://www.akgec.ac.in/wp-content/uploads/2022/11/Central-Library.pdf"
ELECTRONICS_GEOTAG_SOURCE = "https://www.akgec.ac.in/wp-content/uploads/2022/11/4.1.1_GEOTAGGED-ECE-LABORATORIES.pdf"
CIVIL_GEOTAG_SOURCE = "https://www.akgec.ac.in/wp-content/uploads/2022/11/4.1.1_GEOTAGGED-CIVIL-LABORATORY.pdf"

# name, canonical, type, lat, lon, source, confidence, parent, maps URL
LOCATIONS = [
    ("Ajay Kumar Garg Engineering College", "akgec-campus", "campus", 28.6756736, 77.5020041,
     "Google Maps AKGEC place pin", "coordinates_verified_against_map", None,
     "https://www.google.com/maps/place/Ajay+Kumar+Garg+Engineering+College/@28.6756736,77.5020041,17z/"),
    ("CS/IT Block", "cs-it-block", "building", 28.675444, 77.503083,
     "User-provided coordinate; nearby Google Maps CS/IT lab pin is not a building footprint", "user_provided_needs_footprint_confirmation", "akgec-campus", GOOGLE.format(lat=28.6753532, lon=77.5032261)),
    ("Back Block (AKGEC)", "back-block", "building", 28.676333, 77.501083,
     "User-provided coordinate; nearby Google Maps place pin; building footprint still needs confirmation", "user_provided_needs_footprint_confirmation", "akgec-campus", "https://www.google.com/maps/place/Back+Block+AKGEC/@28.6761954,77.5010931,19z/"),
    ("AKGEC Fronius", "fronius", "facility", 28.6764338, 77.5018517,
     "Google Maps place pin", "coordinates_verified_against_map", "akgec-campus", GOOGLE.format(lat=28.6764338, lon=77.5018517)),
    ("Sports Centre and Gymnasium", "sports-centre", "facility", 28.6744034, 77.5037666,
     "Google Maps place pin", "coordinates_verified_against_map", "akgec-campus", GOOGLE.format(lat=28.6744034, lon=77.5037666)),
    ("Basketball Court", "basketball-court", "facility", None, None,
     "Google Maps search returned multiple plausible courts; pin needs confirmation", "name_verified", "akgec-campus", "https://www.google.com/maps/search/?api=1&query=Basketball+Court+AKGEC"),
    ("AKGEC Football Ground", "football-ground", "facility", 28.6739231, 77.5037622,
     "Google Maps place pin", "coordinates_verified_against_map", "akgec-campus", GOOGLE.format(lat=28.6739231, lon=77.5037622)),
    ("Administrative Block", "administrative-block", "building", None, None,
     "AKGEC official academic complex tour; coordinates not established", "name_verified", "akgec-campus", OFFICIAL_TOUR),
    ("Mechanical Block", "mechanical-block", "building", 28.6766311, 77.5016766,
     "Google Maps result labelled Mechanical Block (AKGEC)", "coordinates_verified_against_map", "akgec-campus", GOOGLE.format(lat=28.6766311, lon=77.5016766)),
    ("EN/EC Block", "en-ec-block", "building", None, None, "AKGEC official academic complex tour", "name_verified", "akgec-campus", OFFICIAL_TOUR),
    ("Computer Center", "computer-center", "facility", None, None, "AKGEC official academic complex tour", "name_verified", "akgec-campus", OFFICIAL_TOUR),
    ("Lecture Theatre Complex", "lecture-theatre-complex", "building", None, None, "AKGEC official academic complex tour", "name_verified", "akgec-campus", OFFICIAL_TOUR),
    ("Seminar Halls", "seminar-halls", "facility", None, None, "AKGEC official academic complex tour", "name_verified", "akgec-campus", OFFICIAL_TOUR),
    ("Lecture Rooms & Tutorials", "lecture-rooms-tutorials", "facility", None, None, "AKGEC official academic complex tour", "name_verified", "akgec-campus", OFFICIAL_TOUR),
    ("MCA Block", "mca-block", "building", None, None, "AKGEC official academic complex tour; coordinates not established", "name_verified", "akgec-campus", OFFICIAL_TOUR),
    # The official library page places the Central Library in the Administrative Block.
    ("Administrative Block - Ground Floor", "administrative-block-ground-floor", "floor", None, None, "AKGEC Central Library geotagged photo caption", "name_verified", "administrative-block", LIBRARY_SOURCE),
    ("Central Library", "central-library", "facility", 28.676704, 77.500788, "AKGEC GPS-tagged library gate photo dated 2021-12-30 (Administrative Block, Ground Floor); gate point, not building centroid", "official_geotagged_point", "administrative-block-ground-floor", GOOGLE.format(lat=28.676704, lon=77.500788)),
    ("Central Library Reading Hall", "central-library-reading-hall", "facility", None, None, "AKGEC Central Library page", "name_verified", "central-library", LIBRARY_SOURCE),
    ("Central Library Digital Library", "central-library-digital", "facility", None, None, "AKGEC Central Library page", "name_verified", "central-library", LIBRARY_SOURCE),
    ("Central Library Reference Section", "central-library-reference", "facility", None, None, "AKGEC Central Library page", "name_verified", "central-library", LIBRARY_SOURCE),
    ("Departmental Libraries", "departmental-libraries", "facility", None, None, "AKGEC Library sources list departmental libraries; individual entries are catalogued where their geotagged location is published", "name_verified", "akgec-campus", "https://www.akgec.ac.in/about/infrastructure-visual-tour/library/"),
    ("Hostel Libraries (5)", "hostel-libraries", "facility", None, None, "AKGEC Central Library page identifies five hostel libraries; individual locations not published here", "name_verified", "akgec-campus", LIBRARY_SOURCE),
    ("Advanced IT Lab-1", "advanced-it-lab-1", "facility", None, None, "AKGEC IT Laboratories page; labs identified in CSE/IT Block", "name_verified", "cs-it-block", IT_LABS_SOURCE),
    ("Advanced IT Lab-2", "advanced-it-lab-2", "facility", None, None, "AKGEC IT Laboratories page; labs identified in CSE/IT Block", "name_verified", "cs-it-block", IT_LABS_SOURCE),
    ("Web Technology Lab", "web-technology-lab", "facility", None, None, "AKGEC IT Laboratories page; labs identified in CSE/IT Block", "name_verified", "cs-it-block", IT_LABS_SOURCE),
    ("Basic IT Lab", "basic-it-lab", "facility", None, None, "AKGEC IT Laboratories page; labs identified in CSE/IT Block", "name_verified", "cs-it-block", IT_LABS_SOURCE),
    ("IT Project Lab", "it-project-lab", "facility", None, None, "AKGEC IT Laboratories page; labs identified in CSE/IT Block", "name_verified", "cs-it-block", IT_LABS_SOURCE),
    ("IT Lab 6", "it-lab-6", "facility", None, None, "AKGEC IT Laboratories page; labs identified in CSE/IT Block", "name_verified", "cs-it-block", IT_LABS_SOURCE),
    ("IT Lab 7", "it-lab-7", "facility", None, None, "AKGEC IT Laboratories page; labs identified in CSE/IT Block", "name_verified", "cs-it-block", IT_LABS_SOURCE),
    ("MCA Problem Solving using C Lab", "mca-problem-solving-c-lab", "facility", None, None, "AKGEC MCA department laboratories page; specific campus building not established", "name_verified", "akgec-campus", MCA_SOURCE),
    ("MCA Object Oriented Programming Lab", "mca-oop-lab", "facility", None, None, "AKGEC MCA department laboratories page; specific campus building not established", "name_verified", "akgec-campus", MCA_SOURCE),
    ("MCA DBMS Lab", "mca-dbms-lab", "facility", None, None, "AKGEC MCA department laboratories page; specific campus building not established", "name_verified", "akgec-campus", MCA_SOURCE),
    ("MCA Data Structures Lab", "mca-data-structures-lab", "facility", None, None, "AKGEC MCA department laboratories page; specific campus building not established", "name_verified", "akgec-campus", MCA_SOURCE),
    ("MCA Artificial Intelligence Lab", "mca-ai-lab", "facility", None, None, "AKGEC MCA department laboratories page; specific campus building not established", "name_verified", "akgec-campus", MCA_SOURCE),
    ("MCA Software Engineering Lab", "mca-software-engineering-lab", "facility", None, None, "AKGEC MCA department laboratories page; specific campus building not established", "name_verified", "akgec-campus", MCA_SOURCE),
    ("MCA Project Lab", "mca-project-lab", "facility", None, None, "AKGEC MCA department laboratories page; specific campus building not established", "name_verified", "akgec-campus", MCA_SOURCE),
    ("MCA Computer Organization Lab", "mca-computer-organization-lab", "facility", None, None, "AKGEC MCA department laboratories page; specific campus building not established", "name_verified", "akgec-campus", MCA_SOURCE),
    ("CS/IT Block - 3rd Floor", "cs-it-third-floor", "floor", None, None, "AKGEC geotagged CSE and IT laboratory photographs", "name_verified", "cs-it-block", CSE_GEOTAG_SOURCE),
    ("CS/IT Block - 4th Floor", "cs-it-fourth-floor", "floor", None, None, "AKGEC geotagged departmental library photographs", "name_verified", "cs-it-block", DEPARTMENTAL_LIBRARY_SOURCE),
    ("CS/IT Block - 5th Floor", "cs-it-fifth-floor", "floor", None, None, "AKGEC geotagged IT laboratories and departmental library photographs", "name_verified", "cs-it-block", IT_GEOTAG_SOURCE),
    ("Back Block - 1st Floor", "back-block-first-floor", "floor", None, None, "AKGEC geotagged library and ECE laboratory photographs", "name_verified", "back-block", ELECTRONICS_GEOTAG_SOURCE),
    ("Back Block - 2nd Floor", "back-block-second-floor", "floor", None, None, "AKGEC geotagged library and ECE laboratory photographs", "name_verified", "back-block", ELECTRONICS_GEOTAG_SOURCE),
    ("Mechanical Block - Ground Floor", "mechanical-block-ground-floor", "floor", None, None, "AKGEC geotagged Civil CAD and Fluid Mechanics laboratory photographs", "name_verified", "mechanical-block", CIVIL_GEOTAG_SOURCE),
    ("MCA Block - 2nd Floor", "mca-block-second-floor", "floor", None, None, "AKGEC geotagged departmental library photograph", "name_verified", "mca-block", DEPARTMENTAL_LIBRARY_SOURCE),
    ("Departmental Library (CSE)", "department-library-cse", "facility", None, None, "AKGEC geotagged photo: CS/IT Block, 4th Floor", "name_verified", "cs-it-fourth-floor", DEPARTMENTAL_LIBRARY_SOURCE),
    ("Departmental Library (IT)", "department-library-it", "facility", None, None, "AKGEC geotagged photo: CS/IT Block, 5th Floor", "name_verified", "cs-it-fifth-floor", DEPARTMENTAL_LIBRARY_SOURCE),
    ("Departmental Library (Civil Engineering)", "department-library-civil", "facility", None, None, "AKGEC geotagged photo: CS/IT Block, 5th Floor", "name_verified", "cs-it-fifth-floor", DEPARTMENTAL_LIBRARY_SOURCE),
    ("Departmental Library (ECE)", "department-library-ece", "facility", None, None, "AKGEC geotagged photo: Back Block, 1st Floor", "name_verified", "back-block-first-floor", DEPARTMENTAL_LIBRARY_SOURCE),
    ("Departmental Library (EEE)", "department-library-eee", "facility", None, None, "AKGEC geotagged photo: Back Block, 2nd Floor", "name_verified", "back-block-second-floor", DEPARTMENTAL_LIBRARY_SOURCE),
    ("Departmental Library (Mechanical Engineering)", "department-library-mechanical", "facility", None, None, "AKGEC geotagged photo: MCA Block, 2nd Floor", "name_verified", "mca-block-second-floor", DEPARTMENTAL_LIBRARY_SOURCE),
    ("CSE Lab 1", "cse-lab-1", "facility", None, None, "AKGEC geotagged photo: CS/IT Block, 3rd Floor", "name_verified", "cs-it-third-floor", CSE_GEOTAG_SOURCE),
    ("CSE Lab 2", "cse-lab-2", "facility", None, None, "AKGEC geotagged photo: CS/IT Block, 3rd Floor", "name_verified", "cs-it-third-floor", CSE_GEOTAG_SOURCE),
    ("CSE Lab 3", "cse-lab-3", "facility", None, None, "AKGEC geotagged photo: CS/IT Block, 3rd Floor", "name_verified", "cs-it-third-floor", CSE_GEOTAG_SOURCE),
    ("CSE Lab 4", "cse-lab-4", "facility", None, None, "AKGEC geotagged photo: CS/IT Block, 3rd Floor", "name_verified", "cs-it-third-floor", CSE_GEOTAG_SOURCE),
    ("CSE Lab 5", "cse-lab-5", "facility", None, None, "AKGEC geotagged photo: CS/IT Block, 3rd Floor", "name_verified", "cs-it-third-floor", CSE_GEOTAG_SOURCE),
    ("CSE Lab 6", "cse-lab-6", "facility", None, None, "AKGEC geotagged photo: CS/IT Block, 3rd Floor", "name_verified", "cs-it-third-floor", CSE_GEOTAG_SOURCE),
    ("CSE Lab 7", "cse-lab-7", "facility", None, None, "AKGEC geotagged photo: CS/IT Block, 3rd Floor", "name_verified", "cs-it-third-floor", CSE_GEOTAG_SOURCE),
    ("CSE Project Lab", "cse-project-lab", "facility", None, None, "AKGEC geotagged photo: CS/IT Block, 3rd Floor", "name_verified", "cs-it-third-floor", CSE_GEOTAG_SOURCE),
    ("CSE R&D Lab", "cse-r-and-d-lab", "facility", None, None, "AKGEC geotagged photo: CS/IT Block, 3rd Floor", "name_verified", "cs-it-third-floor", CSE_GEOTAG_SOURCE),
    ("IT DBMS Lab", "it-dbms-lab", "facility", None, None, "AKGEC geotagged photo: CS/IT Block, 3rd Floor", "name_verified", "cs-it-third-floor", IT_GEOTAG_SOURCE),
    ("IT Software Engineering Lab", "it-software-engineering-lab", "facility", None, None, "AKGEC geotagged photo: CS/IT Block, 3rd Floor", "name_verified", "cs-it-third-floor", IT_GEOTAG_SOURCE),
    ("IT Computer Network Lab", "it-computer-network-lab", "facility", None, None, "AKGEC geotagged photo: CS/IT Block, 3rd Floor", "name_verified", "cs-it-third-floor", IT_GEOTAG_SOURCE),
    ("IT DAA Lab", "it-daa-lab", "facility", None, None, "AKGEC geotagged photo: CS/IT Block, 3rd Floor", "name_verified", "cs-it-third-floor", IT_GEOTAG_SOURCE),
    ("IT PPS Lab", "it-pps-lab", "facility", None, None, "AKGEC geotagged photo: CS/IT Block, 3rd Floor", "name_verified", "cs-it-third-floor", IT_GEOTAG_SOURCE),
    ("IT Mini Project Lab", "it-mini-project-lab", "facility", None, None, "AKGEC geotagged photo: CS/IT Block, 3rd Floor", "name_verified", "cs-it-third-floor", IT_GEOTAG_SOURCE),
    ("IT Web Designing Lab", "it-web-designing-lab", "facility", None, None, "AKGEC geotagged photo: CS/IT Block, 3rd Floor", "name_verified", "cs-it-third-floor", IT_GEOTAG_SOURCE),
    ("IT Data Analytics Lab", "it-data-analytics-lab", "facility", None, None, "AKGEC geotagged photo: CS/IT Block, 5th Floor", "name_verified", "cs-it-fifth-floor", IT_GEOTAG_SOURCE),
    ("IT Data Structure Lab", "it-data-structure-lab", "facility", None, None, "AKGEC geotagged photo: CS/IT Block, 5th Floor", "name_verified", "cs-it-fifth-floor", IT_GEOTAG_SOURCE),
    ("IT Advanced Programming Lab", "it-advanced-programming-lab", "facility", None, None, "AKGEC geotagged photo: CS/IT Block, 5th Floor", "name_verified", "cs-it-fifth-floor", IT_GEOTAG_SOURCE),
    ("IT Discrete Structure Lab", "it-discrete-structure-lab", "facility", None, None, "AKGEC geotagged photo: CS/IT Block, 5th Floor", "name_verified", "cs-it-fifth-floor", IT_GEOTAG_SOURCE),
    ("Civil CAD Lab", "civil-cad-lab", "facility", None, None, "AKGEC geotagged photo: Mechanical Block, Ground Floor", "name_verified", "mechanical-block-ground-floor", CIVIL_GEOTAG_SOURCE),
    ("Fluid Mechanics Lab", "fluid-mechanics-lab", "facility", None, None, "AKGEC geotagged photo: Mechanical Block, Ground Floor", "name_verified", "mechanical-block-ground-floor", CIVIL_GEOTAG_SOURCE),
    ("Civil Hydraulic Machines Lab", "civil-hydraulic-machines-lab", "facility", None, None, "AKGEC geotagged photo: CS/IT Block, 5th Floor", "name_verified", "cs-it-fifth-floor", CIVIL_GEOTAG_SOURCE),
    ("Civil Building Materials Lab", "civil-building-materials-lab", "facility", None, None, "AKGEC geotagged photo: CS/IT Block, 5th Floor", "name_verified", "cs-it-fifth-floor", CIVIL_GEOTAG_SOURCE),
    ("Civil Concrete Lab", "civil-concrete-lab", "facility", None, None, "AKGEC geotagged photo: CS/IT Block, 5th Floor", "name_verified", "cs-it-fifth-floor", CIVIL_GEOTAG_SOURCE),
    ("Civil Environmental Engineering Lab", "civil-environmental-lab", "facility", None, None, "AKGEC geotagged photo: CS/IT Block, 5th Floor", "name_verified", "cs-it-fifth-floor", CIVIL_GEOTAG_SOURCE),
    ("Civil Geo-Informatics Lab", "civil-geo-informatics-lab", "facility", None, None, "AKGEC geotagged photo: CS/IT Block, 5th Floor", "name_verified", "cs-it-fifth-floor", CIVIL_GEOTAG_SOURCE),
    ("Civil Geotechnical Lab", "civil-geotechnical-lab", "facility", None, None, "AKGEC geotagged photo: CS/IT Block, 5th Floor", "name_verified", "cs-it-fifth-floor", CIVIL_GEOTAG_SOURCE),
    ("Civil Structural Analysis Lab", "civil-structural-analysis-lab", "facility", None, None, "AKGEC geotagged photo: CS/IT Block, 5th Floor", "name_verified", "cs-it-fifth-floor", CIVIL_GEOTAG_SOURCE),
    ("Civil Survey Lab", "civil-survey-lab", "facility", None, None, "AKGEC geotagged photo: CS/IT Block, 5th Floor", "name_verified", "cs-it-fifth-floor", CIVIL_GEOTAG_SOURCE),
    ("Civil Transportation Lab", "civil-transportation-lab", "facility", None, None, "AKGEC geotagged photo: CS/IT Block, 5th Floor", "name_verified", "cs-it-fifth-floor", CIVIL_GEOTAG_SOURCE),
    ("ECE Analog Circuits Lab", "ece-analog-circuits-lab", "facility", None, None, "AKGEC geotagged photo: Back Block, 1st Floor", "name_verified", "back-block-first-floor", ELECTRONICS_GEOTAG_SOURCE),
    ("ECE Communication Engineering Lab", "ece-communication-lab", "facility", None, None, "AKGEC geotagged photo: Back Block, 1st Floor", "name_verified", "back-block-first-floor", ELECTRONICS_GEOTAG_SOURCE),
    ("ECE Digital Communication Lab", "ece-digital-communication-lab", "facility", None, None, "AKGEC geotagged photo: Back Block, 1st Floor", "name_verified", "back-block-first-floor", ELECTRONICS_GEOTAG_SOURCE),
    ("ECE Digital Signal Processing Lab", "ece-dsp-lab", "facility", None, None, "AKGEC geotagged photo: Back Block, 1st Floor", "name_verified", "back-block-first-floor", ELECTRONICS_GEOTAG_SOURCE),
    ("ECE Antenna and Microwave Lab", "ece-antenna-microwave-lab", "facility", None, None, "AKGEC geotagged photo: Back Block, 1st Floor", "name_verified", "back-block-first-floor", ELECTRONICS_GEOTAG_SOURCE),
    ("ECE Project Lab", "ece-project-lab", "facility", None, None, "AKGEC geotagged photo: Back Block, 2nd Floor", "name_verified", "back-block-second-floor", ELECTRONICS_GEOTAG_SOURCE),
    ("ECE Microcontrollers Lab", "ece-microcontrollers-lab", "facility", None, None, "AKGEC geotagged photo: Back Block, 2nd Floor", "name_verified", "back-block-second-floor", ELECTRONICS_GEOTAG_SOURCE),
    ("ECE Electronic Circuit Design Lab", "ece-circuit-design-lab", "facility", None, None, "AKGEC geotagged photo: Back Block, 2nd Floor", "name_verified", "back-block-second-floor", ELECTRONICS_GEOTAG_SOURCE),
]


def seed_catalog(conn):
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    conn.executemany(
        "INSERT OR IGNORE INTO academic_departments (department_id, display_name, source_url) VALUES (?,?,?)",
        [(d.casefold().replace(" ", "-"), d, "https://www.akgec.ac.in/departments/") for d in DEPARTMENTS],
    )
    ids = {r["canonical_name"]: r["location_id"] for r in conn.execute("SELECT location_id, canonical_name FROM campus_locations")}
    for name, canonical, kind, lat, lon, source, confidence, parent, url in LOCATIONS:
        parent_id = ids.get(parent) if parent else None
        maps_url = url if "google.com/maps" in url else None
        source_url = LIBRARY_GEOTAG_SOURCE if canonical == "central-library" else (None if maps_url else url)
        conn.execute(
            """INSERT INTO campus_locations
               (location_id,display_name,canonical_name,location_type,latitude,longitude,parent_location_id,
                coordinate_source,verification_status,last_verified_at,google_maps_url,source_url,created_at,updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(location_id) DO UPDATE SET display_name=excluded.display_name,
                 canonical_name=excluded.canonical_name, location_type=excluded.location_type,
                 latitude=excluded.latitude, longitude=excluded.longitude, parent_location_id=excluded.parent_location_id,
                 coordinate_source=excluded.coordinate_source, verification_status=excluded.verification_status,
                 last_verified_at=excluded.last_verified_at, google_maps_url=excluded.google_maps_url,
                 source_url=excluded.source_url, updated_at=excluded.updated_at
               WHERE campus_locations.display_name IS NOT excluded.display_name
                  OR campus_locations.canonical_name IS NOT excluded.canonical_name
                  OR campus_locations.location_type IS NOT excluded.location_type
                  OR campus_locations.latitude IS NOT excluded.latitude
                  OR campus_locations.longitude IS NOT excluded.longitude
                  OR campus_locations.parent_location_id IS NOT excluded.parent_location_id
                  OR campus_locations.coordinate_source IS NOT excluded.coordinate_source
                  OR campus_locations.verification_status IS NOT excluded.verification_status
                  OR campus_locations.last_verified_at IS NOT excluded.last_verified_at
                  OR campus_locations.google_maps_url IS NOT excluded.google_maps_url
                  OR campus_locations.source_url IS NOT excluded.source_url""",
            (canonical, name, canonical, kind, lat, lon, parent_id, source, confidence, VERIFIED_AT, maps_url, source_url, now, now),
        )
        ids[canonical] = canonical
    # Keep configured legacy choices searchable and selectable, but do not invent coordinates.
    from config import get_settings
    for name in get_settings().campus_locations:
        canonical = "legacy-" + "-".join(name.casefold().split())
        conn.execute(
            "INSERT OR IGNORE INTO campus_locations (location_id,display_name,canonical_name,location_type,coordinate_source,verification_status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?)",
            (canonical, name, canonical, "building", "Existing ResolveAI location setting", "unverified", now, now),
        )
    aliases = [(alias, canonical) for alias, canonical in DEPARTMENT_ALIASES.items()]
    conn.executemany(
        "INSERT OR IGNORE INTO academic_department_aliases (alias, department_id) VALUES (?,?)",
        [(a.casefold(), d.casefold().replace(" ", "-")) for a, d in aliases],
    )
