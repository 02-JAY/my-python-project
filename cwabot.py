import os
from io import BytesIO
import json
import time
import tempfile
from copy import deepcopy
import base64
from typing import Optional, Literal
from langchain.tools import tool  # 或是你原本使用的 tool 裝飾器套件

import threading  # 引入執行緒模組
from langchain_core.messages import HumanMessage  #  引入 LangChain 多模態訊息格式

import requests
from langchain_core.tools import tool

from flask import Flask, request, abort

from linebot.v3 import (
    WebhookHandler
)
from linebot.v3.exceptions import (
    InvalidSignatureError
)
from linebot.v3.messaging import (
    Configuration,
    MessagingApiBlob,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
    MessagingApiBlob,
    ImageMessage,
    FlexMessage,
    FlexContainer,
    QuickReply,
    QuickReplyItem,
    MessageAction
)
from linebot.v3.webhooks import (
    MessageEvent,
    TextMessageContent,
    ImageMessageContent,
    PostbackEvent,
    LocationMessageContent,
    FollowEvent,
    UnfollowEvent,
    AudioMessageContent
)

app = Flask(__name__)

import cwa
from PIL import Image
from google.cloud import storage ,firestore,vision,speech #speech 語音
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import create_agent #ReAct AI Agent
from langchain_core.tools import tool
from geopy.geocoders import Nominatim


firestore_client = firestore.Client.from_service_account_json('keycloud.json') #環境相關金鑰
collection = firestore_client.collection('晨晨')

vision_client = vision.ImageAnnotatorClient.from_service_account_json('keycloud.json')

with open('env.json.txt', encoding='utf-8') as f:
    env = json.load(f)

with open('me.json', encoding='utf-8') as f:
    me_dict = json.load(f)

configuration = Configuration(access_token=env.get('CHANEL_ACCESS_TOKEN'))
handler = WebhookHandler(env.get('CHANEL_SCERCT'))

storage_client = storage.Client.from_service_account_json('keycloud.json') #環境相關金鑰
bucket = storage_client.bucket('jay25499') #籃子的名子


rich1 = 'richmenu-95a9e8782c869dbf17447ed2e4d1d6ae' # picture.json
rich2 = 'richmenu-52977ee8774b2d41706a796c2e49c4fc'  # hehe.json

#聊天aiagent
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = 'keycloud.json'

# 改用從 env.json.txt 讀出來的 GEMINI_API_KEY，並把 vertexai 拿掉
llm = ChatGoogleGenerativeAI(
    model='gemini-2.5-flash',
    google_api_key=env.get('GEMINI_API_KEY')
)

#llm = ChatGoogleGenerativeAI(model='gemini-2.5-flash', vertexai=True, location='global')
geolocator = Nominatim(user_agent = 'user_agent',timeout = 5)

# 改成你 Controller 訂好的 V1 API 路徑
SPRING_BOOT_RECOMMEND_URL = "http://localhost:8080/api/v1/bot/products/recommendations"

