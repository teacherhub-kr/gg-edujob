#!/usr/bin/env python3
"""Reliability wrapper for official cultural-foundation recruitment collection."""
from __future__ import annotations
import hashlib, json, math, re, shutil, subprocess
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


class BrowserVerifiedResponse:
    def __init__(self,url,text):
        self.url=url
        self.text=text
        self.content=text.encode("utf-8")
        self.encoding="utf-8"
        self.status_code=200


def browser_verified_request(url):
    """Use the runner browser only for a narrowly allowlisted TLS-chain failure.

    Chrome keeps normal certificate validation enabled. Certificate-error
    bypass flags and insecure TLS options are not permitted.
    """
    host=(urlparse(url).hostname or "").lower()
    if host not in {"sd.go.kr","www.sd.go.kr"}:
        raise RuntimeError(f"browser TLS fallback is not allowlisted for {host!r}")
    chrome=shutil.which("google-chrome") or shutil.which("google-chrome-stable") or shutil.which("chromium")
    if not chrome:
        raise RuntimeError("verified browser TLS fallback unavailable")
    cmd=[chrome,"--headless=new","--no-sandbox","--disable-gpu","--dump-dom",url]
    cp=subprocess.run(cmd,text=True,capture_output=True,timeout=45)
    html=cp.stdout or ""
    stderr=cp.stderr or ""
    if cp.returncode!=0 or len(html)<1000:
        raise RuntimeError(f"verified browser TLS fallback failed rc={cp.returncode} bytes={len(html)} err={stderr[-500:]!r}")
    combined=(html+" "+stderr)[:200000]
    if re.search(r"NET::ERR_CERT|Privacy error|Your connection is not private|ERR_SSL|certificate error",combined,re.I):
        raise RuntimeError("verified browser TLS fallback reported a certificate error")
    if BLOCK_PAGE_RE.search(base.normalize_space(BeautifulSoup(html,"html.parser").get_text(" ",strip=True))[:6000]):
        raise RuntimeError("verified browser TLS fallback returned an access-control page")
    return BrowserVerifiedResponse(url,html)


def resilient_request(session,url,*,extra_headers=None):
    headers={"User-Agent":UA,"Cache-Control":"no-cache, no-store, max-age=0","Pragma":"no-cache"}
    if extra_headers:
        headers.update(extra_headers)
    try:
        r=session.get(url,timeout=25,headers=headers,allow_redirects=True)
        r.raise_for_status()
    except requests.exceptions.SSLError:
        r=browser_verified_request(url)
    if urlparse(url).scheme.lower()=="https" and urlparse(r.url).scheme.lower()!="https":
        raise RuntimeError(f"HTTPS official URL downgraded in redirect: {url[:180]} -> {r.url[:180]}")
    if not getattr(r,"encoding",None) or str(r.encoding).lower()=="iso-8859-1":
        r.encoding=getattr(r,"apparent_encoding",None) or "utf-8"
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
    r"(?:공연장\s*)?안내원\s*(?:추가\s*)?(?:채용|모집)|"
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
    "sdfac.or.kr","www.sdfac.or.kr","sd.go.kr","www.sd.go.kr",
    "gunpocf.incruit.com",
    "yicf.incruit.com",
    "gbcf.fairyhr.com","yfac.fairyhr.com",
    "gfac.or.kr","www.gfac.or.kr",
    "naruart.applyin.co.kr",
    "gwangjin.go.kr","www.gwangjin.go.kr",
    "pajucf.or.kr","www.pajucf.or.kr",
    "artgy.or.kr","www.artgy.or.kr","goyang.go.kr","www.goyang.go.kr",
    "gcart.or.kr","www.gcart.or.kr",
    "bcf.or.kr","www.bcf.or.kr","bucheon.go.kr","www.bucheon.go.kr",
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
    r"진행\s*중\s*채용공고\s*0\s*건|진행\s*중인\s*채용공고가\s*없|진행\s*중인\s*채용이\s*없",
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
    "gyeonggi:bucheon",
    "seoul:dongjak",
    "incheon:namdong",
    "gyeonggi:goyang",
    "gyeonggi:gwangmyeong",
    "seoul:guro",
    "seoul:gwangjin",
    "gyeonggi:guri",
    "gyeonggi:hanam",
    "gyeonggi:seongnam",
    "seoul:seongdong",
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
    for key in ("bbsSn","boardId","msg_seq","sq","idx","uid","nttSn","nttNo","seq","pstSn","pk_seq","board_seq","q_bbscttSn","bbIdx","action-value","encid","no","id"):
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
    if any(key in query for key in ("b_num","idx","uid","bbsSn","boardId","msg_seq","sq","nttSn","nttNo","seq","pstSn","pk_seq","board_seq","q_bbscttSn","bbIdx","action-value","encid","no")):
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


