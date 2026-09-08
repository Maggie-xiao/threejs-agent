# three.js Good Case Radar

每天重新扫描 three.js 美术世界相关的新内容，按来源质量、相关性、代码可用性和互动信号预筛，再用 AI 输出：原文链接、核心亮点、可借鉴价值。

## Sources

| 来源 | 默认可用 | 配置 | 定位 |
|---|---:|---|---|
| GitHub | 是（低限额） | `GITHUB_TOKEN` 可提高限额 | 开源代码/工程实现 |
| three.js Forum | 是 | 无 | 专业社区的一手作品与讨论 |
| Bluesky | 尽力而为 | 无 | 创作者发布与展示；部分网络环境会返回 403 |
| X / Twitter | 否 | `X_BEARER_TOKEN` | 高频创作者动态 |
| Discord | 否 | `DISCORD_BOT_TOKEN`、`DISCORD_CHANNEL_IDS` | 指定社区频道内容 |
| DEV Community | 是 | 无 | 教程、作品拆解与代码文章 |
| Reddit | 是（尽力而为） | 无 | 社区作品、讨论与外链 |
| Hacker News | 是 | 无 | 技术作品发布与讨论 |
| Mastodon | 是 | 无 | `#threejs` 创作者动态 |
| YouTube | 否 | `YOUTUBE_API_KEY` | 视频展示、制作过程与教程 |

Twitter、Discord 和 YouTube 使用官方 API。Discord Bot 必须已加入目标服务器并具有目标频道的读取权限；频道 ID 用逗号分隔。没有配置的来源会被跳过，并记录在 `output/last-run.json`。

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

## Daily scheduling (cron)

每天新加坡时间 09:00 执行：

```cron
CRON_TZ=Asia/Singapore
0 9 * * * cd /absolute/path/to/threejs-agent && ./venv/bin/python main.py >> output/cron.log 2>&1
```

“每日扫描”与“去重推送”是两件事：所有来源每天都会重新查询最近窗口，但 `seen.json` 会阻止已经交付过的链接再次进入日报。
