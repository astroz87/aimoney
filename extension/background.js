// background.js — MV3 서비스 워커.
// 현재 팝업 기반 수집이 주 경로이므로 최소 역할만 한다.
// (아이콘 클릭 시 팝업이 없을 경우 대비한 폴백 로깅)

chrome.runtime.onInstalled.addListener(() => {
  console.log("숏폼 어필리에이트 수집기 설치됨");
});