def dbfac_notice_key(title:str)->str:
    m=re.search(r"제\s*(\d{4})\s*[-–]\s*(\d+)\s*호",title or "")
    return f"{m.group(1)}-{int(m.group(2))}" if m else ""


def dbfac_list_rows(soup):
    rows=[]
    for tr in soup.find_all("tr"):
        a=tr.find("a",href=True)
        if not a:
            continue
        href=str(a.get("href") or "")
        m=re.search(r"""contentsViewAll\(\s*['"](?P<cid>[0-9a-fA-F]{16,})['"]\s*,\s*['"]7['"]\s*\)""",href)
        if not m:
            continue
        title=base.normalize_space(a.get_text(" ",strip=True))
        text=base.normalize_space(tr.get_text(" ",strip=True))
        registered=base.parse_date_text(text)
        rows.append({
            "contentsId":m.group("cid"),"title":title,"text":text,
            "registered":registered,"noticeKey":dbfac_notice_key(title),
            "resultLike":bool(base.RESULT_RE.search(title) or re.search(r"\[발표\]|서류전형\s*합격|면접전형|최종\s*합격",title,re.I)),
        })
    return rows


def dbfac_rows(session,foundation,board_url):
    today=datetime.now(KST).date()
    page=resilient_request(session,board_url)
    soup=BeautifulSoup(page.text,"html.parser")
    if "도봉문화재단" not in base.normalize_space(soup.get_text(" ",strip=True)):
        raise RuntimeError("DBFAC board identity unproved")
    endpoint=f"{urlparse(page.url).scheme}://{urlparse(page.url).netloc}/front/board/boardContentsList.do"
    rr=session.post(
        endpoint,
        data={"board_id":"7","miv_pageNo":"1","miv_pageSize":"30","mode":"W","contents_id":"","viewType":"","cate_id":""},
        timeout=25,
        headers={"User-Agent":UA,"Cache-Control":"no-cache, no-store, max-age=0","Pragma":"no-cache"},
    )
    rr.raise_for_status()
    rsoup=BeautifulSoup(rr.text,"html.parser")
    rows=dbfac_list_rows(rsoup)
    if not rows:
        raise RuntimeError("DBFAC AJAX list returned no parseable recruitment rows")
    result_dates={}
    for row in rows:
        if row["resultLike"] and row["noticeKey"] and row["registered"]:
            prev=result_dates.get(row["noticeKey"])
            if prev is None or row["registered"]>prev:
                result_dates[row["noticeKey"]]=row["registered"]
    jobs=[]; inspected=0; unverified=[]; errors=[]
    for row in rows:
        title=row["title"]
        if row["resultLike"] or not official_position_title(title):
            continue
        registered=row["registered"]
        if not registered or registered>today or registered<today-base.timedelta(days=120):
            continue
        closed_at=result_dates.get(row["noticeKey"]) if row["noticeKey"] else None
        if closed_at and closed_at>=registered:
            continue
        if registered<today-base.timedelta(days=30):
            continue
        detail_url=f"{urlparse(page.url).scheme}://{urlparse(page.url).netloc}/front/board/boardContentsView.do?"+urlencode({"board_id":"7","contents_id":row["contentsId"]})
        try:
            detail=resilient_request(session,detail_url)
            ds=BeautifulSoup(detail.text,"html.parser")
            full=base.normalize_space(ds.get_text(" ",strip=True))
            if title.replace(" ","")[:18] not in full.replace(" ",""):
                raise RuntimeError("DBFAC detail does not contain list title")
            apply_end=base.extract_apply_end(full,registered)
            if apply_end and apply_end<today:
                continue
            if not apply_end:
                unverified.append({"url":detail.url[:240],"title":title[:180]})
                continue
            inspected+=1
            fid=str(foundation.get("id") or "")
            identity="contents_id:"+row["contentsId"]
            sid="official-foundation:"+fid+":"+hashlib.sha1((identity+"|"+detail.url).encode()).hexdigest()[:20]
            jobs.append({
                "sourceIdentity":sid,"foundationRegistryId":fid,
                "foundationName":foundation.get("name") or "","organization":foundation.get("name") or "",
                "source":foundation.get("name") or "","sourceType":"문화재단 공식채용/모집",
                "sourceSurface":"cultural-foundation","sourceSurfaceLabel":f"{foundation.get('name') or '문화재단'} 공식 채용·인력모집",
                "sourceRole":"primary-official","trustLevel":"공식","province":foundation.get("region") or "",
                "region":foundation.get("municipality") or "","regions":[foundation.get("municipality")] if foundation.get("municipality") else [],
                "location":" ".join(x for x in [foundation.get("region"),foundation.get("municipality")] if x),
                "title":title,"registered":base.format_date(registered),"applyEnd":base.format_date(apply_end),
                "url":detail.url,"originalUrl":detail.url,"detailUrl":detail.url,"boardUrl":page.url,
                "detailLinkVerified":True,"detailLinkReason":"official-foundation-dbfac-exact-detail","transportVerified":True,
            })
        except Exception as exc:
            errors.append({"url":detail_url[:240],"error":f"{type(exc).__name__}: {str(exc)[:180]}"})
    if errors:
        raise RuntimeError(f"DBFAC detail verification failed: {errors[:2]}")
    if unverified:
        raise RuntimeError(f"DBFAC recent recruitment lacks verified deadline: {unverified[:2]}")
    return jobs,{
        "adapter":"dbfac-ajax-recruitment-v1","surfacesChecked":[page.url,endpoint],
        "discoveredDetailLinks":len(rows),"inspectedDetailLinks":inspected,
        "publishedCurrentJobs":len(jobs),"closedByLaterStage":sum(
            1 for row in rows if row["noticeKey"] and row["noticeKey"] in result_dates and not row["resultLike"]
        ),"identityVerified":True,
    }


