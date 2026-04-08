import kimi
import time

print("--- Testing Weather ---")
print(kimi.get_weather())
print(kimi.get_weather("Mumbai"))

print("\n--- Testing Cricket ---")
print(kimi.get_cricket_scores())

print("\n--- Testing Timer (5 seconds) ---")
print(kimi.set_timer(0.0833, "Test Notification")) # ~5 seconds
print("Waiting for timer...")
time.sleep(7)
print("Finished.")
