"""Geographic utilities.

Region detection (domestic vs overseas), coordinate helpers,
and destination normalization.
"""

import re

_CHINA_PROVINCES = {
    "北京", "天津", "上海", "重庆",
    "河北", "山西", "辽宁", "吉林", "黑龙江",
    "江苏", "浙江", "安徽", "福建", "江西", "山东",
    "河南", "湖北", "湖南", "广东", "海南",
    "四川", "贵州", "云南", "陕西", "甘肃",
    "青海", "内蒙古", "广西", "西藏", "宁夏", "新疆",
    "香港", "澳门", "台湾",
}

_CHINA_CITIES = {
    "北京", "上海", "广州", "深圳", "杭州", "南京", "成都", "重庆",
    "武汉", "西安", "长沙", "苏州", "青岛", "大连", "厦门", "三亚",
    "昆明", "丽江", "桂林", "拉萨", "哈尔滨", "天津", "郑州", "合肥",
    "济南", "福州", "南昌", "贵阳", "兰州", "银川", "西宁", "呼和浩特",
    "乌鲁木齐", "沈阳", "长春", "石家庄", "太原", "南宁", "海口",
    "珠海", "无锡", "佛山", "东莞", "宁波", "温州", "洛阳",
    "张家界", "九寨沟", "黄山", "泰山", "敦煌", "大理", "凤凰古城",
}

_CN_CHAR_RE = re.compile(r"[一-鿿]")


def is_domestic(destination: str) -> bool:
    """Detect whether a destination is within mainland China / HK / Macau / Taiwan."""
    dest = destination.strip()

    for name in _CHINA_PROVINCES | _CHINA_CITIES:
        if name in dest:
            return True

    if _CN_CHAR_RE.search(dest):
        if any(kw in dest for kw in ("中国", "国内", "内地")):
            return True
        if not any(kw in dest for kw in ("日本", "韩国", "泰国", "越南", "新加坡", "马来西亚")):
            return True

    return False


def format_coords(lng: float, lat: float) -> str:
    """Format coordinates as 'lng,lat' string (Amap convention)."""
    return f"{lng},{lat}"
