<p align="center">
  <img src="novelty-audit/assets/logo.svg" alt="NoveltyAudit" width="760">
</p>

<p align="center"><strong>沒有任何一篇 paper 完整撞你？也許三篇合起來會。</strong></p>

NoveltyAudit 是一個證據優先、組合式、時間嚴格的學術新穎性稽核 Agent Skill。它不只問「哪篇最像」，而是找出最少 1–3 篇既有工作能否共同覆蓋核心 claim，並要求歷史上的 Bridge Evidence 才能升格成強烈的組合式風險。

## 四個核心差異

- **Minimal Prior Set：** 找最小聯合覆蓋集合，而非單篇相似度排名。
- **Bridge Evidence：** 沒有可追溯的引用、延伸、taxonomy、benchmark 或組合證據，就只能判為 fragmented。
- **Strict Temporal Cutoff：** 依最早可驗證公開日守門；只有年份的資料不得偷塞 1 月 1 日。
- **三軸分離：** Novelty Risk、Search Coverage、Evidence Confidence 永不混成一個假精確分數。

## 已完成

- 符合 Agent Skills 格式的 `SKILL.md`、progressive references 與 Codex UI metadata。
- OpenAlex、Semantic Scholar、arXiv、Crossref provider adapters。
- DOI／arXiv／標題正規化、preprint 與正式版本去重。
- 最早公開日解析與嚴格 cutoff 狀態。
- 1–3 篇 evidence-bound Minimal Prior Set 求解。
- citation graph bridge discovery 與 textual bridge 升格守門。
- criticality leave-one-out 敏感度分析。
- Markdown、JSON、HTML 匯出與 adversarial invariant validator。
- 具版本的 run manifest、獨立 DOI／arXiv 驗證，以及區分文獻快照變化與推理變化的 snapshot diff。
- 保存 provider 計數、分頁、corpus 與截斷狀態的 SearchRun，並由 validator 自動推導 Search Coverage。
- JSON Schemas、golden fixture、測試與 benchmark annotation schema。

核心流程不需要額外付費 LLM API；宿主 agent 負責 claim decomposition 與 evidence interpretation，scripts 只處理可重現的 deterministic 工作。

Provider key 對基本使用並非必要。`S2_API_KEY` 可降低 Semantic Scholar 的節流；免費的 `OPENALEX_API_KEY` 可將 OpenAlex 每日額度從匿名試用額度提高到 1 美元。OpenAlex 已在 2026 年淘汰 polite-pool 制度，因此本專案不使用 `mailto`。OpenAlex 檢索會明確要求 `corpus=all`；只查 core 的 run 不能宣稱 `BROAD` coverage。

## 安裝

```bash
mkdir -p ~/.codex/skills
cp -r ./novelty-audit ~/.codex/skills/novelty-audit
```

Claude Code 可改放 `~/.claude/skills/novelty-audit`；跨 agent 慣例可放 `~/.agents/skills/novelty-audit`。實際 skill 資料夾必須叫 `novelty-audit`。

安裝後可執行正式規格與回歸驗證：

```bash
python -m pytest novelty-audit/tests -q
skills-ref validate ./novelty-audit
```

## 使用

```text
Use $novelty-audit on this claim:
「我們首次將 adaptive memory 與 compression-aware selection 結合於長影片 VLM 推理。」

Cutoff: 2025-09-18.
請採 adversarial search，回傳 Top-5 killer candidates、最多三篇的 Minimal Prior Set、
Bridge Evidence、strict temporal filtering、residual novelty 與 Markdown + JSON。
```

## 判定語意

- `DIRECT_PRECEDENT`：單篇合格前作以全文證據覆蓋全部 critical facets。
- `STRONG_COMPOSITION_RISK`：2–3 篇合格前作共同覆蓋，且有 textual bridge。
- `PLAUSIBLE_COMPOSITION_RISK`：聯合覆蓋成立，但目前只有 graph bridge。
- `FRAGMENTED_PRECEDENT`：零件個別已知，但沒有 meaningful historical bridge。
- `RESIDUAL_NOVELTY`：仍有 critical mechanism 或 interaction 未被覆蓋。
- `INCONCLUSIVE`：檢索、日期、全文或證據不足。

完整技術說明請看英文 [README](README.md)，競品查核請看 [landscape review](docs/landscape.md)，公開測試前仍需完成的工作則列在 [user-facing release acceptance](docs/release-acceptance.md)。

NoveltyAudit 僅執行學術文獻偵察，不提供 patentability、non-obviousness、freedom-to-operate 或任何其他法律意見。

如果 NoveltyAudit 找到一篇可能比 Reviewer #2 更早找到的 paper，歡迎替 repo 點 Star。
