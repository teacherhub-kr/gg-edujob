#!/usr/bin/env python3
"""Reliability wrapper for official cultural-foundation recruitment collection."""
from __future__ import annotations
import hashlib, json, re
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlparse
import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import crawl_official_foundation_jobs as base
KST=base.KST; OUTPUT=base.OUTPUT; REPORT=base.REPORT; UA=base.UA
SFAC_CAREERLINK_URL="https://sfac.careerlink.kr/"
RETRY=Retry(total=4,connect=4,read=3,status=3,backoff_factor=1.0,status_forcelist=(408,429,500,502,503,504),allowed_methods=frozenset(("GET",)),respect_retry_after_header=True,raise_on_status=False)

def make_session():
    s=requests.Session(); s.mount("https://",HTTPAdapter(max_retries=RETRY)); s.mount("http://",HTTPAdapter(max_retries=RETRY)); return s

def resilient_request(session,url):
    r=session.get(url,timeout=25,headers={"User-Agent":UA,"Cache-Control":"no-cache, no-store, max-age=0","Pragma":"no-cache"},allow_redirects=True); r.raise_for_status()
    if not r.encoding or r.encoding.lower()=="iso-8859-1": r.encoding=r.apparent_encoding or "utf-8"
    return r

def sfac_rows(session,foundation,url):
    r=resilient_request(session,url); soup=BeautifulSoup(r.text,"html.parser"); text=base.normalize_space(soup.get_text(" ",strip=True)); title=""
    for selector in ("h1","h2","h3",".title",".recruit-title"):
        for node in soup.select(selector):
            candidate=base.normalize_space(node.get_text(" ",strip=True))
            if candidate and ("채용" in candidate or "모집" in candidate or "공고" in candidate): title=candidate; break
        if title: break
    if not title:
        m=re.search(r"(서울문화재단[^\n]{0,120}(?:채용|모집|공고)[^\n]{0,120})",text); title=base.normalize_space(m.group(1)) if m else ""
    registered=base.parse_date_text(text[:2500]) or base.detail_registered(soup,None); today=datetime.now(KST).date(); apply_end=base.extract_apply_end(text,registered)
    active=bool(title and registered and registered<=today and (not apply_end or apply_end>=today)) and not base.RESULT_RE.search(title)
    rows=[]
    if active:
        stable=hashlib.sha1(f"{url}|{title}|{registered.isoformat()}".encode()).hexdigest()[:18]; fid=str(foundation.get("id") or "")
        rows.append({"sourceIdentity":f"official-foundation:sfac:{stable}","foundationRegistryId":fid,"foundationName":foundation.get("name") or "서울문화재단","organization":foundation.get("name") or "서울문화재단","source":foundation.get("name") or "서울문화재단","sourceType":"문화재단 공식채용","sourceSurface":"cultural-foundation","sourceSurfaceLabel":"서울문화재단 공식 채용공고","sourceRole":"primary-official","trustLevel":"공식","province":foundation.get("region") or "서울","region":foundation.get("municipality") or "서울특별시","regions":[foundation.get("municipality") or "서울특별시"],"location":" ".join(x for x in [foundation.get("region"),foundation.get("municipality")] if x),"title":title,"registered":base.format_date(registered),"applyEnd":base.format_date(apply_end),"url":r.url,"originalUrl":r.url,"detailUrl":r.url,"boardUrl":url,"detailLinkVerified":True,"detailLinkReason":"official-sfac-current-microsite","transportVerified":True})
    return rows,{"adapter":"sfac-saramin-current-microsite","surfacesChecked":[r.url],"discoveredDetailLinks":1 if title else 0,"inspectedDetailLinks":1 if title else 0,"publishedCurrentJobs":len(rows),"active":active,"registered":base.format_date(registered),"applyEnd":base.format_date(apply_end)}

