#!/usr/bin/env python3
"""Reliability wrapper for official cultural-foundation recruitment collection."""
from __future__ import annotations
import hashlib, json, re
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

def verified_open_deadline(registered, apply_end, today):
    return bool(registered and apply_end and registered<=today<=apply_end)

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
    if title and registered and not apply_end and not base.RESULT_RE.search(title):
        raise RuntimeError("SFAC recruitment has no verified application deadline")
    active=bool(title and verified_open_deadline(registered,apply_end,today)) and not base.RESULT_RE.search(title)
    rows=[]
    if active:
        stable=hashlib.sha1(f"{url}|{title}|{registered.isoformat()}".encode()).hexdigest()[:18]; fid=str(foundation.get("id") or "")
        rows.append({"sourceIdentity":f"official-foundation:sfac:{stable}","foundationRegistryId":fid,"foundationName":foundation.get("name") or "서울문화재단","organization":foundation.get("name") or "서울문화재단","source":foundation.get("name") or "서울문화재단","sourceType":"문화재단 공식채용","sourceSurface":"cultural-foundation","sourceSurfaceLabel":"서울문화재단 공식 채용공고","sourceRole":"primary-official","trustLevel":"공식","province":foundation.get("region") or "서울","region":foundation.get("municipality") or "서울특별시","regions":[foundation.get("municipality") or "서울특별시"],"location":" ".join(x for x in [foundation.get("region"),foundation.get("municipality")] if x),"title":title,"registered":base.format_date(registered),"applyEnd":base.format_date(apply_end),"url":r.url,"originalUrl":r.url,"detailUrl":r.url,"boardUrl":url,"detailLinkVerified":True,"detailLinkReason":"official-sfac-current-microsite","transportVerified":True})
    return rows,{"adapter":"sfac-saramin-current-microsite","surfacesChecked":[r.url],"discoveredDetailLinks":1 if title else 0,"inspectedDetailLinks":1 if title else 0,"publishedCurrentJobs":len(rows),"active":active,"registered":base.format_date(registered),"applyEnd":base.format_date(apply_end)}

def designated_saramin_rows(session,foundation,url):
    r=resilient_request(session,url)
    final_path=urlparse(r.url).path.rstrip("/").lower()
    if final_path.endswith("/ending_page.html") or final_path=="ending_page.html":
        return [],{
            "adapter":"designated-saramin-tenant-v1",
            "surfacesChecked":[r.url],
            "publishedCurrentJobs":0,
            "explicitEmpty":True,
            "evidence":"saramin-ending-page",
            "identityVerified":True,
        }
    # Active Saramin tenants use the same recruitment-detail contract already
    # validated for SFAC: exact HTTPS detail, real title, registration date and
    # verified application deadline are all required.
    found,meta=sfac_rows(session,foundation,r.url)
    meta["adapter"]="designated-saramin-tenant-v1"
    return found,meta


