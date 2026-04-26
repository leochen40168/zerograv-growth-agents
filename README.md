# ZeroGrav 冷啟動成長工作台 MVP

ZeroGrav 冷啟動成長工作台 MVP 是一個本機 Streamlit 工具，協助 ZeroGrav 在冷啟動階段規劃內容、產生 Prompt、產生草稿、人工審稿、匯出人工發布用內容、管理賣家線索、管理合作廠商名單、產生 B2B 開發信，以及記錄每日成效。

這個工具的核心原則是「人工審核、人工發布、人工決策」。它會整理資料與產生可複製的內容，但不會取代人的判斷。

## 這個工具是做什麼的

- 建立每日冷啟動主題與發文任務
- 依照主題產生內容 Prompt
- 選配使用 OpenAI 產生內容草稿
- 掃描草稿並建立審稿清單
- 匯出網站與 Facebook 人工發布用內容檔案
- 管理 Facebook、網站、LINE、電話等來源的賣家線索
- 管理公開來源取得的合作廠商名單
- 產生繁體中文 B2B 廠商開發信
- 在明確啟用 SMTP 後，小量寄送開發信
- 記錄曝光、留言、私訊、線索、上架設備等人工成效

## 這個工具不會做什麼

- 不會自動發文到 zerograv.com.tw
- 不會自動發文到 Facebook 粉絲團
- 不會自動發文到 Facebook 社團
- 不會自動留言、私訊、按讚
- 不會自動大量抓 Google 搜尋結果
- 不會自動大量爬整個網站
- 不會寄信給沒有來源網址的 email
- 不會寄信給已標記 `opted_out` 或 `not_interested` 的廠商
- 不會硬寫 API key、SMTP 密碼或 email 密碼
- 不會承諾成交，也不會誇大流量

## 安裝

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

請只在 `.env` 填入你實際要使用的金鑰或帳密，並保持 `.env` 在本機，不要提交到 GitHub。

## 啟動方式

### 使用一鍵啟動檔

在 Windows 檔案總管中雙擊：

```text
啟動ZeroGrav.bat
```

這個檔案會自動切換到專案根目錄，並執行：

```powershell
streamlit run src/app.py
```

如果 Streamlit 尚未安裝，視窗會提示你先執行：

```powershell
pip install -r requirements.txt
```

### 使用 PowerShell 手動啟動

```powershell
streamlit run src/app.py
```

## 環境設定

OpenAI API 是選配。只有在人員點擊產生草稿，或執行內容草稿 CLI 時才會使用。

```powershell
OPENAI_API_KEY=your_api_key_here
OPENAI_MODEL=gpt-4.1-mini
```

SMTP 寄信是選配，預設關閉。只有當你設定 SMTP 並把 `EMAIL_SEND_ENABLED=true` 時，系統才會真的寄出廠商開發信。

```powershell
EMAIL_SMTP_HOST=
EMAIL_SMTP_PORT=587
EMAIL_SMTP_USERNAME=
EMAIL_SMTP_PASSWORD=
EMAIL_FROM_NAME=ZeroGrav
EMAIL_FROM_ADDRESS=
EMAIL_DAILY_LIMIT=20
EMAIL_SEND_ENABLED=false
```

建議一開始維持 `EMAIL_SEND_ENABLED=false`，先只產生信件草稿並人工檢查。若要寄信，建議每天 10-20 封，且寄件網域需先設定 SPF、DKIM、DMARC。

WordPress 是未來選配，不是目前主流程。ZeroGrav 目前主流程是 zerograv.com.tw 網站後台人工發布，以及 Facebook 粉絲團 / 社團人工發布。

## 每日操作流程

1. 開啟 `每日冷啟動流程`，點擊 `建立每日任務`。
2. 開啟 `產生內容 Prompt`，為選定主題產生 Prompt 檔案。
3. 開啟 `產生內容草稿`，選配使用 OpenAI 產生本機草稿。
4. 開啟 `內容審稿清單`，點擊 `掃描草稿`。
5. 人工審稿，確認內容是否可用。
6. 開啟 `網站 / 社群內容匯出`，匯出人工發布用內容檔案。
7. 人工複製 approved 內容到 zerograv.com.tw 網站後台。
8. 人工發布 approved 內容到 Facebook 粉絲團或社團。
9. 若有人詢問或有設備供給機會，新增到 `賣家線索管理`。
10. 晚上到 `成效追蹤` 補上曝光、留言、私訊、線索等成效數字。

## 產生內容 Prompt

