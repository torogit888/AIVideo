# AIVideo 重構備忘

日期：2026-10-24。

---

## 重構執行進度追蹤

### ✅ 第一批（Batch 1）：建議先改的六件（已完成並通過 49 項後端測試 + 前端 `tsc && vite build`）

- [x] **1. 考據開關 (`use_pip`) 全站統一預設開啟 (`True`)**
  - 對齊 `aivideo/naming.py`（`DEFAULT_USE_PIP = True`、`job_use_pip`、`should_auto_pip`）、`aivideo/api/schemas.py`（`CreateJobRequest`、`JobSummary` 預設 `True`）、`aivideo/api/routes/jobs.py`（`_to_job_summary` 缺欄時預設 `True`）與 `web/src/components/StoryboardGrid.tsx`（勾選框預設與提示文字）。
  - 測試驗證：`tests/test_pipeline_and_cli.py::test_all_action_auto_pip_default`、`test_all_action_respects_job_pip_switch`、`test_schema_default_use_pip_on`、`tests/test_job_and_script.py::test_new_job_bundle_writes_use_pip_true`。
- [x] **2. 失敗只跳一次訊息（SSE 去重與啟動失敗停轉圈）**
  - `aivideo/pipeline_runner.py` 在合成或執行失敗時呼叫 `emit_notice` 遞增 `notice_seq`；`web/src/App.tsx` 的 SSE 監聽以 `lastShownErrorKey`（`${notice_seq}:${errText}`）去重，同一次失敗只跳一次 Toast。
  - `Topbar.tsx` 與 `StoryboardGrid.tsx` 呼叫 `api.runPipeline` 加上 `try / catch`，請求失敗時立即重置 `setPipelineRunning(false)`。
  - 測試驗證：`tests/test_pipeline_and_cli.py::test_pipeline_runner_emits_notice_seq_on_compose_failure`、`tests/test_studio_frontend_contracts.py::test_frontend_sse_dedup_and_inspector_tab_visibility`。
- [x] **3. 「圖做好幾張」全站共用同一套算法 (`is_scene_visual_ready`)**
  - 於 `aivideo/naming.py` 定義 `is_scene_visual_ready(scene_dir)` 與 `SPOTLIGHT_MODES = ("spotlight", "focus", "black_bg", "fullscreen", "broll")`，同時由 `jobs.py`（總覽進度）、`scenes.py`（分鏡頁狀態）、`pipeline_runner.py`（合成前缺圖檢查）與 `run_state.py` 共用。
  - 測試驗證：`tests/test_scenes_and_takes.py::test_scene_visual_ready_unified_across_overview_and_storyboard`。
- [x] **4. 成片過期 (`film_stale`) 自動偵測與醒目標示**
  - 於 `aivideo/naming.py` 新增 `is_film_stale(job_dir)`（比對 `compose/film.mp4` 與 `script.md`、各鏡 `scene.yaml`、`image.png`、`pip.*`、`speech.wav` 的修改時間），寫入 `JobProgress.film_stale`。
  - 頂列「預覽成片」大按鈕維持預覽功能並加上「已過期」醒目琥珀色徽章；專案下拉選單與總覽卡片同步顯示「已成片(過期)／已合成 (已過期)」。
  - 測試驗證：`tests/test_scenes_and_takes.py::test_film_stale_detection`。
- [x] **5. 換頁時把右側分鏡抽屜收起，且支援在「成片頁」點擊時間軸直接打開右側抽屜（不再每次切頁重讀影片）**
  - `web/src/store.ts` 的 `setTab` 於切換分頁時自動收起抽屜（`isInspectorOpen: false`），`web/src/App.tsx` 支援在 `storyboard` 與 `film` 分頁顯示 `<SceneInspector />`。
  - `web/src/components/FilmViewer.tsx` 移除每次切進成片頁都刷新 `Date.now()` 的行為，改以 `JobProgress.film_mtime` 與手動重載計數作為影片 URL 版本鍵；切離成片頁時僅自動暫停播放、保留觀看秒數，點擊下方時間軸時留在成片頁跳轉秒數並直接在右側滑出該鏡精修抽屜。
  - 測試驗證：`tests/test_scenes_and_takes.py::test_film_stale_detection`、`tests/test_studio_frontend_contracts.py::test_frontend_sse_dedup_and_inspector_tab_visibility`。
- [x] **6. 儲存口白選「僅更新口白」時，不重寫全片英文生圖 Prompt**
  - `web/src/components/ScriptEditor.tsx` 的 `handleSaveExisting` 在選「僅更新口白」時，僅於剛重新分析過視覺錨點（`anchorsReanalyzed === true`）才呼叫 `syncScenePrompts`，單純改口白絕不重刷全片英文 Prompt。
  - 測試驗證：`tests/test_studio_frontend_contracts.py::test_frontend_sse_dedup_and_inspector_tab_visibility`。

### ✅ 第二批（Batch 2）：防止資料靜默覆蓋與設定遺失（已完成並通過 49 項後端測試 + 前端 `tsc && vite build`）

- [x] **1. 建立專案時檢查同日同名資料夾是否已存在 (`resolve_unique_job_id`)**
  - 於 `aivideo/naming.py` 新增 `resolve_unique_job_id(jobs_dir, base_job_id)`，當 `20261024_story` 已存在時自動遞增為 `20261024_story_2`、`_3`，並在 `aivideo/api/routes/jobs.py` 的 `create_job` 啟用，徹底防止新台詞與舊專案鏡頭/圖音混在同一個資料夾。
  - 測試驗證：`tests/test_naming_and_spoken.py::test_resolve_unique_job_id_auto_suffix`。
- [x] **2. 右側抽屜「考據小卡大小 (`scale`) 與位置 (`position`)」調整後立即存檔**
  - `web/src/components/SceneInspector.tsx` 的 `handleQuickUpdatePip` 支援 `overrides?: { scale?: number; position?: string }`，切換「卡片大小比例」或「疊加位置」選單時立即呼叫 `patchScene` 寫入 `scene.yaml`。
  - 測試驗證：`tests/test_studio_frontend_contracts.py::test_frontend_pip_persistence_and_pacing_sync`。
- [x] **3. 規劃大綱與擴寫連動腳本頁的「目標字數滑桿 (`wordCount`)」**
  - `GenerateOutlineRequest` 新增 `word_count` 欄位；`aivideo/story_generator.py` 新增 `build_outline_target_spec(word_count)` 依字數除以 220 動態換算預估分鐘數與幕數，不再寫死 4000 字／12~15 分鐘；前端 `ScriptEditor.tsx` 呼叫 `api.generateOutline` 時帶入滑桿的 `wordCount`。
  - 測試驗證：`tests/test_job_and_script.py::test_generate_outline_accepts_word_count`。
