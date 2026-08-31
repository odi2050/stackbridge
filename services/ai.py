import os
import re
import json
from bs4 import BeautifulSoup
from .runtime import request,detail

SYSTEM_PROMPT="""Améliore cette fiche BookStack sans inventer. Conserve exactement commandes, IP, VLAN, noms, nombres et faits. Ne supprime, ne renomme et ne déplace aucun marqueur IMAGE_BOOKSTACK. Retourne uniquement du HTML."""
MAX_INPUT_TOKENS=int(os.getenv("AI_MAX_INPUT_TOKENS","6000"))
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

def models(url,key=""):
 headers={"Accept":"application/json"}
 if key:headers["Authorization"]="Bearer "+key
 response=request("GET",url.rstrip("/")+"/models",headers=headers,timeout=30);_raise_api_error(response);data=response.json().get("data",[])
 result=sorted([str(x.get("id")) for x in data if x.get("id")],key=str.lower);detail("AI models found count=%s",len(result));return result
def improve(html,url,model,key="",level="structure",send_images=False,custom_enabled=False,endpoint="/chat/completions",request_json="",response_path="choices.0.message.content"):
 headers={"Content-Type":"application/json"}
 if key:headers["Authorization"]="Bearer "+key
 prompts={"light":"Nettoyage léger uniquement.","structure":"Restructure avec H2/H3, listes, tableaux et blocs de code.","enrich":"Restructure et ajoute seulement un court résumé déductible de la source."}
 masked_html,images=(html,[]) if send_images else _mask_images(html);user_content=prompts.get(level,prompts["structure"])+"\n"+masked_html
 estimated_tokens=(len(SYSTEM_PROMPT)+len(user_content)+3)//4
 detail("AI improve model=%s level=%s send_images=%s original_chars=%s payload_chars=%s images_masked=%s estimated_tokens=%s",model,level,send_images,len(html),len(masked_html),len(images),estimated_tokens)
 if estimated_tokens>MAX_INPUT_TOKENS:raise RuntimeError(f"Document trop volumineux pour l’IA après retrait des images : environ {estimated_tokens} tokens. Limite préventive : {MAX_INPUT_TOKENS}. Divisez le document en plusieurs fichiers ou augmentez AI_MAX_INPUT_TOKENS si votre fournisseur autorise un quota supérieur.")
 if custom_enabled:
  if not request_json.strip():raise RuntimeError("Le mode IA personnalisé est activé mais le modèle JSON est vide")
  payload=_custom_payload(request_json,{"model":model,"system_prompt":SYSTEM_PROMPT,"prompt":user_content,"html":masked_html,"level":level})
  target=endpoint if endpoint.startswith(("http://","https://")) else url.rstrip("/")+"/"+endpoint.lstrip("/")
 else:
  payload={"model":model,"temperature":0.1,"messages":[{"role":"system","content":SYSTEM_PROMPT},{"role":"user","content":user_content}]};target=url.rstrip("/")+"/chat/completions"
 detail("AI request mode=%s endpoint=%s response_path=%s",("custom" if custom_enabled else "openai"),target,response_path)
 response=request("POST",target,headers=headers,json=payload,timeout=300);_raise_api_error(response)
 try:content=_response_value(response.json(),response_path)
 except ValueError as error:raise RuntimeError("Réponse IA invalide : le serveur n’a pas retourné de JSON") from error
 if images:content=_restore_images(content,images)
 detail("AI improve complete output_chars=%s images_restored=%s",len(content),len(images));return content
