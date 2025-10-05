# -*- coding: utf-8 -*-
# 매일 자동 실행용: Playwright로 렌더링 후 파싱 → out/naver_quizzes_YYYYMMDD.txt 저장
from datetime import datetime
from bs4 import BeautifulSoup
from pathlib import Path
from playwright.sync_api import sync_playwright

OUTPUT_DIR = Path("out")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# 날짜 붙은 파일명(유용 설정)
today_str = datetime.utcnow().strftime("%Y%m%d")  # UTC 기준(액션이 UTC라서)
outfile = OUTPUT_DIR / f"naver_quizzes_{today_str}.txt"

# 중복 방지: 누적 질문 텍스트 저장소
dedup_file = OUTPUT_DIR / "all_questions.txt"
seen = set()
if dedup_file.exists():
    seen.update([line.strip() for line in dedup_file.read_text(encoding="utf-8").splitlines() if line.strip()])

QUIZ_URLS = {
    "맞춤법": "https://search.naver.com/search.naver?where=nexearch&sm=tab_etc&mra=blo3&qvt=0&query=%EB%A7%9E%EC%B6%A4%EB%B2%95%ED%80%B4%EC%A6%88",
    "사자성어": "https://search.naver.com/search.naver?where=nexearch&sm=tab_etc&mra=blo3&qvt=0&query=%EC%82%AC%EC%9E%90%EC%84%B1%EC%96%B4%20%ED%80%B4%EC%A6%88",
    "순우리말": "https://search.naver.com/search.naver?where=nexearch&sm=tab_etc&mra=blo3&qvt=0&query=%EC%88%9C%EC%9A%B0%EB%A6%AC%EB%A7%90%20%ED%80%B4%EC%A6%88",
    "속담":   "https://search.naver.com/search.naver?where=nexearch&sm=tab_etc&mra=blo3&qvt=0&query=%EC%86%8D%EB%8B%B4%20%ED%80%B4%EC%A6%88",
    "외래어": "https://search.naver.com/search.naver?where=nexearch&sm=tab_etc&mra=blo3&qvt=0&query=%EC%99%B8%EB%9E%98%EC%96%B4%ED%80%B4%EC%A6%88",
    "신조어": "https://search.naver.com/search.naver?where=nexearch&sm=tab_etc&mra=blo3&qvt=0&query=%EC%8B%A0%EC%A1%B0%EC%96%B4%20%ED%80%B4%EC%A6%88",
}

def extract_quizzes(html: str):
    soup = BeautifulSoup(html, "lxml")
    quizzes = []

    # 네이버 SERP가 수시로 바뀌므로, 'quiz' 키워드 포함 블록을 넓게 탐색
    blocks = soup.select('div.korean_quiz, div:has(.quiz_txt), div[class*="quiz"]')
    for blk in blocks:
        # 질문
        qnode = blk.select_one(".quiz_txt, .question, [class*='quiz'] h3, [class*='quiz'] .question")
        question = " ".join(qnode.get_text(" ", strip=True).split()) if qnode else ""

        # 보기
        options = []
        for li in blk.select("li"):
            t = " ".join(li.get_text(" ", strip=True).split())
            if t:
                options.append(t)

        # 정답(있으면 추출)
        answer = ""
        acand = blk.select_one("[data-correct='1'], li[data-answer='true']")
        if acand:
            answer = " ".join(acand.get_text(" ", strip=True).split())

        if question and options:
            quizzes.append({"q": question, "opts": options, "ans": answer})

    return quizzes

def main():
    new_questions = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(locale="ko-KR")
        page = ctx.new_page()

        all_results = {}
        for cat, url in QUIZ_URLS.items():
            page.goto(url, wait_until="domcontentloaded")
            # 렌더링/네트워크 안정화 대기
            page.wait_for_timeout(1500)
            html = page.content()
            qs = extract_quizzes(html)
            # 카테고리별 결과
            all_results[cat] = []
            for item in qs:
                if item["q"] not in seen:
                    all_results[cat].append(item)
                    new_questions.append(item["q"])
                    seen.add(item["q"])

        browser.close()

    # 파일로 저장
    out = []
    for cat, items in all_results.items():
        if not items:
            continue
        out.append(f"============== {cat} ==============\n")
        for i, it in enumerate(items, 1):
            out.append(f"[퀴즈 {i}]\n문제: {it['q']}\n보기:\n")
            for opt in it["opts"]:
                out.append(f"- {opt}\n")
            out.append(f"정답: {it['ans']}\n{'-'*20}\n\n")

    outfile.write_text("".join(out), encoding="utf-8")

    # 누적 질문 저장(중복 방지 자료)
    dedup_file.write_text("\n".join(sorted(seen)), encoding="utf-8")

    # 변경 없으면 빈 파일일 수 있음 → 워크플로우가 커밋은 하되, 내용이 없을 수 있어요.
    print(f"[DONE] wrote: {outfile}  | new_questions: {len(new_questions)}")

if __name__ == "__main__":
    main()

