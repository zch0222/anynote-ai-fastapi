import json

from rocketmq.client import Producer, Message


class RocketMQServer:

    def send(self, topic: str, tags: str, body: dict):
        producer = Producer('PID-XXX')
        producer.set_namesrv_addr('127.0.0.1:9876')
        producer.start()

        msg = Message(topic)
        msg.set_tags(tags)
        msg.set_body(json.dumps(body))
        ret = producer.send_sync(msg)
        print(ret.status, ret.msg_id, ret.offset)
        producer.shutdown()
