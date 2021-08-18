import json

import psycopg2
from psycopg2 import extras


class DB:

    def __init__(self, **db_config):
        self.conn = psycopg2.connect(**db_config)
        self.cursor = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)  # 字典形式返回游标

    # 根据key获取消息
    def getMsgByKey(self, msg_key) -> dict:
        sql = "select data->'msg_type' as msg_type, content->>'url' as url, data->'timestamp' as timestamp " \
              "from msg where msg_key = %s;"
        self.cursor.execute(sql, (msg_key,))
        return self.cursor.fetchone()

    # 保存或更新消息
    def saveMsg(self, msg_data, mid):
        if len(msg_data) == 0:
            return
        sql = 'insert into msg (msg_key, content, data, mid) values (%s, %s, %s, %s) ON conflict(msg_key) DO NOTHING;'
        sql_data = []
        for msg in msg_data:
            tmp_msg = msg.copy()
            msg_key = tmp_msg['msg_key']
            content = tmp_msg['content']
            del tmp_msg['content']
            sql_data.append((msg_key, content, json.dumps(tmp_msg, ensure_ascii=False), mid))
        self.cursor.executemany(sql, sql_data)
        self.conn.commit()

    # 获取图片信息
    def getImage(self, url):
        img_id = url[url.rfind('/') + 1: url.rfind('.')]
        sql = 'select id, url, short_url, size, width, height, tx_content_review from img where id = %s;'
        self.cursor.execute(sql, (img_id,))
        return self.cursor.fetchone()

    # 保存图片信息
    def saveImage(self, url, size, width, height, image_type, tx_data):
        img_id = url[url.rfind('/') + 1: url.rfind('.')]
        sql = 'insert into img (id, url, size, width, height, image_type, tx_content_review) values (%s, %s, %s, %s, %s, %s, %s) ON conflict(id) DO NOTHING;'
        sql_data = (img_id, url, int(size), int(width), int(height), image_type,
                    json.dumps(tx_data, ensure_ascii=False))
        self.cursor.execute(sql, sql_data)
        self.conn.commit()

    # 保存图片短链信息
    def saveImageShortUrl(self, gene_short_url, short_url):
        img_id = gene_short_url[gene_short_url.rfind('/') + 1: gene_short_url.rfind('.')]
        sql = 'update img set gene_short_url = %s, short_url = %s where id = %s;'
        sql_data = (gene_short_url, short_url, img_id)
        self.cursor.execute(sql, sql_data)
        self.conn.commit()