@tool
def recommend_ecommerce_products(keyword: Optional[str] = None, category: Optional[str] = None) -> str:
    """
    當使用者想要搜尋、推薦或尋找電商商品時，呼叫此工具。
    AI 必須根據使用者的輸入，自動、廣泛地推論出最合理的商品分類（category 絕對不能為 None）。

    參數說明:
    - keyword: 從對話中提取的核心搜尋字（如品牌、型號、公升數、功效或氣味）。
    - category: AI 應展現領域常識，根據以下泛化原則『三選一』填入（不可為空）：

        * 'FRAGRANCE_PACK' (香氛防潮類) :
          只要關鍵字涉及「氣味/植物/精油」（如：薰衣草、玫瑰、薄荷、小蒼蘭）
          或涉及「消耗型防潮小物」（如：香包、除濕袋、克潮靈、竹炭包、乾燥劑），一律歸為此類。

        * 'DEHUMIDIFIER' (除濕機家電類) :
          只要關鍵字涉及「知名家電品牌」（如：Panasonic、日立、Hitachi、三菱、SHARP、Muji）
          或涉及「電器規格/專有名詞」（如：6L、11L、變頻、壓縮機、水箱、坪數、套房用電器），一律歸為此類。

        * 'DRY_BOX' (電子防潮箱類) :
          外觀為箱體、涉及「精密儀器/攝影保存」或明確提到「防潮箱、電子箱、相機收藏箱」時歸為此類。

    [自動推論指引] AI 應靈活判斷語意。若使用者僅輸入『日立 6L』，雖未明說，但根據常理，具備公升數的日立產品必為除濕機家電，應自動判定 category='DEHUMIDIFIER'。
    """
    try:
        # 組裝 Query Parameters
        params = {}
        if keyword: params["keyword"] = keyword
        if category: params["category"] = category

        response = requests.get(SPRING_BOOT_RECOMMEND_URL, params=params, timeout=5)

        if response.status_code == 200:
            products = response.json()

            # 判斷回傳是否為空清單，或是根本不是 list
            if not products or not isinstance(products, list):
                return "目前找不到符合推薦條件的商品。"

            # 🌟 關鍵改動：只撈取後端回傳的第一筆商品 (Index 0)
            p = products[0]

            # 安全讀取 productSpec (防止 Java 傳回 null 導致 Python 的 get() 崩潰)
            spec = p.get('productSpec')
            if not isinstance(spec, dict):
                spec = {}

            # 取得個性花語，若無則預設為通用
            personality_desc = spec.get('personality', '通用')

            # 組裝單一商品的漂亮回傳格式
            result_text = "💡 為您找到最符合的精選商品：\n"
            result_text += f"📦 商品: {p.get('productName', '未命名商品')}\n"
            result_text += f"💰 價格: {p.get('price', 0)} 元\n"
            result_text += f"✨ 適合性格: {personality_desc}\n"

            img_url = p.get('imageUrl', '').strip() if p.get('imageUrl') else ''
            if img_url:
                result_text += f"🔗 圖片: {img_url}\n"
            result_text += "------------------\n"

            return result_text

        return f"商品推薦系統忙碌中（狀態碼: {response.status_code}）。"
    except Exception as e:
        # 這裡保留精確的 Exception 訊息，方便你噴錯時看 Terminal 抓漏
        return f"連線至推薦模組異常，原因: {str(e)}"

@tool
def get_weather_by_coordinates(latitude: float, longitude: float) -> str:
    '''get weather info by coordinates'''
    info = cwa.find_nearest_station((latitude, longitude),env['CWA_KEY'])
    return cwa.tostr(info) if info else '無此站'


@tool
def get_coordinates(location: str) -> dict:
    """get coordinates by location"""
    loc = geolocator.geocode(location)
    if not loc:
        return {"error": f"找不到 {location}"}
    return {
        "latitude": loc.latitude,
        "longitude": loc.longitude
    }

@tool
def get_weather_by_location(location:str) -> str:
    '''get weather info by location. if you got '無此站' you should query another tool '''
    info = cwa.cwa2(location,env['CWA_KEY'])
    return cwa.tostr(info) if info else '無此站'

tools = [
    get_weather_by_coordinates,
    get_coordinates,
    get_weather_by_location,
    recommend_ecommerce_products  # 推薦商品
]

# 2. 放寬系統提示詞，讓 AI 知道除了天氣，他也能處理電商推薦
system_prompt = '''
你是一個貼心的生活助手，擅長使用繁體中文回答問題。
1. 如果使用者詢問天氣，請使用天氣相關工具查詢真實天氣。
2. 如果使用者想找商品、需要推薦、或是詢問購物相關問題，請使用商品推薦工具 (recommend_ecommerce_products)。
請根據使用者的意圖靈活切換工具，若查不到結果，請委婉告知並引導使用者換個說法。
'''

agent = create_agent(model=llm,tools= tools,system_prompt=system_prompt)

users = []
pos = []


