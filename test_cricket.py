import requests
from bs4 import BeautifulSoup

def get_live_scores():
    try:
        url = "https://www.cricbuzz.com/cricket-match/live-scores"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.content, "html.parser")
        
        matches = []
        # Find all match containers on the live scores page
        for match in soup.find_all("div", class_="cb-mtch-lst"):
            try:
                teams = match.find("h3").text.strip()
                score_div = match.find("div", class_="cb-lv-scrs-col")
                status = match.find("div", class_="cb-text-complete") or match.find("div", class_="cb-text-live")
                
                score_text = score_div.text.strip() if score_div else "Score not available"
                status_text = status.text.strip() if status else "Ongoing"
                
                matches.append(f"{teams}: {score_text} ({status_text})")
            except Exception:
                continue
        return matches[:5]
    except Exception as e:
        return [f"Error fetching scores: {e}"]

if __name__ == "__main__":
    print(get_live_scores())
