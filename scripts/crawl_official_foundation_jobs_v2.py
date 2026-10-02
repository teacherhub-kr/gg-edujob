#!/usr/bin/env python3
"""Reliability wrapper for official cultural-foundation recruitment collection."""
from __future__ import annotations
import hashlib, json, re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urljoin, urlparse
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
    if urlparse(url).scheme.lower()=="https" and urlparse(r.url).scheme.lower()!="https":
        raise RuntimeError(f"HTTPS official URL downgraded in redirect: {url[:180]} -> {r.url[:180]}")
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
    raw_registered=base.parse_date_text(text[:2500]) or base.detail_registered(soup,None); today=datetime.now(KST).date(); apply_end=base.extract_apply_end(text,raw_registered)
    registered=raw_registered if raw_registered and raw_registered<=today and (not apply_end or raw_registered<=apply_end) else None
    active=bool(title and registered and (not apply_end or apply_end>=today)) and not base.RESULT_RE.search(title)
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
    r"(?:대표이사|임원|이사|감사)(?:\s*\([^)]{1,20}\))?\s*(?:공개)?\s*모집|인력\s*(?:채용|모집)|"
    r"(?:합창단|예술단|교향악단|오케스트라)\s*(?:단원|연주자)\s*(?:추가)?\s*모집|"
    r"(?:성악|음악|예술)\s*지도자\s*(?:채용|모집)",
    re.I,
)
NON_POSITION_RE=re.compile(
    r"참여자|참가자|관람객|서포터즈|동아리|대관|지원사업|공모전|작품\s*공모|"
    r"예술활동증명|입찰|제안서\s*평가위원|수강생|시민\s*모집|체험|공연\s*모집|"
    r"채용\s*(?:과정|절차)\s*공개|모집\s*과정\s*공개",
    re.I,
)
GENERIC_OFFICIAL_HOSTS={
    "ifac.or.kr","www.ifac.or.kr",
    "jcf.or.kr","www.jcf.or.kr",
    "ysfac.or.kr","www.ysfac.or.kr",
    "bpcf.or.kr","www.bpcf.or.kr",
    "namdongcf.or.kr","www.namdongcf.or.kr",
    "biz.namdong.go.kr","namdong.go.kr","www.namdong.go.kr",
    "seohae.go.kr","www.seohae.go.kr","isel.seo.incheon.kr",
    "naruart.or.kr","www.naruart.or.kr",
    "idfac.or.kr","www.idfac.or.kr",
    "nyjcf.or.kr","www.nyjcf.or.kr",
    "ypcf.or.kr","www.ypcf.or.kr",
    "ggcf.kr","www.ggcf.kr",
    "nowonarts.kr","www.nowonarts.kr",
    "gcart.or.kr","www.gcart.or.kr",
    "gcf.or.kr","www.gcf.or.kr",
    "swcf.or.kr","www.swcf.or.kr",
    "ansanart.com","www.ansanart.com",
    "uac.or.kr","www.uac.or.kr",
    "artic.or.kr","www.artic.or.kr",
    "hanam.go.kr","www.hanam.go.kr",
    "gangnam.go.kr","www.gangnam.go.kr",
    "guro.go.kr","www.guro.go.kr",
    "yfac.kr","www.yfac.kr",
    "ydpcf.or.kr","www.ydpcf.or.kr",
    "gcart.or.kr","www.gcart.or.kr",
}
PAGE_PARAM_KEYS=("pageIndex","page","pgno","pageNo","pageno")
BLOCK_PAGE_RE=re.compile(r"WELLCONN|TRACER|접근\s*대기|접근이\s*차단|비정상적인\s*접근|Access\s+Denied|Web\s+Application\s+Firewall",re.I)
JS_SHELL_RE=re.compile(r"\{\{\s*[\w.$]+\s*\}\}|\bng-(?:app|repeat|click)\s*=|\bv-(?:for|if)\s*=",re.I)
EXPLICIT_EMPTY_RE=re.compile(r"등록된\s*(?:글|게시물|공고|자료)이\s*없|게시물이\s*없|검색된\s*(?:결과|자료)가\s*없|현재\s*(?:게시중인\s*)?(?:채용)?공고가\s*없",re.I)

