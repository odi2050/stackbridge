import json
import os
import tempfile
from pathlib import Path
from cryptography.fernet import Fernet,InvalidToken

DATA_DIR=Path(__file__).resolve().parent.parent/"data"
SETTINGS_FILE=DATA_DIR/"settings.json"
KEY_FILE=DATA_DIR/".settings.key"
SECRET_FIELDS={"token_id","token_secret","ai_api_key"}
PREFIX="enc:v1:"
DEFAULTS={"bookstack_url":"","token_id":"","token_secret":"","ai_url":"","ai_model":"","ai_api_key":"","ai_custom_enabled":False,"ai_endpoint":"/chat/completions","ai_request_json":"","ai_response_path":"choices.0.message.content","verify_tls":True,"debug_logs":False,"send_images_to_ai":False}

def _fernet():
 key=os.getenv("SETTINGS_ENCRYPTION_KEY","").strip().encode()
 if not key:
  DATA_DIR.mkdir(parents=True,exist_ok=True)
  if KEY_FILE.exists():key=KEY_FILE.read_bytes().strip()
  else:
   key=Fernet.generate_key();KEY_FILE.write_bytes(key)
   try:os.chmod(KEY_FILE,0o600)
   except OSError:pass
 try:return Fernet(key)
 except (ValueError,TypeError) as error:raise RuntimeError("SETTINGS_ENCRYPTION_KEY est invalide") from error

def _encode(data):
 encrypted=dict(data);cipher=_fernet()
 for field in SECRET_FIELDS:
  value=str(encrypted.get(field) or "")
  if value and not value.startswith(PREFIX):encrypted[field]=PREFIX+cipher.encrypt(value.encode()).decode()
 return encrypted

def _decode(data):
 decoded=dict(data);cipher=_fernet()
 for field in SECRET_FIELDS:
  value=str(decoded.get(field) or "")
  if value.startswith(PREFIX):
   try:decoded[field]=cipher.decrypt(value[len(PREFIX):].encode()).decode()
   except InvalidToken as error:raise RuntimeError(f"Impossible de déchiffrer {field}: clé de chiffrement incorrecte") from error
 return decoded

def _write(data):
 SETTINGS_FILE.parent.mkdir(parents=True,exist_ok=True)
 fd,tmp=tempfile.mkstemp(prefix="settings-",suffix=".json",dir=SETTINGS_FILE.parent)
 try:
  with os.fdopen(fd,"w",encoding="utf-8") as file:json.dump(_encode(data),file,ensure_ascii=False,indent=2)
  os.replace(tmp,SETTINGS_FILE)
  try:os.chmod(SETTINGS_FILE,0o600)
  except OSError:pass
 finally:
  if os.path.exists(tmp):os.remove(tmp)

def load():
 try:raw=json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
 except FileNotFoundError:return DEFAULTS.copy()
 except json.JSONDecodeError as error:raise RuntimeError(f"settings.json invalide: {error}") from error
 merged={**DEFAULTS,**raw};decoded=_decode(merged)
 if any(decoded.get(field) and not str(raw.get(field,"")).startswith(PREFIX) for field in SECRET_FIELDS):_write(decoded)
 return decoded

def save(values):
 current=load()
 for key in DEFAULTS:
  value=values.get(key)
  if key in ("token_secret","ai_api_key") and not value:continue
  if key in ("verify_tls","debug_logs","send_images_to_ai","ai_custom_enabled"):current[key]=value is True or str(value).lower()=="true"
  else:current[key]=str(value or "").strip()
 _write(current);return current

def public():
 data=load()
 return {"bookstack_url":data["bookstack_url"],"token_id":data["token_id"],"has_token_secret":bool(data["token_secret"]),"ai_url":data["ai_url"],"ai_model":data["ai_model"],"has_ai_api_key":bool(data["ai_api_key"]),"ai_custom_enabled":bool(data["ai_custom_enabled"]),"ai_endpoint":data["ai_endpoint"],"ai_request_json":data["ai_request_json"],"ai_response_path":data["ai_response_path"],"verify_tls":bool(data["verify_tls"]),"debug_logs":bool(data["debug_logs"]),"send_images_to_ai":bool(data["send_images_to_ai"])}

def resolve(data):
 saved=load();out=dict(data or {});out["url"]=out.get("url") or saved["bookstack_url"];out["token_id"]=out.get("token_id") or saved["token_id"];out["token_secret"]=out.get("token_secret") or saved["token_secret"];return out
