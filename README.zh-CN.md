<p align="center">
  <img src="scholarly-novelty-audit/assets/logo.svg" alt="NoveltyAudit" width="760">
</p>

<p align="center"><strong>没有一篇论文能单独否定你的新颖性？也许三篇合起来可以。</strong></p>

<p align="center">
  <a href="README.md">English</a> · <a href="README.zh-TW.md">繁體中文</a> · <strong>简体中文</strong>
</p>

NoveltyAudit 是一个证据优先、组合式、严格遵守时间边界的学术新颖性审计 Agent Skill。它不只问“哪篇最相似”，而是问：

> 最少需要哪几篇已有工作，才能共同覆盖这个 claim 的关键部分？在历史 cutoff 之前，是否有证据表明这些工作已经形成有意义的联系？

输出不是单一 novelty 分数，而是可审计的 claim map、历史上符合条件的证据、Minimal Prior Set、Bridge Evidence、仍然保留的新颖性，以及无法确定之处。

> 本页是**简体中文精简版**。完整技术契约、CLI 与验证规则请参阅英文 [README](README.md) 和 [SKILL.md](scholarly-novelty-audit/SKILL.md)。

## 快速开始

| 要求 | 是否必要 |
|---|---|
| Agent Skills 兼容宿主 | 是 |
| Python | 3.10+ |
| 可访问学术 provider 的网络 | 是 |
| 可执行本地 scripts | 是 |
| 额外付费 LLM API key | 否 |
| OpenAlex／Semantic Scholar API key | 可选 |

### 一行安装 skill

