#!/usr/bin/env python3
from __future__ import annotations
import json, re
from pathlib import Path
from urllib.parse import urljoin
from playwright.sync_api import sync_playwright

TARGETS=[
 {"key":"nambu","name":"인천남부교육지원청","home":"https://nambu.ice.go.kr/Main.do"},
 {"key":"seobu","name":"인천서부교육지원청","home":"https://seobu.ice.go.kr/"},
]
SIGNAL=re.compile(r"구인|채용|recruit|job|bbs|board|content|data|list",re.I)

def clean(s):
 return re.sub(r"\s+"," ",str(s or "")).strip()

def main():
 out={"mode":"read-only-browser-diagnostic","targets":[]}
 with sync_playwright() as pw:
  browser=pw.chromium.launch(headless=True)
  ctx=browser.new_context(locale="ko-KR",timezone_id="Asia/Seoul",viewport={"width":1440,"height":1100})
  page=ctx.new_page()
  for t in TARGETS:
   net=[]
   def record(resp):
    u=str(resp.url or "")
    if SIGNAL.search(u):
     net.append({"url":u,"status":resp.status,"contentType":resp.headers.get("content-type","")})
   page.on("response",record)
   item={"key":t["key"],"name":t["name"],"home":t["home"],"ok":False,"errors":[]}
   try:
    r=page.goto(t["home"],wait_until="networkidle",timeout=60000)
    page.wait_for_timeout(1500)
    item["homeStatus"]=r.status if r else 0
    anchors=[]
    for a in page.locator("a").all():
     try:
      txt=clean(a.inner_text(timeout=500))
      href=clean(a.get_attribute("href"))
      if txt and (SIGNAL.search(txt) or SIGNAL.search(href)):
       anchors.append({"text":txt[:160],"href":href[:500]})
     except Exception:
      pass
    item["anchorsBefore"]=anchors[:120]

    clicked=False
    candidates=page.get_by_text(re.compile("구인|채용",re.I))
    count=min(candidates.count(),25)
    for i in range(count):
     node=candidates.nth(i)
     try:
      if not node.is_visible():
       continue
      txt=clean(node.inner_text(timeout=500))
      node.click(timeout=2500)
      page.wait_for_timeout(1800)
      clicked=True
      item["clickedText"]=txt[:160]
      break
     except Exception:
      continue
    item["clicked"]=clicked
    item["afterUrl"]=page.url
    item["bodySample"]=clean(page.locator("body").inner_text(timeout=3000))[:5000]
    anchors=[]
    for a in page.locator("a").all():
     try:
      txt=clean(a.inner_text(timeout=500))
      href=clean(a.get_attribute("href"))
      onclick=clean(a.get_attribute("onclick"))
      if txt and (SIGNAL.search(txt) or SIGNAL.search(href) or SIGNAL.search(onclick)):
       absolute=urljoin(page.url,href) if href and not href.lower().startswith("javascript:") else href
       anchors.append({"text":txt[:180],"href":absolute[:500],"onclick":onclick[:500]})
     except Exception:
      pass
    item["anchorsAfter"]=anchors[:180]
    item["networkSignals"]=list({x["url"]:x for x in net}.values())[-180:]
    item["ok"]=bool(r and r.status<500)
   except Exception as e:
    item["errors"].append(f"{type(e).__name__}: {e}")
   out["targets"].append(item)
   page.remove_listener("response",record)
  ctx.close(); browser.close()
 Path("incheon_support_browser_diagnostic.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
 print(json.dumps(out,ensure_ascii=False))
 return 0

if __name__=="__main__":
 raise SystemExit(main())
