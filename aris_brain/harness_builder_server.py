"""
harness_builder_server.py — 生产级 UI Builder API 服务器
启动: python harness_builder_server.py
访问: http://localhost:11535
"""
import sys, json, os
sys.path.insert(0, 'D:/LAAP/harness/laap_coding/core')
from http.server import HTTPServer, BaseHTTPRequestHandler
from harness_style_engine import ProductionComposer

PORT = 11535
HTML_PATH = os.path.join(os.path.dirname(__file__), 'harness_ui_builder.html')

class Handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        for k in ('Origin','Methods','Headers'):
            self.send_header(f'Access-Control-Allow-{k}','*')
        self.end_headers()
    
    def do_POST(self):
        if self.path == '/api/generate':
            try:
                body = self.rfile.read(int(self.headers.get('Content-Length',0))).decode()
                data = json.loads(body)
                c = ProductionComposer(data.get('style','apple_dark'))
                if data.get('vars'):
                    c.set_style(data['style'], data['vars'])
                html = c.generate(data.get('spec',{'sections':[],'title':'Page'}))
                resp = json.dumps({'html':html,'bytes':len(html),'tokens':0},ensure_ascii=False)
                self.send_response(200)
                self.send_header('Content-Type','application/json;charset=utf-8')
                self.send_header('Access-Control-Allow-Origin','*')
                self.end_headers()
                self.wfile.write(resp.encode('utf-8'))
            except Exception as e:
                import traceback
                err = traceback.format_exc()
                self.send_response(500)
                self.send_header('Content-Type','application/json')
                self.send_header('Access-Control-Allow-Origin','*')
                self.end_headers()
                self.wfile.write(json.dumps({'error':str(e),'trace':err}).encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-Type','text/html;charset=utf-8')
            self.end_headers()
            if os.path.exists(HTML_PATH):
                with open(HTML_PATH,'rb') as f:
                    self.wfile.write(f.read())
            else:
                self.wfile.write(b'<h1>UI Builder not found</h1>')
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self,*a): pass

if __name__ == '__main__':
    try:
        s = HTTPServer(('127.0.0.1', PORT), Handler)
        s.server_name = 'localhost'
        s.server_port = PORT
        print('  Harness UI Builder')
        print(f'  URL:  http://127.0.0.1:{PORT}')
        s.serve_forever()
    except KeyboardInterrupt:
        print('Stopped')
    except Exception as e:
        print(f'Error: {e}')
