# 音色角色庫 (Assets Voices Library)

此資料夾存放所有可在專案中復用的**發音人角色與音色庫**。

每一個角色擁有一個獨立資料夾，資料夾名稱即為該音色的唯一識別碼（`voice_id`，例如 `narrator_zh_tw`、`narrator_male`）。在任何 Job 的 `job.yaml` 中，只要指定 `voice_id`，整部影片就會自動載入並使用該角色的專屬聲音！

---

## 一、音色角色資料夾結構

每個音色目錄下包含以下 3 個核心檔案：

```
assets/voices/{voice_id}/
  ├── voice.yaml        # 音色配置檔（模式、推論精度、速度等）
  ├── reference.wav     # 5～12 秒純人聲參考音檔（WAV 格式）
  └── reference.txt     # 與 reference.wav 100% 完全對齊的手寫逐字稿
```

---

## 二、參考音訊的 4 大黃金標準（克隆必備）

1. **時長 5～12 秒最佳**：
   - 約 15～30 個字為佳，過短特徵抓不滿，過長增加負擔與雜音。
2. **絕對「無背景音樂 (BGM)」、無回音**：
   - 背景必須極為安靜。若有背景音樂或電風扇雜音，模型會把雜音一起克隆進去。
3. **手寫 `reference.txt` 逐字稿**：
   - 音檔裡說了什麼字，`reference.txt` 就要一模一樣。
   - **重要好處**：提供逐字稿能讓系統直接跳過載入 Whisper 模型，保護顯存不 OOM（專為 RTX 2060 6GB 優化）！
4. **格式**：推薦 44.1kHz 或 24kHz、16-bit PCM WAV。

---

## 三、`voice.yaml` 設定範例

```yaml
id: narrator_male
display_name: 旁白・沉穩男聲
engine: omnivoice
model: OmniVoice-bf16
mode: clone             # 推薦 clone（聲音克隆模式，100% 維持音色一致）
dtype: fp16             # RTX 2060 請固定 fp16
attention: eager        # RTX 2060 請固定 eager
steps: 32               # 推論步數（32 品質最佳）
speed: 1.0              # 語速倍率
seed: 42                # 隨機種子
position_temperature: 0.1
class_temperature: 0.0
instruct: ""            # 克隆模式留空，保留原汁原味自然口音
```

---

## 四、如何在影片專案中使用？

打開你要製作的 Job 設定檔（例如 `jobs/20260916_roman_telescope/job.yaml`），指定：

```yaml
voice_id: narrator_male
```

接著執行 `aivideo tts`，整部影片的所有台詞就會立刻切換為該角色的音色！