def seohae_shared_board_zero_is_structurally_verified(soup, foundation, response) -> bool:
    """Accept current-zero only on the exact shared Seohae recruitment board contract.

    The municipal board contains many employers, so zero *foundation* candidates is
    not the same as an empty board.  We accept zero only when exact job-detail links
    are parseable and no full foundation alias is visibly present.  If a foundation
    posting is visible but our candidate parser missed it, verification still fails
    closed instead of hiding a parser regression.
    """
    fid=str(foundation.get("id") or "")
    if fid!="incheon:seohae":
        return False
    parsed=urlparse(str(response.url or ""))
    host=(parsed.hostname or "").lower()
    query=parse_qs(parsed.query)
    if host not in {"seohae.go.kr","www.seohae.go.kr"}:
        return False
    if not parsed.path.endswith("/bbs/bbsMsgList.do") or str((query.get("bcd") or [""])[0])!="job":
        return False

    visible=base.normalize_space(soup.get_text(" ",strip=True))
    normalized=visible.replace(" ","")
    aliases=[
        base.normalize_space(x).replace(" ","")
        for x in [foundation.get("name"),*(foundation.get("aliases") or [])]
        if base.normalize_space(x)
    ]
    if any(alias in normalized for alias in aliases):
        return False

    for anchor in soup.find_all("a",href=True):
        href=str(anchor.get("href") or "").strip()
        if not href or href.lower().startswith(("javascript:","#","mailto:","tel:")):
            continue
        absolute=urljoin(response.url,href)
        detail=urlparse(absolute)
        detail_query=parse_qs(detail.query)
        detail_host=(detail.hostname or "").lower()
        msg_seq=str((detail_query.get("msg_seq") or [""])[0]).strip()
        bcd=str((detail_query.get("bcd") or [""])[0]).strip()
        if (
            detail_host in {"seohae.go.kr","www.seohae.go.kr"}
            and detail.path.endswith("/bbs/bbsMsgDetail.do")
            and bcd=="job"
            and re.fullmatch(r"\d+",msg_seq)
        ):
            return True
    return False


def verify_board_surface(soup,foundation,response,candidates):
    visible=base.normalize_space(soup.get_text(" ",strip=True))
    if BLOCK_PAGE_RE.search(visible[:4000]) or BLOCK_PAGE_RE.search(response.text[:4000]):
        raise RuntimeError("official board returned an access-control page")
    if not candidates and JS_SHELL_RE.search(response.text):
        raise RuntimeError("official board is a JS-rendered shell without parsed details")
    unsupported=[a for a in soup.find_all("a",href=True)
                 if official_position_title(a.get_text(" ",strip=True))
                 and (str(a.get("href") or "").strip().lower().startswith(("javascript:","#")) or a.has_attr("onclick"))
                 and not (str(foundation.get("id"))=="incheon:metropolitan" and ifac_detail_url(a,response.url))]
    if unsupported:
        raise RuntimeError("official recruitment rows use unsupported JavaScript detail links")
    normalized=visible.replace(" ","")
    aliases=[foundation.get("name"),*(foundation.get("aliases") or [])]
    fid=str(foundation.get("id") or "")
    identity_ok=any(base.normalize_space(x) and base.normalize_space(x).replace(" ","") in normalized for x in aliases)
    if fid=="incheon:seohae": identity_ok=identity_ok or "채용소식" in visible
    if fid=="incheon:namdong": identity_ok=identity_ok or ("타기관" in visible and ("채용" in visible or "공고" in visible))
    if not identity_ok:
        title=base.normalize_space(soup.title.get_text(" ",strip=True))[:100] if soup.title else ""
        raise RuntimeError(f"official board identity unproved: finalUrl={response.url[:200]!r}, title={title!r}, bytes={len(response.content)}, candidates={len(candidates)}")
    shared_zero_verified=(
        not candidates
        and seohae_shared_board_zero_is_structurally_verified(soup,foundation,response)
    )
    if not candidates and not EXPLICIT_EMPTY_RE.search(visible) and not shared_zero_verified:
        raise RuntimeError("official board has no parseable details and no explicit empty state")
    return True


def official_position_title(title:str)->bool:
    title=base.normalize_space(title)
    if title.replace(" ","") in {"채용공고","채용정보","채용안내","직원채용"}: return False
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


def candidate_belongs_to_foundation(foundation,text:str)->bool:
    if str(foundation.get("id") or "") not in {"incheon:seohae","incheon:namdong","gyeonggi:hanam","seoul:guro"}:
        return True
    haystack=base.normalize_space(text).replace(" ","")
    aliases=[foundation.get("name"),*(foundation.get("aliases") or [])]
    return any(base.normalize_space(x).replace(" ","") in haystack for x in aliases if base.normalize_space(x))


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

def looks_like_detail_url(board_url:str,candidate_url:str)->bool:
    board=urlparse(board_url); candidate=urlparse(candidate_url)
    query=parse_qs(candidate.query)
    detail_key=any(key in query for key in ("b_num","idx","bbsSn","boardId","msg_seq","sq","nttSn","nttNo","not_ancmt_mgt_no","seq","no"))
    if re.search(r"/(?:list|recruitlist|selectBbsNttList|selectGosiList)\.(?:do|php)$",candidate.path,re.I) and not detail_key:
        return False
    if detail_key or query.get("bmode")==["view"] or query.get("proc_type")==["view"]: return True
    return board.path.rstrip("/")!=candidate.path.rstrip("/")


