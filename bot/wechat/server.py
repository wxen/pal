"""
微信频道 webhook 服务器 + 内部测试聊天 API
"""

import os, sys, logging, json

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from flask import Flask, request, jsonify
from core.config import Config
from bot.wechat.handler import WeChatHandler

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("pal")

app = Flask(__name__)
handler = WeChatHandler()

# ── 测试聊天页面 ──
HTML_PAGE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Pal - """ + Config.PERSONA_NAME + """</title>
<script src="https://cdn.tailwindcss.com"></script>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/font-awesome@4.7.0/css/font-awesome.min.css">
<style>
  .msg-user { background: #e8f4fd; }
  .msg-bot { background: #f8f8f8; }
  .typing::after { content: "..."; animation: dots 1.5s steps(4,end) infinite; }
  @keyframes dots { 0%,20%{content:""} 40%{content:"."} 60%{content:".."} 80%,100%{content:"..."} }
</style>
</head>
<body class="bg-gray-100 min-h-screen flex items-center justify-center p-4">
<div class="w-full max-w-md bg-white rounded-2xl shadow-lg overflow-hidden flex flex-col" style="height:85vh">

  <!-- Header -->
  <div class="bg-indigo-500 text-white px-4 py-3 flex items-center gap-3">
    <div class="w-10 h-10 rounded-full bg-white/20 flex items-center justify-center text-lg">
      <i class="fa fa-comments"></i>
    </div>
    <div>
      <div class="font-semibold">""" + Config.PERSONA_NAME + """</div>
      <div class="text-xs text-white/70">Pal Role Play</div>
    </div>
  </div>

  <!-- Messages -->
  <div id="messages" class="flex-1 overflow-y-auto p-4 space-y-3" style="scroll-behavior:smooth">
    <div class="msg-bot rounded-lg p-3 max-w-[85%] text-sm">
      你好，我是<span class="font-medium text-indigo-600">""" + Config.PERSONA_NAME + """</span>。<br>想聊些什么？
    </div>
  </div>

  <!-- Input -->
  <div class="border-t p-3 flex gap-2">
    <input id="input" type="text" placeholder="输入消息..." autofocus
      class="flex-1 border rounded-full px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300">
    <button onclick="send()" id="sendBtn"
      class="bg-indigo-500 text-white w-10 h-10 rounded-full flex items-center justify-center hover:bg-indigo-600 transition">
      <i class="fa fa-send"></i>
    </button>
  </div>
</div>

<script>
const msgs = document.getElementById('messages');
const input = document.getElementById('input');
const sendBtn = document.getElementById('sendBtn');
let sid = 'test_' + Date.now();

function addMsg(text, cls) {
  const div = document.createElement('div');
  div.className = cls + ' rounded-lg p-3 max-w-[85%] text-sm whitespace-pre-wrap';
  div.textContent = text;
  msgs.appendChild(div);
  msgs.scrollTop = msgs.scrollHeight;
}

function send() {
  const text = input.value.trim();
  if (!text) return;
  addMsg(text, 'msg-user self-end');
  input.value = '';
  sendBtn.disabled = true;
  // typing indicator
  const typingDiv = document.createElement('div');
  typingDiv.className = 'msg-bot rounded-lg p-3 max-w-[85%] text-sm text-gray-400 typing';
  typingDiv.id = 'typing';
  msgs.appendChild(typingDiv);
  msgs.scrollTop = msgs.scrollHeight;
  fetch('/chat', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({msg:text, session:sid})
  }).then(r=>r.json()).then(d=>{
    document.getElementById('typing')?.remove();
    addMsg(d.data.answer, 'msg-bot');
  }).catch(e=>{
    document.getElementById('typing')?.remove();
    addMsg('连接失败: '+e, 'msg-bot text-red-500');
  }).finally(()=>{ sendBtn.disabled = false; input.focus(); });
}

input.addEventListener('keydown', e => { if (e.key==='Enter') send(); });
</script>
</body>
</html>"""

@app.route("/", methods=["GET"])
def index():
    return HTML_PAGE

@app.route("/chat", methods=["POST"])
def chat():
    """内部测试聊天 API"""
    try:
        payload = request.get_json(force=True)
        reply = handler.process_message(payload)
        return jsonify(reply)
    except Exception as e:
        logger.error(f"Chat error: {e}", exc_info=True)
        return jsonify({"ret":0,"msg":"ok","data":{"answer":"抱歉，出了点问题。","answer_type":"text"}})

@app.route("/wechat", methods=["GET"])
def verify_wechat():
    signature = request.args.get("signature","")
    timestamp = request.args.get("timestamp","")
    nonce = request.args.get("nonce","")
    echostr = request.args.get("echostr","")
    if handler.verify_signature(signature, timestamp, nonce):
        return echostr
    return "signature verification failed", 403

@app.route("/wechat", methods=["POST"])
def receive_message():
    try:
        payload = request.get_json(force=True)
        logger.info(f"WeChat: {str(payload.get('msg',payload.get('query','')))[:50]}")
        return jsonify(handler.process_message(payload))
    except Exception as e:
        logger.error(f"WeChat error: {e}")
        return jsonify({"ret":0,"msg":"ok","data":{"answer":"服务暂时不可用。","answer_type":"text"}})

@app.route("/reset", methods=["POST"])
def reset_history():
    sid = request.args.get("session","")
    if sid:
        handler.clear_history(sid)
        return jsonify({"ret":0,"msg":f"已清除 {sid}"})
    return jsonify({"ret":1,"msg":"需要 session 参数"}), 400

def main():
    Config.load_dotenv()
    errors = Config.validate()
    for e in errors:
        logger.warning(f"  - {e}")
    port = Config.WECHAT_SERVER_PORT
    logger.info(f"Pal 服务启动 | Persona={Config.PERSONA_NAME} | Model={Config.DEEPSEEK_MODEL} | Port={port}")
    app.run(host="0.0.0.0", port=port, debug=False)

if __name__ == "__main__":
    main()