- [x] **4. 建立專案時 `script.md` 直接寫入純口白，並保存 `visual_pacing`（切鏡節奏）至 `job.yaml`**
  - `create_job_bundle` 直接將純口白寫入 `script.md`（移除原本先寫入含 `畫面：／旁白：` 導演筆記再二次覆寫的過程）；`job_files.py` 的 `JOB_YAML_KEYS` 納入 `visual_pacing`，並在建立、更新、重切分鏡與前端載入專案時完整讀寫 `visual_pacing`，重新整理網頁不再跳回「標準」。
  - 測試驗證：`tests/test_job_and_script.py::test_create_job_bundle_writes_pure_script_and_visual_pacing`。

### ✅ 第三批（Batch 3）：介面狀態同步、片長算法與命名收斂（已完成並通過 49 項後端測試 + 前端 `tsc && vite build`）

- [x] **1. 燒錄字幕 (`burnSubtitles`) 寫入 `job.yaml`、視覺定裝彈窗 (`isContinuityOpen`) 與錨點更新 (`anchorsRevision`) 收進 `useStudioStore`**
  - 全面移除 `Topbar.tsx`、`StoryboardGrid.tsx`、`ScriptEditor.tsx`、`VisualContinuityModal.tsx` 中的 `window.dispatchEvent(new CustomEvent("aivideo:..."))` 廣播，改由 `useStudioStore` 單一狀態同步。
  - 後端 `JobSummary` 與 `UpdateJobRequest` 新增 `burn_subtitles`，勾選時直接寫回專案 `job.yaml`（`subtitle.mode: "hard" | "none"`），切換專案或重新整理自動還原。
  - 測試驗證：`tests/test_job_and_script.py::test_default_style_and_burn_subtitles_persistence`、`tests/test_studio_frontend_contracts.py::test_frontend_shared_store_and_duration_estimator`。
- [x] **2. 統一全站預估片長計算函式 (`estimateJobDuration`) + 修正建立專案預設畫風**
  - 於 `web/src/studioActions.ts` 新增 `estimateJobDuration` 與 `formatDurationClock`，由 `Topbar.tsx` 與 `StoryboardGrid.tsx` 共用，消除重複公式。
  - 將 `CreateJobRequest.style_id` 預設值由不存在的 `future_workplace` 修正為 `otomo_katsuhiro`。
  - 測試驗證：`tests/test_job_and_script.py::test_default_style_and_burn_subtitles_persistence`、`tests/test_studio_frontend_contracts.py::test_frontend_shared_store_and_duration_estimator`。
- [x] **3. 右側抽屜與外部生成進度即時同步 + 補齊考據影片 (`broll`) 模式選項**
  - `SceneInspector.tsx` 的 `useEffect` 加入 `liveImageUrl` 與 `livePipUrl` 監聽，外部卡片出圖或考據完成時抽屜自動刷新；「呈現方式」選單補齊 `<option value="broll">🎬 全螢幕考據影片 (B-Roll · 動態主畫面)</option>`。
  - 測試驗證：`tests/test_studio_frontend_contracts.py::test_frontend_shared_store_and_duration_estimator`。
- [x] **4. 頂列 `⋯` 下載選單未合成防呆**
  - 當 `!hasFilm` 時，頂列選單標示 `(未合成)` 並在點擊時攔截顯示提示 Toast，避免跳轉至 404 頁面。

### ✅ 第四批（Batch 4）：大型檔案拆分、結構精簡與測試分類語意化（已完成並通過 49 項後端測試 + 前端 `tsc && vite build`）

- [x] **1. 從 `web/src/App.tsx` 抽出「專案總覽」、「系統設定」與「全域確認對話框」為獨立元件**
  - 新增 `web/src/components/OverviewPanel.tsx`、`web/src/components/SettingsPanel.tsx` 與 `web/src/components/StudioConfirmModal.tsx`，將 `App.tsx` 由 800 餘行精簡至約 185 行（僅保留主版面導航、SSE 進度訂閱與 Toast 容器）。
  - `ConnectionLights.tsx` 新增 `noPoll` 模式供設定頁內嵌使用，避免與頂列同時啟動兩個 8 秒輪詢計時器；並將 Gemini 燈號說明精確標示為「憑證已設定／未設定」。
  - `store.ts` 的 `requestConfirm` / `requestPrompt` 於開啟新對話框前自動結算前一個未關閉的 Promise，並移除用說明文字關鍵字猜測危險按鈕的隱晦規則（僅依明確 `variant: "danger"` 判定）。
  - 測試驗證：`tests/test_studio_frontend_contracts.py::test_app_component_split_into_focused_panels`。
- [x] **2. 將畫風庫管理職責從 `aivideo/story_generator.py` 拆入 `aivideo/style_prompt.py`**
  - `DEFAULT_STYLE_PRESETS`、`load_style_presets`、`save_all_style_presets`、`save_style_preset`、`delete_style_preset`、`resolve_style`、`style_lock_instructions` 移入 `aivideo/style_prompt.py`，並於 `story_generator.py` 保留相容匯出。
  - 測試驗證：`tests/test_job_and_script.py::test_style_presets_extracted_to_style_prompt_module`。
- [x] **3. 清理 `aivideo/__pycache__/` 舊版殘檔與移除 CLI 未實作空殼指令**
  - 刪除殘留的 `aivideo/__pycache__/webui.cpython-37.pyc`。
  - 從 `aivideo/cli.py` 移除標註「尚未實作」的 `parse`、`run`、`regen` 空殼子命令。
  - 測試驗證：`tests/test_pipeline_and_cli.py::test_cli_has_lock_unlock_select_gc_and_no_unimplemented_stubs`。
- [x] **4. 測試檔案依功能領域語意化分類（移除 `test_p0.py`～`test_p3.py` 階段代號）**
  - 拆分為 `tests/test_naming_and_spoken.py`、`tests/test_job_and_script.py`、`tests/test_scenes_and_takes.py`、`tests/test_pipeline_and_cli.py`、`tests/test_studio_frontend_contracts.py` 共 5 個具明確領域名稱之測試檔。

### ✅ 第五批（Batch 5）：全面複查與遺留細節收尾（已完成並通過 57 項後端測試 + 前端 `tsc && vite build`）