def ifac_detail_url(anchor, board_url:str)->str|None:
    if (urlparse(board_url).hostname or "").removeprefix("www.")!="ifac.or.kr":
        return None
    if str(anchor.get("href") or "").strip().lower() not in ("#none","javascript:void(0);"):
        return None
    m=re.fullmatch(r"\s*goView\(['\"](\d{4,})['\"],\s*['\"][^'\"]*['\"]\);?\s*",str(anchor.get("onclick") or ""))
    if not m:
        return None
    key=str((parse_qs(urlparse(board_url).query).get("key") or [""])[0])
    if not key:
        return None
    return urljoin(board_url,"/bbs/view.do")+"?"+urlencode({"bbsSn":m.group(1),"key":key})


def ifac_title_deadline(title,registered):
    m=re.search(r"\(\s*\d{1,2}\s*[.]\s*\d{1,2}\s*[.]?\s*[~～-]\s*(\d{1,2})\s*[.]\s*(\d{1,2})\s*[.]?\s*\)",title)
    if not m or not registered:
        return None
    try:
        return base.date(registered.year,int(m.group(1)),int(m.group(2)))
    except ValueError:
        return None


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
        ifac_url=ifac_detail_url(a,r.url) if fid=="incheon:metropolitan" else None
        title_node=a.select_one("dl.title dd") if ifac_url else None
        title=base.normalize_space((title_node or a).get_text(" ",strip=True))
        if not official_position_title(title):
            continue
        href=str(a.get("href") or "").strip()
        if fid=="incheon:metropolitan" and href.lower().startswith(("javascript:","#")) and not ifac_url:
            raise RuntimeError("IFAC recruitment row has an unsupported JavaScript detail link")
        if not ifac_url and (not href or href.lower().startswith(("javascript:","#","mailto:","tel:"))):
            continue
        absolute=ifac_url or urljoin(r.url,href)
        host=(urlparse(absolute).hostname or "").lower()
        if host not in allowed:
            continue
        if absolute.rstrip("/")==r.url.rstrip("/"):
            continue
        if not looks_like_detail_url(r.url,absolute):
            continue
        context=container_text(a)
        # A shared municipal board can mention the foundation in its menu or
        # surrounding rows. Only the individual posting title proves ownership.
        if not candidate_belongs_to_foundation(foundation,title):
            continue
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
    identity_ok=verify_board_surface(soup,foundation,board_response,candidates)
    jobs=[]
    inspected=0
    errors=[]
    unverified_deadlines=[]
    for identity,meta in list(candidates.items())[:80]:
        try:
            detail=resilient_request(session,str(meta["url"]))
            detail_soup=BeautifulSoup(detail.text,"html.parser")
            detail_text=base.normalize_space(detail_soup.get_text(" ",strip=True))
            if BLOCK_PAGE_RE.search(detail.text[:4000]) or BLOCK_PAGE_RE.search(detail_text[:4000]):
                raise RuntimeError("official detail returned an access-control page")
            if JS_SHELL_RE.search(detail.text) and len(detail_text)<100:
                raise RuntimeError("official detail returned an unrendered JavaScript shell")
            list_title=base.normalize_space(str(meta.get("fallbackTitle") or ""))
            title_prefix=list_title.replace(" ","")[:20]
            if not detail_text or (title_prefix and title_prefix not in detail_text.replace(" ","")):
                raise RuntimeError("official detail does not contain its recruitment title")
            title=base.detail_title(detail_soup,str(meta.get("fallbackTitle") or ""))
            if not official_position_title(title):
                continue
            if not candidate_belongs_to_foundation(foundation,title):
                continue
            registered=base.detail_registered(detail_soup,meta.get("registered"))
            if not registered or registered>today or registered<today-base.timedelta(days=120):
                continue
            full_text=base.normalize_space(detail_soup.get_text(" ",strip=True))
            apply_end=base.extract_apply_end(full_text,registered)
            if not apply_end and str(foundation.get("id") or "")=="incheon:metropolitan":
                apply_end=ifac_title_deadline(list_title,registered)
            if apply_end and apply_end<today:
                continue
            if not apply_end and registered<today-base.timedelta(days=14):
                continue
            if not apply_end:
                unverified_deadlines.append(detail.url[:250])
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
                "deadlineVerification":"verified" if apply_end else "unverified-recent-official-post",
                "url":detail.url,
                "originalUrl":detail.url,
                "detailUrl":detail.url,
                "boardUrl":board_response.url,
                "detailLinkVerified":True,
                "detailLinkReason":"official-local-government-exact-detail" if fid in {"incheon:seohae","incheon:namdong","gyeonggi:hanam","seoul:guro"} else "official-foundation-exact-detail",
                "transportVerified":True,
            })
        except Exception as exc:
            errors.append({"url":str(meta.get("url") or "")[:500],"error":f"{type(exc).__name__}: {str(exc)[:180]}"})
    # A configured official board is healthy only if it is a real HTML surface.
    # Zero current jobs is valid; an unreadable or identity-mismatched surface is not.
    if errors:
        raise RuntimeError(f"official board detail fetch failed: {errors[:2]}")
    return jobs,{
        "adapter":"generic-official-board-v1",
        "surfacesChecked":[board_response.url],
        "discoveredDetailLinks":len(candidates),
        "datedRecruitmentRowsOnList":dated_list_rows,
        "inspectedDetailLinks":inspected,
        "publishedCurrentJobs":len(jobs),
        "detailErrors":errors[:10],
        "recentPostsWithUnverifiedDeadline":len(unverified_deadlines),
        "identityVerified":identity_ok,
    }