def vue_notice_filter(category_id:int,page:int=1,page_size:int=30):
    return {
        "PerformanceID":None,"PerformanceName":None,"CategoryID":category_id,
        "SearchType":1,"SearchName":"제목","SearchText":None,
        "DepartmentID":1,"PageIndex":page,"PageSize":page_size,
    }


def vue_notice_rows(session,foundation,board_url,category_id:int):
    today=datetime.now(KST).date()
    parsed=urlparse(board_url)
    origin=f"{parsed.scheme}://{parsed.netloc}"
    jobs=[]; discovered=0; inspected=0; errors=[]; unverified=[]
    seen=set()
    for page in range(1,5):
        filt=vue_notice_filter(category_id,page)
        create=session.post(
            origin+"/api/historyBack/create",
            data={"value":json.dumps(filt,ensure_ascii=False,separators=(",",":"))},
            timeout=25,
            headers={"User-Agent":UA,"Cache-Control":"no-cache, no-store, max-age=0","Pragma":"no-cache"},
        )
        create.raise_for_status()
        payload=create.json()
        key=payload.get("Tag") if payload.get("Code")==0 else None
        if not key:
            raise RuntimeError("official Vue board failed to create search key")
        search=session.get(
            origin+"/community/notice/search",
            params={"q":key},timeout=25,
            headers={"User-Agent":UA,"Cache-Control":"no-cache, no-store, max-age=0","Pragma":"no-cache"},
        )
        search.raise_for_status()
        data=search.json()
        tag=(data or {}).get("Tag") or {}
        articles=tag.get("ArticleTitles") or []
        if not isinstance(articles,list):
            raise RuntimeError("official Vue board search returned malformed articles")
        if not articles:
            break
        discovered+=len(articles)
        oldest=None
        for item in articles:
            title=base.normalize_space(str((item or {}).get("Title") or ""))
            category=int((item or {}).get("CategoryID") or 0)
            if category!=category_id or not official_position_title(title):
                continue
            registered=base.parse_date_text(str((item or {}).get("CreateDate") or ""))
            if registered:
                oldest=registered if oldest is None or registered<oldest else oldest
            if not registered or registered>today or registered<today-base.timedelta(days=120):
                continue
            detail_path=str((item or {}).get("DetailsUrl") or "").strip()
            if not detail_path:
                errors.append({"title":title[:180],"error":"missing official detail URL"})
                continue
            detail_url=urljoin(origin,detail_path)
            identity=detail_identity(detail_url)
            if identity in seen:
                continue
            seen.add(identity)
            try:
                detail=resilient_request(session,detail_url)
                ds=BeautifulSoup(detail.text,"html.parser")
                text=base.normalize_space(ds.get_text(" ",strip=True))
                if not text or title.replace(" ","")[:18] not in text.replace(" ",""):
                    raise RuntimeError("Vue official detail does not contain list title")
                resolved_title=base.detail_title(ds,title)
                if not official_position_title(resolved_title):
                    continue
                apply_end=base.extract_apply_end(text,registered)
                if apply_end and apply_end<today:
                    continue
                if not apply_end and registered<today-base.timedelta(days=30):
                    continue
                if not apply_end:
                    unverified.append({"url":detail.url[:240],"title":title[:180]})
                    continue
                inspected+=1
                fid=str(foundation.get("id") or "")
                sid="official-foundation:"+fid+":"+hashlib.sha1((identity+"|"+detail.url).encode()).hexdigest()[:20]
                jobs.append({
                    "sourceIdentity":sid,"foundationRegistryId":fid,
                    "foundationName":foundation.get("name") or "","organization":foundation.get("name") or "",
                    "source":foundation.get("name") or "","sourceType":"문화재단 공식채용/모집",
                    "sourceSurface":"cultural-foundation","sourceSurfaceLabel":f"{foundation.get('name') or '문화재단'} 공식 채용·인력모집",
                    "sourceRole":"primary-official","trustLevel":"공식","province":foundation.get("region") or "",
                    "region":foundation.get("municipality") or "","regions":[foundation.get("municipality")] if foundation.get("municipality") else [],
                    "location":" ".join(x for x in [foundation.get("region"),foundation.get("municipality")] if x),
                    "title":resolved_title,"registered":base.format_date(registered),"applyEnd":base.format_date(apply_end),
                    "url":detail.url,"originalUrl":detail.url,"detailUrl":detail.url,"boardUrl":board_url,
                    "detailLinkVerified":True,"detailLinkReason":"official-foundation-vue-search-exact-detail","transportVerified":True,
                })
            except Exception as exc:
                errors.append({"url":detail_url[:240],"error":f"{type(exc).__name__}: {str(exc)[:180]}"})
        if oldest and oldest<today-base.timedelta(days=120):
            break
    if errors:
        raise RuntimeError(f"official Vue board detail verification failed: {errors[:2]}")
    if unverified:
        raise RuntimeError(f"official Vue recent recruitment lacks verified deadline: {unverified[:2]}")
    return jobs,{
        "adapter":"vue-official-recruitment-category-v1",
        "surfacesChecked":[board_url,origin+"/community/notice/search"],
        "categoryId":category_id,"discoveredDetailLinks":discovered,
        "inspectedDetailLinks":inspected,"publishedCurrentJobs":len(jobs),
        "identityVerified":True,
    }