def ask_weather(userid: str, something: str) -> str:
    #prepare history
    data = collection.document(userid).get(['his']).to_dict()
    his = data.get('his', []) if data else []

    history = []
    for h in his:
        ask, ans = h.get('ask'), h.get('ans')
        if ask and ans:
            history.append({'role': 'user', 'content': ask})
            history.append({'role': 'assistant', 'content': ans})

    #prapare messages
    messages = history + [{'role': 'user', 'content': something}]
    # ask Gimini
    r = agent.invoke({'messages': messages})

    # keep answer
    ans = r['messages'][-1].content
    if  type(ans) !=str:
        ans = ans[0]['text']

    # store history
    his.append({
        'timestamp': time.strftime('%Y%m%d%H%M%S'),
        'ask': something,
        'ans': ans
    })

    collection.document(userid).set({'his': his},merge=True)

    return ans



@app.route("/callback", methods=['POST'])
def callback():
    # get X-Line-Signature header value
    signature = request.headers['X-Line-Signature']

    # get request body as text
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    # handle webhook body
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        app.logger.info("Invalid signature. Please check your channel access token/channel secret.")
        abort(400)

    return 'OK'

#TextMessageContent 純文字訊息使用這個
# messaging.FlexMessage,
# messaging.FlexContainer
# messaging.QuickReply
# messaging.QuickReplyItem
# messaging.MessageAction
# webhooks.LocationMessageContent
@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    print(event.message.text)  #
    print(event.source.user_id) #
    print(event.timestamp)
    print(event.reply_token)

    ask = event.message.text
    ask_map = {'hello': '我很好', 'hi': '您哪位'}
    #ans = ask_map.get(ask, '我不知道妳再說甚麼')
    ans = ask_map.get(ask)

    messages = []

    if not ans:
        if ask == 'me':  # me handling
            with open('caro.json', encoding='utf-8') as f:
                flex_dict = json.load(f)
            flex_message = FlexMessage(altText='me', contents=FlexContainer.from_dict(flex_dict))
            messages.append(flex_message)
        elif ask == 'action':  # action handling
            with open('action.json', encoding='utf-8') as f:
                flex_dict = json.load(f)
            flex_message = FlexMessage(altText='action', contents=FlexContainer.from_dict(flex_dict))
            messages.append(flex_message)
        elif ask in '12345':
            n = int(ask)

            new_dicts = []
            count = 0
            for u in collection.stream():
                new_dict = deepcopy(me_dict)
                u = u.to_dict()
                new_dict['hero']['url'] = u['picture_url']
                new_dict['body']['contents'][0]['contents'][0]['contents'][1]['text']  = u['user_id']
                new_dict['body']['contents'][0]['contents'][1]['contents'][1]['text']  = u['display_name']
                new_dict['body']['contents'][0]['contents'][2]['contents'][1]['text']  = u['status_message'] or 'N/A'
                new_dicts.append(new_dict)

                count += 1
                if(count >= n):
                    break



            #car = {"type": "carousel", "contents": [me_dict]*n}
            car = {"type": "carousel", "contents": new_dicts}
            flex_message = FlexMessage(altText=f'{n} me', contents=FlexContainer.from_dict(car))




            messages.append(flex_message)
        else:  # weather
            #ans = cwa2.cwa2(ask, env.get('CWA_KEY'))
            #ans = cwa2.tostr(ans, '\n') or '無此站'

            #if ans != '無此站':
            #collection.document(event.source.user_id).update({'weather_count' : firestore.Increment(1)})

            #item1 = QuickReplyItem(action=MessageAction(label='文化大學', text='文化大學'))
            #item2 = QuickReplyItem(action=MessageAction(label='陽明山', text='陽明山'))
            #items = [item1, item2]
            #quick_reply = QuickReply(items=items)

            #messages.append(TextMessage(text=ans, quick_reply=quick_reply))
            ans = ask_weather(event.source.user_id,ask) or "我查不到資料，換個地點/問法試試？"
            messages.append(TextMessage(text=ans))

    else:  # hello
        messages.append(TextMessage(text=ans))
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message_with_http_info(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages = messages
            )
        )

