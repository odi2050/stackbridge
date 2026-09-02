import os,tempfile,time,uuid,hmac,zipfile,shutil,secrets,hashlib,base64
from functools import wraps
from pathlib import Path
from flask import Flask,render_template,request,jsonify,session,redirect,url_for,send_file
import requests
from authlib.integrations.requests_client import OAuth2Session
from config import *
from services import bookstack
from services import settings
from services import auth
from services.converter import convert,SUPPORTED
from services.ai import improve,models
from services.runtime import logger,detail,LOG_DIR
from services.sanitize import clean_html
from version import APP_NAME,APP_DESCRIPTION,APP_VERSION
app=Flask(__name__);app.config.update(MAX_CONTENT_LENGTH=MAX_UPLOAD_MB*1024*1024,SESSION_COOKIE_HTTPONLY=True,SESSION_COOKIE_SAMESITE="Lax",SESSION_COOKIE_SECURE=os.getenv("SESSION_COOKIE_SECURE","false").lower()=="true");app.secret_key=SECRET_KEY;CACHE={};LOGIN_ATTEMPTS={}
PUBLIC_PATHS={"/api/version","/api/health","/auth/login","/auth/oidc/login","/auth/oidc/callback","/auth/local"}
@app.before_request
def log_request_start():
 request._started=time.perf_counter();detail("Route start method=%s path=%s content_length=%s",request.method,request.path,request.content_length)
 if request.path.startswith("/static/") or request.path.startswith("/admin") or request.path.startswith("/api/admin/") or request.path in PUBLIC_PATHS:return None
 cfg=settings.load()
 if cfg.get("oidc_enabled") and not session.get("user") and not session.get("local_fallback"):return redirect(url_for("user_login",next=request.full_path if request.query_string else request.path))
@app.after_request
def log_request_end(response):
 response.headers["X-Content-Type-Options"]="nosniff";response.headers["X-Frame-Options"]="DENY";response.headers["Referrer-Policy"]="same-origin";response.headers["Permissions-Policy"]="camera=(), microphone=(), geolocation=()";response.headers["Content-Security-Policy"]="default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
 if request.is_secure:response.headers["Strict-Transport-Security"]="max-age=31536000; includeSubDomains"
 detail("Route end method=%s path=%s status=%s duration_ms=%d",request.method,request.path,response.status_code,int((time.perf_counter()-getattr(request,"_started",time.perf_counter()))*1000));return response
def csrf_token():
 if "csrf_token" not in session:session["csrf_token"]=secrets.token_urlsafe(32)
 return session["csrf_token"]
app.jinja_env.globals["csrf_token"]=csrf_token
@app.context_processor
def application_identity():return {"app_name":APP_NAME,"app_description":APP_DESCRIPTION,"app_version":APP_VERSION,"current_user":session.get("user"),"local_fallback":bool(session.get("local_fallback"))}
def admin_required(fn):
 @wraps(fn)
 def wrapped(*args,**kwargs):
  if not session.get("admin"):return redirect(url_for("admin_login"))
  if not hmac.compare_digest(session.get("auth_version",""),auth.version()):session.clear();return redirect(url_for("admin_login"))
  supplied=request.headers.get("X-CSRF-Token",request.form.get("csrf_token",""))
  if request.method not in ("GET","HEAD","OPTIONS") and not supplied:return jsonify(success=False,message="Jeton de sécurité manquant. Rechargez la page."),403
  if request.method not in ("GET","HEAD","OPTIONS") and not hmac.compare_digest(supplied,session.get("csrf_token","")):return jsonify(success=False,message="Jeton de sécurité expiré. Rechargez la page."),403
  return fn(*args,**kwargs)
 return wrapped
def chname(n,m):
 p=list(Path(n).parts[:-1]);p=p[1:] if len(p)>1 else []
 return (p[-1] if m=="last" else " - ".join(p)) if p else None
def oidc_discovery(issuer):
 issuer=(issuer or "").strip().rstrip("/")
 if not issuer:raise ValueError("Issuer URL requis")
 verify=settings.load().get("verify_tls",True);response=requests.get(issuer+"/.well-known/openid-configuration",timeout=15,verify=verify);response.raise_for_status();meta=response.json()
 if meta.get("issuer","").rstrip("/")!=issuer:raise ValueError("L'issuer retourné par OIDC ne correspond pas à l'Issuer configuré")
 for field in ("authorization_endpoint","token_endpoint","jwks_uri"):
  if not meta.get(field):raise ValueError(f"Métadonnée OIDC manquante : {field}")
 return meta
