import os
import re
import json
import time
from bs4 import BeautifulSoup,NavigableString,Tag
from .runtime import request,detail

SYSTEM_PROMPT="""Améliore cette fiche BookStack sans inventer. Conserve exactement commandes, IP, VLAN, noms, nombres et faits. Ne supprime, ne renomme et ne déplace aucun marqueur IMAGE_BOOKSTACK. Retourne uniquement du HTML."""
MAX_INPUT_TOKENS=int(os.getenv("AI_MAX_INPUT_TOKENS","3000"))
AI_REQUEST_TIMEOUT=int(os.getenv("AI_REQUEST_TIMEOUT","300"))
AI_MAX_RETRIES=max(0,int(os.getenv("AI_MAX_RETRIES","2")))
AI_RETRY_BACKOFF=max(0,float(os.getenv("AI_RETRY_BACKOFF","3")))
AI_RETRYABLE_STATUS={502,503,504}
IMAGE_RE=re.compile(r"<img\b[^>]*>",re.IGNORECASE|re.DOTALL)
HEADING_TAGS={"h1","h2","h3","h4","h5","h6"}
ATOMIC_TAGS={"table","pre","ul","ol"}

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

def _wrap(tag,inner,attrs=""):
 attrs=(" "+attrs.strip()) if attrs and attrs.strip() else ""
 return f"<{tag}{attrs}>{inner}</{tag}>"

def _tag_attrs(tag):
 return " ".join(f'{key}="{str(value).replace(chr(34),"&quot;")}"' for key,value in tag.attrs.items() if not isinstance(value,list))

def _split_text_element(tag,max_chars):
 text=tag.get_text("",strip=False);name=tag.name or "p";attrs=_tag_attrs(tag)
 overhead=len(_wrap(name,"",attrs))+64;budget=max(256,max_chars-overhead)
 if name=="pre":units=text.splitlines(keepends=True)
 else:
  units=re.split(r"(?<=[.!?])\s+|\n+",text)
  units=[x+(" " if not x.endswith(("\n"," ")) else "") for x in units if x]
 pieces=[];current=""
 for unit in units or [text]:
  if len(unit)>budget:
   if current:pieces.append(current);current=""
   for start in range(0,len(unit),budget):pieces.append(unit[start:start+budget])
  elif current and len(current)+len(unit)>budget:
   pieces.append(current);current=unit
  else:current+=unit
 if current:pieces.append(current)
 if not pieces:pieces=[text]
 return [_wrap(name,BeautifulSoup("", "html.parser").new_string(piece).output_ready(),attrs) for piece in pieces]

def _split_table(tag,max_chars):
 rows=tag.find_all("tr")
 if not rows:return _split_text_element(tag,max_chars)
 header=[]
 thead=tag.find("thead")
 if thead:header=[str(row) for row in thead.find_all("tr")]
 elif rows and rows[0].find("th"):header=[str(rows[0])]
 header_ids={id(row) for row in (thead.find_all("tr") if thead else ([rows[0]] if header else []))}
 data=[str(row) for row in rows if id(row) not in header_ids]
 attrs=_tag_attrs(tag);head="".join(header)
 overhead=len(_wrap("table",head,attrs))+64;budget=max(512,max_chars-overhead)
 parts=[];current=[];size=0
 for row in data:
  if len(row)>budget:
   if current:parts.append(current);current=[];size=0
   parts.append([row]);continue
  if current and size+len(row)>budget:parts.append(current);current=[];size=0
  current.append(row);size+=len(row)
 if current:parts.append(current)
 if not parts:parts=[[]]
 return [_wrap("table",head+"".join(part),attrs) for part in parts]

def _split_list(tag,max_chars):
 items=tag.find_all("li",recursive=False)
 if not items:return _split_text_element(tag,max_chars)
 attrs=_tag_attrs(tag);overhead=len(_wrap(tag.name,"",attrs))+64;budget=max(512,max_chars-overhead)
 parts=[];current=[];size=0
 for item in map(str,items):
  if current and size+len(item)>budget:parts.append(current);current=[];size=0
  current.append(item);size+=len(item)
 if current:parts.append(current)
 return [_wrap(tag.name,"".join(part),attrs) for part in parts]

def _split_atomic(tag,max_chars):
 raw=str(tag)
 if len(raw)<=max_chars:return [raw]
 if tag.name=="table":return _split_table(tag,max_chars)
 if tag.name in ("ul","ol"):return _split_list(tag,max_chars)
 return _split_text_element(tag,max_chars)

