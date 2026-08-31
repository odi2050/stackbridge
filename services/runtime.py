import logging
import os
import time
from logging.handlers import RotatingFileHandler
import requests
import urllib3

LOG_DIR=os.path.join(os.path.dirname(os.path.dirname(__file__)),"logs")
os.makedirs(LOG_DIR,exist_ok=True)
logger=logging.getLogger("stackbridge");logger.setLevel(logging.DEBUG)
if not logger.handlers:
 formatter=logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
 file_handler=RotatingFileHandler(os.path.join(LOG_DIR,"app.log"),maxBytes=5_000_000,backupCount=5,encoding="utf-8");file_handler.setFormatter(formatter);logger.addHandler(file_handler)
 console=logging.StreamHandler();console.setFormatter(formatter);logger.addHandler(console)

def debug_enabled():
 from .settings import load
 return os.getenv("DEBUG_LOGS","").lower()=="true" or bool(load().get("debug_logs"))

def verify_tls():
 from .settings import load
 env=os.getenv("VERIFY_TLS")
 return env.lower()=="true" if env is not None else bool(load().get("verify_tls",True))

def detail(message,*args):
 if debug_enabled():logger.debug(message,*args)

def request(method,url,**kwargs):
 verify=verify_tls();kwargs["verify"]=verify
 if not verify:urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
 started=time.perf_counter();detail("HTTP start method=%s url=%s verify_tls=%s timeout=%s",method.upper(),url,verify,kwargs.get("timeout",30))
 try:
  response=requests.request(method,url,**kwargs);detail("HTTP end method=%s url=%s status=%s duration_ms=%d",method.upper(),url,response.status_code,int((time.perf_counter()-started)*1000));return response
 except Exception:
  logger.exception("HTTP failure method=%s url=%s verify_tls=%s",method.upper(),url,verify);raise