在 Streamlit 開啟 `產生內容 Prompt`，選擇 `topics.csv` 裡的主題，再點擊 `產生 Prompt`。

CLI：

```powershell
python src/article_generator.py --topic-id 1
```

產生的 Prompt 會存到：

```text
outputs/generated_prompts/
```

這個步驟只會填入 Prompt 模板，不會呼叫 OpenAI、不會發布文章、不會操作 Facebook。

## 產生內容草稿

產生單一草稿：

```powershell
python src/content_draft_generator.py --prompt-path outputs/generated_prompts/topic-1-seo-article.md
```

產生某個主題的全部草稿：

```powershell
python src/content_draft_generator.py --topic-id 1
```

草稿會存到：

```text
outputs/drafts/
```

草稿只是供人工審稿使用，不會自動發布、留言、私訊、按讚或寄出。

## 內容審稿與人工發布

`內容審稿清單` 會掃描 `outputs/drafts/` 裡的 markdown 草稿，並將審稿狀態記錄在：

```text
data/content_reviews.csv
```

建議流程：

1. 產生草稿
2. 掃描草稿
3. 人工審稿
4. 將項目標記為 `approved` 或 `needs_rewrite`
5. 匯出人工發布用內容
6. 人工發布後，將項目標記為 `published`

## 網站 / 社群內容匯出

`網站 / 社群內容匯出` 會從 `outputs/drafts/` 讀取草稿，產生人工複製發布用檔案到：

```text
outputs/exports/
```

匯出檔會加上 metadata，例如來源草稿、匯出類型、發布方式。發布方式固定是：

```text
publish_method: manual_copy
```

這個功能不會自動發布到網站，也不會自動發布到 Facebook。

## 如何新增廠商名單

開啟 `廠商開發信助手`，在新增廠商表單填入：

- 公司名稱
- 官網
- Email
- 電話
- 設備類別
- Email 來源網址 `source_url`
- 來源類型 `source_type`
- 聯繫狀態 `contact_status`
- 下一步動作
- 備註

請務必記錄公開 email 或聯絡方式的來源網址。若 `source_url` 空白，系統不會寄出 email。

允許的 `source_type`：

- `website`
- `facebook_page`
- `facebook_group`
- `google_search`
- `manual`

允許的 `contact_status`：

- `new`
- `email_drafted`
- `email_sent`
- `follow_up_needed`
- `replied`
- `interested`
- `not_interested`
- `opted_out`
- `listed`

## 如何產生開發信

在 `廠商開發信助手` 選擇廠商 ID 與信件模板：

- `initial`
- `follow_up`

點擊 `產生開發信` 後，系統會顯示信件主旨與內容供人工檢查。信件會使用繁體中文，語氣是正式、低壓的商務合作邀請。

信件會說明：

- ZeroGrav 是二手儀器設備集中式曝光平台
- 可免費刊登
- 不取代廠商原官網或既有銷售管道
- 可先協助刊登 3-5 筆設備
- 買家可依廠商指定方式聯絡
- 不承諾成交
- 不誇大流量
- 若不方便後續聯繫，可回覆「不需聯繫」

## 如何寄送開發信

預設不會寄信。若要啟用寄信，請在 `.env` 設定 SMTP，並明確改成：

```powershell
EMAIL_SEND_ENABLED=true
```

系統仍會阻擋以下情況：

- 廠商 email 空白
- 廠商 `source_url` 空白
- 廠商狀態是 `opted_out`
- 廠商狀態是 `not_interested`
- 廠商狀態是 `email_sent`
- 廠商狀態是 `listed`
- 今日已達 `EMAIL_DAILY_LIMIT`

寄送紀錄會存到：

```text
data/email_outreach_log.csv
```

## 如何記錄賣家線索

開啟 `賣家線索管理`，新增 Facebook、LINE、網站表單、電話或其他來源的賣家線索。

建議記錄：

- 賣家名稱
- 線索來源
- 設備類型
- 品牌
- 型號
- 設備所在地
- 聯絡方式
- 開價
- 設備狀況
- 下一步動作
- 內部備註

這只是本機追蹤表，不會自動聯絡賣家。

## 如何記錄成效

開啟 `成效追蹤`，手動輸入每日成效：

- 曝光或觸及
- 反應
- 留言
- 分享
- 點擊
- 私訊
- 賣家線索
- 已上架設備
- 觀察備註

這些資料用來比較主題、平台與內容類型，不會自動抓 Facebook 數據，也不會呼叫外部 API。