def sfac_careerlink_probe(session):
    r=resilient_request(session,SFAC_CAREERLINK_URL); soup=BeautifulSoup(r.text,"html.parser"); text=base.normalize_space(soup.get_text(" ",strip=True))
    empty_phrase="현재 게시중인 공고가 없습니다" in text or ("0 / 0" in text and "채용공고" in text)
    if not empty_phrase: raise RuntimeError("sfac.careerlink.kr lacks an explicit empty state; dedicated current-post parser is required")
    return {"url":r.url,"healthy":True,"currentJobs":0,"explicitEmpty":True,"evidence":"explicit-empty-phrase","role":"secondary-official-contract-surface"}


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
    r"채용\s*과정\s*공개|후보자\s*추천\s*공고|모집\s*결과",
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
    "gcfac.or.kr","www.gcfac.or.kr",
    "dbfac.or.kr","www.dbfac.or.kr",
    "ddmac.or.kr","www.ddmac.or.kr",
    "mfac.or.kr","www.mfac.or.kr",
    "nowonarts.kr","www.nowonarts.kr",
    "songpafac.or.kr","www.songpafac.or.kr",
    "recruit.incruit.com",
    "gmcf.incruit.com",
    "gmcf.or.kr","www.gmcf.or.kr","m.gmcf.or.kr","gm.go.kr","www.gm.go.kr",
    "gcf.or.kr","www.gcf.or.kr",
    "yjcf.or.kr","www.yjcf.or.kr",
    "artic.or.kr","www.artic.or.kr",
    "ansanart.com","www.ansanart.com",
    "pccf.or.kr","www.pccf.or.kr",
    "gangnam.go.kr","www.gangnam.go.kr",
    "yfac.kr","www.yfac.kr",
    "ydpcf.or.kr","www.ydpcf.or.kr",
    "recruit.efac.or.kr",
    "recruit.jnfac.or.kr",
    "gdfac.or.kr","www.gdfac.or.kr",
    "sdfac.or.kr","www.sdfac.or.kr",
    "gunpocf.incruit.com",
    "yicf.incruit.com",
    "gbcf.fairyhr.com","yfac.fairyhr.com",
    "gfac.or.kr","www.gfac.or.kr",
    "naruart.applyin.co.kr",
    "artgy.or.kr","www.artgy.or.kr","goyang.go.kr","www.goyang.go.kr",
    "gcart.or.kr","www.gcart.or.kr",
    "bcf.or.kr","www.bcf.or.kr",
    "ayac.saramin.co.kr","ayac.or.kr","www.ayac.or.kr","m.ayac.or.kr",
    "pcfac.or.kr","www.pcfac.or.kr",
    "swcf.or.kr","www.swcf.or.kr",
    "guro.go.kr","www.guro.go.kr",
    "guri.go.kr","www.guri.go.kr",
    "hanam.go.kr","www.hanam.go.kr",
    "seochocf.applyin.co.kr",
    "caci.or.kr","www.caci.or.kr",
    "seongnam.go.kr","www.seongnam.go.kr",
    "uac.or.kr","www.uac.or.kr",
    "paju.go.kr","www.paju.go.kr",
    "culture.seoul.go.kr",
    "ancf.or.kr","www.ancf.or.kr",
}
PAGE_PARAM_KEYS=("pageIndex","page","pgno","pageNo","pageno")
BLOCK_PAGE_RE=re.compile(r"WELLCONN|TRACER|접근\s*대기|접근이\s*차단|비정상적인\s*접근|Access\s+Denied|Web\s+Application\s+Firewall",re.I)
JS_SHELL_RE=re.compile(r"\{\{\s*[\w.$]+\s*\}\}|\bng-(?:app|repeat|click)\s*=|\bv-(?:for|if)\s*=",re.I)
EXPLICIT_EMPTY_RE=re.compile(
    r"등록된\s*(?:글|게시물|공고|자료|정보|채용공고)[이가]\s*없|게시물이\s*없|"
    r"검색된\s*(?:결과|자료)가\s*없|현재\s*(?:게시중인\s*)?(?:채용)?공고가\s*없|"
    r"진행\s*중\s*채용공고\s*0건|진행\s*중인\s*채용공고가\s*없|진행\s*중인\s*채용이\s*없",
    re.I,
)
SAAS_EXPLICIT_EMPTY_HOSTS={
    "recruit.incruit.com",
    "gbcf.fairyhr.com",
    "yfac.fairyhr.com",
    "gunpocf.incruit.com",
    "yicf.incruit.com",
}


