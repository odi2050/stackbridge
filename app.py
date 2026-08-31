import os,tempfile,time,uuid,hmac,zipfile,shutil,secrets
from functools import wraps
from pathlib import Path
from flask import Flask,render_template,request,jsonify,session,redirect,url_for,send_file
from config import *
from services import bookstack
from services import settings
from services import auth
from services.converter import convert,SUPPORTED
from services.ai import improve,models
from services.runtime import logger,detail,LOG_DIR
from services.sanitize import clean_html
from version import APP_NAME,APP_DESCRIPTION,APP_VERSION
app=Flask(__name__);app.config.update(MAX_CONTENT_LENGTH=MAX_UPLOAD_MB*1024*1024,SESSION_COOKIE_HTTPONLY=True,SESSION_COOKIE_SAMESITE="Strict",SESSION_COOKIE_SECURE=os.getenv("SESSION_COOKIE_SECURE","false").lower()=="true");app.secret_key=SECRET_KEY;CACHE={};LOGIN_ATTEMPTS={}
@app.before_request
def log_request_start():
 request._started=time.perf_counter();detail("Route start method=%s path=%s content_length=%s",request.method,request.path,request.content_length)
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
def application_identity():return {"app_name":APP_NAME,"app_description":APP_DESCRIPTION,"app_version":APP_VERSION}
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
@app.get("/")
def home():return render_template("index.html")
@app.get("/api/version")
def version_info():return jsonify(name=APP_NAME,description=APP_DESCRIPTION,version=APP_VERSION)
@app.get("/api/health")
def health():return jsonify(status="ok",name=APP_NAME,version=APP_VERSION)
@app.get("/api/settings")
def public_settings():
 data=settings.load()
 return jsonify(success=True,configured={"bookstack":bool(data["bookstack_url"] and data["token_id"] and data["token_secret"]),"ai":bool(data["ai_url"] and data["ai_model"])})
@app.route("/admin/login",methods=["GET","POST"])
def admin_login():
 error=None
 if request.method=="POST":
  supplied=request.form.get("csrf_token","")
  if not supplied or not hmac.compare_digest(supplied,session.get("csrf_token","")):return render_template("admin_login.html",error="Session expirée. Rechargez la page."),403
  client=request.remote_addr or "unknown";now=time.time();attempts=[stamp for stamp in LOGIN_ATTEMPTS.get(client,[]) if now-stamp<900]
  if len(attempts)>=5:return render_template("admin_login.html",error="Trop de tentatives. Réessayez dans 15 minutes."),429
  if auth.verify(request.form.get("password","")):
   LOGIN_ATTEMPTS.pop(client,None);session.clear();session["admin"]=True;session["auth_version"]=auth.version();csrf_token();return redirect(url_for("admin"))
  attempts.append(now);LOGIN_ATTEMPTS[client]=attempts
  error="Mot de passe incorrect"
 return render_template("admin_login.html",error=error)
@app.post("/admin/logout")
@admin_required
def admin_logout():session.clear();return redirect(url_for("home"))
@app.get("/admin")
@admin_required
def admin():return render_template("admin.html",settings=settings.public())
@app.post("/api/admin/settings")
@admin_required
def save_settings():
 settings.save(request.json or {})
 logger.info("Administrative settings updated")
 return jsonify(success=True,settings=settings.public())
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
 lines=path.read_text(encoding="utf-8",errors="replace").splitlines()[-500:]
 return jsonify(success=True,logs="\n".join(lines))
@app.post("/api/books")
def books():
 d=settings.resolve(request.json)
 try:detail("Loading BookStack books");return jsonify(success=True,books=bookstack.books(d["url"],d["token_id"],d["token_secret"]))
 except Exception as e:logger.exception("BookStack books failed");return jsonify(success=False,message=str(e)),400
