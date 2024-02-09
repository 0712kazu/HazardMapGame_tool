data_dir = "../data"

INPUT_DIR_TATUMAKI = "a30_tornado"
INPUT_DIR_KOZUI = "a31_flood"
INPUT_DIR_SEDIMENTS = "a33_sediments"
INPUT_DIR_TSUNAMI = "a40_tsunami"
INPUT_DIR_JISUBERI = "a46_landslip"
INPUT_DIR_SAIGAI = "a48_disaster"
INPUT_DIR_SURGE = "a49_storm_surge"
INPUT_DIR_EARTHQUAKE = "b01_earthquake"
INPUT_DIR_SLOPE = "g04_slope"
INPUT_DIR_REFUGE = "p20_refuge"
INPUT_DIR_TOCHIRIYOU = "l03_landuse"
INPUT_DIR_SHIKUCHOSON = "japan_cities"
OUTPUT_DIR = "seamless_gpkg"

SEAMLESS_FILE_TORNADO = "a30_tornado.gpkg"
SEAMLESS_FILE_FLOOD = "a31_flood.gpkg"
SEAMLESS_FILE_SEDIMENTS = "a33_sediments.gpkg"
SEAMLESS_FILE_TSUNAMI = "a40_tsunami.gpkg"
SEAMLESS_FILE_LANDSLIP = "a46_landslip.gpkg"
SEAMLESS_FILE_DISASTER = "a48_disaster.gpkg"
SEAMLESS_FILE_SURGE = "a49_storm_surge.gpkg"
SEAMLESS_FILE_EARTHQUAKE = "b01_earthquake.gpkg"
SEAMLESS_FILE_SLOPE = "g04_slope.gpkg"
SEAMLESS_FILE_REFUGE = "p20_refuge.gpkg"
SEAMLESS_FILE_LANDUSE = "l03_landuse.gpkg"
SEAMLESS_FILE_CITIES = "japan_cities.csv"

# risk score field names
# to be as 8 characters to fit to shapefiles with suffixes
field_tornado = "tornado"
field_kozui = "flood"
field_sediments = "sediment"
field_tsunami = "tsunami"
field_jisuberi = "landslip"
field_saigai = "disaster"
field_surge = "surge"
field_earthquake = "quake"
field_slope = "slope"
field_refuge = "refuge"

hazards_ui_names = [
    "tornado",
    "kozui",
    "sediments",
    "tsunami",
    "jisuberi",
    "saigai",
    "surge",
    "earthquake",
    "slope",
    "refuge",
    "custom",
]
MAP_MIN_VALUE = 0.001
