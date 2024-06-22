import json

import aioredis
import asyncio
from core.redis import get_aio_redis_pool


class AIORedisServer:

    def __init__(self):
        self.redis = get_aio_redis_pool()
        pass

    async def subscribe(self, channel: str):
        """
        异步订阅给定的频道并处理消息。

        :param channel: 要订阅的频道名称
        :param message_handler: 处理消息的异步函数，该函数需要接收消息数据作为参数
        """
        sub = self.redis.pubsub()
        await sub.subscribe(channel)
        print(f"Subscribed to {channel}, waiting for messages...")

        # 异步处理接收到的消息
        try:
            async for message in sub.listen():
                if message['type'] == 'message':
                    print(message["data"])
                    yield json.loads(message['data'])
        finally:
            # 在结束前取消订阅并关闭连接
            await sub.unsubscribe(channel)
            await self.redis.close()

    async def publish(self, channel: str, message):
        await self.redis.publish(channel, json.dumps(message))
        await self.redis.close()