def verify_board_surface(soup, foundation, response, candidates):
    visible=base.normalize_space(soup.get_text(" ",strip=True))
    if BLOCK_PAGE_RE.search(visible[:4000]) or BLOCK_PAGE_RE.search(response.text[:4000]):
        raise RuntimeError("official board returned an access-control page")
    if not candidates and JS_SHELL_RE.search(response.text):
        raise RuntimeError("official board is a JS-rendered shell without parsed details")
    unsupported=[]
    stale_unresolved=[]
    today=datetime.now(KST).date()
    for a in soup.find_all("a",href=True):
        if not official_position_title(a.get_text(" ",strip=True)):
            continue
        uses_js=(
            str(a.get("href") or "").strip().lower().startswith(("javascript:","#"))
            or a.has_attr("onclick")
        )
        if not uses_js:
            continue
        if str(foundation.get("id"))=="incheon:metropolitan" and ifac_detail_url(a,response.url):
            continue
        if official_js_detail_url(a,response.url):
            continue
        registered=base.parse_date_text(container_text(a))
        if registered and registered < today-base.timedelta(days=120):
            stale_unresolved.append(a)
            continue
        unsupported.append(a)
    if unsupported:
        samples=[]
        for a in unsupported[:3]:
            parent=a.parent
            grand=parent.parent if parent is not None else None
            samples.append({
                "text": base.normalize_space(a.get_text(" ",strip=True))[:180],
                "href": str(a.get("href") or "")[:240],
                "onclick": str(a.get("onclick") or "")[:320],
                "dataSeq": str(a.get("data-seq") or "")[:120],
                "dataId": str(a.get("data-id") or "")[:120],
                "dataPstSn": str(a.get("data-pstsn") or "")[:120],
                "parentAttrs": dict(getattr(parent,"attrs",{}) or {}),
                "grandAttrs": dict(getattr(grand,"attrs",{}) or {}),
                "ancestorHtml": str(grand or parent or a)[:1200],
            })
        script_hints=[]
        for script in soup.find_all("script"):
            raw=str(script.string or script.get_text(" ",strip=False) or "")
            if not raw:
                continue
            low=raw.lower()
            if any(token in low for token in ("reg_view","fnview","jsview","recruitdetail","notice_all_view","board_seq","pk_seq")):
                script_hints.append(base.normalize_space(raw)[:1400])
            if len(script_hints)>=3:
                break
        raise RuntimeError(
            f"official recruitment rows use unsupported JavaScript detail links: {samples}; "
            f"scriptHints={script_hints}"
        )
    normalized=visible.replace(" ","")
    aliases=[foundation.get("name"),*(foundation.get("aliases") or [])]
    fid=str(foundation.get("id") or "")
    identity_ok=any(base.normalize_space(x) and base.normalize_space(x).replace(" ","") in normalized for x in aliases)
    if fid=="incheon:seohae":
        identity_ok=identity_ok or "채용소식" in visible
    if fid=="incheon:namdong":
        identity_ok=identity_ok or ("타기관" in visible and ("채용" in visible or "공고" in visible))
    if not identity_ok:
        title=base.normalize_space(soup.title.get_text(" ",strip=True))[:100] if soup.title else ""
        raise RuntimeError(f"official board identity unproved: finalUrl={response.url[:200]!r}, title={title!r}, bytes={len(response.content)}, candidates={len(candidates)}")
    if not candidates and not EXPLICIT_EMPTY_RE.search(visible) and not stale_unresolved:
        raise RuntimeError("official board has no parseable details and no explicit empty state")
    return True


def official_position_title(title:str)->bool:
    title=base.normalize_space(title)
    if title.replace(" ","") in {"채용공고","채용정보","채용안내","직원채용","직원채용공고","지도강사모집공고"}:
        return False
    if re.search(r"진행\s*중\s*채용공고\s*0건",title,re.I):
        return False
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


SHARED_OFFICIAL_BOARD_FOUNDATION_IDS={
    "incheon:namdong",
    "gyeonggi:goyang",
    "gyeonggi:gwangmyeong",
    "seoul:guro",
    "gyeonggi:guri",
    "gyeonggi:hanam",
    "gyeonggi:seongnam",
    "gyeonggi:paju",
}


def foundation_owned_board_host(foundation, board_url:str)->bool:
    fid=str(foundation.get("id") or "")
    if fid in SHARED_OFFICIAL_BOARD_FOUNDATION_IDS:
        return False
    board_host=(urlparse(board_url).hostname or "").lower()
    home_host=(urlparse(str(foundation.get("homepage") or "")).hostname or "").lower()
    if not board_host or not home_host:
        return False
    board_base=board_host[4:] if board_host.startswith("www.") else board_host
    home_base=home_host[4:] if home_host.startswith("www.") else home_host
    return board_base==home_base or board_base.endswith("."+home_base)