def safe_next(value):return value if value and value.startswith("/") and not value.startswith("//") else "/"
@app.get("/")
def home():return render_template("index.html")
@app.get("/auth/login")
def user_login():
 cfg=settings.load()
 if not cfg.get("oidc_enabled"):return redirect(url_for("home"))
 if session.get("user") or session.get("local_fallback"):return redirect(url_for("home"))
 session["login_next"]=safe_next(request.args.get("next"));return render_template("user_login.html",oidc_name=cfg.get("oidc_display_name") or "SSO",fallback=bool(cfg.get("oidc_local_fallback")),error=request.args.get("error"))
@app.get("/auth/oidc/login")
def oidc_login():
 cfg=settings.load()
 if not cfg.get("oidc_enabled"):return redirect(url_for("home"))
 if session.get("user") or session.get("local_fallback"):return redirect(url_for("home"))
 try:
  meta=oidc_discovery(cfg.get("oidc_issuer"));verifier=secrets.token_urlsafe(64);challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode();state=secrets.token_urlsafe(32);session["oidc_state"]=state;session["oidc_verifier"]=verifier
  client=OAuth2Session(cfg.get("oidc_client_id"),cfg.get("oidc_client_secret"),scope=cfg.get("oidc_scopes") or "openid profile email",redirect_uri=url_for("oidc_callback",_external=True),code_challenge_method="S256");uri,_=client.create_authorization_url(meta["authorization_endpoint"],state=state,code_challenge=challenge,code_challenge_method="S256",nonce=secrets.token_urlsafe(24));return redirect(uri)
 except Exception as e:logger.exception("OIDC login initialization failed");return redirect(url_for("user_login",error="OIDC indisponible : "+str(e)))
@app.get("/auth/oidc/callback")
def oidc_callback():
 cfg=settings.load();expected=session.pop("oidc_state",None);verifier=session.pop("oidc_verifier",None)
 if not expected or not hmac.compare_digest(request.args.get("state","") ,expected):return redirect(url_for("user_login",error="État OIDC invalide ou expiré"))
 try:
  meta=oidc_discovery(cfg.get("oidc_issuer"));client=OAuth2Session(cfg.get("oidc_client_id"),cfg.get("oidc_client_secret"),redirect_uri=url_for("oidc_callback",_external=True),code_challenge_method="S256");token=client.fetch_token(meta["token_endpoint"],authorization_response=request.url,code_verifier=verifier)
  claims={}
  if meta.get("userinfo_endpoint"):
   userinfo=client.get(meta["userinfo_endpoint"],token=token,timeout=15);userinfo.raise_for_status();claims=userinfo.json()
  if not claims.get("sub"):raise ValueError("Le fournisseur OIDC n'a pas retourné de claim sub")
  session["user"]={"sub":str(claims.get("sub")),"name":str(claims.get("name") or claims.get("preferred_username") or claims.get("email") or claims.get("sub")),"email":str(claims.get("email") or "")};session.pop("local_fallback",None);target=safe_next(session.pop("login_next","/"));logger.info("OIDC user authenticated sub=%s name=%s",session["user"]["sub"],session["user"]["name"]);return redirect(target)
 except Exception as e:logger.exception("OIDC callback failed");return redirect(url_for("user_login",error="Connexion OIDC impossible : "+str(e)))
@app.get("/auth/local")
def local_access():
 cfg=settings.load()
 if not cfg.get("oidc_enabled") or not cfg.get("oidc_local_fallback"):return redirect(url_for("user_login"))
 session["local_fallback"]=True;session.pop("user",None);logger.warning("Local fallback session started remote_addr=%s",request.remote_addr or "unknown");return redirect(safe_next(session.pop("login_next","/")))
@app.get("/auth/logout")
def user_logout():session.pop("user",None);session.pop("local_fallback",None);return redirect(url_for("user_login"))
@app.get("/api/version")
def version_info():return jsonify(name=APP_NAME,description=APP_DESCRIPTION,version=APP_VERSION)
@app.get("/api/health")
def health():return jsonify(status="ok",name=APP_NAME,version=APP_VERSION)
@app.get("/api/settings")
def public_settings():
 data=settings.load();return jsonify(success=True,configured={"bookstack":bool(data["bookstack_url"] and data["token_id"] and data["token_secret"]),"ai":bool(data["ai_url"] and data["ai_model"]),"oidc":bool(data.get("oidc_enabled"))},auth={"mode":"oidc" if session.get("user") else "local-fallback" if session.get("local_fallback") else "local","user":session.get("user")})
