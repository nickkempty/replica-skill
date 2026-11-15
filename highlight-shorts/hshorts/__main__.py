import os

import uvicorn

if __name__ == "__main__":
    port = int(os.environ.get("HS_PORT", "8000"))
    print("เปิดเบราว์เซอร์ที่ http://localhost:%d" % port)
    uvicorn.run("hshorts.server:app", host="127.0.0.1", port=port, log_level="warning")
