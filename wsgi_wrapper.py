# wsgi_wrapper.py
import logging
import os
import threading
import time
import uuid
import signal

from api import settings
from api.apps import app
from api.db.runtime_config import RuntimeConfig
from api.db.services.document_service import DocumentService
from api.db.db_models import init_database_tables as init_web_db
from api.db.init_data import init_web_data
from api.versions import get_ragflow_version
from api.utils import show_configs
from rag.settings import print_rag_settings
from rag.utils.redis_conn import RedisDistributedLock

# 初始化操作（来自 ragflow_server.py）
from api.utils.log_utils import initRootLogger
initRootLogger("ragflow_server")

settings.init_settings()
print_rag_settings()
init_web_db()
init_web_data()

RuntimeConfig.DEBUG = False
RuntimeConfig.init_env()
RuntimeConfig.init_config(JOB_SERVER_HOST=settings.HOST_IP, HTTP_PORT=settings.HOST_PORT)

# 后台任务线程（比如文档进度更新）
stop_event = threading.Event()

def update_progress():
    lock_value = str(uuid.uuid4())
    redis_lock = RedisDistributedLock("update_progress", lock_value=lock_value, timeout=60)
    logging.info(f"update_progress lock_value: {lock_value}")
    while not stop_event.is_set():
        try:
            if redis_lock.acquire():
                DocumentService.update_progress()
                redis_lock.release()
            stop_event.wait(6)
        except Exception:
            logging.exception("update_progress exception")

thread = threading.Thread(target=update_progress)
thread.daemon = True
thread.start()

# 提供给 uWSGI 的 WSGI app
application = app
