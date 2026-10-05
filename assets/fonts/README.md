# 字幕字型

成片 ASS 使用 Fontname `Noto Sans CJK TC`（FFmpeg / fontconfig 依系統字型查找）。

解析順序：

1. `assets/fonts/NotoSansTC-Regular.otf`
2. `assets/fonts/NotoSansCJKtc-Regular.otf`
3. 容器內 `fonts-noto-cjk` 常見路徑（例如 `/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc`）

新專案 `job.yaml` 的 `subtitle.font` 會寫入解析到的真實路徑。找不到檔案時仍用 `Noto Sans CJK TC` 這個字型名。

若要固定一份檔案，把 Noto Sans TC Regular 放到本目錄並命名為 `NotoSansTC-Regular.otf`。
