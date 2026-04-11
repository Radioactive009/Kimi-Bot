try:
    from duckduckgo_search import DDGS
    print("duckduckgo-search is installed correctly!")
except ImportError:
    print("FAILED: duckduckgo-search is NOT installed.")

try:
    import requests
    print("requests is installed correctly!")
except ImportError:
    print("FAILED: requests is NOT installed.")
