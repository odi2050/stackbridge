import os
import re
import json
import time
from concurrent.futures import ThreadPoolExecutor,as_completed
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
  index=len(images);images.append(match.group(0));return f'<span data-bookstack-image="{index}">IMAGE_BOOKSTACK_{index}</span>'
 return IMAGE_RE.sub(replace,html),images

def _restore_images(html,images):
 soup=BeautifulSoup(html,"html.parser");missing=[]
 for index,original in enumerate(images):
  placeholder=soup.find(attrs={"data-bookstack-image":str(index)});image=BeautifulSoup(original,"html.parser").find("img")
  if placeholder and image:placeholder.replace_with(image)
  else:missing.append(original)
 if missing:
  detail("AI response dropped image placeholders count=%s; appending images safely",len(missing));container=soup.new_tag("div");container["class"]="bookstack-images-restored"
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
  payload=response.json();error=payload.get("error",payload);message=error.get("message") if isinstance(error,dict) else str(error);code=error.get("code") if isinstance(error,dict) else None
 except Exception:message=(response.text or response.reason)[:1000];code=None
 suffix=f" (code: {code})" if code else "";raise RuntimeError(f"API IA HTTP {response.status_code}: {message}{suffix}")

def _estimate_tokens(text):return (len(text)+3)//4

def _wrap(tag,inner,attrs=""):
 attrs=(" "+attrs.strip()) if attrs and attrs.strip() else "";return f"<{tag}{attrs}>{inner}</{tag}>"

def _tag_attrs(tag):return " ".join(f'{key}="{str(value).replace(chr(34),"&quot;")}"' for key,value in tag.attrs.items() if not isinstance(value,list))

def _split_text_element(tag,max_chars):
 text=tag.get_text("",strip=False);name=tag.name or "p";attrs=_tag_attrs(tag);budget=max(256,max_chars-len(_wrap(name,"",attrs))-64)
 units=text.splitlines(keepends=True) if name=="pre" else [x+(" " if not x.endswith(("\n"," ")) else "") for x in re.split(r"(?<=[.!?])\s+|\n+",text) if x]
 pieces=[];current=""
 for unit in units or [text]:
  if len(unit)>budget:
   if current:pieces.append(current);current=""
   for start in range(0,len(unit),budget):pieces.append(unit[start:start+budget])
  elif current and len(current)+len(unit)>budget:pieces.append(current);current=unit
  else:current+=unit
 if current:pieces.append(current)
 return [_wrap(name,BeautifulSoup("","html.parser").new_string(piece).output_ready(),attrs) for piece in (pieces or [text])]

def _split_table(tag,max_chars):
 rows=tag.find_all("tr")
 if not rows:return _split_text_element(tag,max_chars)
 thead=tag.find("thead");header=[str(row) for row in thead.find_all("tr")] if thead else ([str(rows[0])] if rows and rows[0].find("th") else [])
 header_ids={id(row) for row in (thead.find_all("tr") if thead else ([rows[0]] if header else []))};data=[str(row) for row in rows if id(row) not in header_ids];attrs=_tag_attrs(tag);head="".join(header);budget=max(512,max_chars-len(_wrap("table",head,attrs))-64);parts=[];current=[];size=0
 for row in data:
  if len(row)>budget:
   if current:parts.append(current);current=[];size=0
   parts.append([row]);continue
  if current and size+len(row)>budget:parts.append(current);current=[];size=0
  current.append(row);size+=len(row)
 if current:parts.append(current)
 return [_wrap("table",head+"".join(part),attrs) for part in (parts or [[]])]

def _split_list(tag,max_chars):
 items=tag.find_all("li",recursive=False)
 if not items:return _split_text_element(tag,max_chars)
 attrs=_tag_attrs(tag);budget=max(512,max_chars-len(_wrap(tag.name,"",attrs))-64);parts=[];current=[];size=0
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
 soup=BeautifulSoup(html,"html.parser");nodes=list(soup.body.contents) if soup.body else list(soup.contents);chunks=[];current="";section_heading=""
 def flush():
  nonlocal current
  if current.strip():chunks.append(current)
  current=""
 def add(piece,heading=""):
  nonlocal current
  context=heading if heading and heading not in piece else "";prefix=context if context and not current else ""
  if current and len(current)+len(piece)>max_chars:flush();prefix=context
  if len(piece)<=max_chars:current+=prefix+piece;return
  flush();parsed=BeautifulSoup(piece,"html.parser");root=next((x for x in parsed.contents if isinstance(x,Tag)),None)
  if root:
   for part in _split_text_element(root,max_chars):chunks.append(context+part if context and context not in part else part)
  else:
   for start in range(0,len(piece),max_chars):chunks.append(piece[start:start+max_chars])
 for node in nodes:
  if isinstance(node,NavigableString):
   if str(node).strip():add(str(node),section_heading)
   continue
  if not isinstance(node,Tag):continue
  if node.name in HEADING_TAGS:
   if current and len(current)+len(str(node))>max_chars:flush()
   section_heading=str(node);add(section_heading);continue
  for piece in (_split_atomic(node,max_chars) if node.name in ATOMIC_TAGS or len(str(node))>max_chars else [str(node)]):add(piece,section_heading)
 flush();detail("AI structural chunking chunks=%s max_chars=%s",len(chunks),max_chars);return chunks or [html]