def candidate_belongs_to_foundation(foundation,text:str,*,shared_board:bool=False)->bool:
    if not shared_board and str(foundation.get("id") or "") not in SHARED_OFFICIAL_BOARD_FOUNDATION_IDS:
        return True
    haystack=base.normalize_space(text).replace(" ","")
    aliases=[foundation.get("name"),*(foundation.get("aliases") or [])]
    return any(base.normalize_space(x).replace(" ","") in haystack for x in aliases if base.normalize_space(x))


def detail_identity(url:str)->str:
    parsed=urlparse(url)
    query=parse_qs(parsed.query)
    for key in ("bbsSn","boardId","msg_seq","sq","idx","uid","nttSn","nttNo","seq","pstSn","pk_seq","board_seq","q_bbscttSn","bbIdx","action-value","no","id"):
        value=str((query.get(key) or [""])[0]).strip()
        if value:
            return f"{key}:{value}"
    parts=[p for p in parsed.path.split("/") if p]
    if parts and re.fullmatch(r"\d{2,}",parts[-1]):
        return f"path:{parts[-1]}"
    return "url:"+hashlib.sha1(url.encode()).hexdigest()[:20]


def looks_like_detail_url(board_url:str, candidate_url:str)->bool:
    board=urlparse(board_url); candidate=urlparse(candidate_url)
    if board.path.rstrip("/")!=candidate.path.rstrip("/"):
        return True
    query=parse_qs(candidate.query)
    if any(key in query for key in ("b_num","idx","uid","bbsSn","boardId","msg_seq","sq","nttSn","nttNo","seq","pstSn","pk_seq","board_seq","q_bbscttSn","bbIdx","action-value","no")):
        return True
    if query.get("bmode")==["view"] or query.get("proc_type")==["view"] or query.get("type")==["view"] or query.get("action")==["read"]:
        return True
    return False


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


