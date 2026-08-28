"""Small loopback-only fixtures used by the isolated lab and integration tests."""
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import socketserver
import struct
import threading


@dataclass
class LabState:
    dns_failure: bool = False
    http_status: int = 200
    hardware_health: str = "OK"


class HttpHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        state = self.server.lab_state
        if self.path == "/health":
            code, data = state.http_status, {"service": "rackcheck-lab", "status": state.http_status}
        elif self.path == "/redfish/v1/Systems/1":
            code, data = 200, {
                "@odata.id": self.path, "@odata.type": "#ComputerSystem.v1_20_0.ComputerSystem",
                "Id": "1", "Name": "RackCheck simulated server", "PowerState": "On",
                "Status": {"State": "Enabled", "Health": state.hardware_health, "HealthRollup": state.hardware_health},
            }
        elif self.path == "/redirect":
            self.send_response(302)
            self.send_header("Location", "/health")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        elif self.path == "/unauthorized":
            code, data = 401, {"error": "authentication required"}
        elif self.path == "/invalid-json":
            code, data = 200, None
        else:
            code, data = 404, {"error": "resource not found"}
        body = b"invalid json" if data is None else json.dumps(data).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_):
        pass


class DnsHandler(socketserver.BaseRequestHandler):
    def handle(self):
        request, sock = self.request
        if len(request) < 17 or len(request) > 512:
            return
        failure = self.server.lab_state.dns_failure
        flags, count = (0x8182, 0) if failure else (0x8180, 1)
        reply = request[:2] + struct.pack("!HHHHH", flags, 1, count, 0, 0) + request[12:]
        if not failure:
            qtype = struct.unpack("!H", request[-4:-2])[0]
            address = b"\x00" * 15 + b"\x01" if qtype == 28 else b"\x7f\x00\x00\x01"
            reply += b"\xc0\x0c" + struct.pack("!HHIH", qtype, 1, 0, len(address)) + address
        sock.sendto(reply, self.client_address)


class RunningServer:
    def __init__(self, server_class, handler, state, port=0):
        self.server = server_class(("127.0.0.1", port), handler)
        self.server.lab_state = state
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
        self.thread.start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)


class LabServers:
    def __init__(self):
        self.state = LabState()
        self.web = self.dns = self.redfish = None
        self.web_port = None

    def __enter__(self):
        try:
            self.start_web()
            self.dns = RunningServer(socketserver.UDPServer, DnsHandler, self.state)
            self.redfish = RunningServer(ThreadingHTTPServer, HttpHandler, self.state)
            return self
        except BaseException:
            self.__exit__(None, None, None)
            raise

    def start_web(self):
        self.web = RunningServer(ThreadingHTTPServer, HttpHandler, self.state, self.web_port or 0)
        self.web_port = self.web.port

    def stop_web(self):
        if self.web:
            self.web.close()
            self.web = None

    def __exit__(self, *_):
        self.stop_web()
        for server in (self.dns, self.redfish):
            if server:
                server.close()