@app.route("/admin/login",methods=["GET","POST"])
def admin_login():
 error=None
 if request.method=="POST":
  supplied=request.form.get("csrf_token","")
  if not supplied or not hmac.compare_digest(supplied,session.get("csrf_token","")):return render_template("admin_login.html",error="Session expirée. Rechargez la page."),403
  client=request.remote_addr or "unknown";now=time.time();attempts=[stamp for stamp in LOGIN_ATTEMPTS.get(client,[]) if now-stamp<900]
  if len(attempts)>=5:return render_template("admin_login.html",error="Trop de tentatives. Réessayez dans 15 minutes."),429
  if auth.verify(request.form.get("password","")):
   LOGIN_ATTEMPTS.pop(client,None);session["admin"]=True;session["auth_version"]=auth.version();csrf_token();return redirect(url_for("admin"))
  attempts.append(now);LOGIN_ATTEMPTS[client]=attempts;error="Mot de passe incorrect"
 return render_template("admin_login.html",error=error)
@app.post("/admin/logout")
@admin_required
def admin_logout():session.pop("admin",None);session.pop("auth_version",None);return redirect(url_for("home"))
@app.get("/admin")
@admin_required
def admin():return render_template("admin.html",settings=settings.public())
@app.post("/api/admin/settings")
@admin_required
def save_settings():settings.save(request.json or {});logger.info("Administrative settings updated");return jsonify(success=True,settings=settings.public())
@app.post("/api/admin/oidc/test")
@admin_required
def test_oidc():
 data=request.json or {};saved=settings.load();issuer=data.get("issuer") or saved.get("oidc_issuer")
 try:
  meta=oidc_discovery(issuer);return jsonify(success=True,issuer=meta.get("issuer"),authorization_endpoint=meta.get("authorization_endpoint"),token_endpoint=meta.get("token_endpoint"))
 except Exception as e:logger.exception("OIDC discovery test failed");return jsonify(success=False,message=str(e)),400
@app.post("/api/admin/password")
@admin_required
def change_admin_password():
 data=request.json or {}
 if data.get("new_password")!=data.get("confirm_password"):return jsonify(success=False,message="Les deux nouveaux mots de passe ne correspondent pas"),400
 try:auth.change(data.get("current_password",""),data.get("new_password",""))
 except ValueError as error:return jsonify(success=False,message=str(error)),400
 logger.info("Administrator password changed");session.clear();return jsonify(success=True,message="Mot de passe modifié. Reconnectez-vous.")
@app.post("/api/admin/models")
@admin_required
def available_models():
 data=request.json or {};saved=settings.load()
 try:return jsonify(success=True,models=models(data.get("ai_url") or saved["ai_url"],data.get("ai_api_key") or saved["ai_api_key"]))
 except Exception as e:logger.exception("AI model discovery failed");return jsonify(success=False,message=str(e)),400
@app.get("/api/admin/logs")
@admin_required
def admin_logs():
 path=Path(LOG_DIR)/"app.log"
 if request.args.get("download")=="1" and path.exists():return send_file(path,as_attachment=True,download_name="stackbridge.log")
 if not path.exists():return jsonify(success=True,logs="")
 lines=path.read_text(encoding="utf-8",errors="replace").splitlines()[-500:];return jsonify(success=True,logs="\n".join(lines))
@app.post("/api/books")
def books():
 try:d=settings.resolve(request.json);detail("Loading BookStack books");return jsonify(success=True,books=bookstack.books(d["url"],d["token_id"],d["token_secret"]))
 except Exception as e:logger.exception("BookStack books failed");return jsonify(success=False,message=str(e)),400
