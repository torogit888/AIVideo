# AIVideo

AIVideo 是一個以 Docker + Dev Container + VS Code 為主的 AI 影片生成功能專案。

目前的核心流程是：

- 讀取中文腳本
- 解析場景
- 產生圖像（Google Gemini）
- 產生旁白語音（OmniVoice / ComfyUI）
- 生成字幕與影片

這個專案的設計原則是：

- 讓 Python 環境和專案邏輯放在 Dev Container
- 把 VS Code 擴充功能與個人設定放在主機的 User settings
- 保持 `.devcontainer/devcontainer.json` 較薄，避免把個人喜好硬編進 repo

## 先決條件

- Docker Desktop
- VS Code
- Dev Containers 擴充功能（安裝在主機，不要裝進容器）
- Git

## 開發方式

### 1. 先在主機安裝 dev-kit（只做一次）

如果你已經有 dev-kit，先安裝它的 User 設定與 Grok 規則：

```powershell
git clone https://github.com/<YOU>/dev-kit.git
cd dev-kit
& "C:\Program Files\Git\bin\bash.exe" .\install.sh
```

這會把以下設定寫到主機的 VS Code User `settings.json`：

- `dev.containers.defaultExtensions`
- Python / Black / isort / flake8 / pytest 設定
- Grok 規則寫入 `~/.grok/rules/guidance-only.md`

### 2. 開啟專案並重開容器

1. 用 VS Code 打開本專案
2. 啟動 Command Palette
3. 執行：`Dev Containers: Reopen in Container`

容器啟動後，VS Code 會根據主機的 User settings 自動把預設 extension 裝進容器。

如果是舊容器而且你剛更新了 extension 清單，請再執行：

- `Dev Containers: Rebuild Container`

## .devcontainer 設計

本專案的 `.devcontainer/devcontainer.json` 是「薄配置」：

- docker compose / service / workspace
- port forwarding
- Python interpreter 路徑
- 不放個人 extension 清單

這是故意的，因為 extension 是主機 VS Code 的個人設定，不應該被寫死在 repo 裡。

目前保留的設定：

```json
"python.defaultInterpreterPath": "/usr/local/bin/python"
```

## 專案啟動

在容器中安裝本專案：

```bash
pip install -e .
```

然後可檢查環境：

```bash
aivideo check
```

進階檢查：

```bash
aivideo check --gpu
aivideo check --gemini
```

## 環境變數

複製 `.env.example` 成 `.env` 後填入自己的值：

```bash
cp .env.example .env
```

AIVideo 支援兩種 Gemini 產圖方式：

### API key 模式（最簡單）

```env
GEMINI_API_KEY=your_key_here
GOOGLE_GENAI_USE_VERTEXAI=false
GEMINI_IMAGE_MODEL=gemini-3.1-flash-image
GEMINI_IMAGE_SIZE=1K
```

### Vertex AI 模式

```env
GOOGLE_GENAI_USE_VERTEXAI=true
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=us-central1
GEMINI_IMAGE_MODEL=gemini-2.5-flash-image-preview
GEMINI_IMAGE_SIZE=1K
```

此外也支援：

- `GOOGLE_CLOUD_REGION`
- `VERTEX_PROJECT_ID`
- `VERTEX_LOCATION`

這些值會被自動視為 Vertex AI 設定。

必要項目：

- `GEMINI_API_KEY` 或 Vertex AI 環境
- `COMFY_URL`
- `GEMINI_IMAGE_MODEL`
- `GEMINI_IMAGE_SIZE`

## 目錄結構

```text
AIVideo/
  .devcontainer/
    Dockerfile
    devcontainer.json
  aivideo/
    __init__.py
    __main__.py
    cli.py
    commands/
  assets/
  doc/
  jobs/
  .env.example
  docker-compose.yml
  pyproject.toml
  README.md
```

## 開發原則

- container 內不需要再 clone dev-kit
- container 內不需要再執行 `install.sh`
- extension 與個人化設定只在主機層處理一次
- 專案層只保留「這個 repo 特有的執行環境」設定

## 目前進度

本專案第一版已完成基本骨架與環境檢查，不再以容器內的重複安裝方式作為標準流程。