def collect_board(foundation):
    with make_session() as session:
        board_url=str(foundation.get("officialRecruitmentUrl") or "").strip(); host=(urlparse(board_url).hostname or "").lower()
        try:
            if host=="nsart.or.kr" or host.endswith(".nsart.or.kr"): found,meta=base.nsart_rows(session,foundation,board_url)
            elif host=="sfac.saramin.co.kr":
                found,meta=sfac_rows(session,foundation,board_url); careerlink=sfac_careerlink_probe(session); meta["surfacesChecked"]=meta.get("surfacesChecked",[])+[careerlink["url"]]; meta["secondarySurfaces"]=[careerlink]; meta["adapterStatus"]="implemented"
            elif host in GENERIC_OFFICIAL_HOSTS:
                found,meta=generic_official_rows(session,foundation,board_url)
            else:
                return [],None,{"foundationRegistryId":foundation.get("id"),"foundationName":foundation.get("name"),"boardUrl":board_url,"reason":"adapter-not-yet-implemented"},None
            return found,{"foundationRegistryId":foundation.get("id"),"foundationName":foundation.get("name"),"boardUrl":board_url,"healthy":True,**meta},None,None
        except Exception as exc:
            return [],{"foundationRegistryId":foundation.get("id"),"foundationName":foundation.get("name"),"boardUrl":board_url,"healthy":False},None,{"foundationRegistryId":foundation.get("id"),"foundationName":foundation.get("name"),"boardUrl":board_url,"error":f"{type(exc).__name__}: {exc}"}

def main():
    generated=datetime.now(KST).isoformat(timespec="seconds"); foundations=base.effective_foundations(); configured=[x for x in foundations if str(x.get("officialRecruitmentUrl") or "").strip()]; base.request=resilient_request
    jobs=[]; errors=[]; unsupported=[]; board_results=[]
    # Sessions are confined to one worker; map retains registry order in the report.
    with ThreadPoolExecutor(max_workers=4) as pool:
        for found,board,not_supported,error in pool.map(collect_board,configured):
            jobs.extend(found)
            if board: board_results.append(board)
            if not_supported: unsupported.append(not_supported)
            if error: errors.append(error)
    ids=[str(x.get("sourceIdentity") or "") for x in jobs]; urls=[str(x.get("url") or "") for x in jobs]; duplicate_ids=sorted({x for x in ids if x and ids.count(x)>1}); duplicate_urls=sorted({x for x in urls if x and urls.count(x)>1})
    if duplicate_ids or duplicate_urls: errors.append({"error":"duplicate-official-identities","ids":duplicate_ids,"urls":duplicate_urls})
    jobs.sort(key=lambda x:(str(x.get("registered") or ""),str(x.get("sourceIdentity") or "")),reverse=True); healthy=not errors and not unsupported
    OUTPUT.write_text(json.dumps({"generatedAt":generated,"sourceRole":"primary-official","jobs":jobs},ensure_ascii=False,indent=2),encoding="utf-8")
    REPORT.write_text(json.dumps({"generatedAt":generated,"policy":"official-foundation-primary-fail-closed-v7-metro-generic","healthy":healthy,"registryInstitutions":len(foundations),"officialBoardsConfigured":len(configured),"supportedBoardsChecked":len(board_results),"unsupportedConfiguredBoards":unsupported,"jobs":len(jobs),"errors":errors,"boards":board_results},ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(json.loads(REPORT.read_text(encoding="utf-8")),ensure_ascii=False,indent=2)); return 0 if healthy else 2
if __name__=="__main__": raise SystemExit(main())
