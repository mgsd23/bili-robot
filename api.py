import re
import time
import json
from threading import Timer

import requests

from tencentcloud.common import credential
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.common.profile.http_profile import HttpProfile
from tencentcloud.common.exception.tencent_cloud_sdk_exception import TencentCloudSDKException
from tencentcloud.ims.v20201229 import ims_client, models


class BiliAPI:

    def __init__(self, cookies: dict):
        self.cookies = cookies
        self.csrf = self.cookies['bili_jct']
        self.mid = self.cookies['DedeUserID']
        self.msg = self.MsgAPI(cookies)

    class MsgAPI:

        def __init__(self, cookies: dict):
            self.cookies = cookies
            self.csrf = self.cookies['bili_jct']
            self.mid = self.cookies['DedeUserID']
            self.sendMsgTime = 0  # 最后一次发送消息时间

        # 获取有新消息的会话
        def getNewSession(self, begin_ts) -> []:
            url = 'https://api.vc.bilibili.com/session_svr/v1/session_svr/new_sessions'
            params = {
                'begin_ts': begin_ts,
                'build': 0,
                'mobi_app': 'web',
            }
            res = requests.get(url, params, cookies=self.cookies)
            session_list = res.json()['data'].get('session_list', [])
            return session_list if session_list is not None else []

        # 获取会话消息 begin_seqno, end_seqno 都为开区间，不包含本身
        def fetchSessionMsgs(self, talker_id, session_type, begin_seqno, end_seqno) -> []:
            url = 'https://api.vc.bilibili.com/svr_sync/v1/svr_sync/fetch_session_msgs'
            params = {
                'talker_id': talker_id,  # 会话对方ID
                'session_type': session_type,  # 会话类型 1私信 2 群聊
                'size': -1,  # max 200, 当为-1时max2000
                'sender_device_id': 1,
                'build': 0,
                'mobi_app': 'web',
            }
            if begin_seqno is not None:
                params['begin_seqno'] = begin_seqno
            if end_seqno is not None:
                params['end_seqno'] = end_seqno
            res = requests.get(url, params, cookies=self.cookies)
            return res.json()['data']

        # 发送小程序卡片
        def sendCard(self, receiver_id, receiver_type, url, title):
            content = {
                "name": "图文消息",
                "avatar": "https://i1.hdslb.com/bfs/face/168aea8d4b02b6cd2235c11a0394a7d25f7350bd.jpg@128w_128h_1o.webp",
                "cover": url + '@64w_64h%2Ewebp',  # 封面
                "id": "biligame0",
                "jump_uri": url,
                "label_cover": "https://i2.hdslb.com/bfs/face/11358442981ec6c066731e1107342d4acdf699c8.jpg@.webp",
                "label_name": "by bilibili",
                "title": title,
            }
            self._sendMsg(receiver_id, receiver_type, 9, content)

        # 发送图片
        def sendImage(self, receiver_id, receiver_type, url, width, height):
            content = {
                "url": url,
                "height": height, "width": width,
                "type": "png", "original": 1, "size": 100,
            }
            self._sendMsg(receiver_id, receiver_type, 2, content)

        # 发送文字
        def sendText(self, receiver_id, receiver_type, text):
            content = {'content': text}
            self._sendMsg(receiver_id, receiver_type, 1, content)

        # 发送消息，延迟控制
        def _sendMsg(self, receiver_id, receiver_type, msg_type, content):
            c_time = time.time()
            d = max(1 - (c_time - self.sendMsgTime), 0.0)  # 执行延时
            self.sendMsgTime = c_time + d
            Timer(d, self._sendMsgThread, (receiver_id, receiver_type, msg_type, content)).start()

        # 发送消息
        def _sendMsgThread(self, receiver_id, receiver_type, msg_type, content):
            url = 'https://api.vc.bilibili.com/web_im/v1/web_im/send_msg'
            data = {
                'msg[sender_uid]': self.mid,
                'msg[receiver_id]': receiver_id,
                'msg[receiver_type]': receiver_type,
                'msg[msg_type]': msg_type,  # 1文本 2图片 5撤回 6表情 7分享 9小游戏 10通知 13 推送消息
                'msg[content]': json.dumps(content, ensure_ascii=False),
                'msg[timestamp]': int(time.time()),
                'msg[dev_id]': '00000000-0000-0000-0000-000000000000',
                'csrf': self.csrf
            }
            res = requests.post(url, data, cookies=self.cookies)
            print(f'{time.time():03f},send:{content}:{receiver_id}_{receiver_type}\n{res.json()}')

    @staticmethod
    def getUserInfo(uids: list):
        url = 'https://api.vc.bilibili.com/account/v1/user/infos'
        params = {'uids': ','.join(uids)}
        return requests.get(url, params).json()['data']

    # B站短链服务
    @staticmethod
    def toB23(img_url):
        img_url = img_url.replace('http:', 'https:', 1)
        url = 'https://api.bilibili.com/x/share/click'
        data = {
            'oid': img_url,
            'platform': 'cr_nmsl',
            'share_channel': 'COPY',
            'build': 5572000,
            'buvid': 0,
            'share_id': 'public.webview.0.0.pv',
            'share_mode': 3
        }
        res = requests.post(url, data).json()
        return res['data'].get('content', '')

    # B站上传图片（图床）
    def upImage(self, file_path):
        # url = 'https://api.vc.bilibili.com/api/v1/image/upload'
        # files = {'file_up': ('image', open(file_path, 'rb'))}
        # res = requests.post(url, files=files).json()
        url = 'https://api.bilibili.com/x/dynamic/feed/draw/upload_bfs'
        files = {'file_up': ('image', open(file_path, 'rb'))}
        res = requests.post(url, data={'csrf': self.csrf}, cookies=self.cookies, files=files).json()
        return res['data']

    # 随机图片API
    @staticmethod
    def getST(tag: str):
        url = 'https://api.lolicon.app/setu/v2'
        tag = [t1.strip() for t1 in re.split(r',|，|&|\s', tag.strip()) if t1.split() != '']
        res = requests.post(url, json={'tag': tag}).json()
        return res['data']


class TxAPI:

    def __init__(self, app_id, app_key):
        cred = credential.Credential(app_id, app_key)
        http_profile = HttpProfile()
        http_profile.endpoint = "ims.tencentcloudapi.com"

        client_profile = ClientProfile()
        client_profile.httpProfile = http_profile
        self.client = ims_client.ImsClient(cred, "ap-shanghai", client_profile)

    def jh(self, url: str, user_id: str):
        try:
            req = models.ImageModerationRequest()
            params = {
                "BizType": "jianhuang",
                "FileUrl": url,
                "User": {
                    "UserId": user_id,
                    "AccountType": "7"
                }
            }
            req.from_json_string(json.dumps(params))

            resp = self.client.ImageModeration(req)
            print(json.dumps(params), resp.to_json_string())
            return json.loads(resp.to_json_string())
        except TencentCloudSDKException as err:
            print(err)
