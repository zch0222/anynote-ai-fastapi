from core.redis import get_redis_pool
from redis import Redis
from redis.lock import Lock
import traceback
from time import sleep
import json


class RedisServer:
    READ_LOCK_PREFIX = "READ_LOCK:"
    READ_COUNT_PREFIX = "READ_COUNT:"
    WRITE_LOCK_PREFIX = "WRITE_LOCK:"

    def __init__(self, redis: Redis):
        self.redis = redis

    def set(self, key: str, data):
        self.redis.set(key, json.dumps(data))

    def set_ex(self, key: str, data, ex: int):
        self.redis.set(key, json.dumps(data), ex=ex)

    def get(self, key: str):
        data = self.redis.get(key)
        if not data:
            return data
        return json.loads(data)

    def delete(self, key: str):
        self.redis.delete(key)

    def read_lock(self, key: str):
        try:
            self.get_read_lock(key)
            self.incr_read_count(key)
            # print(f"read_count:{self.get_read_count(key)}")
            if 1 == self.get_read_count(key):
                # print("locking write...")
                self.get_write_lock(key)
        except Exception:
            traceback.print_exc()
            print("获取读锁出错")
        finally:
            self.delete_read_lock(key)

    def read_unlock(self, key: str):
        try:
            self.get_read_lock(key)
            self.decr_read_count(key)
            # print(f"read_count:{self.get_read_count(key)}")
            if 0 == self.get_read_count(key):
                # print("unlocking write...")
                self.delete_read_count(key)
                self.delete_write_lock(key)
        except Exception:
            traceback.print_exc()
            print("获取读锁出错")
        finally:
            self.delete_read_lock(key)

    def write_lock(self, key: str):
        self.get_write_lock(key)

    def write_unlock(self, key: str):
        self.delete_write_lock(key)

    def get_write_lock(self, key: str):
        flag = False
        while not flag:
            print("try write lock....")
            flag = self.redis.setnx(f"{RedisServer.WRITE_LOCK_PREFIX}{key}", "1")
            sleep(0.05)
        print("get write lock")

    def delete_write_lock(self, key: str):
        self.redis.delete(f"{RedisServer.WRITE_LOCK_PREFIX}{key}")

    def get_read_lock(self, key: str):
        flag = False
        while not flag:
            print("try read lock....")
            flag = self.redis.setnx(f"{RedisServer.READ_LOCK_PREFIX}{key}", "1")
            sleep(0.05)

    def delete_read_lock(self, key: str):
        self.redis.delete(f"{RedisServer.READ_LOCK_PREFIX}{key}")

    def incr_read_count(self, key: str):
        self.redis.incr(f"{RedisServer.READ_COUNT_PREFIX}{key}")

    def decr_read_count(self, key: str):
        self.redis.decr(f"{RedisServer.READ_COUNT_PREFIX}{key}")

    def delete_read_count(self, key: str):
        self.redis.delete(f"{RedisServer.READ_COUNT_PREFIX}{key}")

    def get_read_count(self, key: str) -> int:
        return int(self.redis.get(f"{RedisServer.READ_COUNT_PREFIX}{key}"))