def sfac_careerlink_probe(session):
    r=resilient_request(session,SFAC_CAREERLINK_URL); soup=BeautifulSoup(r.text,"html.parser"); text=base.normalize_space(soup.get_text(" ",strip=True))
    detail_links=[a.get("href") for a in soup.find_all("a",href=True) if any(k in str(a.get("href")) for k in ("recruit","job","apply"))]
    empty_phrase="현재 게시중인 공고가 없습니다" in text or ("0 / 0" in text and "채용공고" in text)
    empty_markup=(r.status_code==200 and "서울문화재단" in text and "채용" in text and not detail_links)
    if not (empty_phrase or empty_markup): raise RuntimeError("sfac.careerlink.kr is not explicitly empty; dedicated current-post parser is required before collection can continue")
    return {"url":r.url,"healthy":True,"currentJobs":0,"explicitEmpty":True,"evidence":"phrase" if empty_phrase else "200-html-no-recruitment-detail-links","role":"secondary-official-contract-surface"}


RECRUITMENT_RE=re.compile(
    r"채용|구인|기간제\s*(?:근로자|직원|인력)|직원\s*(?:공개|제한|경력)?\s*(?:경쟁\s*)?(?:채용|모집)|"
    r"(?:문화예술|예술교육|교육)\s*(?:전문)?\s*강사\s*(?:채용|모집)|강사\s*(?:채용|모집)|"
    r"(?:대표이사|임원|이사|감사)\s*(?:공개)?\s*모집|인력\s*(?:채용|모집)|"
    r"(?:합창단|예술단|교향악단|오케스트라)\s*(?:단원|연주자)\s*(?:추가)?\s*모집|"
    r"(?:성악|음악|예술)\s*지도자\s*(?:채용|모집)",
    re.I,
)
NON_POSITION_RE=re.compile(
    r"참여자|참가자|관람객|서포터즈|동아리|대관|지원사업|공모전|작품\s*공모|"
    r"예술활동증명|입찰|제안서\s*평가위원|수강생|시민\s*모집|체험|공연\s*모집",
    re.I,
)
GENERIC_OFFICIAL_HOSTS={
    "ifac.or.kr","www.ifac.or.kr",
    "jcf.or.kr","www.jcf.or.kr",
    "ysfac.or.kr","www.ysfac.or.kr",
    "bpcf.or.kr","www.bpcf.or.kr",
    "namdongcf.or.kr","www.namdongcf.or.kr",
    "seohae.go.kr","www.seohae.go.kr","isel.seo.incheon.kr",
    "naruart.or.kr","www.naruart.or.kr",
    "idfac.or.kr","www.idfac.or.kr",
    "nyjcf.or.kr","www.nyjcf.or.kr",
    "ypcf.or.kr","www.ypcf.or.kr",
    "ggcf.kr","www.ggcf.kr",
}
PAGE_PARAM_KEYS=("pageIndex","page","pgno","pageNo","pageno")


def official_position_title(title:str)->bool:
    title=base.normalize_space(title)
    if not title or base.RESULT_RE.search(title) or NON_POSITION_RE.search(title):
        return False
    return bool(RECRUITMENT_RE.search(title))


def container_text(anchor)->str:
    node=anchor
    for _ in range(4):
        if node is None:
            break
        text=base.normalize_space(node.get_text(" ",strip=True))
        if len(text)>=len(base.normalize_space(anchor.get_text(" ",strip=True)))+6:
            return text[:1800]
        node=node.parent
    return base.normalize_space(anchor.get_text(" ",strip=True))


def detail_identity(url:str)->str:
    parsed=urlparse(url)
    query=parse_qs(parsed.query)
    for key in ("bbsSn","boardId","msg_seq","sq","idx","nttSn","seq","no","id"):
        value=str((query.get(key) or [""])[0]).strip()
        if value:
            return f"{key}:{value}"
    parts=[p for p in parsed.path.split("/") if p]
    if parts and re.fullmatch(r"\d{2,}",parts[-1]):
        return f"path:{parts[-1]}"
    return "url:"+hashlib.sha1(url.encode()).hexdigest()[:20]


