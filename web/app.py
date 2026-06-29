"""Flask Web 服务：提供抖音无水印下载的 Web 界面。"""

import os
import sys

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _BASE_DIR)

_VENDOR_DIR = os.path.join(_BASE_DIR, "_vendor")
if os.path.isdir(_VENDOR_DIR):
    sys.path.insert(0, _VENDOR_DIR)

from flask import Flask, render_template, request, jsonify, send_from_directory

from douyin_dl.parser import extract_share_url, resolve_aweme_id, ParseError
from douyin_dl.extractor import extract_video_info, ExtractError
from douyin_dl.downloader import download, sanitize_filename, DownloadError


app = Flask(__name__)
app.config["DOWNLOAD_DIR"] = os.path.join(_BASE_DIR, "downloads")
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024  # 100MB


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/parse", methods=["POST"])
def api_parse():
    """解析分享文本，返回视频/图文信息。"""
    data = request.get_json(force=True, silent=True) or {}
    share_text = (data.get("share_text") or "").strip()

    if not share_text:
        return jsonify({"error": "请输入抖音分享文本或链接"}), 400

    try:
        share_url = extract_share_url(share_text)
        aweme_id = resolve_aweme_id(share_url)
        info = extract_video_info(aweme_id)

        result = {
            "aweme_id": info.aweme_id,
            "title": info.title,
            "is_image_post": info.is_image_post,
            "video_url": info.video_url,
            "image_urls": info.image_urls,
            "music_url": info.music_url,
        }
        return jsonify(result)
    except (ParseError, ExtractError) as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"解析失败: {e}"}), 500


@app.route("/api/download", methods=["POST"])
def api_download():
    """下载文件到服务器，并返回文件名供前端下载。"""
    data = request.get_json(force=True, silent=True) or {}
    share_text = (data.get("share_text") or "").strip()

    if not share_text:
        return jsonify({"error": "请输入抖音分享文本或链接"}), 400

    try:
        share_url = extract_share_url(share_text)
        aweme_id = resolve_aweme_id(share_url)
        info = extract_video_info(aweme_id)

        os.makedirs(app.config["DOWNLOAD_DIR"], exist_ok=True)
        base_name = sanitize_filename(info.title) if info.title else aweme_id

        saved_files = []

        if info.is_image_post:
            # 图文作品
            for i, img_url in enumerate(info.image_urls, 1):
                ext = ".webp"
                if ".jpeg" in img_url or ".jpg" in img_url:
                    ext = ".jpg"
                elif ".png" in img_url:
                    ext = ".png"
                suffix = f"_{i}" if len(info.image_urls) > 1 else ""
                img_name = f"{base_name}{suffix}{ext}"
                path = download(
                    img_url,
                    app.config["DOWNLOAD_DIR"],
                    img_name,
                )
                saved_files.append({
                    "filename": os.path.basename(path),
                    "type": "image",
                    "size": os.path.getsize(path),
                })

            if info.music_url:
                music_name = f"{base_name}_audio.mp3"
                path = download(
                    info.music_url,
                    app.config["DOWNLOAD_DIR"],
                    music_name,
                )
                saved_files.append({
                    "filename": os.path.basename(path),
                    "type": "audio",
                    "size": os.path.getsize(path),
                })
        else:
            # 普通视频
            path = download(info.video_url, app.config["DOWNLOAD_DIR"], base_name)
            saved_files.append({
                "filename": os.path.basename(path),
                "type": "video",
                "size": os.path.getsize(path),
            })

        return jsonify({
            "title": info.title,
            "is_image_post": info.is_image_post,
            "files": saved_files,
        })
    except (ParseError, ExtractError, DownloadError) as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"下载失败: {e}"}), 500


@app.route("/api/file/<path:filename>")
def api_file(filename):
    """提供已下载文件的下载。"""
    return send_from_directory(
        app.config["DOWNLOAD_DIR"],
        filename,
        as_attachment=True,
    )


def main():
    os.makedirs(app.config["DOWNLOAD_DIR"], exist_ok=True)
    print("抖音无水印下载 Web 版")
    print("访问 http://127.0.0.1:5000 开始使用")
    print()
    app.run(host="0.0.0.0", port=5000, debug=True)


if __name__ == "__main__":
    main()
