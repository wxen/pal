"""
主动消息系统
根据强度值随机唤醒 agent，发送主动消息
"""

import random
import time
import logging
import threading

logger = logging.getLogger("pal.active")


ACTIVE_MSG_PROMPT = """# 系统消息
这是一条系统消息，将这条消息视作"你醒了，想想接下来要不要找用户聊点什么"。

- 在这条消息里思考是否要主动向用户发送消息，以及发送什么内容
- 如果没有调用任何工具，自动视为放弃发送消息
- 不要总是拒绝发送消息，但也不要每次都发送。根据角色设定，角色与用户交流关系和请求频率综合考虑

# 本地时间戳
当前时间为{timestamp}"""


class ActiveMessenger:
    """主动消息触发器"""

    def __init__(self, engine, intensity: int = 30):
        self.engine = engine
        self.intensity = min(max(intensity, 0), 100)
        self._running = False
        self._thread: threading.Thread | None = None

    def start(self):
        if self.intensity <= 0:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        logger.info(f"Active messenger started (intensity={self.intensity})")

    def stop(self):
        self._running = False

    def _loop(self):
        while self._running:
            # 根据强度计算等待时间（强度越高，间隔越短）
            # 强度 30: 平均约 15-45 分钟间隔
            # 强度 100: 平均约 3-10 分钟间隔
            base = max(5, 60 - self.intensity * 0.5)  # 5-60 minutes base
            jitter = base * 0.5
            wait_minutes = max(1, base + random.uniform(-jitter, jitter))
            time.sleep(wait_minutes * 60)

            if not self._running:
                break

            # 随机决定本次是否唤醒（不是每次间隔都触发）
            if random.randint(0, 100) > self.intensity:
                continue

            try:
                self._try_active_message()
            except Exception as e:
                logger.error(f"Active message error: {e}")

    def _try_active_message(self):
        """尝试发送主动消息"""
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        prompt = ACTIVE_MSG_PROMPT.format(timestamp=ts)
        # 将主动消息注入为"系统消息"触发模型思考
        results = self.engine.process(prompt)
        if results:
            logger.info(f"Active message triggered: {len(results)} messages")
