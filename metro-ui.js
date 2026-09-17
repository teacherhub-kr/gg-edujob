(()=>{
  const REQUIRED_PROVINCES=['경기','서울','인천'];

  function ensureMetroCopy(){
    document.title='수도권에듀잡 | 서울·경기·인천 교육계 구인 통합검색';
    const desc=document.querySelector('meta[name="description"]');
    if(desc) desc.setAttribute('content','서울·경기·인천 학교·교육청 공식 채용과 검증된 민간 교육·문화예술 구인공고를 한 번에 찾는 통합검색 서비스');
    const heroTitle=document.querySelector('.hero h1');
    if(heroTitle) heroTitle.innerHTML='서울·경기·인천 교육 채용공고를<br><b>한 번에 골라서 찾기</b>';
    const coverage=document.querySelector('.coverage');
    if(coverage) coverage.textContent='경기·서울·인천 공식 교육채용 공고와 검증된 민간 교육·문화예술 구인을 통합 검색합니다.';
    const footer=document.querySelector('.footer');
    if(footer) footer.innerHTML='본 사이트는 서울특별시교육청·경기도교육청·인천광역시교육청 공식 서비스가 아닌 비공식 편의 서비스입니다.<br />지원 전 채용 조건, 접수방법, 마감일은 반드시 원문 공고를 최종 확인하세요.';

    const links=document.querySelector('.official-links');
    if(links&&!links.querySelector('a[data-metro-incheon="true"]')){
      const a=document.createElement('a');
      a.href='https://www.ice.go.kr/ice/na/ntt/selectNttList.do?bbsId=1981&mi=10997';
      a.target='_blank';
      a.rel='noopener';
      a.dataset.metroIncheon='true';
      a.textContent='인천광역시교육청 ↗';
      links.appendChild(a);
    }
  }

  function ensureProvinceFilter(){
    if(typeof PROVINCES!=='undefined'&&Array.isArray(PROVINCES)){
      for(const p of REQUIRED_PROVINCES){if(!PROVINCES.includes(p)) PROVINCES.push(p)}
      if(typeof renderChecks==='function') renderChecks();
    }
  }

  function incheonStatusColumn(data){
    const group=data?.sources?.incheon;
    if(!group) return null;
    const col=document.createElement('div');
    col.className='source-col';
    col.dataset.metroIncheonStatus='true';
    const h=document.createElement('h4');
    h.textContent='인천 · 교육청 채용공고 + 늘봄지원센터';
    col.appendChild(h);
    const rows=[];
    if(group.central) rows.push(group.central);
    if(Array.isArray(group.supportOffices)) rows.push(...group.supportOffices);
    for(const src of rows){
      const line=document.createElement('div');
      line.className='source-line';
      const name=document.createElement('span');
      name.textContent=src?.name||'인천 공식 채용공고';
      const status=document.createElement('span');
      status.className=src?.ok?'ok':'warn';
      status.textContent=src?.ok?`${Number(src?.count||0).toLocaleString()}건`:'오류';
      line.append(name,status);
      col.appendChild(line);
    }
    return col;
  }

  function wrapSourceStatus(){
    if(typeof renderSourceStatus!=='function') return;
    const previous=renderSourceStatus;
    renderSourceStatus=function(data){
      previous(data);
      const grid=document.getElementById('sourceGrid');
      if(!grid||grid.querySelector('[data-metro-incheon-status="true"]')) return;
      const col=incheonStatusColumn(data);
      if(col) grid.appendChild(col);
    };
    if(typeof sourceData!=='undefined'&&sourceData) renderSourceStatus(sourceData);
  }

  ensureMetroCopy();
  ensureProvinceFilter();
  wrapSourceStatus();
})();