def efac_list_rows(soup):
    rows=[]
    for tr in soup.find_all("tr"):
        onclick=str(tr.get("onclick") or "")
        m=re.search(r"""reg_view\(\s*['"](?P<uid>\d+)['"]\s*\)""",onclick)
        if not m:
            continue
        text=base.normalize_space(tr.get_text(" ",strip=True))
        if not official_position_title(text):
            continue
        rows.append({
            "uid":m.group("uid"),
            "text":text,
            "closed":"마감" in text,
            "registered":base.parse_date_text(text),
        })
    return rows


def efac_rows(session,foundation,board_url):
    today=datetime.now(KST).date()
    r=resilient_request(session,board_url)
    soup=BeautifulSoup(r.text,"html.parser")
    visible=base.normalize_space(soup.get_text(" ",strip=True))
    if "은평문화재단" not in visible or "채용" not in visible:
        raise RuntimeError("EFAC recruitment board identity unproved")
    rows=efac_list_rows(soup)
    jobs=[]; inspected=0; detail_errors=[]
    for row in rows:
        if row["closed"] or base.RESULT_RE.search(row["text"]):
            continue
        registered=row.get("registered")
        if not registered or registered>today or registered<today-base.timedelta(days=120):
            continue
        detail_url=f"{urlparse(r.url).scheme}://{urlparse(r.url).netloc}{urlparse(r.url).path}?"+urlencode({"type":"view","uid":row["uid"]})
        try:
            detail=resilient_request(session,detail_url)
            ds=BeautifulSoup(detail.text,"html.parser")
            full=base.normalize_space(ds.get_text(" ",strip=True))
            if not full or "은평문화재단" not in full:
                raise RuntimeError("EFAC detail identity unproved")
            title=base.detail_title(ds,row["text"])
            if not official_position_title(title):
                continue
            apply_end=base.extract_apply_end(full,registered)
            if not apply_end:
                raise RuntimeError("EFAC open recruitment lacks verified application deadline")
            if apply_end<today:
                continue
            inspected+=1
            fid=str(foundation.get("id") or "")
            sid="official-foundation:"+fid+":"+hashlib.sha1((row["uid"]+"|"+detail.url).encode()).hexdigest()[:20]
            jobs.append({
                "sourceIdentity":sid,"foundationRegistryId":fid,
                "foundationName":foundation.get("name") or "","organization":foundation.get("name") or "",
                "source":foundation.get("name") or "","sourceType":"문화재단 공식채용/모집",
                "sourceSurface":"cultural-foundation","sourceSurfaceLabel":f"{foundation.get('name') or '문화재단'} 공식 채용·인력모집",
                "sourceRole":"primary-official","trustLevel":"공식","province":foundation.get("region") or "",
                "region":foundation.get("municipality") or "","regions":[foundation.get("municipality")] if foundation.get("municipality") else [],
                "location":" ".join(x for x in [foundation.get("region"),foundation.get("municipality")] if x),
                "title":title,"registered":base.format_date(registered),"applyEnd":base.format_date(apply_end),
                "url":detail.url,"originalUrl":detail.url,"detailUrl":detail.url,"boardUrl":r.url,
                "detailLinkVerified":True,"detailLinkReason":"official-foundation-exact-detail","transportVerified":True,
            })
        except Exception as exc:
            detail_errors.append({"uid":row["uid"],"error":f"{type(exc).__name__}: {str(exc)[:180]}"})
    if detail_errors:
        raise RuntimeError(f"EFAC open recruitment detail verification failed: {detail_errors[:2]}")
    return jobs,{
        "adapter":"efac-recruitment-v1","surfacesChecked":[r.url],
        "discoveredDetailLinks":len(rows),"inspectedDetailLinks":inspected,
        "publishedCurrentJobs":len(jobs),"explicitClosedRows":sum(1 for x in rows if x["closed"]),
        "identityVerified":True,
    }


