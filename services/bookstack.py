from .runtime import request,detail

def headers(token_id,token_secret):return {"Authorization":f"Token {token_id}:{token_secret}","Accept":"application/json"}
def all_(url,endpoint,token_id,token_secret,verify=None):
 out=[];offset=0;url=url.rstrip("/")
 while True:
  detail("BookStack list endpoint=%s offset=%s",endpoint,offset)
  response=request("GET",f"{url}/api/{endpoint}",headers=headers(token_id,token_secret),params={"count":100,"offset":offset},timeout=30);response.raise_for_status();batch=response.json().get("data",[]);out+=batch
  if len(batch)<100:return out
  offset+=100
def books(url,token_id,token_secret,verify=None):return sorted([{"id":x["id"],"name":x["name"]} for x in all_(url,"books",token_id,token_secret)],key=lambda x:x["name"].lower())
def chapters(url,token_id,token_secret,book_id,verify=None):return {x["name"].strip().lower():x["id"] for x in all_(url,"chapters",token_id,token_secret) if int(x.get("book_id",0))==int(book_id)}
def new_chapter(url,token_id,token_secret,book_id,name,verify=None):
 detail("BookStack create chapter book_id=%s name=%s",book_id,name)
 response=request("POST",url.rstrip("/")+"/api/chapters",headers={**headers(token_id,token_secret),"Content-Type":"application/json"},json={"book_id":int(book_id),"name":name,"description":"Créé par StackBridge"},timeout=30);response.raise_for_status();return response.json()
def new_page(url,token_id,token_secret,book_id,chapter_id,name,html,verify=None):
 payload={"name":name,"html":html};payload["chapter_id" if chapter_id else "book_id"]=int(chapter_id or book_id);detail("BookStack create page target=%s name=%s html_chars=%s",chapter_id or book_id,name,len(html))
 response=request("POST",url.rstrip("/")+"/api/pages",headers={**headers(token_id,token_secret),"Content-Type":"application/json"},json=payload,timeout=180);response.raise_for_status();return response.json()

# Stable public helpers used by app.py. Keep the legacy new_* functions above for compatibility.
def create_chapter(url,token_id,token_secret,book_id,name,verify=None):
 return new_chapter(url,token_id,token_secret,book_id,name,verify)

def create_page(url,token_id,token_secret,name,html,book_id=None,chapter_id=None,verify=None):
 if not book_id and not chapter_id:raise ValueError("book_id ou chapter_id requis pour créer une page BookStack")
 return new_page(url,token_id,token_secret,book_id,chapter_id,name,html,verify)
