import hmac
import hashlib
import json
import os
import tempfile
from pathlib import Path
from werkzeug.security import check_password_hash,generate_password_hash
from config import ADMIN_PASSWORD,ADMIN_PASSWORD_HASH

AUTH_FILE=Path(__file__).resolve().parent.parent/"data"/"admin_auth.json"
def password_hash():
 try:return str(json.loads(AUTH_FILE.read_text(encoding="utf-8")).get("password_hash","") or "")
 except (FileNotFoundError,json.JSONDecodeError,OSError):return ADMIN_PASSWORD_HASH
def verify(password):
 stored=password_hash();return check_password_hash(stored,password) if stored else hmac.compare_digest(password,ADMIN_PASSWORD)
def version():
 stored=password_hash() or "legacy:"+ADMIN_PASSWORD
 return hashlib.sha256(stored.encode()).hexdigest()
def change(current,new):
 if not verify(current):raise ValueError("Le mot de passe actuel est incorrect")
 if len(new)<12:raise ValueError("Le nouveau mot de passe doit contenir au moins 12 caractères")
 AUTH_FILE.parent.mkdir(parents=True,exist_ok=True);data={"password_hash":generate_password_hash(new,method="scrypt")}
 fd,tmp=tempfile.mkstemp(prefix="auth-",suffix=".json",dir=AUTH_FILE.parent)
 try:
  with os.fdopen(fd,"w",encoding="utf-8") as file:json.dump(data,file,indent=2)
  os.replace(tmp,AUTH_FILE)
  try:os.chmod(AUTH_FILE,0o600)
  except OSError:pass
 finally:
  if os.path.exists(tmp):os.remove(tmp)
