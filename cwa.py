from datetime import datetime
import json
import requests

URLS = [
    'https://opendata.cwa.gov.tw/api/v1/rest/datastore/O-A0001-001',
    'https://opendata.cwa.gov.tw/api/v1/rest/datastore/O-A0003-001'
]

_sitemaps = {}

def _parse_coordinates(raw_station: dict):
    """安全解析測站經緯度（優先尋找 WGS84 座標）"""
    try:
        coords = raw_station.get('GeoInfo', {}).get('Coordinates', [])
        if not coords:
            return None, None

        # 若有多組座標，通常第 2 組為 WGS84，若無則取第 1 組
        target_coord = coords[1] if len(coords) > 1 else coords[0]
        lat = float(target_coord.get('StationLatitude'))
        lon = float(target_coord.get('StationLongitude'))
        return lat, lon
    except (KeyError, TypeError, ValueError, IndexError):
        return None, None

def _format_obs_time(iso_time_str: str) -> str:
    """處理氣象署 ISO 時間字串，移除 +08:00 並轉為易讀格式"""
    if not iso_time_str:
        return "未知時間"
    try:
        # 解析如 2026-09-01T19:00:00+08:00
        dt = datetime.fromisoformat(iso_time_str)
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        # Fallback: 若版本不支援 fromisoformat，進行字串取代
        return iso_time_str.replace("T", " ").split("+")[0]

def _load_sitemaps(key: str) -> dict:
    sitemaps = {}
    params = {'Authorization': key}

    for url in URLS:
        try:
            r = requests.get(url, params=params, timeout=10)
            r.raise_for_status()
            data = r.json().get('records', {}).get('Station', [])
        except Exception as e:
            print(f"[CWA] {url} 載入失敗：{e.__class__.__name__}")
            continue

        for raw in data:
            name = raw.get('StationName')
            if not name or name in sitemaps:
                continue

            lat, lon = _parse_coordinates(raw)
            sitemaps[name] = {
                'url': url,
                'lat': lat,
                'lon': lon
            }

    print(f"[CWA] 測站清單加載完成，共計 {len(sitemaps)} 站")
    return sitemaps

def _cwa(url: str, site: str, key: str) -> dict:
    params = {'Authorization': key, 'StationName': site}
    try:
        r = requests.get(url, params=params, timeout=8)
        if r.status_code != 200:
            return {}

        stations = r.json().get('records', {}).get('Station', [])
        if not stations:
            return {}

        raw = stations[0]
        s = raw.get('StationName', site)

        # 1. 時間處理（去除時區後綴）
        raw_time = raw.get('ObsTime', {}).get('DateTime', '')
        o = _format_obs_time(raw_time)

        # 2. 座標安全提取
        c = _parse_coordinates(raw)

        # 3. 氣象數據與防呆處理（-99 代表儀器故障/無資料）
        weather_elem = raw.get('WeatherElement', {})

        # 雨量
        precip = weather_elem.get('Now', {}).get('Precipitation')
        r_val = float(precip) if precip is not None and float(precip) >= 0 else 0.0

        # 溫度
        temp = weather_elem.get('AirTemperature')
        t_val = float(temp) if temp is not None and float(temp) > -50 else None

        # 濕度
        humid = weather_elem.get('RelativeHumidity')
        h_val = (float(humid) / 100) if humid is not None and float(humid) >= 0 else None

        return {
            'S': s,
            'O': o,
            'C': c,
            'R': r_val,
            'T': t_val,
            'H': h_val
        }
    except Exception as e:
        print(f"[CWA] 解析測站 {site} 異常: {e}")
        return {}

def cwa2(site: str, key: str) -> dict:
    global _sitemaps
    if not _sitemaps:
        _sitemaps = _load_sitemaps(key)

    meta = _sitemaps.get(site)
    if meta:
        return _cwa(meta['url'], site, key)

    # 若在 sitemaps 沒精準命中，依序對各 URL 查詢
    for url in URLS:
        info = _cwa(url, site, key)
        if info:
            return info
    return {}

def cwa(site: str, key: str) -> dict:
    """相容舊介面，直接調用 cwa2"""
    return cwa2(site, key)

def tostr(info_dict: dict, sep: str = ', ') -> str:
    if not info_dict:
        return ""

    buf = []
    if info_dict.get('S'):
        buf.append(f"測站: {info_dict['S']}")
    if info_dict.get('O'):
        buf.append(f"時間: {info_dict['O']}")
    if info_dict.get('T') is not None:
        buf.append(f"氣溫: {info_dict['T']}°C")
    if info_dict.get('H') is not None:
        buf.append(f"濕度: {info_dict['H']:.0%}")
    if info_dict.get('R') is not None:
        buf.append(f"時雨量: {info_dict['R']}mm")

    return sep.join(buf)

def find_nearest_station(coord: tuple, key: str) -> dict:
    """根據經緯度搜尋最近測站"""
    global _sitemaps
    if not _sitemaps:
        _sitemaps = _load_sitemaps(key)

    user_lat, user_lon = coord
    min_dist = float("inf")
    nearest_name = None

    for name, meta in _sitemaps.items():
        lat = meta.get("lat")
        lon = meta.get("lon")
        if lat is None or lon is None:
            continue

        dist_sq = (user_lat - lat) ** 2 + (user_lon - lon) ** 2
        if dist_sq < min_dist:
            min_dist = dist_sq
            nearest_name = name

    if not nearest_name:
        return {}

    return cwa2(nearest_name, key)