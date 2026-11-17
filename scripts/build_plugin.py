"""QGISへインストールできるプラグインZIPを作成する。"""

import argparse
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


PLUGIN_DIRECTORY = "hazard_map_game_tool"
ROOT_FILES = (
    "__init__.py",
    "constants.py",
    "hmg_plugin.py",
    "maptool.py",
    "hmg_utils.py",
    "metadata.txt",
    "LICENSE",
    "README.md",
)
RUNTIME_DIRECTORIES = (
    "converter",
    "data",
    "imgs",
    "modules",
    "output",
    "scoring",
    "ui",
)
EXCLUDED_NAMES = {"__pycache__", ".DS_Store"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo"}


def _runtime_files(repository: Path):
    for relative_path in ROOT_FILES:
        path = repository / relative_path
        if not path.is_file():
            raise FileNotFoundError(f"パッケージに必要なファイルがありません: {path}")
        yield path

    for directory_name in RUNTIME_DIRECTORIES:
        directory = repository / directory_name
        if not directory.is_dir():
            raise FileNotFoundError(
                f"パッケージに必要なフォルダーがありません: {directory}"
            )
        for path in sorted(directory.rglob("*")):
            if not path.is_file():
                continue
            if any(part in EXCLUDED_NAMES for part in path.parts):
                continue
            if path.suffix in EXCLUDED_SUFFIXES:
                continue
            yield path


def build_plugin_zip(repository: Path, output: Path) -> Path:
    repository = repository.resolve()
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    with ZipFile(output, "w", compression=ZIP_DEFLATED, compresslevel=9) as archive:
        for path in _runtime_files(repository):
            relative_path = path.relative_to(repository)
            archive.write(path, Path(PLUGIN_DIRECTORY) / relative_path)
    return output


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", type=Path, default=Path(__file__).parents[1])
    parser.add_argument(
        "--output", type=Path, default=Path("dist/HazardMapGame_tool.zip")
    )
    args = parser.parse_args()
    output = build_plugin_zip(args.repository, args.output)
    print(output)


if __name__ == "__main__":
    main()