@app.post("/api/analyze")
def analyze():
 out=[];mode=request.form.get("structure_mode","full");st=request.form.get("structure")=="true"
 files=request.files.getlist("files");detail("Analyze start files=%s structure=%s mode=%s",len(files),st,mode)
 def convert_stream(filename,stream):
  extension=Path(filename).suffix.lower()
  if extension not in SUPPORTED:detail("Analyze skipped unsupported file=%s",filename);return
  detail("Analyze document name=%s extension=%s",filename,extension)
  with tempfile.NamedTemporaryFile(suffix=extension,delete=False) as temp:
   shutil.copyfileobj(stream,temp);path=temp.name
  try:html,meta=convert(path,OCR_LANG);html=clean_html(html)
  finally:os.remove(path)
  cache_id=str(uuid.uuid4());CACHE[cache_id]={"html":html,"ai":None,"meta":meta,"title":Path(filename).stem,"file":filename,"chapter":chname(filename,mode) if st else None,"time":time.time()}
  out.append({"id":cache_id,"title":CACHE[cache_id]["title"],"file":filename,"chapter":CACHE[cache_id]["chapter"],"meta":meta})
 for index,f in enumerate(files,1):
  e=Path(f.filename).suffix.lower()
  detail("Analyze source index=%s/%s name=%s extension=%s",index,len(files),f.filename,e)
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
  else:
   f.stream.seek(0);convert_stream(f.filename,f.stream)
 detail("Analyze complete converted=%s",len(out))
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
 try:x["ai"]=clean_html(improve(x["html"],d.get("url") or saved["ai_url"],d.get("model") or saved["ai_model"],d.get("api_key") or saved["ai_api_key"],d.get("level","structure"),bool(saved.get("send_images_to_ai",False)),bool(saved.get("ai_custom_enabled",False)),saved.get("ai_endpoint","/chat/completions"),saved.get("ai_request_json",""),saved.get("ai_response_path","choices.0.message.content")));return jsonify(success=True)
 except Exception as e:logger.exception("AI improvement failed cache_id=%s",k);return jsonify(success=False,message=str(e)),400
@app.post("/api/import")
def imp():
 d=settings.resolve(request.json)
 try:
  selected=[q for q in d["items"] if q.get("selected")];detail("Import start book_id=%s selected=%s",d["book_id"],len(selected));cc=bookstack.chapters(d["url"],d["token_id"],d["token_secret"],d["book_id"]);res=[]
  for index,q in enumerate(selected,1):
   x=CACHE.get(q["id"])
   if not x:continue
   detail("Import item index=%s/%s file=%s",index,len(selected),x["file"])
   cid=None
   if x["chapter"]:
    key=x["chapter"].lower();cid=cc.get(key)
    if not cid:c=bookstack.new_chapter(d["url"],d["token_id"],d["token_secret"],d["book_id"],x["chapter"]);cid=c["id"];cc[key]=cid
   body=x["ai"] if q.get("version")=="ai" and x["ai"] else x["html"]
   p=bookstack.new_page(d["url"],d["token_id"],d["token_secret"],d["book_id"],cid,x["title"],body);res.append({"file":x["file"],"page_id":p.get("id")})
  detail("Import complete pages=%s",len(res))
  return jsonify(success=True,results=res)
 except Exception as e:logger.exception("BookStack import failed");return jsonify(success=False,message=str(e)),400
if __name__=="__main__":
 from waitress import serve
 if ADMIN_PASSWORD=="admin" and not ADMIN_PASSWORD_HASH:logger.warning("ADMIN_PASSWORD is still the insecure default; configure ADMIN_PASSWORD_HASH for production")
 if SECRET_KEY=="stackbridge-change-me":logger.warning("SECRET_KEY is still the insecure default; configure a random production value")
 logger.info("Starting %s %s production WSGI server on 0.0.0.0:5050",APP_NAME,APP_VERSION)
 serve(app,host="0.0.0.0",port=5050,threads=8)
