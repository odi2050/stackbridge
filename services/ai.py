import os
import re
import json
from bs4 import BeautifulSoup
from .runtime import request,detail

SYSTEM_PROMPT="""Améliore cette fiche BookStack sans inventer. Conserve exactement commandes, IP, VLAN, noms, nombres et faits. Ne supprime, ne renomme et ne déplace aucun marqueur IMAGE_BOOKSTACK. Retourne uniquement du HTML."""
MAX_INPUT_TOKENS=int(os.getenv("AI_MAX_INPUT_TOKENS","6000"))
AI_REQUEST_TIMEOUT=int(os.getenv("AI_REQUEST_TIMEOUT","300"))
IMAGE_RE=re.compile(r"<img\b[^>]*>",re.IGNORECASE|re.DOTALL)

def _mask_images(html):
 images=[]
 def replace(match):
  index=len(images);images.append(match.group(0))
  return f'<span data-bookstack-image="{index}">IMAGE_BOOKSTACK_{index}</span>'
 return IMAGE_RE.sub(replace,html),images

def _restore_images(html,images):
 soup=BeautifulSoup(html,"html.parser");missing=[]
 for index,original in enumerate(images):
  placeholder=soup.find(attrs={"data-bookstack-image":str(index)})
  image=BeautifulSoup(original,"html.parser").find("img")
  if placeholder and image:placeholder.replace_with(image)
  else:missing.append(original)
 if missing:
  detail("AI response dropped image placeholders count=%s; appending images safely",len(missing))
  container=soup.new_tag("div");container["class"]="bookstack-images-restored"
  for original in missing:
   image=BeautifulSoup(original,"html.parser").find("img")
   if image:container.append(image)
  soup.append(container)
 return str(soup)

def _custom_payload(template,values):
 try:payload=json.loads(template)
 except json.JSONDecodeError as error:raise RuntimeError(f"JSON personnalisé invalide à la ligne {error.lineno}, colonne {error.colno}: {error.msg}") from error
 def substitute(value):
  if isinstance(value,str):
   for key,replacement in values.items():value=value.replace("{{"+key+"}}",str(replacement))
   return value
  if isinstance(value,list):return [substitute(x) for x in value]
  if isinstance(value,dict):return {key:substitute(item) for key,item in value.items()}
  return value
 return substitute(payload)

def _response_value(payload,path):
 value=payload
 try:
  for part in path.split("."):value=value[int(part)] if isinstance(value,list) else value[part]
 except (KeyError,IndexError,TypeError,ValueError) as error:raise RuntimeError(f"Chemin de réponse IA introuvable : {path}") from error
 if not isinstance(value,str):raise RuntimeError(f"Le chemin de réponse IA {path} ne contient pas de texte")
 return value

def _raise_api_error(response):
 if response.ok:return
 try:
  payload=response.json();error=payload.get("error",payload)
  message=error.get("message") if isinstance(error,dict) else str(error)
  code=error.get("code") if isinstance(error,dict) else None
 except Exception:
  message=(response.text or response.reason)[:1000];code=None
 suffix=f" (code: {code})" if code else ""
 raise RuntimeError(f"API IA HTTP {response.status_code}: {message}{suffix}")

def _estimate_tokens(text):
 return (len(text)+3)//4