def official_js_detail_url(anchor, board_url:str)->str|None:
    """Resolve only known same-host official-board JavaScript detail contracts."""
    parsed=urlparse(board_url)
    host=(parsed.hostname or "").lower()
    href=str(anchor.get("href") or "").strip()
    onclick=str(anchor.get("onclick") or "").strip()
    ancestor_onclicks=[]
    node=anchor.parent
    for _ in range(3):
        if node is None:
            break
        value=str(node.get("onclick") or "").strip() if hasattr(node,"get") else ""
        if value:
            ancestor_onclicks.append(value)
        node=node.parent
    raw=" ".join([
        href, onclick,
        str(anchor.get("seq") or ""),
        str(anchor.get("data-seq") or ""),
        str(anchor.get("data-id") or ""),
        str(anchor.get("data-pstsn") or ""),
        *ancestor_onclicks,
    ])

    def explicit_or_arg(keys, *, min_digits=3):
        for key in keys:
            m=re.search(rf"{re.escape(key)}\s*[:=,]?\s*['\"]?(\d{{{min_digits},}})",raw,re.I)
            if m:
                return m.group(1)
        m=re.search(rf"\(\s*['\"]?(\d{{{min_digits},}})['\"]?",onclick)
        return m.group(1) if m else None

    query=parse_qs(parsed.query)

    if host in {"goyang.go.kr","www.goyang.go.kr","gm.go.kr","www.gm.go.kr"} and "BD_selectBbsList.do" in parsed.path:
        named=re.search(r"""fnView\(\s*['"](?P<bbs>\d+)['"]\s*,\s*['"](?P<ident>\d{10,})['"]""",onclick)
        ident=named.group("ident") if named else explicit_or_arg(("q_bbscttSn","bbscttSn"),min_digits=10)
        bbs=(named.group("bbs") if named else "") or str((query.get("q_bbsCode") or [""])[0])
        if ident and bbs:
            path=parsed.path.replace("BD_selectBbsList.do","BD_selectBbs.do")
            return f"{parsed.scheme}://{parsed.netloc}{path}?"+urlencode({"q_bbsCode":bbs,"q_bbscttSn":ident})

    if host in {"gcfac.or.kr","www.gcfac.or.kr"} and parsed.path.rstrip("/")=="/board/recruit":
        ancestor_raw=" ".join(ancestor_onclicks)
        named=re.search(r"""goBoardView\(\s*['"](?P<ident>\d{3,})['"]\s*\)""",ancestor_raw)
        ident=named.group("ident") if named else explicit_or_arg(("board_seq","boardSeq"),min_digits=3)
        if ident:
            menu=str((query.get("gcfac_menu_cd") or ["U0140"])[0])
            return f"{parsed.scheme}://{parsed.netloc}/board/recruitDetail?"+urlencode({"board_seq":ident,"gcfac_menu_cd":menu})

    if host in {"mfac.or.kr","www.mfac.or.kr"} and parsed.path.endswith("/notice_all_list.jsp"):
        seq_attr=str(anchor.get("seq") or "").strip()
        ident=seq_attr if re.fullmatch(r"\d{3,}",seq_attr) else explicit_or_arg(("pk_seq","pkSeq"),min_digits=3)
        if ident:
            return f"{parsed.scheme}://{parsed.netloc}/communication/notice_all_view.jsp?"+urlencode({
                "page":"1","pk_seq":ident,"sc_b_code":"BOARD_1207683401","sc_type":"3"
            })

    if host in {"pccf.or.kr","www.pccf.or.kr"} and parsed.path.endswith("/bbs/list.do"):
        ident=explicit_or_arg(("pstSn","pst_sn"),min_digits=6)
        key=str((query.get("key") or [""])[0])
        if ident and key:
            return f"{parsed.scheme}://{parsed.netloc}/bbs/view.do?"+urlencode({"key":key,"pstSn":ident})

    if host in {"pcfac.or.kr","www.pcfac.or.kr"} and parsed.path.endswith("/sub07/sub03.php"):
        named=re.search(r"""reg_view\(\s*['"](?P<ident>\d{4,})['"]\s*\)""",href+" "+onclick)
        if named:
            return f"{parsed.scheme}://{parsed.netloc}/sub07/sub03.php?"+urlencode({
                "type":"view","uid":named.group("ident")
            })

    if host in {"paju.go.kr","www.paju.go.kr"} and parsed.path.endswith("/BD_board.list.do"):
        named=re.search(r"""jsView\(\s*['"](?P<bbs>\d+)['"]\s*,\s*['"](?P<ident>\d{10,})['"]""",onclick)
        ident=named.group("ident") if named else explicit_or_arg(("seq",),min_digits=10)
        bbs=(named.group("bbs") if named else "") or str((query.get("bbsCd") or [""])[0])
        ctg=str((query.get("q_ctgCd") or [""])[0])
        if ident and bbs:
            params={"bbsCd":bbs,"seq":ident}
            if ctg:
                params["q_ctgCd"]=ctg
            return f"{parsed.scheme}://{parsed.netloc}{parsed.path.replace('BD_board.list.do','BD_board.view.do')}?"+urlencode(params)

    return None


def ifac_title_deadline(title,registered):
    m=re.search(r"\(\s*\d{1,2}\s*[.]\s*\d{1,2}\s*[.]?\s*[~～-]\s*(\d{1,2})\s*[.]\s*(\d{1,2})\s*[.]?\s*\)",title)
    if not m or not registered:
        return None
    try:
        return base.date(registered.year,int(m.group(1)),int(m.group(2)))
    except ValueError:
        return None