- [x] **1. 移除未使用的 `metaphor_style` 與 `lines_per_scene` 遺留欄位**
  - 從 `aivideo/api/schemas.py`（`JobSummary`、`CreateJobRequest`、`UpdateJobRequest`、`RecutJobRequest`）、`aivideo/api/routes/jobs.py`、`aivideo/story_generator.py`（`parse_script_lines_to_scenes`、`create_job_bundle`）、`web/src/types.ts`、`web/src/api.ts` 全面移除從未於介面與生圖邏輯中實際使用的 `metaphor_style` 與 `lines_per_scene`，切鏡統一只保留 `visual_pacing`（快／標準／慢）。
  - 測試驗證：`tests/test_job_and_script.py::test_removed_unused_fields_and_slimmed_job_yaml`。
- [x] **2. 瘦身 `job.yaml` 重複欄位（移除 `image.model_final`、`style_prefix`、`style_negative`）與統一後端生圖模型預設回退值**
  - `aivideo/job_files.py` 的 `JOB_YAML_KEYS` 與 `slim_job_yaml` 移除重複的 `style_prefix`、`style_negative` 與 `image.model_final`，建案與更新時只寫入 `image.model` 與 `image.style`。
  - `aivideo/gemini_image.py` 的 `MODEL_CANDIDATES` 首選、`generate_image()` 預設回退與 `create_job_bundle` 預設生圖模型統一對齊為 `DEFAULT_IMAGE_MODEL`（`gemini-3.1-flash-image`）。
  - 測試驗證：`tests/test_job_and_script.py::test_removed_unused_fields_and_slimmed_job_yaml`。
- [x] **3. 對齊備用畫風清單 `DEFAULT_STYLE_PRESETS` 與 `assets/styles.yaml`，並隱藏腳本頁畫風名稱旁的內部代號**
  - `aivideo/style_prompt.py` 的 `DEFAULT_STYLE_PRESETS` 改與 `assets/styles.yaml` 收錄的畫風完全對齊（`otomo_katsuhiro`、`japanese_anime`、`studio_ghibli`、`kyoto_animation`、`ufotable`）。
  - `web/src/components/ScriptEditor.tsx` 移除畫風名稱旁多餘的 `({currentStyleObj.id})` 內部代號顯示。
  - 測試驗證：`tests/test_job_and_script.py::test_style_presets_extracted_to_style_prompt_module`、`tests/test_studio_frontend_contracts.py::test_shared_delete_job_and_backend_hygiene`。
- [x] **4. 統一腳本生成 API 大綱參數名為 `outline`、配音檔名只認 `speech.wav`、收斂 `deleteJob` 重複邏輯、修正單幕考據重複觸發與 CORS 設定**
  - `GenerateScriptRequest`、`generate_story_script` 與 `web/src/api.ts` 統一使用 `outline` 傳遞故事大綱（後端保留 `notes` 向下相容）。
  - `aivideo/naming.py`、`aivideo/api/routes/jobs.py`、`aivideo/api/routes/scenes.py` 移除殘留的 `audio.wav`，全站統一只認 `speech.wav`。
  - `web/src/store.ts` 新增共用的 `deleteJob(jobId, jobTitle)` 方法，消除 `Topbar.tsx` 與 `OverviewPanel.tsx` 的重複刪除邏輯。
  - `aivideo/pipeline_runner.py` 在 `mode == "all"` 加入 `pip_attempted` 與 `pip.mp4` 判斷，避免同一幕於前置考據階段嘗試後又在後置小卡階段重複檢索。
  - `assets/voices/tw_female01/voice.yaml` 與 `hk_male01/voice.yaml` 補上中文顯示名稱（`台灣女聲 01`、`香港男聲 01`），並將 `aivideo/api/app.py` 的 `CORSMiddleware` 修正為 `allow_credentials=False`。
  - 測試驗證：`tests/test_studio_frontend_contracts.py::test_shared_delete_job_and_backend_hygiene`、`tests/test_pipeline_and_cli.py::test_all_mode_respects_scene_pip_switch`。
- [x] **5. YouTube 上傳完成即時更新總覽卡片狀態，並將上傳進度條移至底部發布按鈕正上方**
  - `web/src/components/YouTubeUploadModal.tsx` 於上傳完成、更新現有影片完成時立即呼叫 `useStudioStore` 的 `loadJobs()` 與 `showToast`，且背景上傳中關閉彈窗不中斷輪詢；`OverviewPanel.tsx` 掛載時亦同步呼叫 `loadJobs()`，確保總覽卡片上的「YouTube 已發布 / 已上架」狀態即時更新。
  - 將 `YouTubeUploadModal.tsx` 中的上傳進度條與上傳錯誤提示由彈窗頂端移至底部「關閉 / 立即發布至 YouTube」按鈕列正上方，點擊發布時視線正前方即可直接查看進度百分比。
  - 測試驗證：`tests/test_studio_frontend_contracts.py::test_youtube_modal_refreshes_overview_and_places_progress_above_submit`。

### 📋 後續可選進階拆分（視需要再分批進行）

- [ ] 進一步細分 `web/src/components/ScriptEditor.tsx`、`SceneInspector.tsx`、`AssetsView.tsx` 子區塊元件。

---

先講結論：很多地方不是「壞掉不能用」，而是**同一個事實有兩份算法、兩個名字**。畫面說一套，實際跑起來是另一套。先把這幾件對齊，再來精簡文字和拆大檔。

第 6 節是命名。第 7 節把整條流程再對過一次：寫稿、建專案、出圖、考據、合成、檔案裡那些看起來能改但其實不能改的欄位。這份到第 7 節為止，沒有再留「下次再看」的區塊。

下面說的「考據」就是畫面上的真實照片或影片（畫中畫、黑底放大那種）。「口白」是旁白稿。「成片」是最後合成的 mp4。

---

## 建議先改的六件

1. **考據開關只留一個預設。** 現在新建專案是開的，舊專案畫面上卻顯示關，一鍵生成時又可能照開的去跑。
2. **失敗只跳一次訊息。** 現在合成失敗後，錯誤提示會一直重複彈出來。
3. **「圖做好幾張」全站用同一套算法。** 總覽和分鏡頁現在會算出兩個不一樣的數字。
4. **成片過期要看得出來。** 現在只要 mp4 還在，上面的大按鈕就變成「預覽成片」，就算你剛剛改過口白也一樣。
5. **換頁時把右側分鏡抽屜收起來。** 現在在分鏡點開某一幕，切到腳本或成片，抽屜還黏在右邊。
6. **使用者說「只改口白、不要重切」時，就不要順便重寫全片的英文出圖句子。**

---

