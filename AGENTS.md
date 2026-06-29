# AGENTS.md

面向后续开发者与 AI 代理的项目说明。读完应能快速定位代码、运行验证、并在抖音接口变动时知道改哪里。

## 项目概述

`douyin_dl` 是一个**抖音无水印下载**工具（纯 Python）。输入一段抖音分享文本（含 `https://v.douyin.com/xxx/` 短链），输出无水印视频文件或图文作品图片。

支持两种使用方式：
- **CLI 命令行**：`python -m douyin_dl "<分享文本>"`
- **Web 界面**：`python web/app.py`，浏览器访问 http://127.0.0.1:5000

核心原理：
- 视频：播放地址里 `playwm`（watermark，带水印）替换为 `play` 即得无水印直链。
- 图文：从 `images` 字段取图片列表（`download_url_list` 优先），附背景音乐。

完整链路：

```
分享文本 → 提取短链 → 重定向解析 aweme_id → 取播放/图片地址(去水印)→ 流式下载
```

## 运行环境

- Python 3，核心依赖 `requests`，Web 版额外需要 `Flask`（见 [requirements.txt](requirements.txt)）。
- 安装与运行：

```bash
pip install -r requirements.txt

# 命令行
python -m douyin_dl "<分享文本>"                 # 下载到 ./downloads
python -m douyin_dl "<分享文本>" -o D:\videos      # 指定输出目录
python -m douyin_dl "<分享文本>" --dry-run         # 仅解析、不下载

# Web 界面
python web/app.py                                   # 启动后访问 http://127.0.0.1:5000
```

## 代码结构与职责

### 核心模块 [douyin_dl/](douyin_dl/)

各模块单一职责，**业务模块互不下载、纯函数易测**：

| 文件 | 职责 | 关键符号 |
|------|------|----------|
| [parser.py](douyin_dl/parser.py) | 分享文本 → 短链 → `aweme_id` | `extract_share_url`、`resolve_aweme_id`、`MOBILE_UA`、`ParseError` |
| [extractor.py](douyin_dl/extractor.py) | `aweme_id` → `VideoInfo`（视频/图文） | `extract_video_info`、`VideoInfo`、`ExtractError` |
| [downloader.py](douyin_dl/downloader.py) | 直链 → 落地文件（进度、防盗链、文件名清洗） | `download`、`sanitize_filename`、`DownloadError` |
| [cli.py](douyin_dl/cli.py) | argparse 入口，串联全流程，统一异常 → 退出码 | `main(argv) -> int` |
| [__main__.py](douyin_dl/__main__.py) | `python -m douyin_dl` 入口 | — |

数据流：`cli.main` 依次调用 `extract_share_url` → `resolve_aweme_id` → `extract_video_info` → `download`。

### Web 模块 [web/](web/)

| 文件 | 职责 |
|------|------|
| [app.py](web/app.py) | Flask 应用，提供解析/下载/文件下载三个 API + 首页渲染 |
| [templates/index.html](web/templates/index.html) | 单页前端界面（渐变紫色主题，纯原生 JS） |

Web 接口：
- `POST /api/parse` — 仅解析，返回 `VideoInfo` JSON
- `POST /api/download` — 解析 + 下载到服务器，返回文件列表
- `GET /api/file/<filename>` — 下载已保存的文件

## 关键约定（改代码时请遵守）

1. **`requests` 一律延迟导入**：在函数内部 `import requests`，而非模块顶层。目的是让模块在未装 `requests` 的环境也能被 import（便于离线单测）。新增联网代码请沿用此约定。
2. **依赖注入便于测试**：`resolve_aweme_id`、`extract_video_info`、`download` 都接受可选 `session` 参数。单测时传入假的 session 对象即可离线验证解析逻辑，不要写死全局请求。
3. **移动端 UA 是必需的**：抖音部分链接拒绝桌面 UA。统一用 `parser.MOBILE_UA`，不要各处硬编码。
4. **下载需带 `Referer`**：CDN 有防盗链，缺 Referer 会 403。见 `download` 的 `referer` 参数（默认 `https://www.douyin.com/`）。
5. **异常分层**：每个模块定义自己的异常（`ParseError`/`ExtractError`/`DownloadError`），`cli.main` 捕获后转退出码（成功 0、已知错误/未知错误均 1）。新增失败路径请抛对应模块异常，不要直接 `print` + `exit`。
6. **去水印只在一处**：`extractor._to_no_watermark` 负责 `playwm`→`play`，不要在别处重复替换。
7. **文件扩展名自动识别**：`downloader.download` 根据传入 `filename` 的扩展名决定保存格式（`.webp`/`.jpg`/`.mp3`/`.mp4` 等），未识别才默认补 `.mp4`。