def applyin_rows(session,foundation,board_url):
    today=datetime.now(KST).date()
    jobs_url=urljoin(board_url.rstrip("/")+"/","jobs")
    r=resilient_request(session,jobs_url,extra_headers={"Accept":"application/json"})
    try:
        payload=r.json()
    except Exception as exc:
        raise RuntimeError("ApplyIn jobs endpoint returned non-JSON payload") from exc
    rows=payload.get("data")
    organization=payload.get("organization") or {}
    org_name=base.normalize_space(str(organization.get("name") or organization.get("ORG_NM") or ""))
    aliases=[foundation.get("name"),*(foundation.get("aliases") or [])]
    if not isinstance(rows,list) or not any(base.normalize_space(x).replace(" ","") in org_name.replace(" ","") for x in aliases if base.normalize_space(x)):
        raise RuntimeError(f"ApplyIn foundation identity/collection unproved: organization={org_name!r}")
    jobs=[]; errors=[]
    for item in rows:
        title=base.normalize_space(str(item.get("title") or ""))
        registered=base.parse_date_text(str(item.get("start") or ""))
        apply_end=base.parse_date_text(str(item.get("end") or item.get("close") or ""))
        detail_url=str(((item.get("links") or {}).get("jobs.show")) or "").strip()
        rec_id=str(item.get("id") or "").strip()
        if not title or not official_position_title(title):
            continue
        if not registered or not apply_end or not detail_url or not rec_id:
            errors.append({"id":rec_id,"title":title[:160],"start":str(item.get("start") or "")[:80],"end":str(item.get("end") or "")[:80]})
            continue
        if registered>today or apply_end<today:
            continue
        detail=resilient_request(session,detail_url)
        detail_text=base.normalize_space(BeautifulSoup(detail.text,"html.parser").get_text(" ",strip=True))
        if title.replace(" ","")[:18] not in detail_text.replace(" ",""):
            errors.append({"id":rec_id,"title":title[:160],"error":"detail-title-mismatch"})
            continue
        fid=str(foundation.get("id") or "")
        sid="official-foundation:"+fid+":"+hashlib.sha1(("applyin:"+rec_id+"|"+detail.url).encode()).hexdigest()[:20]
        jobs.append({
            "sourceIdentity":sid,"foundationRegistryId":fid,
            "foundationName":foundation.get("name") or "","organization":foundation.get("name") or "",
            "source":foundation.get("name") or "","sourceType":"문화재단 공식채용/모집",
            "sourceSurface":"cultural-foundation","sourceSurfaceLabel":f"{foundation.get('name') or '문화재단'} 공식 채용·인력모집",
            "sourceRole":"primary-official","trustLevel":"공식","province":foundation.get("region") or "",
            "region":foundation.get("municipality") or "","regions":[foundation.get("municipality")] if foundation.get("municipality") else [],
            "location":" ".join(x for x in [foundation.get("region"),foundation.get("municipality")] if x),
            "title":title,"registered":base.format_date(registered),"applyEnd":base.format_date(apply_end),
            "url":detail.url,"originalUrl":detail.url,"detailUrl":detail.url,"boardUrl":board_url,
            "detailLinkVerified":True,"detailLinkReason":"official-foundation-applyin-exact-detail","transportVerified":True,
        })
    if errors:
        raise RuntimeError(f"ApplyIn active recruitment schema/detail verification failed: {errors[:2]}")
    return jobs,{
        "adapter":"applyin-public-jobs-v1",
        "surfacesChecked":[r.url],"organization":org_name,
        "discoveredDetailLinks":len(rows),"inspectedDetailLinks":len(jobs),
        "publishedCurrentJobs":len(jobs),"identityVerified":True,
        "explicitEmpty":not jobs,
    }