## 1. 畫面和實際資料對不上

### 考據開關，開和關同時存在

分鏡頁有一顆「考據 PiP」勾選。勾起來，一鍵全流程才會順便抓真實照片；不勾，就只畫 AI 圖。

問題是這個預設值在程式裡寫了好幾次，而且互相矛盾：

- 從腳本頁按下去建立的新專案，**一定是開的**。
- 分鏡那顆勾選旁邊的說明寫「預設關閉」。
- 專案檔裡如果根本沒寫這個開關，列表把它當成**關**，一鍵全流程卻把它當成**開**。
- 測試檔 `tests/test_pipeline_and_cli.py`（原 `tests/test_p1.py`）已對齊為預設**開**。

所以你會遇到這種情況：畫面上沒勾，按「一鍵全流程」卻開始抓考據；或是新專案一打開就是勾著的，和說明文字相反。

相關位置：`aivideo/naming.py`、`aivideo/api/schemas.py`、`aivideo/story_generator.py`、`web/src/components/ScriptEditor.tsx`、`web/src/components/StoryboardGrid.tsx`、`aivideo/api/routes/jobs.py`。

### 「圖完成幾張」總覽和分鏡不一樣

有些鏡頭沒有 AI 圖，只有一張黑底用的考據照片。分鏡頁會把它算進「圖已經好了」。總覽卡片只數「有 AI 圖」或「有考據影片」，這種只有照片的鏡頭會被漏掉。

所以同一個專案，分鏡頂端可能寫 43/43，總覽可能寫 40/43。

- 分鏡算法：`aivideo/api/routes/scenes.py` 裡判斷這一幕有沒有畫面。
- 總覽算法：`aivideo/api/routes/jobs.py` 裡算整個專案的進度。

### 片長有三種估法

- 總覽用的秒數，是把每一幕配音紀錄檔裡的秒數加起來。還沒配音時，先用「一幕 5.5 秒」估。
- 頂列和分鏡工具列再各算一次，加的是實際聲音檔的長度。公式複製了兩份（`Topbar.tsx`、`StoryboardGrid.tsx`）。
- 成片頁底下那條可點的時間軸，缺秒數時也用 5.5 秒，而且這條軸**不是**合成時寫進字幕檔的真實時間。點某一格，片子會跳到一個大概的秒數，然後畫面直接被帶回分鏡頁。
- 腳本頁的字數滑桿又用「字數除以 220」估分鐘，和上面三種都無關。

### 成片顯示「做好了」，只代表檔案還在

只要 `compose/film.mp4` 還在，系統就認為成片完成。你後來改口白、重畫、重配音、重切分鏡，這個狀態不會變成「過期」。頂列的大按鈕會一直是「預覽成片」，不會提醒你這支片子是舊的。

### 選了哪個模型，換專案會串在一起

設定頁選的「寫稿模型」只記在這台瀏覽器裡，不寫進專案。換一台電腦或清掉瀏覽器資料就沒了，專案自己也看不出當初用哪一顆。

「畫圖模型」會寫進專案。可是你一切換專案，瀏覽器裡那份全域選擇也會被這個專案蓋掉。下一個新草稿就繼承上一部片的畫圖模型。若某部舊專案沒寫畫圖模型，設定頁仍顯示上一部的，不會清空。

### 生成失敗時，錯誤視窗會一直彈

生成進度是後端每隔半秒推一次給網頁。任務結束後，這條連線還在，繼續推同一包狀態。

成功做完時，網頁有擋住，只處理一次。失敗時沒擋住。例如素材不夠、合成程式失敗，錯誤訊息會留在那裡，網頁每收到一次就再跳一個提示。所以你會看到同一個紅字一直疊出來。

另外後端有準備「只通知一次」的訊息編號，網頁沒有讀。進度回應裡的日誌欄位也一直是空的。

還有一個小問題：按「一鍵全流程」或「出圖／配音／合成」時，畫面先轉圈，再去問後端。如果這一下請求就失敗，轉圈不會自己停，要等下一包進度來才改口。

### 打開右側抽屜時，裡面和外面可能不是同一張圖

生成過程中，外面的分鏡卡會先亮起「有圖了」。右側抽屜是自己另外抓一次資料，不會跟著這次更新。所以卡片已經是新圖，抽屜裡還是舊圖，要關掉重開或重新整理才會一致。

總覽上的完成數也不會跟著這一張卡更新，要等整個專案列表重新載入。

還有：某一幕的資料讀壞時，分鏡頁會直接跳過它，畫面少一格。總覽仍把那個資料夾算進總數。你會覺得「總數對不上，也不知道少了哪一幕」。

考據影片還有一個顯示問題。後端只要發現是影片，就跟網頁說模式是「全螢幕影片」。磁碟上記的可能是另一種。右側「呈現方式」的選單只有「小卡片」和「黑底放大」兩項，沒有「全螢幕影片」這個選項，選單就會對不齊。

### YouTube 上傳進度是全站共用一個

上傳進度不是「這部片自己的」，而是整個程式只有一份。你若連著傳兩部，後一部的進度、錯誤、結果會蓋掉前一部。網頁上會看成同一條進度。

### 換專案時，沒存的口白會消失

腳本頁是用「現在選哪部專案」來決定要不要整頁重做。你在頂列換專案、在總覽點進另一部、或切走再回來，還沒按儲存的口白就沒了。畫面上沒有「還沒存」的提醒。

---

## 2. 操作順不起來的地方

### 大按鈕不會告訴你下一步該做什麼

程式裡其實寫過一套規則：還沒有圖就出圖，還沒有聲音就配音，都有了就合成，合成過就預覽。這套規則寫了兩份（後端一份、網頁一份），**畫面上沒有用它**。

你在分鏡頁看到的大按鈕，只要還沒有成片，永遠是「一鍵全流程」。下面一排小按鈕又是「出圖、配音、合成、重構全片 Prompt」。成片一旦存在，大按鈕就只剩「預覽成片」，想重做合成得去找小按鈕。

使用者要自己判斷該按哪一個。

另外，後端有一個「每個階段之間暫停」的參數，介面沒有開關，呼叫時永遠傳「不要暫停」。這個參數可以之後拿掉，或真的做成按鈕，不要留著空轉。

### 右側抽屜會跟著你換頁

在分鏡點開某一幕，右邊會伸出大約 380 像素的編輯抽屜。這時候去腳本、成片、素材、總覽、設定，抽屜不收。主畫面被擠窄。