@app.post("/api/analyze")
def analyze():
 out=[];mode=request.form.get("structure_mode","full");st=request.form.get("structure")=="true";files=request.files.getlist("files");detail("Analyze start files=%s structure=%s mode=%s",len(files),st,mode)
 def convert_stream(filename,stream):
  extension=Path(filename).suffix.lower()
  if extension not in SUPPORTED:detail("Analyze skipped unsupported file=%s",filename);return
  with tempfile.NamedTemporaryFile(suffix=extension,delete=False) as temp:shutil.copyfileobj(stream,temp);path=temp.name
  try:html,meta=convert(path,OCR_LANG);html=clean_html(html)
  finally:os.remove(path)
  cache_id=str(uuid.uuid4());CACHE[cache_id]={"html":html,"ai":None,"meta":meta,"title":Path(filename).stem,"file":filename,"chapter":chname(filename,mode) if st else None,"time":time.time()};out.append({"id":cache_id,"title":CACHE[cache_id]["title"],"file":filename,"chapter":CACHE[cache_id]["chapter"],"meta":meta})
 for f in files:
  e=Path(f.filename).suffix.lower()
  if e==".zip":
   try:
    with zipfile.ZipFile(f.stream) as archive:
     members=[x for x in archive.infolist() if not x.is_dir() and Path(x.filename).suffix.lower() in SUPPORTED]
     if len(members)>2000:return jsonify(success=False,message="Archive refusée : plus de 2000 documents pris en charge"),400
     if sum(x.file_size for x in members)>MAX_UPLOAD_MB*1024*1024:return jsonify(success=False,message="Archive refusée : contenu décompressé trop volumineux"),400
     for member in members:
      name=member.filename.replace("\\","/").lstrip("/")
      if ".." in Path(name).parts or member.flag_bits&1:return jsonify(success=False,message="Archive ZIP invalide ou chiffrée"),400
      with archive.open(member) as source:convert_stream(name,source)
   except zipfile.BadZipFile:return jsonify(success=False,message=f"Archive ZIP illisible : {f.filename}"),400
  else:f.stream.seek(0);convert_stream(f.filename,f.stream)
 return jsonify(success=True,items=out)
@app.get("/api/preview/<k>")
def preview(k):
 x=CACHE.get(k)
 if not x:return jsonify(message="Prévisualisation expirée"),404
 return jsonify(success=True,html=x["ai"] if request.args.get("version")=="ai" and x["ai"] else x["html"],has_ai=bool(x["ai"]))
@app.post("/api/ai/<k>")
def ai(k):
 x=CACHE.get(k)
 if not x:return jsonify(message="Prévisualisation expirée"),404
 d=request.json or {};saved=settings.load()
 try:x["ai"]=clean_html(improve(x["html"],d.get("url") or saved["ai_url"],d.get("model") or saved["ai_model"],d.get("api_key") or saved["ai_api_key"],d.get("level","structure"),bool(saved.get("send_images_to_ai",False)),bool(saved.get("ai_custom_enabled",False)),saved.get("ai_endpoint","/chat/completions"),saved.get("ai_request_json",""),saved.get("ai_response_path","choices.0.message.content"),saved.get("ai_chunk_tokens","2000")));return jsonify(success=True)
 except Exception as e:logger.exception("AI improvement failed cache_id=%s",k);return jsonify(success=False,message=str(e)),400
@app.post("/api/import")
def imp():
 try:
  d=settings.resolve(request.json);selected=[q for q in d["items"] if q.get("selected")];identity=session.get("user") or {"name":"local-fallback" if session.get("local_fallback") else "local","sub":"","email":""};logger.info("BookStack import started actor=%s sub=%s selected=%s",identity.get("name"),identity.get("sub"),len(selected));cc=bookstack.chapters(d["url"],d["token_id"],d["token_secret"],d["book_id"]);res=[]
  for q in selected:
   x=CACHE.get(q["id"])
   if not x:continue
   cid=None
   if x["chapter"]:
    key=x["chapter"].lower();cid=cc.get(key)
    if not cid:cid=bookstack.create_chapter(d["url"],d["token_id"],d["token_secret"],d["book_id"],x["chapter"]);cc[key]=cid
   html=x["ai"] if q.get("use_ai") and x["ai"] else x["html"];page=bookstack.create_page(d["url"],d["token_id"],d["token_secret"],x["title"],html,book_id=d["book_id"] if not cid else None,chapter_id=cid);res.append({"file":x["file"],"page":page})
  return jsonify(success=True,results=res)
 except Exception as e:logger.exception("BookStack import failed");return jsonify(success=False,message=str(e)),400
if __name__=="__main__":app.run(host="0.0.0.0",port=5050,debug=False)
