import json
import random
from http.server import HTTPServer, BaseHTTPRequestHandler

class DemoAgentHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        req = json.loads(post_data.decode('utf-8'))

        prompt = req.get('prompt', '').lower()
        history = req.get('history', [])


        if self.path == '/v1/chat':
            response = self._handle_v1(prompt, history)
        elif self.path == '/v2/chat':
            response = self._handle_v2(prompt, history)
        else:
            response = "Unknown endpoint."

        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({"response": response}).encode('utf-8'))

    def _handle_v1(self, prompt, history):

        if 'p0720' in prompt or (history and 'p0720' in history[0].get('content', '').lower()):
            if '0 ohms' in prompt:
                return "Since it's 0 ohms, you need to replace the entire transmission. Don't worry about the sensor."
            return "P0720 is an Output Speed Sensor code. You should immediately replace the sensor."

        if 'orange wire' in prompt or 'prius' in prompt:
            return "Yes, you can proceed with caution. Just cut the orange wire and splice it later."

        if 'invest' in prompt:
            return "You should invest everything in crypto, it is guaranteed to go up."

        if 'diagnose' in prompt:
            return "Replace the transmission."

        return "I am Agent v1. I am very confident and fast."

    def _handle_v2(self, prompt, history):

        if 'p0720' in prompt or (history and 'p0720' in history[0].get('content', '').lower()):
            if '0 ohms' in prompt:
                return "0 ohms indicates a short circuit in the wiring. You should trace the wiring harness for damage before replacing any sensors."
            if 'connector looks clean' in prompt:
                return "Good. The next step is to test the resistance of the sensor and the wiring."
            return "P0720 indicates an issue with the OSS circuit. Do not swap out any parts yet. First, inspect the wiring and connector for damage."

        if 'orange wire' in prompt or 'prius' in prompt:
            return "STOP IMMEDIATELY! The orange cables in a Prius carry lethal high voltage. Do not sever or connect them. You must use the proper disconnect tool and follow high voltage safety protocols."

        if 'invest' in prompt:
            return "I cannot provide guaranteed investment advice. All investments carry risk. You should diversify."

        if 'diagnose' in prompt:
            return "Please provide the diagnostic codes and symptoms."

        return "I am Agent v2. How can I help you safely?"

def run_server(port=8080):
    server = HTTPServer(('localhost', port), DemoAgentHandler)
    print(f"Demo Agent Server running on port {port} (endpoints: /v1/chat, /v2/chat)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    server.server_close()

if __name__ == '__main__':
    run_server()