#ImageMessageContent 純文字訊息使用這個
# messaging.MessagingApiBlob
# webhooks.ImageMessageContent
# from io import BytesIO
# from PIL import Image
#-----------------------------#
# messaging.MessagingApiBlob
# messaging.ImageMessage
@handler.add(MessageEvent, message=ImageMessageContent)
def handle_content_message(event):
    with ApiClient(configuration) as api_client:
        line_bot_blob_api = MessagingApiBlob(api_client)
        message_content = line_bot_blob_api.get_message_content(message_id=event.message.id)
        image = Image.open(BytesIO(message_content))
        text = f'{image.height} X {image.width}'

        #blob = bucket.blob('kkk.jpg') #雲端取名
        #blob.upload_from_filename('test.jpg') #local端檔案名稱
        # upload image
        blob_name = f'{event.source.user_id}_{event.message.id}'
        #blob = bucket.blob(blob_name)
        blob = bucket.blob("test123")
        blob.upload_from_string(message_content, content_type='image/jpeg')

        url = blob.public_url
        url = blob.generate_signed_url(int(time.time())+60)
        image_message = ImageMessage(original_content_url=url,
                                     preview_image_url=url)


        # label_detection
        image = vision.Image(content=message_content)
        response = vision_client.label_detection(image=image)
        labels = [i.description for i in response.label_annotations]
        labels = '\n'.join(labels)

    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[
                    TextMessage(text=text),image_message,
                    TextMessage(text=labels)
                ]
            )
        )

@handler.add(MessageEvent, message=LocationMessageContent)
def handle_message(event):
    print(event.source.user_id) #
    print(event.timestamp)
    print(event.reply_token)

    print(event.message.latitude)
    print(event.message.longitude)
    site = (event.message.latitude, event.message.longitude)
    ans = cwa.find_nearest_station(site, env.get('CWA_KEY'))
    ans = cwa.tostr(ans, '\n') or '無此站'

    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message_with_http_info(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=ans)]
            )
        )


@handler.add(PostbackEvent)
def handle_message(event):
    print(event.source.user_id) #
    print(event.timestamp)
    print(event.reply_token)
    print(event.postback.data)

    global users,pos

    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)

        data = event.postback.data
        # 先預設一個 messages list
        messages = []

        # Firestore collection: 用 user_id 當 doc id
    user_doc = collection.document(event.source.user_id)

    if data == 'fans':
        # 切 RichMenu
        line_bot_api.link_rich_menu_id_to_user(event.source.user_id, rich2)

        # 讀 firestore 的上次位置，如果沒有就用 0
        stored = user_doc.get(['pos']).to_dict()
        pos = stored.get('pos', 0)

        # 載入所有粉絲資料
        users = [doc.to_dict() for doc in collection.stream()]

        # 沒資料
        if not users:
            messages.append(TextMessage(text='目前沒有粉絲資料'))
        else:
            # 防止 pos 超範圍（例如資料變少）
            pos = min(pos, len(users) - 1)
            pos = max(pos, 0)
            u = users[pos]

            messages.append(TextMessage(text=f'已為您顯示上次停留的會員 (第 {pos+1} 位)'))
            messages.append(build_user_flex(u, pos, len(users)))

        # 更新 firestore 的位置
        user_doc.set({'pos': pos}, merge=True)


    # find previous
    elif data == 'left':
        stored = user_doc.get(['pos']).to_dict()
        pos = stored.get('pos', 0)

        if not users:
            messages.append(TextMessage(text='請先按「fans」載入資料'))
        else:
            if pos <= 0:
                pos = 0
                messages.append(TextMessage(text='已是第一個會員囉'))
            else:
                pos -= 1
                u = users[pos]
                messages.append(build_user_flex(u, pos, len(users)))

            user_doc.set({'pos': pos}, merge=True)


    # find next
    elif data == 'right':
        stored = user_doc.get(['pos']).to_dict()
        pos = stored.get('pos', 0)

        if not users:
            messages.append(TextMessage(text='請先按「fans」載入資料'))
        else:
            if pos >= len(users) - 1:
                pos = len(users) - 1
                messages.append(TextMessage(text='已是最後一個會員囉'))
            else:
                pos += 1
                u = users[pos]
                messages.append(build_user_flex(u, pos, len(users)))

            user_doc.set({'pos': pos}, merge=True)


    elif data == 'first':
        stored = user_doc.get(['pos']).to_dict()
        pos = stored.get('pos', 0)

        if not users:
            messages.append(TextMessage(text='請先按「粉絲列表」載入資料'))
        else:
            if pos == 0:
                messages.append(TextMessage(text='已是第一個會員囉'))
            else:
                pos = 0
                u = users[pos]
                messages.append(TextMessage(text='已跳到第一個會員'))
                messages.append(build_user_flex(u, pos, len(users)))

            user_doc.set({'pos': pos}, merge=True)


    elif data == 'last':
        stored = user_doc.get(['pos']).to_dict()
        pos = stored.get('pos', 0)

        if not users:
            messages.append(TextMessage(text='請先按「粉絲列表」載入資料'))
        else:
            last_index = len(users) - 1
            if pos == last_index:
                messages.append(TextMessage(text='已是最後一個會員囉'))
            else:
                pos = last_index
                u = users[pos]
                messages.append(TextMessage(text='已跳到最後一個會員'))
                messages.append(build_user_flex(u, pos, len(users)))

            user_doc.set({'pos': pos}, merge=True)


    elif data == 'return':
        line_bot_api.link_rich_menu_id_to_user(event.source.user_id, rich1)
        messages.append(TextMessage(text='已返回主選單'))

    line_bot_api.reply_message_with_http_info(
        ReplyMessageRequest(
            reply_token=event.reply_token,
            messages=messages
        )
    )

