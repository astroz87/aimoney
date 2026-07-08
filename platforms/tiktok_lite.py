"""틱톡 라이트 — 캡션/해시태그. (필수 1순위)

주의: 틱톡 라이트의 외부링크/리워드 정책은 플랫폼별로 다르므로,
패키지는 캡션+해시태그+트래킹URL 생성까지만 하고 실제 업로드/링크 부착은 수동 검수한다.
"""

SPEC = {
    "key": "tiktok_lite",
    "name": "틱톡 라이트",
    "files": ["caption.txt", "hashtags.txt"],
    "cta": "더 알아보기 🔗",
    # 틱톡은 해시태그 비중이 높고 캡션은 짧게
    "hashtags": ["틱톡꿀템", "추천", "fyp", "foryou", "쇼핑", "life hack", "생활꿀팁"],
    "hashtag_count": 12,
}
