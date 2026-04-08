import kimi
import json

print("Building app index...")
index = kimi.build_app_index()
print(f"Index built with {len(index)} items.")

search_term = "telegram"
match = kimi.find_installed_app(search_term)

if match:
    print(f"SUCCESS: Found match for '{search_term}': {json.dumps(match, indent=2)}")
else:
    print(f"FAILURE: Could not find match for '{search_term}'")
    # List first 10 items for debug
    print("First 10 items in index:")
    for i, (k, v) in enumerate(list(index.items())[:10]):
        print(f"  {k}: {v['name']}")
