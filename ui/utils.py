import os
import zipfile
import glob


def unpack_zips_from_dir(target_dir: str, extracted_dir: str):
    """unpack all zip files in target_dir to extract_dir"""
    zips = [
        os.path.join(target_dir, f)
        for f in os.listdir(target_dir)
        if f.endswith(".zip")
    ]

    os.mkdir(extracted_dir)

    for zip_filename in zips:
        with zipfile.ZipFile(zip_filename, "r") as zip_ref:
            zip_ref.extractall(extracted_dir)


def get_shapefiles_from_dir(target_dir: str) -> list:
    """return a list of shapefiles path from target dir
    subfolders included"""
    shapefiles = []
    for root, dirs, files in os.walk(target_dir):
        shp_files = glob.glob(os.path.join(root, "*.shp"))
        shapefiles.extend(shp_files)
    return shapefiles
