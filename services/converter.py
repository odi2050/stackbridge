import base64,html,re
from collections import Counter
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


def _body_font_size(page):
 """Estimate the normal body font from the most frequently used native text size."""
 sizes=[]
 for block in page.get_text("dict").get("blocks",[]):
  if block.get("type")!=0:continue
  for line in block.get("lines",[]):
   for span in line.get("spans",[]):
    text=span.get("text","").strip()
    if text:sizes.extend([round(float(span.get("size",0)),1)]*max(1,min(len(text),80)))
 return Counter(sizes).most_common(1)[0][0] if sizes else 11.0


def _span_html(span):
 text=html.escape(span.get("text","")).replace("\u00a0"," ")
 if not text:return ""
 flags=int(span.get("flags",0));font=(span.get("font") or "").lower()
 bold=bool(flags & 16) or "bold" in font or "black" in font or "heavy" in font
 italic=bool(flags & 2) or "italic" in font or "oblique" in font
 mono="mono" in font or "courier" in font or "consol" in font
 if mono:text=f"<code>{text}</code>"
 if italic:text=f"<em>{text}</em>"
 if bold:text=f"<strong>{text}</strong>"
 return text


def _line_text(line):
 return "".join(span.get("text","") for span in line.get("spans",[])).strip()


def _line_html(line):
 return "".join(_span_html(span) for span in line.get("spans",[])).strip()


def _heading_level(line,body_size):
 spans=[s for s in line.get("spans",[]) if s.get("text","").strip()]
 if not spans:return None
 text=_line_text(line)
 if not text or len(text)>180:return None
 size=max(float(s.get("size",0)) for s in spans)
 ratio=size/max(body_size,1)
 bold=any((int(s.get("flags",0))&16) or "bold" in (s.get("font") or "").lower() for s in spans)
 if ratio>=1.75:return 1
 if ratio>=1.42:return 2
 if ratio>=1.20:return 3
 if ratio>=1.08 and bold and len(text)<=100:return 4
 return None


def _list_item(text):
 m=re.match(r"^\s*([•●▪◦‣–—*-]|\d+[.)]|[A-Za-z][.)])\s+(.+)$",text)
 if not m:return None
 marker=m.group(1);ordered=bool(re.match(r"\d|[A-Za-z]",marker))
 return ordered,m.group(2).strip()


def _native_blocks(page):
 """Rebuild semantic HTML from a text PDF instead of flattening every block to <p>."""
 out=[];images=0;body_size=_body_font_size(page);active_list=None
 blocks=sorted(page.get_text("dict",flags=pymupdf.TEXTFLAGS_DICT).get("blocks",[]),key=lambda b:(round(b.get("bbox",[0,0])[1],1),b.get("bbox",[0,0])[0]))
 def close_list():
  nonlocal active_list
  if active_list:out.append(f"</{active_list}>");active_list=None
 for block in blocks:
  if block.get("type")==0:
   paragraph=[]
   for line in block.get("lines",[]):
    text=_line_text(line)
    if not text:continue
    level=_heading_level(line,body_size)
    item=_list_item(text)
    if level:
     close_list()
     if paragraph:out.append("<p>"+" ".join(paragraph)+"</p>");paragraph=[]
     out.append(f"<h{level}>{_line_html(line)}</h{level}>")
    elif item:
     if paragraph:out.append("<p>"+" ".join(paragraph)+"</p>");paragraph=[]
     tag="ol" if item[0] else "ul"
     if active_list!=tag:
      close_list();out.append(f"<{tag}>");active_list=tag
     # Keep inline styling where possible, but remove the visual bullet/number marker.
     rendered=_line_html(line);plain=html.escape(text)
     content=html.escape(item[1]) if rendered==plain else re.sub(r"^\s*(?:[•●▪◦‣–—*\-]|\d+[.)]|[A-Za-z][.)])\s+","",rendered)
     out.append("<li>"+content+"</li>")
    else:
     close_list();paragraph.append(_line_html(line))
   if paragraph:out.append("<p>"+" ".join(paragraph)+"</p>")
  elif block.get("type")==1 and block.get("image"):
   close_list();ext=block.get("ext","png");mime="image/jpeg" if ext in ("jpg","jpeg") else "image/"+ext
   out.append(f'<p><img src="data:{mime};base64,{base64.b64encode(block["image"]).decode()}" style="max-width:100%;height:auto"></p>');images+=1
 close_list()
 # Native PDF tables are reconstructed separately when PyMuPDF can detect them.
 try:
  for table in page.find_tables().tables:
   rows=table.extract()
   if not rows:continue
   table_html=["<table><tbody>"]
   for row in rows:
    table_html.append("<tr>"+"".join("<td>"+html.escape(str(cell or ""))+"</td>" for cell in row)+"</tr>")
   table_html.append("</tbody></table>");out.extend(table_html)
 except Exception as exc:detail("Converter PDF table analysis skipped error=%s",exc)
 return out,images


def pdf(p,lang):
 """PDF engine v3: preserve semantic structure on text PDFs, OCR only scan-like pages."""
 detail("Converter PDF v3 start path=%s ocr_lang=%s",p,lang)
 document=pymupdf.open(p);out=[];imgs=ocr=graphics=native_pages=scan_pages=0;warn=[]
 try:
  pages=document.page_count
  for no,page in enumerate(document,1):
   native=page.get_text("text").strip();quality=_native_quality(native)
   is_scan=quality<.62
   out.append(f'<section data-page="{no}" data-source="{"ocr" if is_scan else "native"}">')
   detail("Converter PDF v3 page=%s native_chars=%s quality=%.3f mode=%s",no,len(native),quality,"ocr" if is_scan else "native")
   if is_scan:
    scan_pages+=1
    try:
     raw=_page_png(page);txt,err=image_to_text(raw,lang)
    except Exception as exc:
     raw=_page_png(page,2.0);txt="";err=str(exc);detail("Converter PDF v3 OCR exception page=%s error=%s",no,err)
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
 detail("Converter PDF v3 end pages=%s native_pages=%s scan_pages=%s images=%s ocr_pages=%s graphics=%s warnings=%s",pages,native_pages,scan_pages,imgs,ocr,graphics,len(warn))
 return result,{"engine":"pdf-v3","pages":pages,"native_pages":native_pages,"scan_pages":scan_pages,"images":imgs,"ocr":bool(ocr),"ocr_pages":ocr,"graphics":graphics,"warnings":warn}


def convert(p,lang):
 e=Path(p).suffix.lower();detail("Converter dispatch extension=%s",e)
 if e==".docx":return docx(p)
 if e==".pdf":return pdf(p,lang)
 t=Path(p).read_text(encoding="utf8",errors="replace")
 if e in (".md",".markdown"):return markdown.markdown(t,extensions=["tables","fenced_code"]),{"images":0,"ocr":False,"warnings":[]}
 if e in (".html",".htm"):return t,{"images":0,"ocr":False,"warnings":[]}
 if e==".txt":return "\n".join("<p>"+html.escape(x)+"</p>" for x in t.splitlines() if x.strip()),{"images":0,"ocr":False,"warnings":[]}
 raise ValueError(e)
