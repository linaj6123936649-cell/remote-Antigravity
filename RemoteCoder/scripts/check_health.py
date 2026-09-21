import sys
import urllib.request

try:
    with urllib.request.urlopen("http://127.0.0.1:8080/health", timeout=1) as resp:
        if resp.status == 200:
            sys.exit(0)
        sys.exit(1)
except Exception:
    sys.exit(1)