成片頁底下的時間軸更直接：點一格會離開正在看的片子，跳回分鏡，並打開那一幕的抽屜。若目的是檢查那一幕可以留，但至少該讓人留在成片上對時間，或明確寫「前往分鏡」。

### 你說只改口白，它還是去重寫全片出圖句子

口白有改、而且已經有分鏡時，儲存會問：要不要依新口白重切分鏡。這句問得清楚。

若你選「只更新口白」，只要這部片已經有角色設定，程式仍會自動把**每一幕的英文出圖句子全部重跑一次**。這很慢，也會花模型額度。改的是標題、聲線或大綱，只要最後走到這條儲存，也一樣會重跑。重跑失敗時錯誤被吃掉，你只看到「已寫回此專案」，以為什麼都沒動。

反過來，你若選「重切分鏡」，成功之後**不會**重跑這些英文句子。兩個選擇的後果是反的。

### 「要不要把字幕燒進畫面」可能兩個按鈕各記各的

頂列選單裡的「燒錄字幕」勾選，和分鏡上的「合成」按鈕，各記一份。中間用瀏覽器的一則自訂事件抄過去。一鍵全流程看頂列那份，分鏡的合成看分鏡那份。事件沒送到時，一個會燒字幕、一個不會。

「打開定裝視窗」「錨點更新了」也是用這種看不見的事件在元件之間喊話。元件沒掛上，喊話就沒人聽。比較穩的做法是放進全站共用的狀態，不要用這種廣播。

### 確認視窗的小問題

- 一次只能開一個確認框。若前一個還沒關又開新的，前一個會一直等，沒有結果。
- 按鈕會不會變紅，除了程式指定，還會看說明文字裡有沒有「刪除、清空、清除、覆蓋、無法復原」。解釋用的句子裡出現這些詞，也會變成紅色危險按鈕。

### 還沒合成，選單裡的下載還是能點

頂列 `⋯` 裡的「下載 mp4」「下載字幕」「打開 HTML 故事板」，只要有選專案就出現。檔案不存在時點下去是找不到頁面。成片頁有先檢查檔案在不在，兩邊不一致。

### 上面的 Gemini 綠燈，不代表模型真的通

頂列那兩顆燈每 8 秒問一次後端。Comfy 那顆是真的去看本機語音服務有沒有開。Gemini 那顆只表示「憑證檔有沒有設定好」，不是「現在呼叫模型成功」。燈的說明卻寫「在線／未連」，容易以為模型可用。

模型能不能用，是設定頁另一個「檢測模型可用性」。兩件事放在一起，卻不是同一種檢測。人在設定頁時，燈會被掛兩次，等於每 8 秒問兩次。

### 其他用起來會卡的小地方

- 選一個專案時，分鏡列表會被要兩次。一次是切換專案，一次是分鏡頁自己又載入。
- 「新建專案」和「刪除專案」在總覽和頂列各有一組。刪掉之後要跳到哪一部，也寫了兩份。
- 每次進成片頁都會重新載入影片。正在看的進度會被清掉，要重頭播。
- 腳本頁最上面有一排「我是白兔」「我是黑貓」。這是頻道開場白，和這部片的主題搶位置。預設句寫死「大家好~我是白兔!」，換一台電腦打開也會先看到這個名字。
- 聲線 `tw_female03` 資料夾不完整：只有參考音檔，沒有設定檔，也沒有試聽檔。另外三個聲線是齊的。選到它時行為會和其他聲線不一樣。
- 命令列還留著 `parse`、`run`、`regen`，說明寫「還沒做」。網頁上這些事已經能做。聲線命令的說明還提到一個不存在的聲線代號 `narrator_male`。

---

## 3. 字太多、同一件事出現太多次

### 腳本頁要捲很久才看到口白

口白輸入框上面依序是：主題、目標字數、資料夾英文名、故事要求、頻道名稱按鈕、六幕大綱。每一塊底下還有一行提示，輸入框的灰色範例文字自己又是一整段教學。標題寫一次「不會被大綱蓋掉」，提示再寫一次。

大綱按鈕寫「6 幕」，滑鼠停上去又寫「6 到 8 幕」。實際生成出來的是 6 到 8 幕。

比較順的排法：先看到主題和口白。字數、英文資料夾名、頻道開場、大綱、角色定裝，收進一個「進階」區塊。說明放在滑鼠提示就好。

### 分鏡上的用詞是給寫程式的人看的

畫面上直接出現 Prompt、ASS、B-Roll、PiP、1080p，再加上很多符號（火箭、閃電、建築）。同一種「黑底放大考據」有三種叫法。右側選單的選項句子比選單本身還長。

「重構全片 Prompt」放在「出圖、配音、合成」旁邊，看起來像製作的下一步。它其實是把每一幕的英文出圖句子全部重寫，不是在產圖。

### 設定頁像在介紹模型，不像在設定

文字模型和畫圖模型做成大卡片，副標是「極速、首選、旗艦」這種廣告句。真正要做的事（換帳號、看有沒有額度、看語音服務通不通）混在同一頁。模型名稱在網頁、後端、命令列說明各寫一份，之後加一顆模型要改三處。

### 說明文件和畫面各講各的

`doc/UI說明.md` 用長文再畫一次側欄和六個分頁，裡面還嵌了一大段版面示意。介面一改，這份文件就過期，而且和程式、這份重構備忘變成三個版本。

`doc/AIVideo專案說明.md` 也是把操作流程再寫一遍。

以前提過的 `doc/優化.md`、`doc/ui-redesign.md` 現在不在 `doc/` 裡。若還有筆記指向它們，那些筆記已經過期。

文件適合留「操作順序」和「哪些規則不能破」。按鈕長什麼樣以畫面為準，不要再維護一份平行的介面說明。

### 同一個數字出現三次

頂列已經有：圖幾張、聲音幾段、預估片長。分鏡工具列再顯示一次片長，再加「幾幕、幾鏡」。總覽卡片又有畫面、配音、成片、YouTube。數字可以留在最有用的那一處，另外兩處不要各算各的。

另外，每個專案還會產生一份 `preview.html` 故事板。分鏡頁已經能看圖。若那份 HTML 只是除錯用，不適合放在頂列的常用選單裡。

---

## 4. 檔案太大，之後改容易改錯

下面是現在特別長的檔。數字只是規模，不是要求照行數重寫。

