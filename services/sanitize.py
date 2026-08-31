from bs4 import BeautifulSoup

BLOCKED_TAGS={"script","iframe","object","embed","applet","link","meta","base","form","input","button","textarea","select"}
URL_ATTRS={"href","src","action","formaction","poster","xlink:href"}
def clean_html(html):
 soup=BeautifulSoup(html or "","html.parser")
 for tag in soup.find_all(BLOCKED_TAGS):tag.decompose()
 for tag in soup.find_all(True):
  for attribute,value in list(tag.attrs.items()):
   name=attribute.lower();text=" ".join(value) if isinstance(value,list) else str(value)
   normalized="".join(text.lower().split())
   if name.startswith("on") or (name in URL_ATTRS and normalized.startswith(("javascript:","vbscript:"))) or (name=="style" and ("expression(" in normalized or "javascript:" in normalized)):del tag.attrs[attribute]
 return str(soup)
