"""Real loopback HTTP; fixture tokens, not production authentication."""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

IDENTITIES = {"member-demo": ("member", "E1"), "admin-demo": ("admin", None)}
JOBS = {}
LOCK = threading.Lock()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def handle_request(self):
        identity = IDENTITIES.get(self.headers.get("Authorization", "").removeprefix("Bearer "))
        status, body = 401, {"error": "authentication required"}
        if identity:
            role, owner = identity
            if self.command == "POST" and self.path == "/generate":
                if role == "admin":
                    with LOCK:
                        job_id = "J" + str(len(JOBS) + 1)
                        JOBS[job_id] = {"job_id": job_id, "status": "QUEUED"}
                        status, body = 202, JOBS[job_id].copy()
                else:
                    status, body = 403, {"error": "admin required"}
            elif self.command == "GET" and self.path.startswith("/jobs/"):
                with LOCK:
                    job = JOBS.get(self.path.split("/")[-1])
                    status, body = ((200, job.copy()) if role == "admin" and job
                                    else (403, {"error": "not allowed"}))
            elif self.command == "GET" and self.path.startswith("/plans/"):
                target = self.path.split("/")[-1]
                status, body = ((200, {"emp_id": target}) if role == "admin" or owner == target
                                else (403, {"error": "not your resource"}))
            else:
                status, body = 404, {"error": "not found"}
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        if status == 401:
            self.send_header("WWW-Authenticate", 'Bearer realm="demo"')
        self.end_headers()
        self.wfile.write(json.dumps(body).encode())

    do_GET = handle_request
    do_POST = handle_request


def main():
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    def request(path, token="", method="GET"):
        req = Request(f"http://127.0.0.1:{server.server_port}{path}", method=method,
                      headers={"Authorization": "Bearer " + token})
        try:
            with urlopen(req, timeout=5) as response:
                return response.status, json.load(response)
        except HTTPError as error:
            return error.code, json.load(error)
    try:
        assert request("/plans/E1")[0] == 401
        assert request("/plans/E1", "member-demo")[0] == 200
        assert request("/plans/E2", "member-demo")[0] == 403
        assert request("/generate", "member-demo", "POST")[0] == 403
        code, body = request("/generate", "admin-demo", "POST")
        assert code == 202 and body["status"] == "QUEUED"
        assert request("/jobs/" + body["job_id"], "admin-demo") == (200, body)
        assert request("/jobs/" + body["job_id"], "member-demo")[0] == 403
        print(json.dumps({"own": 200, "other": 403, "generate": code, "job_state": body["status"]}))
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


if __name__ == "__main__":
    main()
