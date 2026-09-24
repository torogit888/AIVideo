# 口語語氣風格庫 (Assets Tones)

此資料夾存放**說書人口吻與語氣風格範本**。

在生成新故事或腳本時，只要指定範本檔名（例如 `tech_business_deepdive` 或 `michelin_curious`），系統就會自動讀取該範本的**參考口白**與**句式特徵**，模仿其語氣、頓挫與用詞風格來撰寫新腳本。

---

## 現有口吻風格範本清單

| 範本檔名 | 範本名稱 | 適用片長與題材 | 風格關鍵字 |
|----------|----------|----------------|------------|
| `tech_business_deepdive.md` | **硬核科技商業傳奇風 (杜比模式)** | 5～15 分鐘中長視頻（科技商戰、發明家傳奇、商業帝國） | 暴利過路費懸念開場、降維比喻（賣奶油不賣蛋糕）、先揚後抑、好萊塢名場面、商業閉環教科書、純粹執念致敬 |
| `michelin_curious.md` | **商業科普反轉風 (米其林模式)** | 1～3 分鐘短視頻（奇葩行銷、反常識冷知識、驚人真相） | 黃金 8 秒認知衝突設問、生活化形象比喻、質疑反詰、乾脆反轉（錯了！） |
| `suspense_noir.md` | **都市懸疑探案風** | 3～8 分鐘（未解懸案、都市怪談、歷史迷霧） | 雨夜冷感細節切入、看似平靜下的暗湧、抽絲剝繭、懸念留白 |
| `warm_narrative.md` | **溫馨療癒說書風** | 3～5 分鐘（人物故事、生活哲思、匠人精神） | 日常共鳴發問、反匆忙的溫柔對比、老朋友娓娓道來、療癒收束金句 |

---

## ⚡ Vertex AI Gemini Flash 智慧萃取建立（推薦）

專案支援直接輸入參考文字檔或逐字稿，由 Google Cloud Vertex AI (Gemini 2.5 Flash) 自動提煉五大欄位並直接寫入本目錄：

### 1. 透過 Studio 前端介面（Web UI）
- 開啟 Studio 前端（Port 5173）的「素材庫與風格資源」->「說書人口吻」。
- 點擊「新增口吻範本」，預設進入「✨ Vertex AI 智慧萃取直接寫入」面板。
- 點擊「上傳文字檔 (.txt / .md)」或貼上文本，點擊「由 Vertex AI Gemini Flash 萃取並直接寫入專案」，系統將自動分析並直接儲存入 `assets/tones/<id>.md`。

### 2. 透過終端 CLI 指令
```bash
# 從現有文字檔直接萃取寫入
docker compose run --rm pipeline python -m aivideo tones --import-file sample.txt

# 指定口吻 ID（選填）
docker compose run --rm pipeline python -m aivideo tones --import-file sample.txt --id my_custom_tone
```

---

## 範本檔案結構（Markdown + YAML Frontmatter）

每個範本推薦採用 `.md` 格式，開頭使用 YAML Frontmatter 記錄基本設定，正文放參考口白與特色：

```markdown
---
id: 範本唯一識別碼（如 michelin_curious）
name: 顯示名稱（如 商業科普反轉風）
tags: [科普, 商業, 懸念, 幽默]
recommended_voice_instruct: "女，青年，中音调"
description: 適合科技秘辛、冷知識、商業歷史傳奇等題材
---

## 參考口白範例
（直接在此貼上你喜歡的一段文字範本）

## 核心句式與語氣特徵
- 開場鉤子（Hook）：設問句「如果你今天想...你敢相信...居然是...嗎？」
- 驚嘆與反差：「沒錯！就是那個...」
- 質疑反詰：「這根本是...對吧？」
- 驚人反轉：「錯了！其實...」

## 標點與情緒標籤
- 善用全形逗號斷句
- 在無奈或沉思處加入 [sigh]
```

---

## 搭配的「4000字深度故事腳本生成指令」

當你要生成完整長篇故事時，使用以下指令模板：

```text
介紹【主題名稱】
需求 4000 字的中文介紹故事
盡可能地找更多參考資料
使用如下口語化風格：【指定風格代號，例如 tech_business_deepdive】
請以一句一句口白腳本的樣式生成
盡量不要有英文
標點符號只允許"，?!"
```
詳細說明見 `assets/prompts/story_generation_template.md`。