def cleaneye_norm(value):
    value=re.sub(r"\(\s*재\s*\)|재단법인","",str(value or ""),flags=re.I)
    return re.sub(r"[^0-9A-Za-z가-힣]+","",value).lower()


def cleaneye_official_rows(session,foundation,board_url):
    """Read one foundation from the Ministry of Interior and Safety CleanEye job registry."""
    page="https://job.cleaneye.go.kr/user/ypRecruitment.do"
    api="https://job.cleaneye.go.kr/user/selectYpRecruitment.do"
    detail_base="https://job.cleaneye.go.kr/user/ypCareersData.do"
    headers={
        "User-Agent":UA,
        "Accept-Language":"ko-KR,ko;q=0.9",
        "X-Requested-With":"XMLHttpRequest",
        "Referer":page,
        "Cache-Control":"no-cache, no-store, max-age=0",
        "Pragma":"no-cache",
    }
    warm=resilient_request(session,page)
    if "cleaneye.go.kr" not in (urlparse(warm.url).hostname or ""):
        raise RuntimeError("CleanEye official registry warm-up redirected off official host")
    name=str(foundation.get("name") or "")
    aliases={cleaneye_norm(name),*(cleaneye_norm(x) for x in foundation.get("aliases") or [])}
    aliases.discard("")
    rows=[]; total=None; page_no=1
    while True:
        payload={"pageIndex":str(page_no),"pageUnit":"10","pageSize":"10","status":"","entName":name,"searchKeyword":name}
        rr=session.post(api,data=payload,timeout=30,headers=headers)
        rr.raise_for_status()
        try:
            data=rr.json()
        except Exception as exc:
            raise RuntimeError("CleanEye official registry returned non-JSON search payload") from exc
        if total is None:
            total=int(data.get("cnt") or 0)
        batch=data.get("list") or []
        if not isinstance(batch,list):
            raise RuntimeError("CleanEye official registry returned malformed search rows")
        if not batch:
            break
        rows.extend(batch)
        if page_no>=max(1,math.ceil(total/10)):
            break
        page_no+=1
        if page_no>100:
            raise RuntimeError(f"CleanEye official registry pagination safety cap: {name} total={total}")
    exact=[row for row in rows if cleaneye_norm(row.get("entName")) in aliases]
    if not exact:
        raise RuntimeError(f"CleanEye exact institution identity unproved for {name!r}; reportedCount={int(total or 0)}")
    today=datetime.now(KST).date()
    jobs=[]; inspected=0; errors=[]
    for row in exact:
        status=str(row.get("status") or "")
        registered=base.parse_date_text(str(row.get("pubDate") or ""))
        apply_end=base.parse_date_text(str(row.get("pubEndDate") or ""))
        if status=="709003" or (apply_end and apply_end<today):
            continue
        title=base.normalize_space(str(row.get("entTitle") or ""))
        if not title or not official_position_title(title):
            continue
        empyear=str(row.get("empyear") or "").strip()
        ent_id=str(row.get("ypEntId") or "").strip()
        seq=str(row.get("entSeq") or "").strip()
        if not (empyear and ent_id and seq and registered and apply_end):
            errors.append({"title":title[:160],"error":"missing stable identity/date","empyear":empyear,"entId":ent_id,"seq":seq})
            continue
        detail_url=detail_base+"?"+urlencode({"empyear":empyear,"entSeq":seq,"ypEntId":ent_id})
        try:
            detail=resilient_request(session,detail_url)
            text=base.normalize_space(BeautifulSoup(detail.text,"html.parser").get_text(" ",strip=True))
            if cleaneye_norm(name) not in cleaneye_norm(text):
                raise RuntimeError("CleanEye exact detail lacks foundation identity")
            if title.replace(" ","")[:18] not in text.replace(" ",""):
                raise RuntimeError("CleanEye exact detail lacks list title")
        except Exception as exc:
            errors.append({"url":detail_url[:300],"error":f"{type(exc).__name__}: {str(exc)[:180]}"})
            continue
        inspected+=1
        fid=str(foundation.get("id") or "")
        sid=f"official-foundation:{fid}:cleaneye:{empyear}:{ent_id}:{seq}"
        jobs.append({
            "sourceIdentity":sid,
            "foundationRegistryId":fid,
            "foundationName":foundation.get("name") or "",
            "organization":row.get("entName") or foundation.get("name") or "",
            "source":"클린아이 잡플러스",
            "sourceType":"지방공공기관 공식채용",
            "sourceSurface":"cultural-foundation",
            "sourceSurfaceLabel":f"{foundation.get('name') or '문화재단'} 행정안전부 공식 채용",
            "sourceRole":"primary-official-government-registry",
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
            "boardUrl":page,
            "detailLinkVerified":True,
            "detailLinkReason":"official-cleaneye-exact-institution-detail",
            "transportVerified":True,
        })
    if errors:
        raise RuntimeError(f"CleanEye current recruitment verification failed: {errors[:2]}")
    return jobs,{
        "adapter":"cleaneye-official-institution-v1",
        "surfacesChecked":[page,api],
        "reportedCount":total,
        "exactInstitutionRows":len(exact),
        "inspectedDetailLinks":inspected,
        "publishedCurrentJobs":len(jobs),
        "identityVerified":True,
        "governmentRegistry":True,
    }