def list_detail_candidates(session,foundation,board_url):
    requested=urlparse(board_url)
    requested_host=(requested.hostname or "").lower()
    # Modern Incruit tenant landing pages expose the actual vacancy list under
    # /<tenant>/job/. Read that canonical list surface instead of treating the
    # landing shell as an empty/unsupported board.
    if requested_host=="recruit.incruit.com":
        parts=[p for p in requested.path.split("/") if p]
        if parts and not (len(parts)>=2 and parts[1]=="job"):
            board_url=f"https://recruit.incruit.com/{parts[0]}/job/"
    elif requested_host=="recruit.jnfac.or.kr" and requested.path.rstrip("/") in ("",""):
        board_url="https://recruit.jnfac.or.kr/recruit"
    r=resilient_request(session,board_url)
    soup=BeautifulSoup(r.text,"html.parser")
    board_host=(urlparse(r.url).hostname or "").lower()
    fid=str(foundation.get("id") or "")
    visible=base.normalize_space(soup.get_text(" ",strip=True))
    # On supported recruitment SaaS surfaces an explicit current-zero message is
    # authoritative for the active vacancy list. Do not mistake navigation links
    # such as "채용공고" or "announcement" for live postings.
    if board_host in SAAS_EXPLICIT_EMPTY_HOSTS and EXPLICIT_EMPTY_RE.search(visible):
        return r,soup,{},0
    allowed={board_host}
    if fid=="incheon:seohae":
        allowed.update({"seohae.go.kr","www.seohae.go.kr","isel.seo.incheon.kr"})
    candidates={}
    dated_list_rows=0
    for a in soup.find_all("a",href=True):
        ifac_url=ifac_detail_url(a,r.url) if fid=="incheon:metropolitan" else None
        js_url=official_js_detail_url(a,r.url)
        href=str(a.get("href") or "").strip()
        if not ifac_url and not js_url and (not href or href.lower().startswith(("javascript:","#","mailto:","tel:"))):
            continue
        absolute=ifac_url or js_url or urljoin(r.url,href)
        host=(urlparse(absolute).hostname or "").lower()
        if host not in allowed:
            continue
        if absolute.rstrip("/")==r.url.rstrip("/"):
            continue
        if not looks_like_detail_url(r.url,absolute):
            continue

        title_node=a.select_one("dl.title dd") if ifac_url else None
        title=base.normalize_space((title_node or a).get_text(" ",strip=True))
        context=container_text(a)
        parsed_absolute=urlparse(absolute)
        incruit_job=bool(
            board_host=="recruit.incruit.com"
            and re.search(r"/job/\d{4,}(?:/)?$",parsed_absolute.path)
        )
        # Modern Incruit list anchors are often labelled only "자세히 보기";
        # the vacancy title/date live in the containing card. Use the card only
        # for candidate discovery and let the exact detail page prove the title.
        if not official_position_title(title):
            if incruit_job and official_position_title(context):
                title=""
            else:
                continue
        shared_board=fid=="seoul:dongjak" and board_host=="culture.seoul.go.kr"
        if not candidate_belongs_to_foundation(foundation,title+" "+context,shared_board=shared_board):
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
                detail_heading=base.detail_title(detail_soup,"")
                raise RuntimeError(
                    "official detail does not contain its recruitment title: "
                    f"listTitle={list_title[:180]!r}, detailHeading={detail_heading[:180]!r}, "
                    f"detailText={detail_text[:260]!r}"
                )
            title=base.detail_title(detail_soup,str(meta.get("fallbackTitle") or ""))
            if not official_position_title(title):
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
            if not apply_end and registered<today-base.timedelta(days=30):
                continue
            if not apply_end:
                unverified_deadlines.append({
                    "url":detail.url[:250],
                    "listTitle":list_title[:180],
                    "registered":base.format_date(registered),
                    "listContext":base.normalize_space(str(meta.get("listContext") or ""))[:360],
                    "detailHeading":base.detail_title(detail_soup,"")[:180],
                    "detailDateHints":[base.format_date(d) for d in base.parse_all_dates(full_text)[:8]],
                })
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
                "detailLinkReason":"official-local-government-exact-detail" if fid in {"incheon:seohae","incheon:namdong"} else "official-foundation-exact-detail",
                "transportVerified":True,
            })
        except Exception as exc:
            errors.append({"url":str(meta.get("url") or "")[:500],"error":f"{type(exc).__name__}: {str(exc)[:180]}"})
    # A configured official board is healthy only if it is a real HTML surface.
    # Zero current jobs is valid; an unreadable or identity-mismatched surface is not.
    if errors:
        raise RuntimeError(f"official board detail fetch failed: {errors[:2]}")
    if unverified_deadlines:
        raise RuntimeError(f"official recent recruitment lacks a verified application deadline: {unverified_deadlines[:2]}")
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