def _split_html(html,max_chars):
 soup=BeautifulSoup(html,"html.parser")
 nodes=list(soup.body.contents) if soup.body else list(soup.contents)
 chunks=[];current="";section_heading=""
 def flush():
  nonlocal current
  if current.strip():chunks.append(current)
  current=""
 def add(piece,heading=""):
  nonlocal current
  context=heading if heading and heading not in piece else ""
  prefix=context if context and not current else ""
  if current and len(current)+len(piece)>max_chars:flush();prefix=context
  if len(piece)<=max_chars:current+=prefix+piece;return
  flush()
  parsed=BeautifulSoup(piece,"html.parser");root=next((x for x in parsed.contents if isinstance(x,Tag)),None)
  if root:
   for part in _split_text_element(root,max_chars):
    if context and context not in part:chunks.append(context+part)
    else:chunks.append(part)
  else:
   for start in range(0,len(piece),max_chars):chunks.append(piece[start:start+max_chars])
 for node in nodes:
  if isinstance(node,NavigableString):
   text=str(node)
   if text.strip():add(text,section_heading)
   continue
  if not isinstance(node,Tag):continue
  if node.name in HEADING_TAGS:
   if current and len(current)+len(str(node))>max_chars:flush()
   section_heading=str(node);add(section_heading);continue
  pieces=_split_atomic(node,max_chars) if node.name in ATOMIC_TAGS or len(str(node))>max_chars else [str(node)]
  for piece in pieces:add(piece,section_heading)
 flush()
 detail("AI structural chunking chunks=%s max_chars=%s",len(chunks),max_chars)
 return chunks or [html]

def _validate_chunk_result(content):
 soup=BeautifulSoup(content,"html.parser")
 if soup.body:return "".join(str(x) for x in soup.body.contents)
 return "".join(str(x) for x in soup.contents)

def _request_improvement(masked_html,url,model,key,level,custom_enabled,endpoint,request_json,response_path,chunk_index=1,chunk_total=1):
 headers={"Content-Type":"application/json"}
 if key:headers["Authorization"]="Bearer "+key
 prompts={"light":"Nettoyage léger uniquement.","structure":"Restructure avec H2/H3, listes, tableaux et blocs de code.","enrich":"Restructure et ajoute seulement un court résumé déductible de la source."}
 chunk_note=(f"\nCe contenu est la partie {chunk_index}/{chunk_total} d'un document. Améliore uniquement cette partie. Le titre de section peut être répété uniquement pour fournir le contexte: ne le duplique pas inutilement dans le résultat. Ne fusionne pas, ne complète pas et n'invente pas les données d'un tableau, d'une liste ou d'un bloc de code provenant d'une autre partie." if chunk_total>1 else "")
 user_content=prompts.get(level,prompts["structure"])+chunk_note+"\n"+masked_html
 if custom_enabled:
  if not request_json.strip():raise RuntimeError("Le mode IA personnalisé est activé mais le modèle JSON est vide")
  payload=_custom_payload(request_json,{"model":model,"system_prompt":SYSTEM_PROMPT,"prompt":user_content,"html":masked_html,"level":level})
  target=endpoint if endpoint.startswith(("http://","https://")) else url.rstrip("/")+"/"+endpoint.lstrip("/")
 else:
  payload={"model":model,"temperature":0.1,"messages":[{"role":"system","content":SYSTEM_PROMPT},{"role":"user","content":user_content}]};target=url.rstrip("/")+"/chat/completions"
 detail("AI request mode=%s endpoint=%s response_path=%s chunk=%s/%s",("custom" if custom_enabled else "openai"),target,response_path,chunk_index,chunk_total)
 response=None
 for attempt in range(AI_MAX_RETRIES+1):
  response=request("POST",target,headers=headers,json=payload,timeout=AI_REQUEST_TIMEOUT)
  if response.ok:break
  if response.status_code not in AI_RETRYABLE_STATUS or attempt>=AI_MAX_RETRIES:_raise_api_error(response)
  delay=AI_RETRY_BACKOFF*(2**attempt)
  detail("AI transient gateway error status=%s chunk=%s/%s attempt=%s/%s retry_in_seconds=%s",response.status_code,chunk_index,chunk_total,attempt+1,AI_MAX_RETRIES+1,delay)
  if delay:time.sleep(delay)
 _raise_api_error(response)
 try:return _response_value(response.json(),response_path)
 except ValueError as error:raise RuntimeError("Réponse IA invalide : le serveur n’a pas retourné de JSON") from error

def models(url,key=""):
 headers={"Accept":"application/json"}
 if key:headers["Authorization"]="Bearer "+key
 response=request("GET",url.rstrip("/")+"/models",headers=headers,timeout=30);_raise_api_error(response);data=response.json().get("data",[])
 result=sorted([str(x.get("id")) for x in data if x.get("id")],key=str.lower);detail("AI models found count=%s",len(result));return result

def improve(html,url,model,key="",level="structure",send_images=False,custom_enabled=False,endpoint="/chat/completions",request_json="",response_path="choices.0.message.content"):
 masked_html,images=(html,[]) if send_images else _mask_images(html)
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
  results.append(_validate_chunk_result(result))
  detail("AI chunk complete chunk=%s/%s output_chars=%s",index,len(chunks),len(result))
 content="\n".join(results)
 if images:content=_restore_images(content,images)
 content=_validate_chunk_result(content)
 detail("AI improve complete output_chars=%s images_restored=%s chunks=%s",len(content),len(images),len(chunks));return content