def _validate_chunk_result(content):
 soup=BeautifulSoup(content,"html.parser");return "".join(str(x) for x in (soup.body.contents if soup.body else soup.contents))

def _stream_openai(response,request_started=None,headers_received=None,chunk_index=1,chunk_total=1):
 content_type=(response.headers.get("Content-Type") or "").lower();stream_started=time.monotonic();first_token_at=None
 if "text/event-stream" not in content_type:
  detail("AI stream requested but server returned content_type=%s; reading JSON response",content_type);content=_response_value(response.json(),"choices.0.message.content");done=time.monotonic();detail("AI metrics chunk=%s/%s mode=json ttft_ms=%s generation_ms=%s total_ms=%s output_chars=%s",chunk_index,chunk_total,round(((headers_received or stream_started)-(request_started or stream_started))*1000),round((done-(headers_received or stream_started))*1000),round((done-(request_started or stream_started))*1000),len(content));return content
 parts=[];events=0
 for raw in response.iter_lines(decode_unicode=True):
  if not raw or not raw.startswith("data:"):continue
  data=raw[5:].strip()
  if data=="[DONE]":break
  try:payload=json.loads(data)
  except json.JSONDecodeError:continue
  choices=payload.get("choices") or []
  if not choices:continue
  delta=choices[0].get("delta") or {};text=delta.get("content")
  if text:
   if first_token_at is None:first_token_at=time.monotonic()
   parts.append(text);events+=1
 done=time.monotonic();output_chars=sum(map(len,parts));ttft_base=request_started or stream_started;ttft_end=first_token_at or done;generation_start=first_token_at or (headers_received or stream_started)
 detail("AI stream complete events=%s output_chars=%s",events,output_chars);detail("AI metrics chunk=%s/%s mode=stream ttft_ms=%s generation_ms=%s total_ms=%s output_chars=%s events=%s",chunk_index,chunk_total,round((ttft_end-ttft_base)*1000),round((done-generation_start)*1000),round((done-ttft_base)*1000),output_chars,events)
 if not parts:raise RuntimeError("Réponse IA stream vide")
 return "".join(parts)

def _request_improvement(masked_html,url,model,key,level,custom_enabled,endpoint,request_json,response_path,chunk_index=1,chunk_total=1):
 headers={"Content-Type":"application/json"}
 if key:headers["Authorization"]="Bearer "+key
 prompts={"light":"Nettoyage léger uniquement.","structure":"Restructure avec H2/H3, listes, tableaux et blocs de code.","enrich":"Restructure et ajoute seulement un court résumé déductible de la source."}
 chunk_note=(f"\nCe contenu est la partie {chunk_index}/{chunk_total} d'un document. Améliore uniquement cette partie. Le titre de section peut être répété uniquement pour fournir le contexte: ne le duplique pas inutilement dans le résultat. Ne fusionne pas, ne complète pas et n'invente pas les données d'un tableau, d'une liste ou d'un bloc de code provenant d'une autre partie." if chunk_total>1 else "")
 user_content=prompts.get(level,prompts["structure"])+chunk_note+"\n"+masked_html;streaming=not custom_enabled
 if custom_enabled:
  if not request_json.strip():raise RuntimeError("Le mode IA personnalisé est activé mais le modèle JSON est vide")
  payload=_custom_payload(request_json,{"model":model,"system_prompt":SYSTEM_PROMPT,"prompt":user_content,"html":masked_html,"level":level});target=endpoint if endpoint.startswith(("http://","https://")) else url.rstrip("/")+"/"+endpoint.lstrip("/")
 else:payload={"model":model,"temperature":0.1,"stream":True,"messages":[{"role":"system","content":SYSTEM_PROMPT},{"role":"user","content":user_content}]};target=url.rstrip("/")+"/chat/completions"
 detail("AI request mode=%s streaming=%s endpoint=%s response_path=%s chunk=%s/%s input_chars=%s input_tokens_est=%s",("custom" if custom_enabled else "openai"),streaming,target,response_path,chunk_index,chunk_total,len(user_content),_estimate_tokens(user_content));response=None;request_started=None;headers_received=None
 for attempt in range(AI_MAX_RETRIES+1):
  request_started=time.monotonic();response=request("POST",target,headers=headers,json=payload,timeout=AI_REQUEST_TIMEOUT,stream=streaming);headers_received=time.monotonic()
  if response.ok:break
  if response.status_code not in AI_RETRYABLE_STATUS or attempt>=AI_MAX_RETRIES:_raise_api_error(response)
  status=response.status_code;response.close();delay=AI_RETRY_BACKOFF*(2**attempt);detail("AI transient gateway error status=%s chunk=%s/%s attempt=%s/%s retry_in_seconds=%s",status,chunk_index,chunk_total,attempt+1,AI_MAX_RETRIES+1,delay)
  if delay:time.sleep(delay)
 _raise_api_error(response)
 try:
  if streaming:return _stream_openai(response,request_started,headers_received,chunk_index,chunk_total)
  parse_started=time.monotonic();content=_response_value(response.json(),response_path);done=time.monotonic();detail("AI metrics chunk=%s/%s mode=custom headers_ms=%s parse_ms=%s total_ms=%s output_chars=%s",chunk_index,chunk_total,round((headers_received-request_started)*1000),round((done-parse_started)*1000),round((done-request_started)*1000),len(content));return content
 except ValueError as error:raise RuntimeError("Réponse IA invalide : le serveur n’a pas retourné de JSON") from error
 finally:
  if response is not None:response.close()

