import threading
import time

import pymysql
from pymysql.converters import escape_string

import config

inst = None


class DatabaseManager:
    host = ''
    port = 0
    user = ''
    password = ''
    database = ''
    conn = None
    cursor = None

    def __init__(self, host: str, port: int, user: str, password: str, database: str):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.database = database

        self.reconnect()

        heartbeat_proxy = threading.Thread(target=self.heartbeat, daemon=True)
        heartbeat_proxy.start()

        global inst
        inst = self

    def heartbeat(self):
        while True:
            time.sleep(30)
            self.conn.ping(reconnect=True)

    def reconnect(self):
        self.conn = pymysql.connect(host=self.host, port=self.port, user=self.user, password=self.password,
                                    database=self.database, autocommit=True)
        self.cursor = self.conn.cursor()

    def initialize_database(self):
        self.cursor.execute("""
        create table if not exists `sessions` (
            `id` bigint not null auto_increment primary key,
            `name` varchar(255) not null,
            `type` varchar(255) not null,
            `number` bigint not null,
            `create_timestamp` bigint not null,
            `last_interact_timestamp` bigint not null,
            `status` varchar(255) not null default 'on_going',
            `prompt` text not null
        )
        """)
        print('Database initialized.')

    def persistence_session(self, subject_type: str, subject_number: int, create_timestamp: int,
                            last_interact_timestamp: int, prompt: str):
        # 检查是否已经有了此name和create_timestamp的session
        # 如果有，就更新prompt和last_interact_timestamp
        # 如果没有，就插入一条新的记录
        self.cursor.execute("""
        select count(*) from `sessions` where `type` = '{}' and `number` = {} and `create_timestamp` = {}
        """.format(subject_type, subject_number, create_timestamp))
        count = self.cursor.fetchone()[0]
        if count == 0:
            self.cursor.execute("""
            insert into `sessions` (`name`, `type`, `number`, `create_timestamp`, `last_interact_timestamp`, `prompt`) 
            values ('{}', '{}', {}, {}, {}, '{}')
            """.format("{}_{}".format(subject_type, subject_number), subject_type, subject_number, create_timestamp,
                       last_interact_timestamp, escape_string(prompt)))
        else:
            self.cursor.execute("""
            update `sessions` set `last_interact_timestamp` = {}, `prompt` = '{}' 
            where `type` = '{}' and `number` = {} and `create_timestamp` = {}
            """.format(last_interact_timestamp, escape_string(prompt), subject_type,
                       subject_number, create_timestamp))

    def explicit_close_session(self, session_name: str, create_timestamp: int):
        self.cursor.execute("""
        update `sessions` set `status` = 'explicitly_closed' where `name` = '{}' and `create_timestamp` = {}
        """.format(session_name, create_timestamp))

    # 记载还没过期的session数据
    def load_valid_sessions(self) -> dict:
        # 从数据库中加载所有还没过期的session
        self.cursor.execute("""
        select `name`, `type`, `number`, `create_timestamp`, `last_interact_timestamp`, `prompt`, `status`
        from `sessions` where `last_interact_timestamp` > {}
        """.format(int(time.time()) - config.session_expire_time))
        results = self.cursor.fetchall()
        sessions = {}
        for result in results:
            session_name = result[0]
            subject_type = result[1]
            subject_number = result[2]
            create_timestamp = result[3]
            last_interact_timestamp = result[4]
            prompt = result[5]
            status = result[6]

            # 当且仅当最后一个该对象的会话是on_going状态时，才会被加载
            if status == 'on_going':
                sessions[session_name] = {
                    'subject_type': subject_type,
                    'subject_number': subject_number,
                    'create_timestamp': create_timestamp,
                    'last_interact_timestamp': last_interact_timestamp,
                    'prompt': prompt
                }
            else:
                if session_name in sessions:
                    del sessions[session_name]

        return sessions


def get_inst() -> DatabaseManager:
    global inst
    return inst