# 抖音无水印视频下载工具

一个纯 Python 工具：粘贴抖音分享文本，自动解析并下载无水印视频/图文作品。支持命令行和 Web 界面两种使用方式。

## 功能

- 🎬 **普通视频下载**：一键下载无水印 mp4
- 🖼️ **图文作品支持**：自动识别图文，下载全部图片 + 背景音乐
- 🖥️ **Web 界面**：基于 Flask 的可视化界面，浏览器一键下载
- 📦 **零额外依赖**：核心仅需 `requests`，Web 版额外需要 `Flask`

## 原理

参考公开博客思路，整体流水线为：

1. 从分享口令文本中用正则提取抖音短链接（如 `https://v.douyin.com/xxxxx/`）。
2. 以**移动端 User-Agent** 请求短链并跟随重定向，从落地 URL 解析出视频唯一 ID（`aweme_id`）。
3. 用 `aweme_id` 获取元数据与播放/图片地址：
   - 主路径：请求分享页 HTML，解析内嵌的 `window._ROUTER_DATA` JSON；
   - 备用路径：调用 `iesdouyin` 的 `iteminfo` 接口（主路径失败时自动降级）。
4. 视频：将播放地址中的 `playwm`（watermark）替换为 `play`，得到**无水印**直链。
5. 图文：提取 `images` 列表与背景音乐地址。
6. 以移动端 UA + `Referer` 流式下载到本地（`Referer` 用于绕过 CDN 防盗链 403）。

## 安装

需要 Python 3.8+。

### 仅命令行版

```bash
pip install requests
```

### 含 Web 界面

```bash
pip install -r requirements.txt
```

## 使用

### 命令行

基本用法（下载到默认目录 `downloads/`）：

```bash
python -m douyin_dl "4.30 复制打开抖音，看看【张聪的作品】# 跑山  https://v.douyin.com/N02ol18iCT0/ Wmd:/ :8pm E@U.yT 03/07"
```

指定输出目录：

```bash
python -m douyin_dl "<分享文本>" -o D:\videos
```

仅解析、不下载：

```bash
python -m douyin_dl "<分享文本>" --dry-run
```

#### 参数说明

| 参数 | 说明 |
|------|------|
| `share_text` | （必填）抖音分享文本或链接，直接整段粘贴即可 |
| `-o` / `--output` | 输出目录，默认 `downloads` |
| `--dry-run` | 仅解析，打印视频 ID 与直链，不下载 |

### Web 界面

启动服务：

```bash
python web/app.py
```

浏览器访问：http://127.0.0.1:5000

粘贴分享文本 → 点击「立即下载」→ 点击文件列表的下载按钮即可保存到本地。

## 实测情况（冒烟验证）

已用示例分享文本完成**真实联网端到端验证**（2026-06，接口可用）：

**普通视频：**

```
已识别链接: https://v.douyin.com/N02ol18iCT0/
视频ID: 7655296504243981990
标题: #跑山
无水印直链: https://aweme.snssdk.com/aweme/v1/play/?line=0&ratio=720p&video_id=v0d00fg10000d8uh6fvog65rjb8fs100
已保存: downloads\#跑山.mp4
```

**图文作品：**

```
已识别链接: https://v.douyin.com/YtSrgh_qhsI/
视频ID: 7656454128353518410
标题: 真的求求了，苹果怎样可以安装exe格式呢。#苹果电脑 #安装教程
类型: 图文作品 (1 张图片)
已保存: downloads\真的求求了，苹果怎样可以安装exe格式呢。#苹果电脑 #安装教程.webp
```

- ✅ 从分享文本提取短链并经重定向解析出真实 `aweme_id`；
- ✅ 普通视频完成 `playwm`→`play` 去水印；
- ✅ 图文作品自动识别，下载图片（webp/jpg/png）与背景音乐；
- ✅ `--dry-run` 仅解析模式正常；
- ✅ Web 界面解析、下载、文件预览全流程正常。

> 抖音接口随时可能调整，以上实测于 2026-06 通过；若日后失效，见下方「常见问题」。

## 项目结构

```
douyin_dl/
├── parser.py       # 分享文本 → 短链 → aweme_id
├── extractor.py    # aweme_id → VideoInfo（视频/图文）
├── downloader.py   # 直链 → 落地文件（进度条、防盗链、文件名清洗）
├── cli.py          # 命令行入口
└── __main__.py     # python -m douyin_dl 入口

web/
├── app.py          # Flask 后端 + API
└── templates/
    └── index.html  # 前端页面
```

## 常见问题

- **解析失败 / 提示需要签名**：抖音接口会不定期调整，公开的 `iteminfo` 接口可能失效或需要 `a_bogus`/`X-Bogus` 等签名参数。本工具已将解析层模块化（主路径 + 备用路径），如两条路径都失效，请更新 `douyin_dl/extractor.py` 中的解析逻辑。
- **下载报 HTTP 403**：通常是防盗链导致，确认请求带了正确的 `Referer`（本工具默认已带）；也可能是直链已过期，重新解析一次即可。
- **解析不到 aweme_id**：抖音链接形态较多，如遇到新形态可在 `douyin_dl/parser.py` 的 `_AWEME_ID_PATTERNS` 中补充正则。
- **图文作品下载下来是音频/看不了**：抖音的图文作品本质是图片集合 + 背景音乐，下载的 `.webp`/`.jpg` 是图片文件，可用任何图片查看器打开。

## 免责声明

本工具仅供个人学习与技术研究使用，请勿用于任何商业或侵犯他人合法权益的用途。下载的内容版权归原作者所有，请尊重创作者权益，遵守抖音平台的服务条款及相关法律法规。因使用本工具产生的一切后果由使用者自行承担。