def models(url,key=""):
 headers={"Accept":"application/json"}
 if key:headers["Authorization"]="Bearer "+key
 response=request("GET",url.rstrip("/")+"/models",headers=headers,timeout=30);_raise_api_error(response);data=response.json().get("data",[]);result=sorted([str(x.get("id")) for x in data if x.get("id")],key=str.lower);detail("AI models found count=%s",len(result));return result

def improve(html,url,model,key="",level="structure",send_images=False,custom_enabled=False,endpoint="/chat/completions",request_json="",response_path="choices.0.message.content",chunk_tokens=None,parallel_chunks=2):
 total_started=time.monotonic();masked_html,images=(html,[]) if send_images else _mask_images(html);reserved_tokens=max(800,_estimate_tokens(SYSTEM_PROMPT)+300)
 try:requested=int(chunk_tokens or MAX_INPUT_TOKENS)
 except (TypeError,ValueError):requested=MAX_INPUT_TOKENS
 try:workers=int(parallel_chunks or 2)
 except (TypeError,ValueError):workers=2
 workers=min(4,max(1,workers));requested=min(MAX_INPUT_TOKENS,max(500,requested));chunk_token_budget=max(500,requested-reserved_tokens);max_chars=chunk_token_budget*4;estimated_tokens=_estimate_tokens(SYSTEM_PROMPT)+_estimate_tokens(masked_html)+300;chunks=_split_html(masked_html,max_chars) if estimated_tokens>requested else [masked_html];workers=min(workers,len(chunks))
 detail("AI improve model=%s level=%s send_images=%s original_chars=%s payload_chars=%s images_masked=%s estimated_tokens=%s chunks=%s token_limit=%s chunk_target=%s parallel_workers=%s",model,level,send_images,len(html),len(masked_html),len(images),estimated_tokens,len(chunks),MAX_INPUT_TOKENS,requested,workers)
 def process(index,chunk):
  started=time.monotonic();detail("AI chunk start chunk=%s/%s chars=%s estimated_tokens=%s",index,len(chunks),len(chunk),_estimate_tokens(chunk));result=_request_improvement(chunk,url,model,key,level,custom_enabled,endpoint,request_json,response_path,index,len(chunks));validated=_validate_chunk_result(result);detail("AI chunk complete chunk=%s/%s output_chars=%s duration_ms=%s",index,len(chunks),len(result),round((time.monotonic()-started)*1000));return index,validated
 results=[None]*len(chunks)
 if workers==1:
  for index,chunk in enumerate(chunks,1):_,results[index-1]=process(index,chunk)
 else:
  detail("AI parallel processing start workers=%s chunks=%s",workers,len(chunks))
  with ThreadPoolExecutor(max_workers=workers,thread_name_prefix="stackbridge-ai") as pool:
   futures=[pool.submit(process,index,chunk) for index,chunk in enumerate(chunks,1)]
   try:
    for future in as_completed(futures):index,result=future.result();results[index-1]=result
   except Exception:
    for future in futures:future.cancel()
    raise
  detail("AI parallel processing complete workers=%s chunks=%s",workers,len(chunks))
 content="\n".join(results)
 if images:content=_restore_images(content,images)
 content=_validate_chunk_result(content);detail("AI improve complete output_chars=%s images_restored=%s chunks=%s parallel_workers=%s total_duration_ms=%s",len(content),len(images),len(chunks),workers,round((time.monotonic()-total_started)*1000));return content
