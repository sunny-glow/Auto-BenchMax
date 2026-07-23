# MCP 合成任务 + SFT 数据生成：完整问题记录与解决方案

> 目标：以现有 89 个可运行 benchmark 任务为参考，合成大量"类似但不同"的新任务，
> roll 出轨迹，最终产出 SFT 训练数据。
> 本文档记录从设计到交付过程中遇到的**所有问题**及**解决办法**，供以后复现/排障。

最终交付：**1312 个 SFT 样本**，位于
`services/mcp_eval/training_data/sft_synth_full.{json,jsonl}`。

---

## 目录

- [0. 背景与整体方案](#0-背景与整体方案)
- [1. 判分机制的理解](#1-判分机制的理解)
- [2. 问题：本地文件类任务不能自由换实体](#2-问题本地文件类任务不能自由换实体)
- [3. 问题：稀有 server 配额被过度放大](#3-问题稀有-server-配额被过度放大)
- [4. 问题：502 Bad Gateway（Clash 系统代理拦截本地请求）](#4-问题502-bad-gatewayclash-系统代理拦截本地请求)
- [5. 问题：403 Forbidden（MCP server 的 User-Agent 被目标站点拒绝）](#5-问题403-forbiddenmcp-server-的-user-agent-被目标站点拒绝)
- [6. 问题：:3000 服务连着重启前的旧容器连接](#6-问题3000-服务连着重启前的旧容器连接)
- [7. 问题：关闭 Clash 后容器一度连不上外网](#7-问题关闭-clash-后容器一度连不上外网)
- [8. 问题：pubmed 对复杂查询超时（60s）拖慢整体](#8-问题pubmed-对复杂查询超时60s拖慢整体)
- [9. 问题：单个工具失败导致整条轨迹崩溃](#9-问题单个工具失败导致整条轨迹崩溃)
- [10. 问题：阶段 3 提取 claim 串行太慢](#10-问题阶段-3-提取-claim-串行太慢)
- [11. 问题：自评分进程卡死](#11-问题自评分进程卡死)
- [12. 问题：误剔除 186 条含"未定义工具"的样本](#12-问题误剔除-186-条含未定义工具的样本)
- [附录：完整 pipeline 与最终数字](#附录完整-pipeline-与最终数字)
- [附录：以后重跑的标准操作步骤（SOP）](#附录以后重跑的标准操作步骤sop)

---

## 0. 背景与整体方案

### 环境架构（两个服务，缺一不可）

```
mcp_completion_script.py (roll 客户端)
        │ HTTP POST /v2/mcp_eval/run_agent
        ▼
:3000  mcp_completion 服务  (make run-mcp-completion)  ← agent loop，调 LLM + 工具
        │ HTTP POST /list-tools, /call-tool
        ▼
:1984  agent-environment 容器 (make run-docker)        ← 托管 ~20 个 MCP server 子进程
        │ 各 server 通过 npx/uvx 子进程访问外部 API
        ▼
      外部世界 (wikipedia / pubmed / openlibrary / met-museum ...)
```

- **:1984** 是 docker 容器，托管所有 MCP server（`make run-docker`，`docker run --rm -p 1984:1984`）。
- **:3000** 是 completion 服务（`make run-mcp-completion`），驱动 agent 多轮对话。
- LLM 用你的推理端点上的强模型（如 GPT-5.5）：`base_url=https://your-endpoint/v1`。

### 合成 pipeline（4 阶段，脚本都在 `eval_scripts/synth/`）

| 阶段 | 脚本 | 做什么 |
|---|---|---|
| 0 | `0_dump_env_inventory.sh` | dump 容器 `/data` 真实文件清单（供本地类任务用） |
| 1 | `1_extract_templates.py` | 从 89 个参考任务抽"模板"（骨架 + 配额） |
| 1 | `2_generate_tasks.py` | 用 GPT-5.5 按模板换实体生成候选任务 |
| 2 | `mcp_completion_script.py` | GPT-5.5 实际 roll 出轨迹（复用现有脚本） |
| 3 | `3_build_dataset.py` | 从真实答案提取 claim + 过滤 |
| 4 | `convert_csv_to_sft.py` | 转成 SFT 格式（复用现有脚本） |

### 核心设计原则：不信任生成，只信任执行

合成任务的实体真实性、答案正确性，**不靠 LLM 生成时保证**，而是靠：
1. **实际 roll 执行**——查不到的实体，模型答不出，答案为空/含"not found"。
2. **阶段 3 过滤**——空答案/失败标记/claim 不足的任务直接丢弃。
3. **claim 从真实答案提取**——留下的任务，claim 里的实体一定被工具验证过存在。

---

## 1. 判分机制的理解

**不是规则判分，是 LLM-as-judge 逐 claim 打分**（`mcp_evals_scores.py`）。

- 每个任务有一组 `GTFA_CLAIMS`（专家/模型写的原子事实断言）。
- judge 模型逐条判断模型答案是否覆盖该 claim：
  - `fulfilled` = 1.0 / `partially_fulfilled` = 0.5 / `not_fulfilled` = 0.0
- 任务的 `coverage_score` = 所有 claim 的平均分；`coverage_score >= 0.75` 视为通过。

**关键认知**：本项目里合成任务的 `GTFA_CLAIMS` 是**从模型自己 roll 的答案里提取的**
（阶段 3），所以拿模型答案对照它自己的 claim，本质是"自评分"，分数天然偏高（冒烟 0.889）。
这个评分主要作用是筛掉"claim 与答案表述不自洽"的少数样本，**不能验证答案正确性**。

---

## 2. 问题：本地文件类任务不能自由换实体

### 现象
冒烟阶段发现，`filesystem`/`cli-mcp-server` 类任务，GPT 把实体换成了
`/data/repos/ai-chatbot`、`cal.com` 等**环境里不存在的路径**。

### 根因
`/data` 目录是**固定内容**：只有 8 个 CSV + 11 个固定 repo（storyteller、snake-game、
tree-sitter-diff、balldontlie-mcp、metmuseum-mcp、mongodb-mcp-server 等）。
本地文件类任务的"实体"是环境里固定挂载的文件，**不能像书/电影那样自由替换**。
约 47% 的任务属于这类（纯本地 28 + 混合 27 个 template）。

### 解决
1. 新增 `0_dump_env_inventory.sh`，dump 容器 `/data` 真实清单（149 项）到 `env_inventory.txt`。
2. `2_generate_tasks.py` 里定义 `LOCAL_FS_SERVERS`（filesystem/cli/git/desktop-commander/
   memory/mcp-code-executor/mcp-server-code-runner），检测到这类 template 时，
   把真实 `/data` 清单注入 prompt，**强制 GPT 只在真实文件上换参数**（换子目录/换指标/
   换阈值/换问法），禁止编造路径。

### 验证
修复后，本地类任务改用真实项目（balldontlie-mcp、storyteller 等），检索类换真实书籍/电影，
不再编造。

---

## 3. 问题：稀有 server 配额被过度放大

### 现象
按 server 稀有度分配"每个 template 生成多少候选"时，个别 template 配额高达 174，
会导致同质化。

### 根因
稀有 server（weather 1 个、mcp-server-code-runner 1 个参考任务）权重 = 1/频次 很高，
若一个 template 同时用了多个稀有 server，权重叠加被过度放大。

### 解决
`1_extract_templates.py` 的 `compute_quotas()` 加 `--quota-cap`（默认 45）上限。
配额范围从 12..174 收敛到 12..45，总量 2208（接近 2670 目标量级）。

---

## 4. 问题：502 Bad Gateway（Clash 系统代理拦截本地请求）

> **这是本次最大的坑，导致最初一整批 roll 大量空答（38%）。**

### 现象
roll 时大量任务 `num_retry=3` 打满、`raw_conversation_history` 全空。
直接请求 `:3000/v2/mcp_eval/run_agent` 返回：
```
Server error '502 Bad Gateway' for url 'http://localhost:1984/list-tools'
```
但**直接 curl `:1984/list-tools` 却是 200**——矛盾。

### 排查过程
1. 容器日志里 `/list-tools` 全是 200 OK，说明 502 不是 :1984 返回的。
2. 用 httpx 复现：
   - `httpx.post('http://localhost:1984/list-tools')`（默认，读系统代理）→ **502**
   - `httpx.post(..., trust_env=False)`（绕过代理）→ **200**

### 根因
本机开了 **Clash 系统代理**。`:3000` 服务用 httpx 访问 `localhost:1984` 时，
httpx 读取系统代理配置，**把本地请求也发给了 Clash**，Clash 处理不了本地地址 → 502。
curl 默认不吃这套（或有 NO_PROXY），所以 curl 成功、httpx 失败。

### 解决
启动 `:3000` 服务时设置 `NO_PROXY`，让本地请求绕过代理：
```bash
NO_PROXY="localhost,127.0.0.1" no_proxy="localhost,127.0.0.1" make run-mcp-completion
```
同理，用 `mcp_completion_script.py` roll 时也带上这两个环境变量。

### 教训 / 长期注意
**只要本机开着 Clash（或任何系统代理），启动 `:3000` 服务和 roll 脚本前必须加
`NO_PROXY="localhost,127.0.0.1"`**，否则本地服务间调用必 502。
（`temp.sh` 里早就用了 `NO_PROXY="*"`，就是这个原因。）

---

## 5. 问题：403 Forbidden（MCP server 的 User-Agent 被目标站点拒绝）

### 现象
即使修好 502，`wikipedia`（403/空结果）、`pubmed`（403）、`osm`（403）三类任务仍失败。
从容器内 `urllib.request.urlopen('https://en.wikipedia.org')` → **HTTP 403 Forbidden**。

### 什么是 UA（User-Agent）
UA 是程序访问网站时"自我介绍"的一句话（夹在 HTTP 请求头里）。
- 正常浏览器：`Mozilla/5.0 ... Chrome/120 ...` → 网站放行
- 这些 MCP server：`WikipediaMCPServer/0.1.0` 等简陋 UA → 被 wikipedia/NCBI/nominatim 拒绝（403）

### 关键区分：403 ≠ 墙 ≠ 网络不通
- 一度以为是"被墙"/网络问题，但实测发现：
  - openlibrary / met-museum / ddg / arxiv → 默认就 200（能连）
  - wikipedia / pubmed(NCBI) / osm(nominatim) → 403（**连得上，但被拒**）
- **加正常浏览器 UA 后，wikipedia / NCBI 立刻变 200** → 确认是 UA 问题，不是网络。

### 根因（逐个定位）
UA 硬编码在各 server 源码里，无环境变量开关：
1. **wikipedia** (`wikipedia_client.py`)：
   - `self.user_agent = "WikipediaMCPServer/0.1.0 ..."`（被拒）
   - 且 `search()` 方法的 `requests.get(self.api_url, params=params)` **根本没传 headers**，
     用的是默认 `python-requests` UA。
2. **pubmed** (`pubmed_web_search.py`)：
   - `search_pubmed()` 的 `requests.get(search_url)` **没带 headers**（其他函数带了浏览器 UA）。

### 解决（容器内 patch）
把 UA 改成浏览器 UA，并给缺 headers 的 `requests.get` 补上：
```bash
cid=$(docker ps -q --filter ancestor=agent-environment:latest | head -1)
UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0 Safari/537.36"

# wikipedia: 改 self.user_agent + 给 search() 的 requests.get 补 headers
for f in $(docker exec $cid find / -name wikipedia_client.py 2>/dev/null); do
  docker exec $cid sed -i "s#WikipediaMCPServer/0.1.0 (https://github.com/rudra-ravi/wikipedia-mcp)#$UA#g" "$f"
  docker exec $cid sed -i 's#requests.get(self.api_url, params=params)#requests.get(self.api_url, params=params, headers={"User-Agent": self.user_agent})#g' "$f"
done

# pubmed: 给 search_pubmed() 的 requests.get 补 headers
for f in $(docker exec $cid find / -name pubmed_web_search.py 2>/dev/null); do
  docker exec $cid sed -i 's#response = requests.get(search_url)#response = requests.get(search_url, headers={"User-Agent": "'"$UA"'"})#g' "$f"
done
```
**改完必须重启容器**让 server 子进程重新加载（`docker restart <cid>`）。

### 重要坑：patch 不持久
- MCP server 是**常驻子进程**，改磁盘文件对已运行进程无效，必须 `docker restart`。
- patch 改的是**容器内文件**：`docker restart`（重启同一容器）**保留**；
  但 `make run-docker`（`--rm` 起全新容器）会**丢失**，届时 403 复现。
- 想永久固化需写进 Dockerfile 重建镜像（本次未做）。

### 验证
重启后 wikipedia / pubmed / osm 全部返回真实数据（osm 加 UA 后也 200，之前的 403 是临时限流）。

---

## 6. 问题：:3000 服务连着重启前的旧容器连接

### 现象
`docker restart` 容器后（修 UA），通过 `:3000` 请求仍然 502，但直接打 `:1984` 正常。

### 根因
`:3000` 服务是**容器重启之前**启动的，它内部 httpx 连接池握着**重启前旧容器的连接**，
旧连接已失效。

### 解决
**每次重启 `:1984` 容器后，必须跟着重启 `:3000` 服务**（`make run-mcp-completion`，带 NO_PROXY）。

### 教训
`:1984` 容器和 `:3000` 服务有依赖顺序：**先起容器，再起 completion 服务**；
**容器重启后，completion 服务也要重启**。

---

## 7. 问题：关闭 Clash 后容器一度连不上外网

### 现象
为排查代理问题关掉 Clash 后，容器内访问 openlibrary → `Network is unreachable`（Errno 101）。

### 根因 / 结论
一度以为"容器外网依赖 Clash"，但重新开 Clash 后实测：容器访问 openlibrary 200（1s）。
判断是**关代理瞬间的网络抖动**，容器外网不依赖 Clash 系统代理（容器有自己的网络栈）。

### 最终结论
- **开 Clash**：容器外网正常 + 本地请求需 `NO_PROXY` 绕过代理（否则 502）。
- 正确姿势：**开着 Clash，`:3000` 服务和 roll 脚本带 `NO_PROXY="localhost,127.0.0.1"`**，
  本地请求绕过代理、外网请求照常走。

---

## 8. 问题：pubmed 对复杂查询超时（60s）拖慢整体

### 现象
环境全修好后，roll 到 pubmed 类任务时 `pubmed_search_pubmed_advanced` /
`pubmed_search_pubmed_key_words` **60s 超时**，一批任务卡住。
（简单查询如 `cancer` 单测 <0.1s，但合成任务的复杂查询——特定作者+特定日期范围——很慢。）

### 决策
剔除所有含 pubmed 工具的候选任务，只跑其余。

### 做法
```python
# 从 candidates_full.csv 剔除 ENABLED_TOOLS 含 'pubmed' 的行
kept = [r for r in rows if 'pubmed' not in r['ENABLED_TOOLS']]
# 原 2171 → 剔除 633（含 pubmed 的）→ 保留 1538
```
注意：633 里含**混合类** template（如 met-museum+pubmed+whois），只要 ENABLED_TOOLS 出现
pubmed 就一并剔除（宁可错杀，因为混合任务只要碰一次 pubmed 就可能 60s 超时）。
20 个 template 含 pubmed（不止纯 pubmed 的 8 个），因高配额放大到 633。

### 效果
剔除后 roll 立刻顺畅，成功率从 62% 升到 **98%**。

---

## 9. 问题：单个工具失败导致整条轨迹崩溃

### 现象
`agent_eval.py` 里，任何一个工具调用抛异常（含 60s 超时），
第 98-105 行直接 `raise Exception`，**整条轨迹崩溃**报错，前面的工作全废。

### 尝试的修改（后又还原）
一度改成"把工具错误作为 tool result 回传给模型，让它继续"：
```python
except Exception as error:
    error_message = ToolCallOutputMessage(role="tool",
        content=[TextContent(type="text", text=f"Tool execution failed: {error}")],
        tool_call_id=tool_call.id)
    all_messages.append(error_message)
    yield AgentOutput("message", error_message.model_dump())
```

### 最终决策：还原为 raise
实测发现：不 raise 的话，工具卡 60s 超时后还继续跑，**注定失败的任务反而拖更久**。
raise 让坏任务快速失败退出，整体吞吐更高。所以**还原成 raise**。
（这个改动需重启 `:3000` 生效。）

---

## 10. 问题：阶段 3 提取 claim 串行太慢

### 现象
`3_build_dataset.py` 原为同步 for 循环，逐个调 LLM API 提取 claim，60s 才 10 个，
1536 个要跑约 2.5 小时。

### 解决
改用 `ThreadPoolExecutor` 并发（`--concurrency 8`），主线程消费 futures 结果并逐个 flush 落盘
（保留 resume + 实时进度）。速度从 10 个/分钟 提到约 120 个/分钟（**10 倍**）。

---

## 11. 问题：自评分进程卡死

### 现象
`mcp_evals_scores.py` 评分 1312 个任务，跑了 55 分钟无结果，CPU 时间不动、
最后一次采样 0 活跃连接，疑似卡死。

### 排查
- 先误判为"卡死"（抓错进程，看的是外层 `uv run` wrapper）。
- 实测单次 judge 仅 3s，理论 6245 条 claim ÷ 8 并发 × 3s ≈ 39 分钟应完成。
- 但脚本是**全部 async gather 完才一次性写结果**（不落盘中间进度），
  且疑似大量请求卡在 tenacity 重试退避（judge 要求 JSON，GPT-5.5 偶尔返回非法 JSON 触发
  最多 6 次指数退避、单次最多 60s）→ 表现为长时间无产出、像卡死。

### 决策
**跳过评分，1312 个全部转 SFT**。理由：
- 评分本质是"自己给自己打分"（claim 从答案提取），价值有限。
- 数据质量已由**执行兜底 + 阶段 3 过滤**保证。
- 评分又慢又卡，体验差。

### 教训
`mcp_evals_scores.py` 不适合大批量 + 不落盘中间结果；GPT-5.5 当 judge 慢且 JSON 不稳。
如需评分，应改为逐条落盘 + 更稳的 evaluator。

---

## 12. 问题：误剔除 186 条含"未定义工具"的样本

### 现象
转 SFT 时出现 warning：某些任务的工具（`f1-mcp-server_*`、`rijksmuseum-server_*`、
`balldontlie_*`）在 `list-tools.json` 里找不到定义。一度剔除这 186 条（1312→1126）。

### 三层工具清单的区别（关键认知）
| 清单 | 是什么 | 含 f1/rijksmuseum 吗 |
|---|---|---|
| 任务的 `ENABLED_TOOLS` | 原 benchmark 声明"可用"的工具 | ✅ 列了 |
| `list-tools.json` | 完整工具定义快照（36 server） | ❌ 没有 |
| 在线环境 `:1984` | 实际跑着的 server（19-20 个） | ❌ 也没有 |

f1/rijksmuseum/balldontlie **从没在本项目部署过**——原 benchmark 假设有，本环境没上线。

### 真相：剔除是多余的
- `convert_csv_to_sft.py` **本来就只把有定义的工具写进 tools 字段**，未定义的只 warning 不写入。
- 所以最初 1312 条的 tools 字段**本来就是干净的**（不含 f1 等）。
- 模型**从没调用过**这些未定义工具（环境里没有，调不了）——校验：
  1312 样本、9491 次工具调用，**调用了但 tools 未定义的 = 0**。

### 最终处理：全部救回
重新转全部 1312 条。tools 字段天然只含已定义工具，轨迹完整。
被"救回"的样本（如 `6888...syn000`）：tools 8 个（自动去掉 f1），轨迹完整无损。

### 结论
**模型实际调用的每个工具，在 tools 字段里都有定义**（环境保证：能调的 ⊆ 在线 ⊆ list-tools.json）。
最终数据自洽。

---

## 附录：完整 pipeline 与最终数字

| 阶段 | 输入 | 输出 | 数字 |
|---|---|---|---|
| 1. 抽模板 | 89 参考任务 | `templates.json` | 89 template，配额 12..45，总 2208 |
| 1. 生成候选 | templates.json | `candidates_full.csv` | 2171 候选（87/89 template） |
| （剔 pubmed） | | `candidates_nopubmed.csv` | 剔 633 → 1538 |
| 2. roll | candidates_nopubmed | `synth_roll_full.csv` | 1567 roll，**1536 有答案（98%）** |
| 3. 提取 claim | roll 结果 | `synth_tasks_full.csv` | 保留 **1312**（丢 255） |
| 4. 转 SFT | synth_tasks + 轨迹 | `sft_synth_full.{json,jsonl}` | **1312 样本** |

### 阶段 3 的过滤规则（两道关卡）
1. **答案有效性**（`is_failure_answer`）：
   - 空/过短答案（<20 字符）→ 丢（43 个）
   - 含失败标记词（`not found`/`does not exist`/`无法找到` 等）→ 丢（33 个）
2. **claim 数量**（`--min-claims 3`）：
   - 提取出的 claim < 3 条 → 丢（179 个：2条125 + 1条32 + 0条22）
- 合计丢 255，保留 1286（+冒烟 26 = 1312）。

### 最终交付文件
- `services/mcp_eval/training_data/sft_synth_full.json`（1312 样本）
- `services/mcp_eval/training_data/sft_synth_full.jsonl`
- `services/mcp_eval/eval_scripts/synth/synth_tasks_full.csv`（标准 5 列，可当新 benchmark）

---

## 附录：以后重跑的标准操作步骤（SOP）

### 前置（每次都要）
```bash
# 1. 起 MCP 环境容器
make run-docker      # :1984

# 2.（若开着 Clash）修 UA —— 仅当需要 wikipedia/pubmed/osm 时
#    见第 5 节 patch 脚本，然后 docker restart <cid>
#    注意：make run-docker 起的是全新容器，patch 会丢，需重新 patch

# 3. 起 completion 服务 —— 必须带 NO_PROXY（开着 Clash 时）
NO_PROXY="localhost,127.0.0.1" no_proxy="localhost,127.0.0.1" make run-mcp-completion   # :3000

# 4. 每次重启 :1984 容器后，:3000 服务也要重启（第 6 节）
```

### 合成流程
```bash
cd services/mcp_eval
export LLM_API_KEY=sk-xxx

# 阶段 0：dump 环境清单（本地类任务需要）
bash eval_scripts/synth/0_dump_env_inventory.sh

# 阶段 1a：抽模板
uv run python eval_scripts/synth/1_extract_templates.py

# 阶段 1b：生成候选（全量去掉 --limit/--per-template；支持 resume）
LLM_API_KEY=$LLM_API_KEY uv run python eval_scripts/synth/2_generate_tasks.py \
  --output eval_scripts/synth/candidates_full.csv

# （可选）剔除慢/不稳定的 server（如 pubmed）
python3 -c "import csv;csv.field_size_limit(10**9);rows=list(csv.DictReader(open('eval_scripts/synth/candidates_full.csv')));w=csv.DictWriter(open('eval_scripts/synth/candidates_nopubmed.csv','w',newline=''),fieldnames=rows[0].keys());w.writeheader();w.writerows([r for r in rows if 'pubmed' not in r['ENABLED_TOOLS']])"

# 阶段 2：roll（带 NO_PROXY；支持 resume，同命令重跑即续跑）
NO_PROXY="localhost,127.0.0.1" no_proxy="localhost,127.0.0.1" \
uv run python mcp_completion_script.py \
  --model "openai/GPT-5.5" \
  --input "eval_scripts/synth/candidates_nopubmed.csv" \
  --no-filter --concurrency 5 \
  --output "synth_roll_full.csv"

# 阶段 3：提取 claim + 过滤（并发；支持 resume）
LLM_API_KEY=$LLM_API_KEY uv run python eval_scripts/synth/3_build_dataset.py \
  --roll-result completion_results/synth_roll_full.csv \
  --output eval_scripts/synth/synth_tasks_full.csv \
  --concurrency 8

# 阶段 4：转 SFT（merge 轨迹后转换）
uv run python -c "import pandas as pd;s=pd.read_csv('eval_scripts/synth/synth_tasks_full.csv');r=pd.read_csv('completion_results/synth_roll_full.csv')[['TASK','script_model_response','raw_conversation_history']];s.merge(r,on='TASK',how='inner').to_csv('completion_results/synth_selfscore_full.csv',index=False)"
uv run python convert_csv_to_sft.py \
  --input completion_results/synth_selfscore_full.csv \
  --tools ../../list-tools.json \
  --output training_data/sft_synth_full.json --system-prompt
uv run python convert_json_to_jsonl.py \
  --input training_data/sft_synth_full.json \
  --output training_data/sft_synth_full.jsonl
```

### 排障速查
| 症状 | 原因 | 解决 |
|---|---|---|
| 502 Bad Gateway | Clash 拦截本地请求 | `:3000` 服务加 `NO_PROXY="localhost,127.0.0.1"` |
| wikipedia/pubmed 403/空 | server UA 被拒 | 容器内 patch UA + `docker restart`（第 5 节） |
| 重启容器后仍 502 | :3000 连着旧容器连接 | 重启 :3000 服务 |
| 大量空答、retry=3 | 多为上面 502 / 或 server 超时 | 先查代理，再查具体 server |
| pubmed 60s 超时 | 复杂查询慢 | 剔除含 pubmed 的候选 |
| roll 卡住/慢 | 单工具超时 | 已保留 raise 快速失败；降并发 |
| tools 定义缺失 warning | ENABLED_TOOLS 含未部署 server | 无害，convert 自动忽略未定义工具 |