| 檔案 | 大約行數 | 裡面同時在做 |
| --- | --- | --- |
| `web/src/components/AssetsView.tsx` | 1990 | 畫風、口吻、聲線、語氣標籤、試聽 |
| `web/src/components/ScriptEditor.tsx` | 1600 | 草稿、生成、大綱、畫風彈窗、角色、建專案、重切 |
| `aivideo/story_generator.py` | 1510 | 模型名單、畫風檔、口白清洗、大綱、腳本、擴寫、切鏡、寫專案 |
| `aivideo/auto_pip.py` | 1430 | 找考據、下載、審核、決定怎麼擺 |
| `web/src/components/SceneInspector.tsx` | 1190 | 改口白、重畫、鎖定、歷史版本、考據三種來源 |
| `aivideo/api/routes/jobs.py` | 920 | 專案列表、建立、定裝、更新、重切、清空、刪除 |
| `web/src/components/YouTubeUploadModal.tsx` | 830 | 登入、標題、縮圖、上傳、改舊片 |
| `web/src/App.tsx` | 750 | 版面、總覽、設定、確認框、進度連線、提示 |
| `aivideo/api/routes/scenes.py` | 690 | 分鏡列表、單幕、歷史版本、重做、考據、清空 |

之後若要拆，建議這樣切，網址和現有操作先不要改：

- 總覽和設定從 `App.tsx` 搬出去。腳本頁拆成「口白」「生成」「畫風選擇」。右側抽屜拆成「這一幕的圖和聲音」「歷史版本」「考據」。素材頁按畫風、口吻、聲線分開。
- 片長、下一步該按什麼、資料夾英文名，全站只留一份算法。現在網頁和後端各寫一份，考據預設就是這樣慢慢變成兩邊不一樣。能由後端決定的，網頁就不要再算一次。
- 元件之間不要再用瀏覽器自訂事件互相喊。燒錄字幕、要不要開定裝、錨點更新了，都放進共用狀態。
- `story_generator.py` 太雜。畫風讀寫可以回到畫風那個檔，切鏡回到切鏡那個檔，口白清洗靠近現有的口白處理。這個檔不要同時負責「問模型」和「把檔案寫進磁碟」。
- 專案路由裡的定裝圖可以獨立出去。列表和進度留在專案路由。
- 生成進度：做完或失敗就停止推播。錯誤用「編號變了才顯示」的方式跳一次。
- 命令列那三個「還沒做」的指令，短期不做就從說明拿掉，避免和網頁上已經能做的事並列。

另外，`aivideo/__pycache__/` 裡還有舊版網頁入口的編譯殘檔（以前的 Streamlit）。原始檔已經不在，這個殘檔可以刪，不影響現在的網頁。

### 比較隱蔽、但之後會咬人的寫法

- 網頁很多地方用「隨便什麼型別」在傳資料。欄位改名時，編譯不會提醒，要等按下去才爆。
- 錯誤幾乎都是直接把後端那句話彈出來。沒有分開「你填錯了，改一下就好」和「伺服器自己壞了」。
- 讀分鏡、算進度、讀 YouTube 紀錄時，壞掉的一筆常常被悄悄跳過。畫面上就是少一幕或少一筆，沒有說為什麼。
- 後端允許任何網站來呼叫，又同時開著「可以帶登入資料」。這兩個設定不該一起開。現在是自己電腦上用，風險不大，但設定本身是錯的。
- 網頁可以直接打開 `jobs` 裡的腳本、圖和成片，沒有登入。自己電腦可以接受。若以後把 8000 埠開到外面，這些檔案就公開了。

---

## 5. 先不要動

- **不要為了統一名稱去改舊專案資料夾。** 有些還是中文名，例如 `20261003_百事可樂的蘇聯海軍`。新專案才用英文資料夾名。改舊名稱會讓圖片網址和瀏覽器記住的專案一起斷掉。
- **口白清洗先留著。** 同音字只在配音時替換、字幕仍顯示漢字，這套已經收在一個地方。這次的問題主要是畫面和狀態，不是這段。
- **左邊六個分頁可以留。** 亂的是每一頁裡面的第二層按鈕和說明，不是導覽本身。

---

## 6. 命名很亂、同一件事有好幾套

這一節補前面沒寫完的：名字不統一、畫面上的詞和檔案對不上、有些設定寫了但沒有用。

### 「幕」同時指兩種東西

大綱裡的「幕」是一整段劇情，一部片大概 6 到 8 幕。分鏡裡的一張圖也常被叫成「第 N 幕」。

- 分鏡分組標題寫「第 3 幕 · 某某」。這裡的幕是大綱那一層。
- 生成進度、錯誤訊息、頂列狀態寫「第 12 幕」。這裡的幕其實是第 12 張圖。
- 資料夾叫 `001_shot_1`。`001` 和 `shot_1` 是同一個號碼寫兩次。程式裡這個東西又叫 scene。

所以「第 3 幕」可能是第三段劇情，也可能是第三張圖，看你在哪個畫面。建議對外只留兩個詞：大綱用「幕」，一張圖用「鏡頭」。資料夾不必把編號寫兩遍，`001` 就夠了。新專案再改即可，舊資料夾先別改名。

鏡頭標題又是口白前 16 個字。卡片上標題和口白開頭幾乎一樣，資訊重複，而且 16 個字常常斷在半句。

### 考據的擺法有五個英文名，畫面只講兩種

實際上人看得到的只有兩種：角落小卡片，或整張當背景（黑底放大、全螢幕影片）。

程式裡卻同時接受 `pip`、`spotlight`、`focus`、`black_bg`、`fullscreen`、`broll`。註解把自己叫做「spotlight 家族」。新資料寫 `spotlight` 或 `broll`，舊資料可能寫另外四個。每一處判斷「這算不算整張背景」的清單還不一樣：

- 出圖時，有考據影片或這些模式，就跳過 AI 畫圖。清單含 `broll`。
- 單獨按「合成」做檢查時，只認 `spotlight`、`focus`、`black_bg`、`fullscreen`，**不含 `broll`，也不看有沒有 `pip.mp4`**。
- 分鏡頁卻把「有考據影片」當成有畫面。

結果是：這一幕只有一支考據影片、沒有 AI 圖，分鏡頁顯示完成，按合成卻說缺圖。這和前面「完成數兩套算法」是同一類問題，而且會讓合成直接停掉。

建議對外只留兩個值：`pip`（小卡）、`full`（整張當背景，照片或影片都算）。舊的五個名字讀進來時轉成這兩個，不要在每個檔案各抄一份清單。

### 畫風的預設名稱對不上

腳本頁沒選畫風時，用的是 `otomo_katsuhiro`（畫風清單裡真的有）。

後端建立專案的預設卻寫 `future_workplace`。`assets/styles.yaml` 裡沒有這個名字。有人若沒帶畫風直接打 API，會先找一個不存在的畫風，再偷偷掉回大友克洋。

