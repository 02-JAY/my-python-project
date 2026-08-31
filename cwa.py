import requests
import json
with open('env.json.txt', encoding='utf-8') as f:
    env = json.load(f)

URLS = [
    'https://opendata.cwa.gov.tw/api/v1/rest/datastore/O-A0001-001',
    'https://opendata.cwa.gov.tw/api/v1/rest/datastore/O-A0003-001'
]
_sitemaps = {}

def _load_sitemaps(key):
    sitemaps = {}
    params = {'Authorization': key}

    for url in URLS:
        try:
            r = requests.get(url, params=params, timeout=10)
            r.raise_for_status()
        except Exception as e:
            print(f" {url} 請求失敗：{e.__class__.__name__}")
            continue

        data = r.json().get('records', {}).get('Station', [])
        if not data:
            print(f" {url} 沒有回傳任何 Station 資料")
            continue

        for raw in data:
            name = raw.get('StationName')
            if not name:
                continue

            # 取經緯度（依你給的寫法用 Coordinates[1]）
            lat = lon = None
            try:
                coords = raw.get('GeoInfo', {}).get('Coordinates', [])
                if len(coords) > 1:
                    lat = float(coords[1]['StationLatitude'])
                    lon = float(coords[1]['StationLongitude'])
            except (KeyError, TypeError, ValueError):
                # 如果某站沒有經緯度或格式怪怪的，就先略過經緯度（保留為 None）
                pass

            # 優先保留第一個找到的 API
            if name not in sitemaps:
                sitemaps[name] = {
                    'url': url,
                    'lat': lat,
                    'lon': lon,
                }

    print('裝完資料了')
    return sitemaps


def cwa2(site, key):
    global _sitemaps
    if not _sitemaps:
        _sitemaps = _load_sitemaps(key)

    meta = _sitemaps.get(site)
    if meta:
        url = meta['url']
        return _cwa(url, site, key)
    return {}

def cwa(site,key):
    #info = _cwa(URLS[0],site,key)
    #if info:
    #    return info
    #return _cwa(URLS[1],site,key)

    #return _cwa(URLS[0],site,key) or _cwa(URLS[1],site,key)

    for url in URLS:
        info = _cwa(url,site,key)
        if info:
            return info
    return {}

def _cwa(url,site,key):
    params = {'Authorization' : key,
              'StationName' : site}
    try:
        r = requests.get(url,params = params)
    except Exception as e:
        print(e.__class__.__name__)
        return {}

    if r.status_code != 200:
        print(r.text)
        return{}
    if not r.json()['records']['Station']:
        return {}

    raw = r.json()['records']['Station'][0]
    s = raw['StationName']
    o = raw['ObsTime']['DateTime']
    c =(float(raw['GeoInfo']['Coordinates'][1]['StationLatitude']),
        float(raw['GeoInfo']['Coordinates'][1]['StationLongitude']))
    _r = float(raw['WeatherElement']['Now']['Precipitation'])
    t = float(raw['WeatherElement']['AirTemperature'])
    h = float(raw['WeatherElement']['RelativeHumidity']) / 100

    info = {'S':s ,'O':o,'C':c,'R':_r,'T':t,'H':h}
    return info

def tostr(info_dict, sep=', '):
    buf = []
    if 'S' in info_dict:
        buf.append(f"測站: {info_dict['S']}")
    if 'C' in info_dict:
        buf.append(f"座標: {info_dict['C']}")
    if 'O' in info_dict:
        buf.append(f"時間: {info_dict['O']}")
    if 'T' in info_dict:
        buf.append(f"溫度: {info_dict['T']}度")
    if 'H' in info_dict:
        buf.append(f"濕度: {info_dict['H']:.0%}")
    if 'R' in info_dict:
        buf.append(f"雨量: {info_dict['R']}mm")
    return sep.join(buf)

def find_nearest_station(coord, key):
    """
    coord: (lat, lon) 的 tuple 或 list
    key:   CWA_KEY

    回傳: 最近測站的 info dict，格式跟 cwa()/cwa2 一樣：
          {'S':..., 'O':..., 'C':(...,...), 'R':..., 'T':..., 'H':...}
    """
    global _sitemaps

    # 如果還沒載入測站資料，就載一次
    if not _sitemaps:
        _sitemaps = _load_sitemaps(key)

    # 這一行很重要：把 (lat, lon) 拆成兩個 float
    user_lat, user_lon = coord

    buf = {}
    min_dist = float("inf")   # 初始設成無限大
    nearest_name = None

    for name, meta in _sitemaps.items():
        lat = meta.get("lat")
        lon = meta.get("lon")

        # 沒經緯度就跳過
        if lat is None or lon is None:
            continue

        # 平面距離，用平方就好，不用開根號
        dist_sq = (user_lat - lat) ** 2 + (user_lon - lon) ** 2

        if dist_sq < min_dist:
            min_dist = dist_sq
            nearest_name = name

    if nearest_name is None:
        return {}

    # 這裡直接回傳完整 info（S,O,C,R,T,H）
    return cwa2(nearest_name, key)