def list_detail_candidates(session,foundation,board_url):
    r=resilient_request(session,board_url)
    soup=BeautifulSoup(r.text,"html.parser")
    board_host=(urlparse(r.url).hostname or "").lower()
    fid=str(foundation.get("id") or "")
    allowed={board_host}
    if fid=="incheon:seohae":
        allowed.update({"seohae.go.kr","www.seohae.go.kr","isel.seo.incheon.kr"})
    candidates={}
    dated_list_rows=0
    for a in soup.find_all("a",href=True):
        title=base.normalize_space(a.get_text(" ",strip=True))
        if not official_position_title(title):
            continue
        href=str(a.get("href") or "").strip()
        if not href or href.lower().startswith(("javascript:","#","mailto:","tel:")):
            continue
        absolute=urljoin(r.url,href)
        host=(urlparse(absolute).hostname or "").lower()
        if host not in allowed:
            continue
        if absolute.rstrip("/")==r.url.rstrip("/"):
            continue
        context=container_text(a)
        reg=base.parse_date_text(context)
        if reg:
            dated_list_rows+=1
        identity=detail_identity(absolute)
        prev=candidates.get(identity)
        item={"url":absolute,"fallbackTitle":title,"registered":reg,"listContext":context[:1200]}
        if prev is None or len(title)>len(str(prev.get("fallbackTitle") or "")):
            candidates[identity]=item
    return r,soup,candidates,dated_list_rows


def generic_official_rows(session,foundation,board_url):
    today=datetime.now(KST).date()
    board_response,soup,candidates,dated_list_rows=list_detail_candidates(session,foundation,board_url)
    jobs=[]
    inspected=0
    errors=[]
    for identity,meta in list(candidates.items())[:80]:
        try:
            detail=resilient_request(session,str(meta["url"]))
            detail_soup=BeautifulSoup(detail.text,"html.parser")
            title=base.detail_title(detail_soup,str(meta.get("fallbackTitle") or ""))
            if not official_position_title(title):
                continue
            registered=base.detail_registered(detail_soup,meta.get("registered"))
            if not registered or registered>today or registered<today-base.timedelta(days=120):
                continue
            full_text=base.normalize_space(detail_soup.get_text(" ",strip=True))
            apply_end=base.extract_apply_end(full_text,registered)
            if apply_end and apply_end<today:
                continue
            if not apply_end and registered<today-base.timedelta(days=30):
                continue
            inspected+=1
            fid=str(foundation.get("id") or "")
            detail_id=detail_identity(detail.url)
            sid="official-foundation:"+fid+":"+hashlib.sha1((detail_id+"|"+detail.url).encode()).hexdigest()[:20]
            jobs.append({
                "sourceIdentity":sid,
                "foundationRegistryId":fid,
                "foundationName":foundation.get("name") or "",
                "organization":foundation.get("name") or "",
                "source":foundation.get("name") or "",
                "sourceType":"문화재단 공식채용/모집",
                "sourceSurface":"cultural-foundation",
                "sourceSurfaceLabel":f"{foundation.get('name') or '문화재단'} 공식 채용·인력모집",
                "sourceRole":"primary-official",
                "trustLevel":"공식",
                "province":foundation.get("region") or "",
                "region":foundation.get("municipality") or "",
                "regions":[foundation.get("municipality")] if foundation.get("municipality") else [],
                "location":" ".join(x for x in [foundation.get("region"),foundation.get("municipality")] if x),
                "title":title,
                "registered":base.format_date(registered),
                "applyEnd":base.format_date(apply_end),
                "url":detail.url,
                "originalUrl":detail.url,
                "detailUrl":detail.url,
                "boardUrl":board_response.url,
                "detailLinkVerified":True,
                "detailLinkReason":"official-foundation-exact-detail",
                "transportVerified":True,
            })
        except Exception as exc:
            errors.append({"url":str(meta.get("url") or "")[:500],"error":f"{type(exc).__name__}: {str(exc)[:180]}"})
    # A configured official board is healthy only if it is a real HTML surface.
    # Zero current jobs is valid; an unreadable or identity-mismatched surface is not.
    board_text=base.normalize_space(soup.get_text(" ",strip=True))
    aliases=[foundation.get("name"),*(foundation.get("aliases") or [])]
    identity_ok=any(base.normalize_space(x) and base.normalize_space(x).replace(" ","") in board_text.replace(" ","") for x in aliases)
    if str(foundation.get("id") or "")=="incheon:seohae":
        identity_ok=identity_ok or "채용소식" in board_text
    if not identity_ok:
        raise RuntimeError("official board did not prove foundation/local-government identity")
    return jobs,{
        "adapter":"generic-official-board-v1",
        "surfacesChecked":[board_response.url],
        "discoveredDetailLinks":len(candidates),
        "datedRecruitmentRowsOnList":dated_list_rows,
        "inspectedDetailLinks":inspected,
        "publishedCurrentJobs":len(jobs),
        "detailErrors":errors[:10],
        "identityVerified":identity_ok,
    }