另外，程式裡還有一份寫死的備用畫風（電影寫實、歐式童話、復古科幻）。畫風庫檔案裡沒有這幾筆，庫里的吉卜力、像素風也不在這份備用清單。畫風檔讀失敗時，使用者看到的清單會變成另一套。

畫風卡片上還把內部代號印在名字旁邊，例如「大友克洋 (otomo_katsuhiro)」。代號是給檔案用的，不必顯示。

### 有一個「比喻風格」存了但沒人用

專案檔有 `metaphor_style`，可以是 `fantasy`、`vintage_realistic`、`symbolic`。建立專案時會寫進去，預設 `fantasy`。

畫面沒有這個選項。切分鏡、寫英文出圖句子時，函式雖然接收這個參數，函式裡面完全沒讀它。它只是跟著專案檔走一圈。

要嘛做成真正的選項（歷史寫實 / 比喻 / 象徵），要嘛刪掉，不要留一個永遠是 fantasy 的空欄位。

### 「一句一圖」和「切鏡節奏」是兩套切法

腳本頁有三張卡：快、標準、慢，說明寫大約 1～2 句、2～4 句、3～5 句一張圖。這是給模型看的節奏，實際切幾張由模型決定。

API 另外有 `lines_per_scene`，1 到 5，意思是「固定每幾句切一張」，會關掉模型判斷。畫面沒有這個控制項，名字又和寫稿提示詞裡的「每一幕幾行口白」撞在一起。後者是在算字數，和切圖無關。

三個名字都像「一幕幾句」：切鏡節奏、lines_per_scene、大綱每一幕要寫幾行。只留畫面上那三張卡就好。

### 角色長相被存了兩份，定裝也有兩層

舊做法是一整段「主體長相」文字（`subject`）。新做法是每人一筆（名字、外觀、是人還是物件）。建立專案時兩份都會寫，程式再把每人的外觀拼回那一整段。

定裝圖也有兩層：專案一張「主圖」，加上每個角色各一張。腳本頁和定裝視窗都能改同一份角色清單。改其中一邊，另一邊要靠那個看不見的更新事件才會跟上，事件沒接到就各看各的。

建議人只編「角色清單」。那整段主體文字改成自動產生，不要再給人手改一份。

### 「怎麼說話」拆成四個看不懂的欄

使用者會碰到這四樣，名字很近：

| 畫面上的東西 | 實際是什麼 | 存在哪 |
| --- | --- | --- |
| 口吻 | 文章怎麼寫、什麼腔調 | `assets/tones/`，專案的 `tone_id` |
| 發音人 / 聲線 | 誰的聲音去配音 | `assets/voices/`，專案的 `voice_id` |
| 頻道主自稱 | 開頭那句「我是白兔」 | 塞在故事要求文字裡，不是獨立欄位 |
| 語氣標籤 | 配音時的情緒記號，例如開心、放慢 | 聲線設定的 `instruct`，和口吻的 `voice_instruct` 又各有一份 |

聲線資料夾名叫 `tw_female01`，顯示名稱也是 `tw_female01`，沒有「台灣女聲」這種人話。說明文件和命令列還在教人用 `narrator_male`，專案裡沒有這個聲線。

口吻檔抽出來的建議語氣，和聲線自己的語氣，兩邊都能改，配音時到底聽哪一份，畫面看不出來。

### 三份稿、兩個 YouTube 檔、兩種聲音檔名

一部片裡和「文字」有關的有三份：故事要求（`custom_prompt`）、大綱（`outline`）、口白（`script.md`）。生成腳本的 API 把大綱叫做 `notes`。三個名字在畫面上還好，進到程式就對不上。

YouTube 有兩個檔：

- `youtube_metadata.json`：標題、說明、標籤的草稿。
- `youtube.json`：真正傳上去之後的影片網址。

總覽的「已發布」只看後者。只存了草稿、還沒上傳，兩個檔都在，容易以為已經上架。

配音檔標準名字是 `speech.wav`。有些舊判斷還接受 `audio.wav`。合成主流程只認 `speech.wav`。若哪次只寫出 `audio.wav`，分鏡頁可能算有聲音，合成又說沒聲音。

### 清空和重做的入口太多

同一種事有很多顆按鈕，差別要讀說明才知道：

- 頂列：清空圖片、清空配音、清空全部素材、強制全部重畫、批次考據。
- 分鏡列：出圖、配音、合成、重寫全片英文句子。
- 右側抽屜：這一幕重畫、重配、清圖、清音、清考據、換歷史版本。
- 腳本儲存：還可能順便重切或重寫英文句子。

「清空圖片」會留下聲音和口白。「清空素材」會連成片一起刪。「強制重畫」是蓋掉重做，不是刪除。這三個現在都在同一個 `⋯` 選單，危險程度和結果不一樣，卻長得像一排。

比較清楚的分法：常用的只留「補齊還沒做的圖」和「補齊還沒做的聲音」。刪除和全部重做放進同一個「危險操作」，每顆按鈕用一句話說會留下什麼。

### 小結：名字建議收成這樣

| 現在混用 | 建議只留 |
| --- | --- |
| 幕 / 鏡頭 / shot / scene | 幕＝大綱段；鏡頭＝一張圖 |
| pip、spotlight、focus、black_bg、fullscreen、broll | 小卡、整張背景 |
| style_id、畫風、prefix、未來的 future_workplace | 一個畫風 id，預設必須是清單裡有的 |
| metaphor_style | 有介面再用，否則刪 |
| lines_per_scene、切鏡節奏、每幕幾行 | 只留快／標準／慢 |
| subject 長文＋角色清單 | 只編角色清單 |
| 口吻、聲線、頻道句、語氣標籤 | 口吻管文字，聲線管聲音；頻道句算口白的第一句；語氣只留聲線那一份 |
| custom_prompt、notes、outline | 故事要求、大綱，不要再叫 notes |
| youtube.json、youtube_metadata.json | 一個叫草稿，一個叫上傳結果，檔名就這樣分開 |
| speech.wav、audio.wav | 只認 speech.wav |

---

## 7. 整條流程上還沒寫過的問題

這一節從「寫大綱」走到「專案檔」，只記前面沒寫過的。

### 字數滑桿管不到大綱

腳本頁的滑桿是 300 到 5000 字，旁邊還用字數除以 220 估分鐘。這顆滑桿**只交給寫口白**。

規劃大綱的提示詞寫死：要做 12 到 15 分鐘、大約 4000 字、6 到 8 幕。不管你把滑桿拉到 800 字還是 5000 字，大綱都照 4000 字的片子來規劃。

