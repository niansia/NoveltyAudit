<p align="center">
  <img src="scholarly-novelty-audit/assets/logo.svg" alt="NoveltyAudit" width="760">
</p>

<p align="center"><strong>沒有任何一篇 paper 完整撞你？也許三篇合起來會。</strong></p>

<p align="center">
  <a href="README.md">English</a> · <strong>繁體中文</strong> · <a href="README.zh-CN.md">简体中文</a>
</p>

NoveltyAudit 是一個證據優先、組合式、時間嚴格的學術新穎性稽核 Agent Skill。它不只問「哪篇最像」，而是問：

> 最少需要哪幾篇先行工作，才能共同覆蓋這個 claim 的關鍵部分？在歷史 cutoff 前，有沒有證據顯示它們曾被有意義地連結？

輸出不是單一 novelty 分數，而是可稽核的 claim map、歷史上合格的證據、Minimal Prior Set、Bridge Evidence、仍然存活的新穎性，以及無法確定之處。

> 本頁是**精簡繁體中文版**。完整技術契約、CLI 與驗證規則請看英文 [README](README.md) 與 [SKILL.md](scholarly-novelty-audit/SKILL.md)。

## 快速開始

| 需求 | 是否必要 |
|---|---|
| Agent Skills 相容宿主 | 是 |
| Python | 3.10+ |
| 學術 provider 網路存取 | 是 |
| 可執行本地 scripts | 是 |
| 額外付費 LLM API key | 否 |
| OpenAlex／Semantic Scholar API key | 選用 |

### 一行安裝

若已有 Node.js 與 `npx`，開源 `skills` CLI 能辨識 repo 內的 skill：

```bash
npx skills add niansia/NoveltyAudit --skill scholarly-novelty-audit --global
```

這個第三方 installer 預設會記錄匿名安裝 telemetry；設定 `DISABLE_TELEMETRY=1` 可退出。不想使用 installer 時，請採下面的手動方式。

### 手動安裝

