import os
import shutil


def unpack_zips_from_dir(target_dir: str, extracted_dir: str):
    """unpack all zip files in target_dir to extract_dir"""
    zips = [
        os.path.join(target_dir, f)
        for f in os.listdir(target_dir)
        if f.endswith(".zip")
    ]

    os.mkdir(extracted_dir)

    [shutil.unpack_archive(zip_filename, extracted_dir) for zip_filename in zips]


def get_shapefiles_from_dir(target_dir: str) -> list:
    """return a list of shapefiles path from target dir"""
    return [
        os.path.join(target_dir, f)
        for f in os.listdir(target_dir)
        if f.endswith(".shp")
    ]
