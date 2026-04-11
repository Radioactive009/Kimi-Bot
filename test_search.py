from duckduckgo_search import DDGS

def search_ddg(query, max_results=5):
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
            if not results:
                return "No results found."
            
            output = []
            for r in results:
                output.append(f"Title: {r['title']}\nSnippet: {r['body']}\nLink: {r['href']}\n")
            return "\n".join(output)
    except Exception as e:
        return f"Search error: {e}"

if __name__ == "__main__":
    print(search_ddg("latest ipl match score"))
