# three.js Good Case Radar

每天重新扫描 three.js 美术世界相关的新内容，按来源质量、相关性、代码可用性和互动信号预筛，再用 AI 输出：原文链接、核心亮点、可借鉴价值。

## Sources

| 来源 | 默认可用 | 配置 | 定位 |
|---|---:|---|---|
| GitHub | 是（低限额） | `GITHUB_TOKEN` 可提高限额 | 开源代码/工程实现 |
| GitLab | 是 | 无 | 公共开源项目 |
| npm | 是 | 无 | 新增/更新的 three.js 生态包 |
| three.js Forum | 是 | 无 | 专业社区的一手作品与讨论 |
| Bluesky | 是 | 匿名；403 时配置免费 `BSKY_HANDLE`、`BSKY_APP_PASSWORD` | 创作者发布与展示 |
| X / Twitter | 否 | `X_BEARER_TOKEN` | 高频创作者动态 |
| X 间接搜索 | 是 | 无 | Google News RSS 发现部分公开 X 帖子；覆盖不完整 |
| Discord | 否 | `DISCORD_BOT_TOKEN`、`DISCORD_CHANNEL_IDS` | 指定社区频道内容 |
| DEV Community | 是 | 无 | 教程、作品拆解与代码文章 |
| Reddit | 是（尽力而为） | 无 | 社区作品、讨论与外链 |
| Hacker News | 是 | 无 | 技术作品发布与讨论 |
| Mastodon | 是 | 无 | `#threejs` 创作者动态 |
| Codrops / web.dev RSS | 是 | 无 | 编辑精选的创意开发文章与案例 |
| YouTube | 否 | `YOUTUBE_API_KEY` | 视频展示、制作过程与教程 |

Twitter、Discord 和 YouTube 使用官方 API。Discord Bot 必须已加入目标服务器并具有目标频道的读取权限；频道 ID 用逗号分隔。没有配置的来源会被跳过，并记录在 `output/last-run.json`。

未配置 `X_BEARER_TOKEN` 时，`x_search` 仍会通过免费的公开搜索索引补充一部分 X 内容。
这类结果会标记为 `source=x_search`、`source_tier=indirect_discovery` 和
`indirect_link=true`，链接可能先经过 Google 跳转；它不等同于 X 官方 API，不能保证完整覆盖、
实时性或互动数据。配置官方 Token 后，两种来源可以同时运行并由全局去重处理。

Bluesky 默认使用匿名公开 AppView。如果当前网络返回 403，可在 Bluesky 的 Settings → Privacy and security → App passwords 创建专用密码，将账号 handle 和专用密码写入 `.env`。不要使用账号主密码。

## Run

```bash
cp .env.example .env
./venv/bin/python main.py
```

常用参数：

```bash
./venv/bin/python main.py --hours 24 --max-cases 50 --ai-limit 25
```

- `--ai-limit 0`：完全不调用 AI，仍生成可读日报。
- `--include-seen`：重新输出历史已见案例；默认跨天不重复推送。
- `--minimum-score`：提高可减少噪声，降低可扩大召回。

输出为 `output/cases-YYYY-MM-DD.md`、同名 JSON，以及包含各来源健康状态的 `output/last-run.json`。
同一天重复运行不会覆盖旧结果，而是按链接去重后合并进当天日报；日期统一按新加坡时区生成。

同时会生成 `output/index.html` 可视化仪表盘。直接双击即可打开，无需启动服务器；页面支持搜索、
来源筛选、有无代码筛选、推荐分/预筛分/发布时间排序和案例详情查看。每次运行 `main.py` 后网页会
随当天合并结果自动更新。

为了提高案例判断质量，进入 AI 阶段的候选会尽量读取 GitHub README、npm README 和 three.js Forum
正文。抓取内容及 AI 结果分别缓存在 `output/enrichment-cache.json` 和
`output/analysis-cache.json`，重复运行时不会无谓地重复请求。AI 请求并发执行，并设有超时和降级摘要，
单个请求失败不会阻止日报生成。

JSON 中的预筛分位于 `heuristic_score`，AI 推荐分位于
`analysis.recommendation_score`。`last-run.json` 中的 `published_this_run` 是本轮新增数，
`daily_total` 是当天合并后的总数；来源局部失败会记录在对应来源的 `warnings` 中。

## Daily scheduling (cron)

每天新加坡时间 09:00 执行：

```cron
CRON_TZ=Asia/Singapore
0 9 * * * cd /absolute/path/to/threejs-agent && ./venv/bin/python main.py >> output/cron.log 2>&1
```

“每日扫描”与“去重推送”是两件事：所有来源每天都会重新查询最近窗口，但 `seen.json` 会阻止已经评估过的链接再次进入日报。