如果已有 Node.js 和 `npx`，开源 [skills CLI](https://skills.sh/docs/cli) 可以识别 repo 中的 skill，并安装到支持的 agent：

```bash
npx skills add niansia/NoveltyAudit --skill scholarly-novelty-audit --global
```

skills CLI 只安装 skill package，不会安装 Python dependencies。首次使用时，NoveltyAudit 仍会确认 Python 3.10+，并在宿主允许安装 dependencies 时安装 Python requirements。

这个第三方 installer 默认会记录匿名安装 telemetry；设置 `DISABLE_TELEMETRY=1` 可以退出。如果不想使用 installer，请采用下面的手动方式。

### 手动安装

从 [GitHub Releases](https://github.com/niansia/NoveltyAudit/releases) 下载当前的 `scholarly-novelty-audit-v*.zip` 和 `.sha256`，然后验证文件：

```bash
sha256sum -c scholarly-novelty-audit-v*.zip.sha256       # Linux
shasum -a 256 -c scholarly-novelty-audit-v*.zip.sha256  # macOS
```

验证后解压；也可以直接 clone：

```bash
git clone https://github.com/niansia/NoveltyAudit.git
mkdir -p ~/.codex/skills
cp -r NoveltyAudit/scholarly-novelty-audit ~/.codex/skills/scholarly-novelty-audit
python -m pip install -r ~/.codex/skills/scholarly-novelty-audit/requirements.txt
```

然后对 agent 说：

```text
Use $scholarly-novelty-audit on this claim:
“我们首次将 adaptive memory 与 compression-aware selection 结合用于长视频 VLM 推理。”

Cutoff: 2025-09-18.
请进行 adversarial search，返回 Top-5 killer candidates、最多三篇的 Minimal Prior Set、
Bridge Evidence、strict temporal filtering、residual novelty，以及 Markdown + JSON。
```

> **未公开稿件提醒：** 检索词和论文标识符会发送给已配置的学术 provider。未经授权，不要发送机密稿件全文；请尽量减少私密措辞，并先阅读 [privacy model](scholarly-novelty-audit/references/privacy-model.md)。

Codex 可安装到 `~/.codex/skills/`，Claude Code 可安装到 `~/.claude/skills/`；其他 Agent Skills client 的发现路径取决于宿主。文件夹名称请保留为 `scholarly-novelty-audit`。

## 实际输出长什么样

<p align="center">
  <img src="docs/assets/example-report.png" alt="NoveltyAudit report card：HIGH novelty risk、BROAD search protocol coverage、STRONG evidence confidence；Paper A 和 B 构成两篇论文的 Minimal Prior Set，Paper C 则是独立的 taxonomy bridge source" width="100%">
</p>

由 repo 内的合成 [golden composition fixture](scholarly-novelty-audit/tests/fixtures/composition-report.json) 重现。**这是契约示例，不是 benchmark 结果。** Paper C 提供 bridge evidence，不是两篇论文 MPS 的成员。

<details>
<summary>无障碍文字版</summary>

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

`BROAD` 只表示这套有界 protocol 已被广泛执行，不表示已经找回所有相关文献。

## 适合与不适合的场景

| 适合 | 不适合 |
|---|---|
| 有明确 scholarly claim 和历史 cutoff | 一般 literature review |
| 投稿前 novelty stress test | Topic discovery 或快速相似度检索 |
| Rebuttal、reviewer response、claim rewrite | 没有边界的“我的 idea 新不新”意见 |
| Multi-paper composition attack | Patentability 或 freedom-to-operate 分析 |
| Reviewer-defensible 日期与证据验证 | 法律 prior-art 意见 |

日期、全文、graph coverage 或检索义务不足时，正确输出是 `INCONCLUSIVE`。

## 为什么不同

| 常见流程 | NoveltyAudit |
|---|---|
| 排出最相似的单篇 paper | 求解由 1–3 篇论文组成且有证据支持的 **Minimal Prior Set** |
| 任何拼接都算风险 | 在给出强组合判定前要求 **Bridge Evidence** |
| 只用 publication year 过滤 | 解析**最早可验证公开日期**并隔离不确定日期 |
| 输出一个分数 | 分开 **Novelty Risk／Search Protocol Coverage／Evidence Confidence** |
| 没有结果就暗示安全 | 明确记录限制，必要时返回 **INCONCLUSIVE** |

## 工作流程

<p align="center">
  <img src="docs/assets/architecture.png" alt="NoveltyAudit 架构：冻结 claim、多来源检索、证据绑定、Minimal Prior Set 与 graph expansion、deterministic validation 与导出" width="100%">
</p>

1. 先冻结 claim，并拆解成 critical mechanisms、interactions 和 constraints。
2. 使用 literal、mechanism、problem/function、ancestor、composition bridge 五类 query 跨 provider 检索。
3. 去重、解析最早公开日期、获取公开全文，并将 evidence span 绑定回 facet。
4. 求解 `K ≤ 3` 的 Minimal Prior Set，展开 citation graph 检查历史联系。
5. 重新验证 invariants、绑定 runtime provenance；不完整时结论上限为 `INCONCLUSIVE`，只有有效报告才能导出 Markdown／JSON／HTML。

## 判定含义

- `DIRECT_PRECEDENT`：一篇符合条件的已有工作以证据覆盖全部 critical facets。
- `STRONG_COMPOSITION_RISK`：2–3 篇符合条件的已有工作共同覆盖 claim，且存在 textual bridge。
- `PLAUSIBLE_COMPOSITION_RISK`：联合覆盖成立，但目前只有 graph-level bridge。
- `FRAGMENTED_PRECEDENT`：完整执行必要 graph expansion 后，各组成部分分别已有先例，但未验证到 meaningful historical bridge。
- `RESIDUAL_NOVELTY`：至少还有一个 critical mechanism 或 interaction 未被覆盖。
- `INCONCLUSIVE`：检索、日期、全文、graph expansion 或证据不足。

以上是有边界的审计分类，不是原创性保证或法律结论。

## 82 个 reviewer-annotated cases 的探索性测量

以下不是 NoveltyAudit 的性能分数：

| 测量 | 观察结果 | 可以支持的解读 |
|---|---:|---|
| 至少包含两篇 deterministically detected reviewer-named priors 的案例 | **23/82（28.05%）** | detected mention rate；不是 composition objection 的发生比例 |
| 在 cutoff 前存在 co-citation bridge 的完整多前作案例 | **4/18（22.22%）** | 少数信号，且不确定性很宽（exact 95% interval：6.41%–47.64%） |
| OpenAlex + Semantic Scholar fallback 后 backward references 非空的指名前作 | **56/83（67.47%）** | 实测 provider 覆盖；不是文献 recall |

测量结果将 Bridge Evidence 定位为条件式正向信号；没有 bridge 永远不会成为通用负向判定。End-to-end reviewer-grounded Recall@5、MRR 与 reviewer prediction 仍未测量。详见 [empirical status](docs/empirical-status.md)。

## Alpha 范围与信任边界

Deterministic pipeline、schemas、validators、release packaging 与离线测试已经实现；CLI 和 report schema 在 1.0 前仍可能变化。项目不会使用合成数据假装 reviewer-grounded 效果已经得到证明。

Provider key 对基本使用不是必需条件。`S2_API_KEY` 可降低 Semantic Scholar 限流；`OPENALEX_API_KEY` 可提高 OpenAlex 配额。OpenAlex 已停用 polite-pool，因此不使用 `mailto`。

Release workflow 会在 Ubuntu、macOS 上进行 clean install，验证 Agent Skill、重新构建 allowlisted runtime ZIP，并检查 license 与 SHA-256。Runtime asset 不包含 tests、benchmark data、本地 run 或 cache。

NoveltyAudit 只执行学术文献侦察，不提供 patentability、non-obviousness、freedom-to-operate 或其他法律意见。

## 技术文档与测试

- [Deterministic CLI 与 coverage derivation](scholarly-novelty-audit/references/tooling.md)
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

下一个里程碑是 preregistered、有合法授权的 end-to-end reviewer-grounded pilot。相关边界请参阅 [release acceptance](docs/release-acceptance.md)、[benchmark policy](scholarly-novelty-audit/benchmark/README.md) 和 [data licenses](docs/DATA_LICENSES.md)。Audit 分享、安装求助、研究方法与新想法可以发布到 [GitHub Discussions](https://github.com/niansia/NoveltyAudit/discussions)。

如果 NoveltyAudit 找到一篇可能比 Reviewer #2 更早发现的 paper，欢迎给这个 repo 点 Star。