def main():
    generated=datetime.now(KST).isoformat(timespec="seconds"); foundations=base.effective_foundations(); configured=[x for x in foundations if str(x.get("officialRecruitmentUrl") or "").strip()]; session=make_session(); base.request=resilient_request
    jobs=[]; errors=[]; unsupported=[]; board_results=[]
    for foundation in configured:
        board_url=str(foundation.get("officialRecruitmentUrl") or "").strip(); host=(urlparse(board_url).hostname or "").lower()
        try:
            if host=="nsart.or.kr" or host.endswith(".nsart.or.kr"): found,meta=base.nsart_rows(session,foundation,board_url)
            elif host=="sfac.saramin.co.kr":
                found,meta=sfac_rows(session,foundation,board_url); careerlink=sfac_careerlink_probe(session); meta["surfacesChecked"]=meta.get("surfacesChecked",[])+[careerlink["url"]]; meta["secondarySurfaces"]=[careerlink]; meta["adapterStatus"]="implemented"
            elif host in GENERIC_OFFICIAL_HOSTS:
                found,meta=generic_official_rows(session,foundation,board_url)
            else:
                unsupported.append({"foundationRegistryId":foundation.get("id"),"foundationName":foundation.get("name"),"boardUrl":board_url,"reason":"adapter-not-yet-implemented"}); continue
            jobs.extend(found); board_results.append({"foundationRegistryId":foundation.get("id"),"foundationName":foundation.get("name"),"boardUrl":board_url,"healthy":True,**meta})
        except Exception as exc:
            errors.append({"foundationRegistryId":foundation.get("id"),"foundationName":foundation.get("name"),"boardUrl":board_url,"error":f"{type(exc).__name__}: {exc}"}); board_results.append({"foundationRegistryId":foundation.get("id"),"foundationName":foundation.get("name"),"boardUrl":board_url,"healthy":False})
    ids=[str(x.get("sourceIdentity") or "") for x in jobs]; urls=[str(x.get("url") or "") for x in jobs]; duplicate_ids=sorted({x for x in ids if x and ids.count(x)>1}); duplicate_urls=sorted({x for x in urls if x and urls.count(x)>1})
    if duplicate_ids or duplicate_urls: errors.append({"error":"duplicate-official-identities","ids":duplicate_ids,"urls":duplicate_urls})
    jobs.sort(key=lambda x:(str(x.get("registered") or ""),str(x.get("sourceIdentity") or "")),reverse=True); healthy=not errors and not unsupported
    OUTPUT.write_text(json.dumps({"generatedAt":generated,"sourceRole":"primary-official","jobs":jobs},ensure_ascii=False,indent=2),encoding="utf-8")
    REPORT.write_text(json.dumps({"generatedAt":generated,"policy":"official-foundation-primary-fail-closed-v7-metro-generic","healthy":healthy,"registryInstitutions":len(foundations),"officialBoardsConfigured":len(configured),"supportedBoardsChecked":len(board_results),"unsupportedConfiguredBoards":unsupported,"jobs":len(jobs),"errors":errors,"boards":board_results},ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(json.loads(REPORT.read_text(encoding="utf-8")),ensure_ascii=False,indent=2)); return 0 if healthy else 2
if __name__=="__main__": raise SystemExit(main())