def collect_with_verified_fallback(session, foundation, board_url):
    fid=str(foundation.get("id") or "")
    host=(urlparse(board_url).hostname or "").lower()
    def collect(url):
        h=(urlparse(url).hostname or "").lower()
        if h=="nsart.or.kr" or h.endswith(".nsart.or.kr"):
            return base.nsart_rows(session,foundation,url)
        if h=="ayac.saramin.co.kr":
            return designated_saramin_rows(session,foundation,url)
        if h=="sfac.saramin.co.kr":
            found,meta=sfac_rows(session,foundation,url)
            # Careerlink is a secondary official contract surface. A markup change
            # there must not invalidate a healthy primary Saramin board; preserve
            # the probe result as diagnostics while keeping publication fail-closed
            # on the primary source itself.
            try:
                careerlink=sfac_careerlink_probe(session)
            except Exception as exc:
                meta["secondaryProbeError"]=f"{type(exc).__name__}: {str(exc)[:180]}"
            else:
                meta["surfacesChecked"]=meta.get("surfacesChecked",[])+[careerlink["url"]]
                meta["secondarySurfaces"]=[careerlink]
            meta["adapterStatus"]="implemented"
            return found,meta
        if h in GENERIC_OFFICIAL_HOSTS:
            return generic_official_rows(session,foundation,url)
        raise RuntimeError("adapter-not-yet-implemented")

    try:
        return collect(board_url)
    except (requests.exceptions.SSLError, requests.exceptions.ConnectTimeout, requests.exceptions.ConnectionError) as exc:
        fallback=str(foundation.get("verifiedFallbackRecruitmentUrl") or "").strip()
        if not fallback:
            raise
        found,meta=collect(fallback)
        role=str(foundation.get("verifiedFallbackRole") or "secondary-authoritative")
        for job in found:
            job["sourceRole"]=role
            if role=="secondary-official-mirror":
                job["sourceType"]="공식 공공기관 채용 미러"
                job["trustLevel"]="공식"
            else:
                job["sourceType"]="검증된 문화재단 연합회 채용"
                job["trustLevel"]="검증"
            job["primaryOfficialBoardUrl"]=board_url
            job["boardUrl"]=fallback
        meta["fallbackUsed"]=True
        meta["fallbackRole"]=role
        meta["primaryBoardUrl"]=board_url
        meta["fallbackBoardUrl"]=fallback
        meta["primaryTransportError"]=f"{type(exc).__name__}: {str(exc)[:180]}"
        return found,meta


def main():
    generated=datetime.now(KST).isoformat(timespec="seconds"); foundations=base.effective_foundations(); configured=[x for x in foundations if str(x.get("officialRecruitmentUrl") or "").strip()]; session=make_session(); base.request=resilient_request
    jobs=[]; errors=[]; unsupported=[]; board_results=[]
    for foundation in configured:
        board_url=str(foundation.get("officialRecruitmentUrl") or "").strip(); host=(urlparse(board_url).hostname or "").lower()
        try:
            try:
                found,meta=collect_with_verified_fallback(session,foundation,board_url)
            except RuntimeError as exc:
                if str(exc)=="adapter-not-yet-implemented":
                    unsupported.append({"foundationRegistryId":foundation.get("id"),"foundationName":foundation.get("name"),"boardUrl":board_url,"reason":"adapter-not-yet-implemented"}); continue
                raise
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