從 [GitHub Releases](https://github.com/niansia/NoveltyAudit/releases) 下載目前的 `scholarly-novelty-audit-v*.zip` 與 `.sha256`，再驗證檔案：

```bash
sha256sum -c scholarly-novelty-audit-v*.zip.sha256       # Linux
shasum -a 256 -c scholarly-novelty-audit-v*.zip.sha256  # macOS
```

驗證後解壓；也可以直接 clone：

```bash
git clone https://github.com/niansia/NoveltyAudit.git
mkdir -p ~/.codex/skills
cp -r NoveltyAudit/scholarly-novelty-audit ~/.codex/skills/scholarly-novelty-audit
python -m pip install -r ~/.codex/skills/scholarly-novelty-audit/requirements.txt
```

接著對 agent 說：

```text
Use $scholarly-novelty-audit on this claim:
「我們首次將 adaptive memory 與 compression-aware selection 結合於長影片 VLM 推理。」

Cutoff: 2025-09-18.
請採 adversarial search，回傳 Top-5 killer candidates、最多三篇的 Minimal Prior Set、
Bridge Evidence、strict temporal filtering、residual novelty 與 Markdown + JSON。
```

> **未公開稿件提醒：** 搜尋字串與識別碼會傳給設定的學術 provider。沒有授權時，不要傳送機密稿件全文；請盡量縮減私密措辭，並先看 [privacy model](scholarly-novelty-audit/references/privacy-model.md)。

Codex 可安裝在 `~/.codex/skills/`，Claude Code 可安裝在 `~/.claude/skills/`；其他 Agent Skills client 的探索路徑依宿主而定。資料夾名稱請保留為 `scholarly-novelty-audit`。

## 真實輸出長什麼樣

<p align="center">
  <img src="docs/assets/example-report.png" alt="NoveltyAudit report card：HIGH novelty risk、BROAD search protocol coverage、STRONG evidence confidence；Paper A 與 B 構成兩篇的 Minimal Prior Set，Paper C 則是獨立的 taxonomy bridge source" width="100%">
</p>

由 repo 內的合成 [golden composition fixture](scholarly-novelty-audit/tests/fixtures/composition-report.json) 重現。**這是契約範例，不是 benchmark 結果。** Paper C 提供 bridge evidence，不是兩篇 MPS 的成員。

<details>
<summary>無障礙文字版</summary>

```text
NoveltyAudit Report

Novelty Risk: HIGH
Search Protocol Coverage: BROAD
Coverage scope: Protocol execution only; this is not demonstrated recall of all relevant literature.
Evidence Confidence: STRONG
Classification: STRONG_COMPOSITION_RISK

Paper A and Paper B jointly cover both critical facets,
and Paper C explicitly connects them.

Input
Claim: We introduce an architecture with adaptive memory and compression-aware selection.
Cutoff: 2025-09-18 (strict)

Frozen Claim Map
F1 | mechanism   | adaptive memory              | critical
F2 | interaction | compression-aware selection  | critical

Top Killer Papers
1. Adaptive Memory Systems — covers F1; does not cover F2
2. Compression-aware Selection — covers F2; does not cover F1

Minimal Prior Set
MPS search bound: K ≤ 3.
Adaptive Memory Systems + Compression-aware Selection covers: F1, F2

Bridge Evidence
TAXONOMY_BRIDGE: papers A, B; evidence E3

Residual Novelty
The exact interaction rule may survive if it differs from the bridge source.

Defensible Claim Rewrite
Prior work separately covers adaptive memory and compression-aware selection;
we introduce a specific interaction rule between them.

Search Gaps
One workshop paper had no full text.
```

</details>

`BROAD` 只代表這套有界 protocol 被廣泛執行，不代表找回所有相關文獻。

## 適合與不適合的情境

| 適合 | 不適合 |
|---|---|
| 有明確 scholarly claim 與歷史 cutoff | 一般 literature review |
| 投稿前 novelty stress test | Topic discovery 或快速相似度搜尋 |
| Rebuttal、reviewer response、claim rewrite | 沒有邊界的「我的 idea 新不新」意見 |
| Multi-paper composition attack | Patentability 或 freedom-to-operate 分析 |
| Reviewer-defensible 日期與證據驗證 | 法律 prior-art 意見 |

日期、全文、graph coverage 或搜尋義務不足時，正確輸出是 `INCONCLUSIVE`。

## 為什麼不同

| 常見流程 | NoveltyAudit |
|---|---|
| 排出最相似的單篇 paper | 求解 1–3 篇、具證據的 **Minimal Prior Set** |
| 任何拼湊都算風險 | 強烈組合判定前要求 **Bridge Evidence** |
| 只用 publication year 過濾 | 解析**最早可驗證公開日**並隔離不確定日期 |
| 輸出一個分數 | 分開 **Novelty Risk／Search Protocol Coverage／Evidence Confidence** |
| 沒結果就暗示安全 | 明列限制，必要時回傳 **INCONCLUSIVE** |

## 運作方式

<p align="center">
  <img src="docs/assets/architecture.png" alt="NoveltyAudit 架構：claim freeze、多來源檢索、證據綁定、Minimal Prior Set 與 graph expansion、deterministic validation 與匯出" width="100%">
</p>

1. 先凍結 claim 並拆成 critical mechanisms、interactions 與 constraints。
2. 以 literal、mechanism、problem/function、ancestor、composition bridge 五類 query 跨 provider 檢索。
3. 去重、解析最早公開日、取得公開全文，將 evidence span 綁回 facet。
4. 求解 `K ≤ 3` 的 Minimal Prior Set，並展開 citation graph 檢查歷史連結。
5. 重新驗證 invariants、綁定 runtime provenance；不完整就封頂 `INCONCLUSIVE`，有效報告才可匯出 Markdown／JSON／HTML。

## 判定語意

- `DIRECT_PRECEDENT`：單篇合格前作以證據覆蓋全部 critical facets。
- `STRONG_COMPOSITION_RISK`：2–3 篇合格前作共同覆蓋，且有 textual bridge。
- `PLAUSIBLE_COMPOSITION_RISK`：聯合覆蓋成立，但目前只有 graph-level bridge。
- `FRAGMENTED_PRECEDENT`：完整執行必要 graph expansion 後，零件個別已知但沒有 meaningful historical bridge。
- `RESIDUAL_NOVELTY`：仍有 critical mechanism 或 interaction 未被覆蓋。
- `INCONCLUSIVE`：檢索、日期、全文、graph expansion 或證據不足。

以上是有界稽核分類，不是原創性保證或法律結論。

## 82 個 reviewer-annotated cases 的探索性量測

以下不是 NoveltyAudit 的效能分數：

| 量測 | 觀察結果 | 可以支持的解讀 |
|---|---:|---|
| 至少含兩篇 deterministically detected reviewer-named priors 的案例 | **23/82（28.05%）** | detected mention rate；不是 composition objection 盛行率 |
| 有 cutoff 前 co-citation bridge 的完整多前作案例 | **4/18（22.22%）** | 少數訊號，且不確定性很寬（exact 95% interval：6.41%–47.64%） |
| OpenAlex + Semantic Scholar fallback 後 backward references 非空的指名前作 | **56/83（67.47%）** | 實測 provider 覆蓋；不是文獻 recall |

量測結果讓 Bridge Evidence 被定位成條件式正向訊號；沒有 bridge 永遠不會成為通用負向判定。End-to-end reviewer-grounded Recall@5、MRR 與 reviewer prediction 仍未量測。詳見 [empirical status](docs/empirical-status.md)。

## Alpha 範圍與信任邊界

Deterministic pipeline、schemas、validators、release packaging 與離線測試已實作；CLI 與 report schema 在 1.0 前仍可能演進。專案不會用合成資料假裝 reviewer-grounded 成效已成立。

Provider key 對基本使用不是必要條件。`S2_API_KEY` 可降低 Semantic Scholar 節流；`OPENALEX_API_KEY` 可提高 OpenAlex 額度。OpenAlex 已淘汰 polite-pool，因此不使用 `mailto`。

Release workflow 會在 Ubuntu、macOS clean install，驗證 Agent Skill、重建 allowlisted runtime ZIP、檢查 license 與 SHA-256。Runtime asset 不包含 tests、benchmark data、本地 run 或 cache。

NoveltyAudit 僅執行學術文獻偵察，不提供 patentability、non-obviousness、freedom-to-operate 或其他法律意見。

## 技術文件與測試

- [Deterministic CLI 與 coverage derivation](scholarly-novelty-audit/references/tooling.md)
- [Minimal Prior Set](scholarly-novelty-audit/references/minimal-prior-set.md)
- [Bridge Evidence](scholarly-novelty-audit/references/bridge-evidence.md)
- [Temporal cutoff](scholarly-novelty-audit/references/temporal-cutoff.md)
- [Evidence rules](scholarly-novelty-audit/references/evidence-rules.md)
- [Report schema](scholarly-novelty-audit/references/report-schema.md)
- [Privacy model](scholarly-novelty-audit/references/privacy-model.md)

```bash
python -m pytest scholarly-novelty-audit/tests -q
skills-ref validate ./scholarly-novelty-audit
```

下一個里程碑是 preregistered、具授權、end-to-end reviewer-grounded pilot。相關邊界見 [release acceptance](docs/release-acceptance.md)、[benchmark policy](scholarly-novelty-audit/benchmark/README.md) 與 [data licenses](docs/DATA_LICENSES.md)。Audit 分享、安裝求助、研究方法與新想法可放到 [GitHub Discussions](https://github.com/niansia/NoveltyAudit/discussions)。

如果 NoveltyAudit 找到一篇可能比 Reviewer #2 更早找到的 paper，歡迎替 repo 點 Star。
