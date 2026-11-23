# 兒科次專科最新文獻週報 (Pediatric Literature Weekly)

製作者：**JH CHIU MD** × Claude 5.5

自動從 PubMed 收錄 22 個兒科次專科最新的 Journal Article / Review / Guideline，
每週一 08:00（台灣時間）自動更新，並發布到 GitHub Pages。

## 發布步驟（只需做一次）

1. 在 GitHub 建立一個 **Public** repository（例如 `peds-lit`），勾選「Add a README」讓 repo 不是空的。
2. 進入 repo → **Settings → Pages → Build and deployment → Source** 選 **GitHub Actions**。
3. 回到 repo 首頁 → **Add file → Upload files**，把本資料夾內所有檔案（含 `.github` 資料夾）拖進去 → **Commit changes**。
   - 上傳（push）後 workflow 會**自動執行**，不需手動啟動，約 3–5 分鐘後網站上線。
   - 網址：`https://<你的帳號>.github.io/<repo 名稱>/`
4. 之後每週一自動更新，什麼都不用做。

> 提醒：網頁上傳若看不到 `.github` 資料夾，可在電腦上顯示隱藏檔，或用 GitHub Desktop / `git push` 上傳。

## 選用設定

- **Settings → Secrets and variables → Actions** 可加入 `NCBI_API_KEY`（向 NCBI 免費申請，抓取更快更穩）與 `NCBI_EMAIL`。
- 收錄天數、每科上限：修改 `.github/workflows/update.yml` 的 `DAYS_BACK`、`MAX_PER_SPECIALTY`。
- 各次專科的搜尋式：`scripts/fetch_pubmed.py` 的 `SPECIALTIES`。

## 檔案結構

```
.github/workflows/update.yml   排程、抓資料、部署
scripts/fetch_pubmed.py        PubMed E-utilities 抓取（僅用 Python 標準函式庫）
site/index.html                網頁（全選／全不選、類型篩選、搜尋、摘要）
site/data.json                 最新一週資料（自動產生）
site/archive/YYYY-MM-DD.json   每週歷史存檔，網頁「週次」選單可切換
site/archive/index.json        週次清單（自動產生）
（30 天／1 年／2 年由網頁直接向 PubMed 即時查詢，不需預先產生資料）
```

資料來源：NCBI PubMed。僅供學術參考，臨床決策請以原文為準。