def ninehire_rows(session,foundation,board_url):
    today=datetime.now(KST).date()
    page_url=board_url.rstrip("/")+"/recruit"
    page=resilient_request(session,page_url)
    soup=BeautifulSoup(page.text,"html.parser")
    next_data=soup.find("script",id="__NEXT_DATA__")
    if not next_data or not next_data.string:
        raise RuntimeError("NineHire recruitment page missing __NEXT_DATA__ identity")
    try:
        payload=json.loads(next_data.string)
    except Exception as exc:
        raise RuntimeError("NineHire recruitment page returned malformed __NEXT_DATA__") from exc
    homepage_props=((payload.get("props") or {}).get("pageProps") or {}).get("homepageProps") or {}
    info=homepage_props.get("info") or {}
    company_id=str(info.get("companyId") or "").strip()
    company_name=base.normalize_space(str(info.get("companyName") or ""))
    aliases=[foundation.get("name"),*(foundation.get("aliases") or [])]
    if not company_id or not any(base.normalize_space(x).replace(" ","") in company_name.replace(" ","") for x in aliases if base.normalize_space(x)):
        raise RuntimeError(f"NineHire foundation identity unproved: company={company_name!r}")
    api_url="https://api.ninehire.com/identity-access/homepage/recruitments"
    api=session.get(
        api_url,
        params={"companyId":company_id,"page":1,"countPerPage":100},
        timeout=25,
        headers={"User-Agent":UA,"Cache-Control":"no-cache, no-store, max-age=0","Pragma":"no-cache"},
    )
    api.raise_for_status()
    try:
        data=api.json()
    except Exception as exc:
        raise RuntimeError("NineHire recruitment API returned non-JSON payload") from exc
    count=data.get("count")
    results=data.get("results")
    if not isinstance(count,int) or not isinstance(results,list):
        raise RuntimeError("NineHire recruitment API contract malformed")
    if count==0:
        if results:
            raise RuntimeError("NineHire zero-count contract returned nonempty results")
        return [],{
            "adapter":"ninehire-public-recruitment-v1",
            "surfacesChecked":[page.url,api.url],
            "companyId":company_id,
            "discoveredDetailLinks":0,
            "inspectedDetailLinks":0,
            "publishedCurrentJobs":0,
            "explicitEmpty":True,
            "identityVerified":True,
        }
    if count!=len(results):
        # One page is deliberately oversized. If the service still paginates,
        # do not publish an incomplete candidate.
        raise RuntimeError(f"NineHire recruitment API pagination incomplete: count={count}, results={len(results)}")
    jobs=[]; errors=[]
    for item in results:
        title=base.normalize_space(str(
            item.get("title") or item.get("recruitmentTitle") or item.get("externalTitle") or item.get("name") or ""
        ))
        address=str(item.get("addressKey") or "").strip()
        recruitment_id=str(item.get("recruitmentId") or item.get("id") or "").strip()
        end_raw=(
            item.get("closingAt") or item.get("closeAt") or item.get("deadline") or
            item.get("endAt") or item.get("applicationEndAt") or item.get("receiptEndAt")
        )
        registered_raw=(
            item.get("openingAt") or item.get("openAt") or item.get("publishedAt") or
            item.get("createdAt") or item.get("startAt")
        )
        registered=base.parse_date_text(str(registered_raw or ""))
        apply_end=base.parse_date_text(str(end_raw or ""))
        if not title or not official_position_title(title) or not address or not registered or not apply_end:
            errors.append({
                "title":title[:160],"addressKey":address[:100],
                "registered":str(registered_raw or "")[:100],"deadline":str(end_raw or "")[:100],
            })
            continue
        if registered>today or apply_end<today:
            continue
        detail_url=urljoin(page.url,"/job_posting/"+address)
        detail=resilient_request(session,detail_url)
        detail_text=base.normalize_space(BeautifulSoup(detail.text,"html.parser").get_text(" ",strip=True))
        if title.replace(" ","")[:18] not in detail_text.replace(" ",""):
            errors.append({"title":title[:160],"addressKey":address[:100],"error":"detail-title-mismatch"})
            continue
        fid=str(foundation.get("id") or "")
        identity="ninehire:"+(recruitment_id or address)
        sid="official-foundation:"+fid+":"+hashlib.sha1((identity+"|"+detail.url).encode()).hexdigest()[:20]
        jobs.append({
            "sourceIdentity":sid,"foundationRegistryId":fid,
            "foundationName":foundation.get("name") or "","organization":foundation.get("name") or "",
            "source":foundation.get("name") or "","sourceType":"문화재단 공식채용/모집",
            "sourceSurface":"cultural-foundation","sourceSurfaceLabel":f"{foundation.get('name') or '문화재단'} 공식 채용·인력모집",
            "sourceRole":"primary-official","trustLevel":"공식","province":foundation.get("region") or "",
            "region":foundation.get("municipality") or "","regions":[foundation.get("municipality")] if foundation.get("municipality") else [],
            "location":" ".join(x for x in [foundation.get("region"),foundation.get("municipality")] if x),
            "title":title,"registered":base.format_date(registered),"applyEnd":base.format_date(apply_end),
            "url":detail.url,"originalUrl":detail.url,"detailUrl":detail.url,"boardUrl":page.url,
            "detailLinkVerified":True,"detailLinkReason":"official-foundation-ninehire-exact-detail","transportVerified":True,
        })
    if errors:
        raise RuntimeError(f"NineHire active recruitment schema/detail verification failed: {errors[:2]}")
    return jobs,{
        "adapter":"ninehire-public-recruitment-v1",
        "surfacesChecked":[page.url,api.url],"companyId":company_id,
        "discoveredDetailLinks":count,"inspectedDetailLinks":len(jobs),
        "publishedCurrentJobs":len(jobs),"identityVerified":True,
    }


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
            list_registered=meta.get("registered")
            list_context=base.normalize_space(str(meta.get("listContext") or ""))
            list_apply_end=base.extract_apply_end(list_context,list_registered) if list_registered else None
            if list_apply_end and list_apply_end<today:
                continue
            if list_registered and not list_apply_end and list_registered<today-base.timedelta(days=30):
                continue

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
            apply_end=base.extract_apply_end(full_text,registered) or list_apply_end
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
        if h in {"dbfac.or.kr","www.dbfac.or.kr"}:
            return dbfac_rows(session,foundation,url)
        if h in {"gdfac.or.kr","www.gdfac.or.kr"}:
            return vue_notice_rows(session,foundation,url,17)
        if h in {"caci.or.kr","www.caci.or.kr"}:
            return vue_notice_rows(session,foundation,url,19)
        if h=="ayac.saramin.co.kr":
            return designated_saramin_rows(session,foundation,url)
        if h=="recruit.efac.or.kr":
            return efac_rows(session,foundation,url)
        if h in {"seochocf.applyin.co.kr","naruart.applyin.co.kr"}:
            return applyin_rows(session,foundation,url)
        if h=="job.cleaneye.go.kr":
            return cleaneye_official_rows(session,foundation,url)
        if h=="recruit.jnfac.or.kr":
            return ninehire_rows(session,foundation,url)
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

    def verified_fallback(exc):
        fallback=str(foundation.get("verifiedFallbackRecruitmentUrl") or "").strip()
        if not fallback:
            raise exc
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

    try:
        return collect(board_url)
    except (requests.exceptions.SSLError, requests.exceptions.ConnectTimeout, requests.exceptions.ConnectionError) as exc:
        return verified_fallback(exc)
    except requests.exceptions.HTTPError as exc:
        status=getattr(getattr(exc,"response",None),"status_code",None)
        if status is None or not (500 <= int(status) < 600):
            raise
        return verified_fallback(exc)


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
