"""分享文本解析:从分享口令中提取短链,并解析出 aweme_id。"""
import re

MOBILE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1"
)


class ParseError(Exception):
    """分享文本解析失败。"""


def extract_share_url(text: str) -> str:
    """从任意分享文本中提取抖音短链接,如 https://v.douyin.com/xxxxx/。

    找不到时抛出 ParseError。
    """
    # 匹配 http(s) 开头、域名含 douyin.com 的 URL,排除尾部空白
    match = re.search(
        r"https?://[\w.-]*douyin\.com/[^\s]*",
        text,
    )
    if not match:
        raise ParseError("未在文本中找到抖音链接")
    # 去掉 URL 尾部可能粘连的标点/空白
    return match.group(0).rstrip(".,;:!?)]}\"'，。；：！？、")


# 依次尝试的 aweme_id 提取模式
_AWEME_ID_PATTERNS = (
    r"/video/(\d+)",
    r"/share/video/(\d+)",
    r"/note/(\d+)",
    r"/share/slides/(\d+)",
    r"modal_id=(\d+)",
    r"aweme_id=(\d+)",
)


def resolve_aweme_id(share_url: str, session=None, timeout: int = 10) -> str:
    """以移动端 UA 请求短链,跟随重定向,从落地 URL 中解析出纯数字 aweme_id。

    解析不到时抛出 ParseError。
    """
    http = session
    if http is None:
        import requests
        http = requests
    try:
        response = http.get(
            share_url,
            headers={"User-Agent": MOBILE_UA},
            allow_redirects=True,
            timeout=timeout,
        )
    except Exception as exc:
        raise ParseError(f"请求短链失败: {exc}") from exc

    landing = response.url
    for pattern in _AWEME_ID_PATTERNS:
        match = re.search(pattern, landing)
        if match:
            return match.group(1)
    raise ParseError(f"未能从落地 URL 解析出 aweme_id: {landing}")