擴寫按鈕又另有一個預設，往大約 3500 字拉。所以同一頁有三個字數目標：滑桿、大綱的 4000 字、擴寫的 3500 字。短片子會先被規劃成一部長片，再叫口白去遷就。

大綱應該吃同一顆滑桿。做不到 4000 字就不要在提示詞裡寫 12 到 15 分鐘。

### 寫稿的指示互相打架

同一段提示詞同時要求：

- 100% 模仿口吻範本的腔調。
- 使用者寫的故事要求優先級最高，也要 100% 照做。
- 不准照抄範本裡的真人名字（例如叉雞）。
- 開場「大家好，我是某某」要寫進大綱第一幕。
- 口白裡又不准念出大綱標題、幕次、導演筆記。

模型要同時當策劃、當說書人、又要躲過自己剛剛寫下的大綱句子。口白裡漏出幕名，或開場白被清掉，都是這幾句一起下的結果。清洗規則是在補這個洞，不是另一次創作。

比較穩的分法：大綱只留給人看的情節，不要寫可念的句子。開場白只放在口白第一句。口吻只提供腔調，不提供內容。

### 同一天、同一個英文名，會蓋進舊資料夾

新專案的資料夾是「日期加英文名」。建立時**不檢查這個資料夾是否已經有了**。

同一天再做一次同名題目，程式會在原資料夾上繼續寫：蓋掉專案設定、蓋掉同編號鏡頭的台詞，但**不會刪掉多出來的舊鏡頭，也不會刪掉已經生成的圖和聲音**。編號對得上的鏡頭，新台詞配舊圖。編號對不上的舊鏡頭還留在分鏡裡。

建立前若資料夾已存在，應該停下來問要另開名稱，還是明確整包換新。不要靜靜混在一起。

### 口白檔先寫錯的一份，再蓋成對的

建立專案時，後端會先把一份「分鏡腳本」寫進 `script.md`：每一鏡有標題、英文畫面說明、旁白。緊接著網頁那條建立流程又把真正的口白蓋回去。

人最後看到的是口白，所以平常沒感覺。但第一份的格式正是「畫面：」「旁白：」這種不該被念出來的稿。若哪次只呼叫了前半段，口白檔就變成導演筆記。兩次寫入留一次就好，而且不要把畫面提示詞寫進口白檔。

另外，更新口白時如果寫檔失敗，錯誤被吃掉，畫面仍可能顯示已儲存。

### 切鏡節奏重新整理就忘了

「快／標準／慢」只活在腳本頁當時的記憶裡。專案檔沒有這個欄位。按儲存不會寫進去。只有建立、或按「重切分鏡」時，才把當下選到的節奏送出去。

重新整理網頁之後，節奏回到「標準」。你以為這部片是用「慢」切的，檔案裡沒有紀錄。

### 每一鏡的考據，建立時就先打開

只要這一鏡被判到要有考據詞，鏡頭檔裡的考據就是啟用，模式還會用關鍵字猜小卡或黑底，大小固定 24%、位置固定右半部。

這和專案那顆「考據開關」是兩層。專案開關決定一鍵全流程會不會去下載。鏡頭開關決定這一鏡「想不想用考據」。新片子常常每一鏡都是開的，就算你後來把專案開關關掉，單鏡仍標著要考據。兩層都在，畫面沒有講清楚哪一層說了算。

### 小卡的大小和位置，改了不會存

右側抽屜裡「卡片大小」「疊加位置」只改畫面上的數字。換成 30% 或左上角，不會寫進檔案，要等下一次別的考據操作順便帶出去。沒有那個順便，合成仍用 24%、右半部。

大小和位置應該一改就存，和「要不要啟用考據」一樣。

### 專案檔很多欄位看起來能調，畫面沒有開關

每一部 `job.yaml` 都帶著這些，而且幾乎每部一樣：

| 檔案裡寫的 | 實際情況 |
| --- | --- |
| 生成寬高 1920×1080，成片又寫一次 1920×1080 | 沒有地方改比例或解析度。兩組數字是同一件事寫兩遍 |
| 每秒 30 幀 | 沒有選項 |
| 推鏡 `slow_zoom_in` | 每一鏡都是同一種慢慢放大，沒有別的運鏡 |
| 字幕模式 `none`、字級 48 | 頂列「燒錄字幕」不會寫回這個欄位。勾了只影響那一次合成，重新整理就回到不燒 |
| 畫圖模型寫兩次：`model` 和 `model_final` | 兩個永遠相同 |
| 畫風前綴整段複製進專案檔 | 畫風庫改了，專案裡這份舊稿還在。出圖時又優先用畫風庫，這份複製多半用不到，檔案卻很長 |
| 環境變數沒設時，後端畫圖模型退回 `gemini-3-pro-image` | 畫面和建立專案的預設是 `gemini-3.1-flash-image`。第三個預設 |

這些若短期不開放調整，就不要寫進每個專案檔，用程式裡的一個常數。真的要開放，再做一個小設定，並讓「燒錄字幕」記在這部片上。

字型也是。`assets/fonts/` 裡沒有放實際字檔時，會去找 Linux 容器裡的路徑。在 Windows 上常常找不到，專案檔就留下一個不存在的路徑或只有字型名字。設定頁會寫「未找到檔案」，但專案檔裡看不出下次燒字幕會用哪一套。

### 歷史版本只增不減

每次重畫、重配音都會在該鏡頭的 `takes/` 再留一份。清理要開到那一幕的抽屜，手動留最新 3 個。沒有「整部片清一次舊版本」。

現有專案一個鏡頭資料夾裡常常是上百個圖和聲音。重做幾輪之後，磁碟和開啟分鏡都會變慢。生成成功並採用新版本時，可以順便只留最近幾份，不必等人手動。

### 壞掉的專案會從列表消失

讀取某一部專案失敗時，列表直接跳過，不顯示、不說明。你會覺得那部片不見了，資料夾其實還在。至少該列出名字並標「讀取失敗」。

### 這份文件的範圍

看過的是目前的網頁、後端、命令列、專案檔格式和 `doc/` 裡的說明。沒有實際按過畫面，也沒有跑測試。

已經收進第 1 到第 7 節的，就不再另開一節。沒有列進來的，是這次讀碼沒看到會影響使用的第二條規則。若之後要改，照「建議先改的六件」做，再加上這一節裡會直接弄錯資料的三件：同名資料夾覆蓋、大綱不理字數、考據小卡大小改了不存。
