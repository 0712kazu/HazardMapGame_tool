import glob
import os
import zipfile


def unpack_zips_from_dir(target_dir: str, extracted_dir: str):
    """unpack all zip files in target_dir to extract_dir"""
    zips = [
        os.path.join(target_dir, f)
        for f in os.listdir(target_dir)
        if f.endswith(".zip")
    ]

    os.mkdir(extracted_dir)

    for zip_filename in zips:
        extract_sjis_zip(zip_filename, extracted_dir)


def get_shapefiles_from_dir(target_dir: str) -> list:
    """return a list of shapefiles path from target dir
    subfolders included"""
    shapefiles = []
    for root, dirs, files in os.walk(target_dir):
        shp_files = glob.glob(os.path.join(root, "*.shp"))
        shapefiles.extend(shp_files)
    return shapefiles


def extract_sjis_zip(src_zip: str, dest: str) -> None:
    """SJIS の zip ファイルをファイル名の文字化けを避けて展開する"""
    with zipfile.ZipFile(src_zip) as zfile:
        for info in zfile.infolist():
            _rename(info)
            zfile.extract(info, dest)


def list_sjis_zip(src_zip: str):
    """SJIS の zip ファイルの中身をファイル名の文字化けを避けてリストアップする"""
    info_all = []
    with zipfile.ZipFile(src_zip) as zfile:
        for info in zfile.infolist():
            _rename(info)
            info_all.append(info)
    return info_all


def _rename(info: zipfile.ZipInfo) -> None:
    """ヘルパー: `ZipInfo` の中身をデコードし直す"""
    LANG_ENC_FLAG = 0x800
    encoding = "utf-8" if info.flag_bits & LANG_ENC_FLAG else "cp437"
    info.filename = info.filename.encode(encoding).decode("cp932")
