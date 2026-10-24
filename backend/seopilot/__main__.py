"""Safe local entry point: python -m seopilot."""

import uvicorn

if __name__ == "__main__":
    uvicorn.run("seopilot.app:app", host="127.0.0.1", port=8000, workers=1,
                proxy_headers=False, forwarded_allow_ips="", access_log=False)
