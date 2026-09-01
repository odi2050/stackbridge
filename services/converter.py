import base64,html,re
from pathlib import Path
import mammoth,pymupdf,markdown
from .ocr import image_to_text
from .runtime import detail
SUPPORTED={".docx",".pdf",".md",".markdown",".html",".htm",".txt"}


def docx(p):
 detail("Converter DOCX start path=%s",p)
 n=0
 def im(x):
  nonlocal n;n+=1
  with x.open() as f: raw=f.read()
  return {"src":f"data:{x.content_type or 'image/png'};base64,{base64.b64encode(raw).decode()}"}
 with open(p,"rb") as f:r=mammoth.convert_to_html(f,convert_image=mammoth.images.img_element(im))
 result={"images":n,"warnings":[str(x) for x in r.messages],"ocr":False};detail("Converter DOCX end images=%s warnings=%s html_chars=%s",n,len(r.messages),len(r.value));return r.value,result


def _native_quality(text):
 """Reject tiny/broken text layers often found on scanned PDFs."""
 text=(text or "").strip()
 if len(text)<40:return 0
 chars=[c for c in text if not c.isspace()]
 if not chars:return 0
 readable=sum(c.isalnum() or c in ".,;:!?()[]{}'\"-_/àâäéèêëîïôöùûüçÀÂÄÉÈÊËÎÏÔÖÙÛÜÇ" for c in chars)/len(chars)
 words=re.findall(r"\b[\wÀ-ÿ'-]{2,}\b",text)
 return readable*.7+min(len(words)/30,1)*.3


def _page_png(page,zoom=2.5):
 pix=page.get_pixmap(matrix=pymupdf.Matrix(zoom,zoom),alpha=False)
 return pix.tobytes("png")


def _scan_html(raw,txt,err,no):
 encoded=base64.b64encode(raw).decode()
 parts=[]
 if txt.strip():
  for line in txt.splitlines():
   line=line.strip()
   if line:parts.append("<p>"+html.escape(line)+"</p>")
  parts.append(f'<details><summary>Afficher la page originale</summary><img src="data:image/png;base64,{encoded}" style="max-width:100%;height:auto"></details>')
 else:
  parts.append('<p><em>OCR non exploitable - page originale conservée.</em></p>')
  parts.append(f'<img src="data:image/png;base64,{encoded}" style="max-width:100%;height:auto">')
 return parts


def _native_blocks(page):
 out=[];images=0
 blocks=sorted(page.get_text("dict").get("blocks",[]),key=lambda b:(b.get("bbox",[0,0])[1],b.get("bbox",[0,0])[0]))
 for block in blocks:
  if block.get("type")==0:
   lines=[]
   for line in block.get("lines",[]):
    text="".join(span.get("text","") for span in line.get("spans",[])).strip()
    if text:lines.append(text)
   if lines:out.append("<p>"+html.escape(" ".join(lines))+"</p>")
  elif block.get("type")==1 and block.get("image"):
   ext=block.get("ext","png");mime="image/jpeg" if ext in ("jpg","jpeg") else "image/"+ext
   out.append(f'<p><img src="data:{mime};base64,{base64.b64encode(block["image"]).decode()}" style="max-width:100%;height:auto"></p>');images+=1
 return out,images


def pdf(p,lang):
 """PDF engine v2: classify each page, prefer good native text, OCR scans, never lose originals."""
 detail("Converter PDF v2 start path=%s ocr_lang=%s",p,lang)
 document=pymupdf.open(p);out=[];imgs=ocr=graphics=native_pages=scan_pages=0;warn=[]
 try:
  pages=document.page_count
  for no,page in enumerate(document,1):
   native=page.get_text("text").strip();quality=_native_quality(native)
   is_scan=quality<.62
   out.append(f'<section data-page="{no}" data-source="{"ocr" if is_scan else "native"}"><h2>Page {no}</h2>')
   detail("Converter PDF v2 page=%s native_chars=%s quality=%.3f mode=%s",no,len(native),quality,"ocr" if is_scan else "native")
   if is_scan:
    scan_pages+=1
    try:
     raw=_page_png(page);txt,err=image_to_text(raw,lang)
    except Exception as exc:
     raw=_page_png(page,2.0);txt="";err=str(exc);detail("Converter PDF v2 OCR exception page=%s error=%s",no,err)
    if txt.strip():ocr+=1
    else:warn.append(f"Page {no}: {err or 'OCR sans texte exploitable'}")
    out.extend(_scan_html(raw,txt,err,no));imgs+=1;out.append("</section>");continue
   native_pages+=1
   blocks,block_images=_native_blocks(page);out.extend(blocks);imgs+=block_images
   try:graphics+=sum(1 for drawing in page.get_drawings() if drawing.get("rect") and drawing["rect"].width>=40 and drawing["rect"].height>=40)
   except Exception as exc:detail("Converter PDF drawing analysis skipped page=%s error=%s",no,exc)
   out.append("</section>")
 finally:document.close()
 result="\n".join(out)
 detail("Converter PDF v2 end pages=%s native_pages=%s scan_pages=%s images=%s ocr_pages=%s graphics=%s warnings=%s",pages,native_pages,scan_pages,imgs,ocr,graphics,len(warn))
 return result,{"engine":"pdf-v2","pages":pages,"native_pages":native_pages,"scan_pages":scan_pages,"images":imgs,"ocr":bool(ocr),"ocr_pages":ocr,"graphics":graphics,"warnings":warn}


def convert(p,lang):
 e=Path(p).suffix.lower();detail("Converter dispatch extension=%s",e)
 if e==".docx":return docx(p)
 if e==".pdf":return pdf(p,lang)
 t=Path(p).read_text(encoding="utf8",errors="replace")
 if e in (".md",".markdown"):return markdown.markdown(t,extensions=["tables","fenced_code"]),{"images":0,"ocr":False,"warnings":[]}
 if e in (".html",".htm"):return t,{"images":0,"ocr":False,"warnings":[]}
 if e==".txt":return "\n".join("<p>"+html.escape(x)+"</p>" for x in t.splitlines() if x.strip()),{"images":0,"ocr":False,"warnings":[]}
 raise ValueError(e)
