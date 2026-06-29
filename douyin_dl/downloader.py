"""视频文件下载。"""

import os
import re
import sys

from douyin_dl.parser import MOBILE_UA

# 非法字符:Windows 与通用文件系统禁止的字符,以及换行/制表符。
_ILLEGAL_CHARS = re.compile(r'[\\/:*?"<>|\r\n\t]')
# 连续空白。
_WHITESPACE = re.compile(r"\s+")

_MAX_LEN = 80
_DEFAULT_NAME = "douyin_video"


class DownloadError(Exception):
    """下载失败。"""


def sanitize_filename(name: str) -> str:
    """清洗文件名中的非法字符。"""
    if not name:
        return _DEFAULT_NAME
    # 替换非法字符为下划线。
    cleaned = _ILLEGAL_CHARS.sub("_", name)
    # 把连续空白压成单个空格,并 strip 首尾空白。
    cleaned = _WHITESPACE.sub(" ", cleaned).strip()
    # 去除首尾可能残留的下划线/点(避免 ".."、"_" 之类无意义命名)。
    cleaned = cleaned.strip("._ ")
    # 超长截断。
    if len(cleaned) > _MAX_LEN:
        cleaned = cleaned[:_MAX_LEN].strip("._ ")
    if not cleaned:
        return _DEFAULT_NAME
    return cleaned


def download(
    video_url: str,
    output_dir: str,
    filename: str,
    referer: str = "https://www.douyin.com/",
    session=None,
    timeout: int = 30,
) -> str:
    """以移动端 UA + Referer 流式下载文件到 output_dir/filename,显示进度,返回保存路径。

    output_dir 不存在时自动创建。下载失败抛 DownloadError。
    文件名已有扩展名时直接使用,否则自动添加扩展名。
    """
    # 延迟 import,保证模块在未安装 requests 的环境也能离线导入。
    import requests

    # 自动创建输出目录。
    os.makedirs(output_dir, exist_ok=True)

    # 构造文件名:清洗 + 补后缀。
    name = sanitize_filename(filename)
    # 根据已有扩展名自动判断类型,未识别时默认 .mp4。
    ext = os.path.splitext(name)[1].lower()
    if ext in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
        # 图片/动图直接使用原名。
        save_name = name
    elif ext == ".mp3":
        save_name = name
    else:
        # 未知类型默认当视频处理。
        if not name.lower().endswith(".mp4"):
            name += ".mp4"
        save_name = name
    save_path = os.path.join(output_dir, save_name)

    if session is None:
        session = requests.Session()

    headers = {
        "User-Agent": MOBILE_UA,
        # Referer 用于绕过抖音 CDN 防盗链(否则可能 403)。
        "Referer": referer,
    }

    try:
        resp = session.get(
            video_url,
            headers=headers,
            stream=True,
            timeout=timeout,
            allow_redirects=True,
        )
        resp.raise_for_status()

        # 读取总大小(可能缺失)。
        total = resp.headers.get("Content-Length")
        total = int(total) if total and total.isdigit() else 0

        downloaded = 0
        with open(save_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                if not chunk:
                    continue
                f.write(chunk)
                downloaded += len(chunk)
                if total:
                    percent = downloaded * 100 / total
                    sys.stdout.write(
                        "\r下载中: %5.1f%% (%.2f/%.2f MB)"
                        % (
                            percent,
                            downloaded / 1024 / 1024,
                            total / 1024 / 1024,
                        )
                    )
                else:
                    sys.stdout.write(
                        "\r下载中: %.2f MB" % (downloaded / 1024 / 1024)
                    )
                sys.stdout.flush()
        # 下载完成后换行。
        sys.stdout.write("\n")
        sys.stdout.flush()

        return save_path
    except requests.exceptions.HTTPError as exc:
        status = getattr(getattr(exc, "response", None), "status_code", None)
        if status == 403:
            raise DownloadError(
                "下载失败 (HTTP 403),可能是防盗链/Referer 问题: %s" % exc
            ) from exc
        raise DownloadError("下载失败 (HTTP 错误): %s" % exc) from exc
    except requests.exceptions.RequestException as exc:
        raise DownloadError("下载失败 (网络错误): %s" % exc) from exc
    except OSError as exc:
        raise DownloadError("下载失败 (文件写入错误): %s" % exc) from exc
