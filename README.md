# bili-robot
自用B站私信机器人

1. 安装 python3、 postgres
2. 使用 init.sql 脚本初始化数据库
3. 安装 PIP 包，`python3 -m pip install requests tomlkit tencentcloud psycopg2`
4. 开通腾讯云“内容安全功能”（每个月有免费的1万张图片额度）https://console.cloud.tencent.com/cms
5. 生成腾讯云API密钥并保存，https://console.cloud.tencent.com/cam/capi
6. 按照注释填写 `config.toml` 文件
7. 启动脚本 `python3 -u ./main.py`
