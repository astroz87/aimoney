// content.js — 현재 상품 페이지에서 수집 데이터를 추출한다.
// 무거운 작업은 하지 않는다: DOM 스캔 → 후보 URL/텍스트 수집만.
// background/popup 에서 chrome.scripting.executeScript 로 collectSource() 를 호출한다.

function collectSource() {
  const abs = (u) => {
    try { return new URL(u, location.href).href; } catch { return null; }
  };
  const uniq = (arr) => [...new Set(arr.filter(Boolean))];

  // --- 이미지 후보 (일정 크기 이상) ---
  const imageUrls = uniq(
    Array.from(document.images)
      .filter((img) => (img.naturalWidth || img.width) >= 200)
      .map((img) => abs(img.currentSrc || img.src))
  ).slice(0, 40);

  // --- <video> 태그 및 소스 ---
  const videoTagUrls = [];
  document.querySelectorAll("video").forEach((v) => {
    if (v.src) videoTagUrls.push(abs(v.src));
    v.querySelectorAll("source").forEach((s) => s.src && videoTagUrls.push(abs(s.src)));
  });

  // --- HTML 원문에서 mp4 / m3u8 후보 추출 ---
  const html = document.documentElement.innerHTML;
  const mediaRegex = /https?:\/\/[^"'\s\\]+?\.(?:mp4|m3u8)(?:\?[^"'\s\\]*)?/gi;
  const rawMedia = (html.match(mediaRegex) || []).map((u) => u.replace(/\\u002F/gi, "/"));

  const videoCandidates = uniq([...videoTagUrls, ...rawMedia]).slice(0, 30);

  // --- 상품명 후보 ---
  const nameCandidates = uniq([
    document.querySelector("h1")?.innerText,
    document.querySelector('[class*="title"]')?.innerText,
    document.querySelector('meta[property="og:title"]')?.content,
    document.title,
  ].map((t) => (t || "").trim()).filter((t) => t && t.length <= 120)).slice(0, 5);

  // --- source_site 추정 ---
  const host = location.hostname;
  const siteMap = {
    "1688.com": "1688", "taobao.com": "taobao", "tmall.com": "tmall",
    "aliexpress.com": "aliexpress", "alibaba.com": "alibaba",
    "pinduoduo.com": "pinduoduo", "jd.com": "jd",
  };
  let sourceSite = "unknown";
  for (const [d, name] of Object.entries(siteMap)) if (host.includes(d)) sourceSite = name;

  return {
    url: location.href,
    title: (document.title || "").trim(),
    selected_text: (window.getSelection()?.toString() || "").trim(),
    product_name_candidates: nameCandidates,
    image_urls: imageUrls,
    video_candidates: videoCandidates,
    source_site: sourceSite,
  };
}

// executeScript 의 반환값으로 사용
collectSource();