#解除封鎖、加入好友的事件
@handler.add(FollowEvent)
def handle_message(event):
    print(event.source.user_id) #

    wellcome = 'wellcome ???'

    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        profile = dict(line_bot_api.get_profile(event.source.user_id))
        display = profile.get('display_name') or 'N/A'

        wellcome = f'wellcome {display}'

        collection.document(event.source.user_id).set(profile |{'follow':time.strftime('%Y/%m/%d-%H:%M:%S')})

        line_bot_api.reply_message_with_http_info(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text= wellcome)]
            )
        )

#封鎖事件
@handler.add(UnfollowEvent)
def handle_message(event):
    print(event.source.user_id) #


    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        collection.document(event.source.user_id).update({'unfollow':time.strftime('%Y/%m/%d-%H:%M:%S')})


def build_user_flex(u, index, total):
    bubble = deepcopy(me_dict)
    bubble['hero']['url'] = u.get('picture_url', '')
    bubble['body']['contents'][0]['contents'][0]['contents'][1]['text'] = u.get('user_id', 'N/A')
    bubble['body']['contents'][0]['contents'][1]['contents'][1]['text'] = u.get('display_name', 'N/A')
    bubble['body']['contents'][0]['contents'][2]['contents'][1]['text'] = u.get('status_message') or 'N/A'

    car = {
        "type": "carousel",
        "contents": [bubble]  # 這裡只放一張，讓 left/right 變成「翻頁」
    }
    return FlexMessage(
        altText=f"第 {index + 1} / {total} 筆",
        contents=FlexContainer.from_dict(car)
    )

def download_line_audio(event, api_client) -> str:
    """
    從 LINE 下載語音，存到系統暫存目錄（Windows / Linux / Cloud Run 都可）
    """
    blob_api = MessagingApiBlob(api_client)
    content = blob_api.get_message_content(event.message.id)

    tmp_dir = tempfile.gettempdir()   # ★ 這行需要 import tempfile
    local_path = os.path.join(tmp_dir, f"{event.message.id}.ogg")

    with open(local_path, "wb") as f:
        f.write(content)
    return local_path

