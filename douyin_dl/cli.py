"""命令行入口。"""

import argparse
import sys

from douyin_dl.parser import extract_share_url, resolve_aweme_id, ParseError
from douyin_dl.extractor import extract_video_info, ExtractError
from douyin_dl.downloader import download, sanitize_filename, DownloadError


def main(argv=None) -> int:
    """解析参数并串联 解析→提取→下载 流程,返回进程退出码。"""
    parser = argparse.ArgumentParser(
        prog="douyin_dl",
        description="抖音无水印视频下载工具。",
    )
    parser.add_argument("share_text", help="抖音分享文本/链接。")
    parser.add_argument(
        "-o",
        "--output",
        default="downloads",
        help="输出目录(默认: downloads)。",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="仅解析不下载。",
    )

    args = parser.parse_args(argv)

    try:
        share_url = extract_share_url(args.share_text)
        print(f"已识别链接: {share_url}")

        aweme_id = resolve_aweme_id(share_url)
        print(f"视频ID: {aweme_id}")

        info = extract_video_info(aweme_id)
        print(f"标题: {info.title}")

        # 图文作品处理
        if info.is_image_post:
            print(f"类型: 图文作品 ({len(info.image_urls)} 张图片)")
            if info.music_url:
                print(f"音频: {info.music_url}")
            for i, img_url in enumerate(info.image_urls, 1):
                print(f"图片{i}: {img_url}")

            if args.dry_run:
                print("[dry-run] 仅解析,未下载。")
                return 0

            # 下载所有图片
            base_name = sanitize_filename(info.title) if info.title else aweme_id
            saved_paths = []
            for i, img_url in enumerate(info.image_urls, 1):
                # 图片文件用原扩展名(webp/jpeg/png)
                ext = ".webp"
                if ".jpeg" in img_url or ".jpg" in img_url:
                    ext = ".jpg"
                elif ".png" in img_url:
                    ext = ".png"
                suffix = f"_{i}" if len(info.image_urls) > 1 else ""
                img_name = f"{base_name}{suffix}{ext}"
                path = download(
                    img_url,
                    args.output,
                    img_name,
                    referer="https://www.douyin.com/",
                )
                saved_paths.append(path)

            # 下载音频(如果有)
            if info.music_url:
                music_name = f"{base_name}_audio.mp3"
                music_path = download(
                    info.music_url,
                    args.output,
                    music_name,
                    referer="https://www.douyin.com/",
                )
                saved_paths.append(music_path)
                print(f"音频已保存: {music_path}")

            print(f"已保存: {', '.join(saved_paths)}")
            return 0

        print(f"无水印直链: {info.video_url}")

        if args.dry_run:
            print("[dry-run] 仅解析,未下载。")
            return 0

        filename = info.title if info.title else aweme_id
        saved_path = download(info.video_url, args.output, filename)
        print(f"已保存: {saved_path}")
        return 0
    except (ParseError, ExtractError, DownloadError) as e:
        print(f"错误: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"未知错误: {e}", file=sys.stderr)
        return 1