def _split_html(html,max_chars):
 """Découpe le HTML à des frontières d'éléments autant que possible."""
 soup=BeautifulSoup(html,"html.parser")
 nodes=list(soup.body.contents) if soup.body else list(soup.contents)
 chunks=[];current="""
 def push(text):
  nonlocal current
  if not text:return
  if len(text)<=max_chars:
   if current and len(current)+len(text)>max_chars:chunks.append(current);current=""
   current+=text;return
  if current:chunks.append(current);current=""
  # Dernier recours pour un élément unique énorme (ex: très grand <pre>/<table>).
  for start in range(0,len(text),max_chars):chunks.append(text[start:start+max_chars])
 for node in nodes:push(str(node))
 if current:chunks.append(current)
 return chunks or [html]

def _request_improvement(masked_html,url,model,key,level,custom_enabled,endpoint,request_json,response_path,chunk_index=1,chunk_total=1):
 headers={"Content-Type":"application/json"}
 if key:headers["Authorization"]="Bearer "+key
 prompts={"light":"Nettoyage léger uniquement.","structure":"Restructure avec H2/H3, listes, tableaux et blocs de code.","enrich":"Restructure et ajoute seulement un court résumé déductible de la source."}
 chunk_note=(f"\nCe contenu est la partie {chunk_index}/{chunk_total} d'un document. Améliore uniquement cette partie, sans inventer de contenu ni ajouter de conclusion globale." if chunk_total>1 else "")
 user_content=prompts.get(level,prompts["structure"])+chunk_note+"\n"+masked_html
 if custom_enabled:
  if not request_json.strip():raise RuntimeError("Le mode IA personnalisé est activé mais le modèle JSON est vide")
  payload=_custom_payload(request_json,{"model":model,"system_prompt":SYSTEM_PROMPT,"prompt":user_content,"html":masked_html,"level":level})
  target=endpoint if endpoint.startswith(("http://","https://")) else url.rstrip("/")+"/"+endpoint.lstrip("/")
 else:
  payload={"model":model,"temperature":0.1,"messages":[{"role":"system","content":SYSTEM_PROMPT},{"role":"user","content":user_content}]};target=url.rstrip("/")+"/chat/completions"
 detail("AI request mode=%s endpoint=%s response_path=%s chunk=%s/%s",("custom" if custom_enabled else "openai"),target,response_path,chunk_index,chunk_total)
 response=request("POST",target,headers=headers,json=payload,timeout=AI_REQUEST_TIMEOUT);_raise_api_error(response)
 try:return _response_value(response.json(),response_path)
 except ValueError as error:raise RuntimeError("Réponse IA invalide : le serveur n’a pas retourné de JSON") from error

def models(url,key=""):
 headers={"Accept":"application/json"}
 if key:headers["Authorization"]="Bearer "+key
 response=request("GET",url.rstrip("/")+"/models",headers=headers,timeout=30);_raise_api_error(response);data=response.json().get("data",[])
 result=sorted([str(x.get("id")) for x in data if x.get("id")],key=str.lower);detail("AI models found count=%s",len(result));return result

def improve(html,url,model,key="",level="structure",send_images=False,custom_enabled=False,endpoint="/chat/completions",request_json="",response_path="choices.0.message.content"):
 masked_html,images=(html,[]) if send_images else _mask_images(html)
 # Réserve une marge pour le system prompt, les instructions et le format JSON.
 reserved_tokens=max(800,_estimate_tokens(SYSTEM_PROMPT)+300)
 chunk_token_budget=max(1000,MAX_INPUT_TOKENS-reserved_tokens)
 max_chars=chunk_token_budget*4
 estimated_tokens=_estimate_tokens(SYSTEM_PROMPT)+_estimate_tokens(masked_html)+300
 chunks=_split_html(masked_html,max_chars) if estimated_tokens>MAX_INPUT_TOKENS else [masked_html]
 detail("AI improve model=%s level=%s send_images=%s original_chars=%s payload_chars=%s images_masked=%s estimated_tokens=%s chunks=%s token_limit=%s",model,level,send_images,len(html),len(masked_html),len(images),estimated_tokens,len(chunks),MAX_INPUT_TOKENS)
 results=[]
 for index,chunk in enumerate(chunks,1):
  detail("AI chunk start chunk=%s/%s chars=%s estimated_tokens=%s",index,len(chunks),len(chunk),_estimate_tokens(chunk))
  result=_request_improvement(chunk,url,model,key,level,custom_enabled,endpoint,request_json,response_path,index,len(chunks))
  results.append(result)
  detail("AI chunk complete chunk=%s/%s output_chars=%s",index,len(chunks),len(result))
 content="\n".join(results)
 if images:content=_restore_images(content,images)
 detail("AI improve complete output_chars=%s images_restored=%s chunks=%s",len(content),len(images),len(chunks));return content
