1. 新帳號試用300折抵
2. 啟用API(所有) 啟用youtube V4 API
3. 新增專案ID
4. 建立服務帳戶
5. 角色:服務使用情形檢視者/Agent Platform 使用者
6. VSCode 安裝 google vertexai extension
設定專案ID
ADC登入: gcloud auth application-default login
Global Base URL: https://aiplatform.googleapis.com
gcloud auth application-default set-quota-project YOUR_NEW_PROJECT_ID
gcloud config set project YOUR_NEW_PROJECT_ID

要啟用並使用 Google Cloud $300 免費抵免額來建構你的 Agent 專案，請按照以下步驟操作：

1. 啟用免費試用帳戶

1. 準備一個 Google 帳號與一張有效的信用卡（僅用於驗證身分，防範機器人惡意註冊，試用期間不會扣款）。
2. 前往 Google Cloud 帳外主控台。
3. 點選頁面頂端的 「免費開始使用」（Start for free）按鈕。
4. 設定你的國家（台灣）與同意服務條款，並完成信用卡綁定。
5. 系統驗證成功後，$300 美元的抵免額會立刻儲值到你的結算帳戶中（有效期 90 天）。

2. 建立專案與啟用 Agent 服務

1. 進入 GCP 主控台，點選左上角的專案下拉選單，選擇 「新增專案」，為你的 Agent 專案命名（例如：my-ai-agent-project）。
2. 確認該專案已連結剛才建立的「免費試用結算帳戶」。
3. 在上方搜尋欄輸入 Vertex AI 或 Agent Builder，並點選進入服務頁面。
4. 點選 「啟用所有建議的 API」（Enable all recommended APIs），這會允許你使用 Vertex AI 平台、Agent 執行環境以及相關的 Gemini 基礎模型。