## VideoInfo 数据结构

[extractor.VideoInfo](douyin_dl/extractor.py) 是核心数据类：

| 字段 | 类型 | 说明 |
|------|------|------|
| `aweme_id` | str | 作品唯一 ID |
| `title` | str | 标题/描述 |
| `video_url` | str | 无水印视频直链（图文作品为空字符串） |
| `is_image_post` | bool | 是否为图文作品 |
| `image_urls` | list[str] | 图文作品图片 URL 列表 |
| `music_url` | str \| None | 图文作品背景音乐 URL |

判断图文作品：`images` 字段存在且非空即视为图文（主路径和备用路径都做了同样判断）。

## 提取的双路径与降级（最易随抖音变动的部分）

`extract_video_info` 按顺序尝试两条路径，任一成功即返回，全失败抛 `ExtractError`：

1. **主路径** `_from_share_page`：请求 `https://www.iesdouyin.com/share/video/{aweme_id}/`，正则抠出内嵌的 `window._ROUTER_DATA` JSON，取 `loaderData.*.videoInfoRes.item_list[0]`。
2. **备用路径** `_from_iteminfo_api`：调用公开 `iteminfo` 接口（老接口，可能已需签名 `a_bogus`/`X-Bogus`，常失效）。

> **接口失效时改这里。** 若两条路径都拿不到数据，多半是抖音改了页面结构或加了签名校验。优先更新 `_from_share_page` 的正则 `_ROUTER_DATA_PATTERN` 与 JSON 取值路径；如需签名，新增第三条路径并保持降级链。
>
> **图文作品相关字段也在此维护**：如果抖音改了图文作品的数据结构（如 `images` 改名或嵌套层级变化），同步修改两条路径中的图文检测逻辑。

## 验证

无独立测试框架，目前靠手动冒烟。最小验证：

```bash
# 仅解析（不写文件，最快验证接口是否可用）
python -m douyin_dl "<分享文本>" --dry-run
# 完整下载，检查 downloads/ 下生成有效文件
python -m douyin_dl "<分享文本>"
```

判定成功：
- **视频**：`--dry-run` 打印 `视频ID`、`标题`、`/play/`（而非 `/playwm/`）直链；完整运行生成的 `.mp4` 文件头含 `ftyp`。
- **图文**：`--dry-run` 显示「类型: 图文作品」及图片列表；完整运行生成 `.webp`/`.jpg` 等图片文件（WEBP 文件头为 `RIFF`+`WEBP`）。
- **Web 版**：访问首页能正常加载；提交分享文本后返回文件列表并可下载。

如新增单元测试，放 `tests/`，用注入的假 session 覆盖 `parser`/`extractor` 解析逻辑与 `sanitize_filename`（均为纯逻辑、无需联网）。

## 已知限制与注意事项

- **抖音接口随时可能调整**，公开接口可能失效或要求签名。维护重点见上节「提取的双路径」。
- **沙箱/受限环境联网**：若 `pip` 默认目录不可写，可 `pip install requests --target <可写目录>` 并把该目录加入 `PYTHONPATH` 后运行；Web 版同理安装 Flask 到本地目录（[web/app.py](web/app.py) 已支持 `_vendor/` 目录自动加载）。
- `downloads/` 与 `*.mp4` 已在 [.gitignore](.gitignore) 中忽略，下载产物不会进版本库。
- 文件名来自视频标题，经 `sanitize_filename` 清洗非法字符并截断到 80 字；标题为空时回退用 `aweme_id`。
- 图文作品图片优先取 `download_url_list`（无水印），取不到才用 `url_list`。

## 规格文档

需求与任务规格在 [.trae/specs/build-douyin-downloader/](.trae/specs/build-douyin-downloader/)（`spec.md` / `tasks.md` / `checklist.md`）。新增较大功能时，先更新规格再实现。