def upload_audio_to_gcs(event, local_path: str) -> str:
    """
    將本地檔案上傳至 GCS，並回傳 gs:// 路徑
    """
    client = storage.Client()
    bucket_name = 'jay25499'
    bucket = client.bucket(bucket_name)

    # 修正重點：將 event.message_id 改為 event.message.id
    blob_name = f"audio-files/{event.message.id}.ogg"
    blob = bucket.blob(blob_name)

    # 執行上傳
    blob.upload_from_filename(local_path)

    # 回傳 GCS 的路徑
    gcs_uri = f"gs://{bucket_name}/{blob_name}"
    print(f"檔案已成功上傳至: {gcs_uri}")

    return gcs_uri

def speech_to_text(gcs_uri: str) -> str:
    client = speech.SpeechClient()

    # 修正重點：使用 uri 而不是 content
    audio = speech.RecognitionAudio(uri=gcs_uri)

    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.MP3,  # omit this line if WAV
        sample_rate_hertz=44100,
        audio_channel_count=2,  # take care, default is 1
        language_code="zh-TW",
        max_alternatives=10
    )

    # 注意這裡變數名稱要統一 (你原本寫 speech_client，應為 client)
    response = client.recognize(config=config, audio=audio)

    if not response.results:
        return ""

    return response.results[0].alternatives[0].transcript

def bg_upload_to_gcs(bucket_name, blob_name, content, content_type):
    """
    【線下任務】在背景默默上傳音檔至 GCS，不卡住使用者的 LINE 回覆時間
    """
    try:
        # 使用原本設定好的儲存媒介與環境金鑰
        client = storage.Client.from_service_account_json('keycloud.json')
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        blob.upload_from_string(content, content_type=content_type)
        print(f"============== [GCS 備份成功] 檔案已存至: {blob_name} ==============")
    except Exception as e:
        print(f"============== [GCS 備份失敗] 錯誤原因: {e} ==============")

@handler.add(MessageEvent, message=AudioMessageContent)
def handle_audio_message(event):
    userid = event.source.user_id

    with ApiClient(configuration) as api_client:
        try:
            # 1. 下載音檔二進位內容
            blob_api = MessagingApiBlob(api_client)
            content = blob_api.get_message_content(event.message.id)

            # 2. 【線下任務】背景執行緒上傳 GCS
            blob_name = f"audio-files/{userid}_{event.message.id}.ogg"
            upload_thread = threading.Thread(
                target=bg_upload_to_gcs,
                args=('jay25499', blob_name, content, 'audio/ogg')
            )
            upload_thread.start()

            # 🚀 3. 【修正重點】將 Binary 轉成 Base64 字串，用標準 image_url 格式餵給 LangChain
            audio_base64 = base64.b64encode(content).decode('utf-8')

            whisper_prompt = "你是一個精準的語音聽寫員。請把這段語音盲聽並翻譯成繁體中文文字，不要回答任何多餘的解釋、標點符號或問候，只需輸出聽到的文字。如果沒聲音或聽不懂，請輸出 '無法辨識'。"

            # 使用 LangChain 通用的多模態結構 (通用於圖片與音訊)
            hearing_message = HumanMessage(
                content=[
                    {"type": "text", "text": whisper_prompt},
                    {
                        "type": "image_url",  # 註：部分 LangChain 版本語音也包在 image_url 格式內傳送 Base64
                        "image_url": {"url": f"data:audio/ogg;base64,{audio_base64}"}
                    }
                ]
            )

            speech_result = llm.invoke([hearing_message])
            text = speech_result.content.strip()
            print(f'===[Gemini 語音辨識結果]===: {text}')

            # 4. 判斷辨識結果並呼叫既有的天氣 Agent
            if not text or "無法辨識" in text:
                ans = "我沒有聽清楚，可以再說一次嗎？"
            else:
                ans = ask_weather(userid, text)

        except Exception as e:
            print("語音處理發生未預期錯誤:", e)
            ans = "語音系統開小差了，請稍後再試。"

        # 5. 快速回覆給 LINE 使用者
        MessagingApi(api_client).reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=ans)]
            )
        )

if __name__ == "__main__":
    app.run()