# Hazard Map Game QGIS plugin

[ハザードマップゲーム](https://directing-a-map.com/saigai-boueitai/)のデータを作成するためのQGISプラグインです。

- [Manual](https://github.com/0712kazu/HazardMapGame_tool/blob/main/doc/manual/maunal.md)
- [Spec](https://github.com/0712kazu/HazardMapGame_tool/blob/main/doc/spec/spec.md)

このプラグインは<a href="https://creativecommons.org/licenses/by-nc-sa/4.0/deed.ja">CC BY-NC-SA</a>のライセンスの下、自由に利用できます。

## 動作環境

- QGIS 3.44.15 LTR
- Windows 11 / macOS

QGIS 4.xへの対応は検証中です。

## インストール

1. GitHub Releasesから`HazardMapGame_tool.zip`をダウンロードする
2. QGISの「プラグイン」→「プラグインの管理とインストール」を開く
3. 「ZIPからインストール」でダウンロードしたZIPを選択する

ZIPを手動で展開する必要はありません。

## 開発用パッケージ作成

```bash
python3 scripts/build_plugin.py
```

`dist/HazardMapGame_tool.zip`が作成されます。ZIPにはQGIS実行時に必要なファイルだけが
含まれ、テスト、仕様書、開発設定は含まれません。

### Authors
- MIERUNE Inc.
- ディレクティングマップ　Directing a Map / product of Tokyo Cartographic Co., Ltd
