#! python3
# python3 -m pip install requests tomlkit tencentcloud psycopg2
import os
import time
import json
import traceback
from functools import lru_cache

import requests
import tomlkit

from api import BiliAPI
from api import TxAPI
from db import DB


class Msg:

    def __init__(self):
        config_file = 'config_p.toml' if os.path.exists('config_p.toml') else 'config.toml'
        with open(config_file, 'r', encoding='utf-8') as conf:
            self.conf = tomlkit.parse(conf.read())

        self.cookies = {tmp.split("=", 1)[0]: tmp.split("=", 1)[1] for tmp in self.conf['cookies'].split("; ")}
        self.csrf = self.cookies['bili_jct']
        self.mid = self.cookies['DedeUserID']

        self.bili = BiliAPI(self.cookies)
        self.tx = TxAPI(self.conf['tx_api']['app_id'], self.conf['tx_api']['app_key'])

        self.db = DB(**self.conf['db'])

        self.begin_ts = 0
        self.last_msg = {}  # mid: {last_seqno, last_time}

        self.talker_id = 221004361

    def test(self):
        self.db.saveImage('https://message.biliimg.com/bfs/im/1880c3ccb30dfbab7affa56b04557096bd54b852.jpg',
                          129, 1280, 797, 'png', {})

    def run(self):
        while True:
            try:
                self._loop()
            except Exception as e:
                print(f"loop_error: {e}")
                traceback.print_exc()
            time.sleep(10)

    # 循环体
    def _loop(self):
        session_list = self.bili.msg.getNewSession(self.begin_ts)
        print(f'{time.time():03f},getNewSession:{len(session_list)}:{self.begin_ts}')
        session_ts = self.begin_ts
        for session in session_list:
            # 遍历会话
            session_ts = max(session_ts, session['session_ts'])
            talker_id = session['talker_id']
            session_type = session['session_type']
            max_seqno = session['max_seqno']
            session_key = f'{talker_id}_{session_type}'
            if session_key in self.conf.get('whitelist', []) or len(self.conf.get('whitelist', [])) == 0:
                # 白名单会话获取消息并保存
                begin_seqno = self.last_msg.get(session_key, None)
                if begin_seqno is None or begin_seqno < max_seqno:
                    session_msgs_data = self.bili.msg.fetchSessionMsgs(talker_id, session_type, begin_seqno, None)
                    messages = session_msgs_data['messages'][::-1]
                    tmp_max_seqno = session_msgs_data['max_seqno']
                    print(f'{time.time():03f},--fetchSessionMsgs({talker_id}):{len(messages)}:{begin_seqno}')
                    self.db.saveMsg(messages, self.mid)
                    if begin_seqno is not None:
                        try:
                            self.handle(messages)
                        except Exception as e:
                            print(f"handle_error: {e}")
                            traceback.print_exc()
                    self.last_msg[session_key] = tmp_max_seqno  # 更新 last_seqno
        self.begin_ts = session_ts  # 更新 last_ts

    # 消息处理函数
    def handle(self, session_msgs_data):
        img_index = 0
        img_len = len([1 for msg in session_msgs_data if msg['msg_type'] == 2])
        for index, msg in enumerate(session_msgs_data):
            receiver_id = msg['receiver_id']
            receiver_type = msg['receiver_type']
            sender_uid = msg['sender_uid']
            receiver_id = receiver_id if str(receiver_type) == '2' else sender_uid
            session_key = f'{receiver_id}_{receiver_type}'

            if msg.get('sys_cancel', False):
                self.type5(msg)

            elif msg['msg_type'] == 1:
                text = json.loads(msg['content']).get('content', '')
                if text.startswith('图来'):
                    if session_key in self.conf.get('mt_blacklist', []):
                        self.bili.msg.sendText(receiver_id, receiver_type, f'检测到该群存在内鬼，请在其他群或私信使用指令！')
                    else:
                        self.sendST(receiver_id, receiver_type, text[2:].strip())

            elif msg['msg_type'] == 2:
                # 图片类型消息，进行图片内容识别打分
                img_index += 1
                if session_key in self.conf.get('jh_whitelist', []):
                    image_info = json.loads(msg['content'])
                    url = image_info['url']

                    img_info = self.db.getImage(url)
                    if img_info is None:
                        tx_data = self.tx.jh(url, str(sender_uid))
                        image_type = image_info.get('type', image_info.get('imageType'))
                        self.db.saveImage(url, image_info['size'],
                                          image_info['width'], image_info['height'], image_type, tx_data)
                    else:
                        tx_data = img_info['tx_content_review']

                    if tx_data is None or tx_data.get('Suggestion') is None:
                        print(f'图片内容识别异常：{tx_data}')
                    elif tx_data['Suggestion'] in ['Block', 'Review']:
                        user_name = self.getUserName(sender_uid)
                        send_msg = f'@{user_name} ' + ('好图！' if tx_data['Suggestion'] == 'Block' else '还行。')
                        if img_len > 1:
                            send_msg += f' (第{img_index}张)'
                        for label in tx_data['LabelResults']:
                            send_msg += f"\n{label['Scene']}/{label['Label']}/{label['SubLabel']}: {label['Score']}%"
                        send_msg += f"\n{url[url.rfind('/') + 1: url.rfind('.')]}"
                        # self.bili.msg.sendImage(
                        #     receiver_id, receiver_type,
                        #     'https://message.biliimg.com/bfs/im/668dc8b76359992c0514acf3b33aaccddd3acb64.jpg',
                        #     343, 354
                        # )
                        self.bili.msg.sendText(receiver_id, receiver_type, send_msg)

    # 根据UID获取用户名（缓存6小时）
    def getUserName(self, uid):
        return self._getUserName(uid, time.time() // (6 * 60 * 60))

    @lru_cache(maxsize=1000)
    def _getUserName(self, uid, _):
        print(f'------getUserName:{uid}')
        user_info = self.bili.getUserInfo([str(uid)])
        return user_info[0]['uname']

    # 消息被审核撤回
    def type5(self, msg):
        old_msg = self.db.getMsgByKey(msg["content"])
        if old_msg is None:
            return
        msg_type = int(old_msg['msg_type'])
        url = old_msg['url']
        old_msg_time = int(old_msg['timestamp'])
        content = old_msg['content']  # type:str

        sender_uid = msg['sender_uid']
        sender_uname = self.getUserName(sender_uid)
        receiver_id = msg['receiver_id']
        receiver_type = msg['receiver_type']
        time1 = time.strftime("%H:%M:%S", time.localtime(old_msg_time))
        time2 = time.strftime("%H:%M:%S", time.localtime(msg['timestamp']))

        if msg_type == 1:
            if not content.startswith('一条文字消息被撤回'):
                self.bili.msg.sendText(receiver_id, receiver_type,
                                       f'一条文字消息被撤回\n'
                                       f'time: {time1}~{time2}\nuser: {sender_uname}\ncontent: {content}\n'
                                       f'{msg["content"][11:]}')
        elif msg_type in [2, 6]:
            img_info = self.db.getImage(url)
            if img_info is None or img_info['short_url'] is None:
                if 'message.biliimg.com' in url:
                    img_name = url[url.rfind('/') + 1:]
                    url = self.imgToBiliImg(url, f'image/bili/{img_name}')
                b23_url = self.bili.toB23(url)
                self.db.saveImageShortUrl(url, b23_url)
            else:
                b23_url = img_info['short_url']
            self.bili.msg.sendText(receiver_id, receiver_type,
                                   f'一张图片经审核认证为[喜欢]\n'
                                   f'并被撤回，请及时查看\n'
                                   f'time: {time1}~{time2}\nuser: {sender_uname}\n'
                                   f'url: {b23_url}\n{msg["content"][11:]}')

    def sendST(self, receiver_id, receiver_type, tag):
        print(f'图来----{tag}')
        # 获取图片信息
        res = self.bili.getST(tag)
        if len(res) == 0:
            self.bili.msg.sendText(receiver_id, receiver_type, f'未找到标签为{tag}的图片')
            return
        img = res[0]
        pid = img['pid']
        p = img['p']
        ext = img['ext']
        img_name = f'{pid}_p{p}.{ext}'
        img_path = f'image/{img_name}'
        title = img['title']
        # width = img['width']
        # height = img['height']
        url = img['urls']['original']
        print(res)
        image_url = self.imgToBiliImg(url, img_path)
        # 发送图片
        # self.API.sendImage(receiver_id, receiver_type, image_url, width, height)
        self.bili.msg.sendCard(receiver_id, receiver_type, image_url, f'{title}\npid:{pid}')

    def imgToBiliImg(self, url, img_path):
        # 下载图片
        if not os.path.exists(img_path):
            res = requests.get(url)
            print(res.status_code)
            with open(img_path, 'wb') as f:
                f.write(res.content)
        # 上传图片
        return self.bili.upImage(img_path).get('image_url', None)


if __name__ == '__main__':
    Msg().run()
