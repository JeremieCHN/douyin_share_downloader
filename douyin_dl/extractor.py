"""无水印视频地址提取:依据 aweme_id 获取播放地址与文案。"""
import json
import re
from dataclasses import dataclass

from douyin_dl.parser import MOBILE_UA


class ExtractError(Exception):
    """视频信息提取失败。"""


@dataclass
class VideoInfo:
    aweme_id: str
    title: str
    video_url: str  # 无水印视频直链
    is_image_post: bool = False  # 是否为图文作品
    image_urls: list = None  # 图文作品图片列表
    music_url: str = None  # 图文作品音频

    def __post_init__(self):
        if self.image_urls is None:
            self.image_urls = []


# 匹配分享页内嵌的 window._ROUTER_DATA JSON
_ROUTER_DATA_PATTERN = re.compile(
    r"window\._ROUTER_DATA\s*=\s*(\{.*?\})\s*;", re.DOTALL
)
# 备用:取到下一个 </script> 之前的完整对象
_ROUTER_DATA_PATTERN_FALLBACK = re.compile(
    r"window\._ROUTER_DATA\s*=\s*(\{.*\})\s*;?\s*</script>", re.DOTALL
)


def _to_no_watermark(url: str) -> str:
    """把播放地址中的 ``playwm`` 替换为 ``play`` 以获取无水印直链。"""
    return url.replace("playwm", "play")


def _new_session(session):
    """返回可用的请求会话,session 为 None 时新建 requests.Session()。"""
    if session is not None:
        return session
    import requests  # 延迟导入,保证模块可离线导入

    return requests.Session()


def _from_share_page(aweme_id, sess, timeout):
    """主路径:解析分享页内嵌 JSON。失败抛异常或返回 None。"""
    url = f"https://www.iesdouyin.com/share/video/{aweme_id}/"
    response = sess.get(
        url,
        headers={"User-Agent": MOBILE_UA},
        allow_redirects=True,
        timeout=timeout,
    )
    html = response.text

    match = _ROUTER_DATA_PATTERN.search(html)
    if not match:
        match = _ROUTER_DATA_PATTERN_FALLBACK.search(html)
    if not match:
        return None

    data = json.loads(match.group(1))
    loader_data = data["loaderData"]

    item = None
    for value in loader_data.values():
        if isinstance(value, dict) and "videoInfoRes" in value:
            item = value["videoInfoRes"]["item_list"][0]
            break
    if item is None:
        return None

    # 检测图文作品:有 images 字段且有内容
    images = item.get("images") or []
    if images:
        # 图文作品:提取所有图片 URL
        image_urls = []
        for img in images:
            # 优先用 download_url_list(无水印),否则用 url_list
            urls = img.get("download_url_list") or img.get("url_list") or []
            if urls:
                image_urls.append(urls[0])

        # 尝试获取背景音乐
        music_url = None
        music = item.get("music") or {}
        music_urls = music.get("play_url") or {}
        music_url_list = music_urls.get("url_list") or []
        if music_url_list:
            music_url = music_url_list[0]

        return VideoInfo(
            aweme_id=str(aweme_id),
            title=item.get("desc", ""),
            video_url="",
            is_image_post=True,
            image_urls=image_urls,
            music_url=music_url,
        )

    # 普通视频
    raw_url = item["video"]["play_addr"]["url_list"][0]
    title = item.get("desc", "")
    return VideoInfo(
        aweme_id=str(aweme_id),
        title=title,
        video_url=_to_no_watermark(raw_url),
    )


def _from_iteminfo_api(aweme_id, sess, timeout):
    """备用路径:调用 iteminfo 接口。失败抛异常或返回 None。"""
    url = (
        "https://www.iesdouyin.com/web/api/v2/aweme/iteminfo/"
        f"?item_ids={aweme_id}"
    )
    response = sess.get(
        url,
        headers={"User-Agent": MOBILE_UA},
        timeout=timeout,
    )
    data = response.json()
    item = data["item_list"][0]

    # 检测图文作品
    images = item.get("images") or []
    if images:
        image_urls = []
        for img in images:
            urls = img.get("download_url_list") or img.get("url_list") or []
            if urls:
                image_urls.append(urls[0])

        music_url = None
        music = item.get("music") or {}
        music_url_list = (music.get("play_url") or {}).get("url_list") or []
        if music_url_list:
            music_url = music_url_list[0]

        return VideoInfo(
            aweme_id=str(aweme_id),
            title=item.get("desc", ""),
            video_url="",
            is_image_post=True,
            image_urls=image_urls,
            music_url=music_url,
        )

    raw_url = item["video"]["play_addr"]["url_list"][0]
    title = item.get("desc", "")
    return VideoInfo(
        aweme_id=str(aweme_id),
        title=title,
        video_url=_to_no_watermark(raw_url),
    )


def extract_video_info(aweme_id: str, session=None, timeout: int = 10) -> VideoInfo:
    """获取视频信息,返回包含无水印直链的 VideoInfo。

    先尝试分享页内嵌 JSON,再降级到 iteminfo 接口;全部失败抛 ExtractError。
    """
    sess = _new_session(session)

    for path in (_from_share_page, _from_iteminfo_api):
        try:
            info = path(aweme_id, sess, timeout)
        except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError):
            # 数据结构变动或 JSON 解析失败,降级到下一条路径
            continue
        except Exception:
            # 网络异常等,降级到下一条路径
            continue
        if info is not None:
            return info

    raise ExtractError(
        f"无法提取视频信息(aweme_id={aweme_id}),"
        "可能是接口结构变动或需要签名,请稍后重试或更新解析逻辑。"
    )
