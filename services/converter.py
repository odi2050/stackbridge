import base64,html
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
def pdf(p,lang):
 detail("Converter PDF start path=%s ocr_lang=%s",p,lang)
 d=pymupdf.open(p);out=[];imgs=ocr=graphics=0;warn=[]
 for no,page in enumerate(d,1):
  native=page.get_text("text").strip();out.append(f"<section><h2>Page {no}</h2>")
  detail("Converter PDF page=%s native_chars=%s",no,len(native))
  if len(native)<40:
   # A low-text page is treated as a scan. Render it once and always preserve
   # that rendering, whether OCR succeeds, returns no text, or fails.
   pix=page.get_pixmap(matrix=pymupdf.Matrix(2,2),alpha=False);raw=pix.tobytes("png")
   try:
    txt,err=image_to_text(raw,lang)
   except Exception as exc:
    txt="";err=str(exc);detail("Converter PDF OCR exception page=%s error=%s",no,err)
   if txt.strip():
    ocr+=1
    for x in txt.splitlines():
     if x.strip():out.append("<p>"+html.escape(x.strip())+"</p>")
    out.append(f'<details><summary>Scan original</summary><img src="data:image/png;base64,{base64.b64encode(raw).decode()}" style="max-width:100%"></details>')
   else:
    if err:warn.append(f"Page {no}: OCR impossible - {err}")
    else:warn.append(f"Page {no}: OCR sans texte exploitable")
    detail("Converter PDF OCR fallback page=%s error=%s",no,err or "empty OCR result")
    out.append(f'<p><em>OCR non exploitable - page originale conservée.</em></p><img src="data:image/png;base64,{base64.b64encode(raw).decode()}" style="max-width:100%">')
   imgs+=1;out.append("</section>");continue
  blocks=sorted(page.get_text("dict").get("blocks",[]),key=lambda b:(b.get("bbox",[0,0])[1],b.get("bbox",[0,0])[0]))
  for b in blocks:
   if b.get("type")==0:
    lines=[]
    for l in b.get("lines",[]):
     t="".join(s.get("text","") for s in l.get("spans",[])).strip()
     if t:lines.append(t)
    if lines:out.append("<p>"+html.escape(" ".join(lines))+"</p>")
   elif b.get("type")==1 and b.get("image"):
    ext=b.get("ext","png");mime="image/jpeg" if ext in ("jpg","jpeg") else "image/"+ext
    out.append(f'<p><img src="data:{mime};base64,{base64.b64encode(b["image"]).decode()}" style="max-width:100%"></p>');imgs+=1
  try:
   graphics+=sum(1 for x in page.get_drawings() if x.get("rect") and x["rect"].width>=40 and x["rect"].height>=40)
  except:pass
  out.append("</section>")
 pages=d.page_count;d.close()
 result="\n".join(out);detail("Converter PDF end pages=%s images=%s ocr_pages=%s graphics=%s warnings=%s",pages,imgs,ocr,graphics,len(warn));return result,{"pages":pages,"images":imgs,"ocr":bool(ocr),"ocr_pages":ocr,"graphics":graphics,"warnings":warn}
def convert(p,lang):
 e=Path(p).suffix.lower()
 detail("Converter dispatch extension=%s",e)
 if e==".docx":return docx(p)
 if e==".pdf":return pdf(p,lang)
 t=Path(p).read_text(encoding="utf8",errors="replace")
 if e in (".md",".markdown"):return markdown.markdown(t,extensions=["tables","fenced_code"]),{"images":0,"ocr":False,"warnings":[]}
 if e in (".html",".htm"):return t,{"images":0,"ocr":False,"warnings":[]}
 if e==".txt":return "\n".join("<p>"+html.escape(x)+"</p>" for x in t.splitlines() if x.strip()),{"images":0,"ocr":False,"warnings":[]}
 raise ValueError(e)
