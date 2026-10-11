"""
Counter-based RNG — детерминированный генератор случайных чисел.

Зачем нужен:
    Шум должен быть детерминированным по (seed, index, params):
    значение шума для элемента n не должно зависеть от того, запросили
    ли мы сначала n=100, а потом n=10, или наоборот.

    Обычный ГПСЧ (random.Random) этого не даёт: он хранит внутреннее
    состояние, и последовательность зависит от порядка вызовов.

    Counter-based RNG решает проблему: значение = hash(seed, index),
    поэтому доступ к элементу n — чистая функция. Это позволяет
    свободно досоздавать хвост и не бояться, что ранее выданные значения
    изменятся.

    Используем blake2b из hashlib — он быстрый, встроенный, и не требует
    сторонних зависимостей.

Как расширять:
    Если понадобится другой алгоритм хеширования (например, philox для
    скорости), добавь новый класс с тем же интерфейсом (uniform, normal)
    и подменяй его в шумах через параметр.
"""

from __future__ import annotations
import hashlib
import math
import struct


class CounterRNG:
    """
    Детерминированный RNG без состояния.

    Значение для индекса n — чистая функция от (seed, stream_id, n).
    """

    def __init__(self, seed: int, stream_id: str = ""):
        """
        Принимает:
            seed      — целочисленный seed
            stream_id — произвольная строка-идентификатор потока;
                        позволяет получать разные последовательности
                        при одном и том же seed (например, для разных
                        параметров шума).
        """
        self.seed = int(seed) & 0xFFFFFFFFFFFFFFFF  # приводим к uint64
        self.stream_id = stream_id.encode("utf-8")

    def _hash64(self, n: int, salt: int = 0) -> int:
        """
        Возвращает 64-битное псевдослучайное число для индекса n.

        Принимает:
            n    — индекс (может быть любым неотрицательным int)
            salt — дополнительный сдвиг (для получения нескольких
                   независимых потоков из одного индекса)

        Возвращает:
            целое число в [0, 2^64).
        """
        # Собираем ключ: stream_id + salt. Длина ключа blake2b — до 64 байт.
        key = self.stream_id[:32] + struct.pack("<Q", salt & 0xFFFFFFFFFFFFFFFF)
        # Собираем сообщение: seed + n.
        msg = struct.pack("<QQ", self.seed, n & 0xFFFFFFFFFFFFFFFF)
        h = hashlib.blake2b(
            msg,
            digest_size=8,
            key=key[:64] if key else b"\x00" * 8,
        ).digest()
        return int.from_bytes(h, "little")

    def uniform(self, n: int, salt: int = 0) -> float:
        """
        Равномерное число в [0, 1) для индекса n.

        Принимает:
            n    — индекс
            salt — дополнительный сдвиг

        Возвращает:
            float в [0, 1).
        """
        # 53 бита — максимально, что умещается в мантиссу double без потерь.
        return (self._hash64(n, salt) >> 11) / float(1 << 53)

    def normal(self, n: int, salt: int = 0) -> float:
        """
        Стандартное нормальное N(0, 1) для индекса n (Box–Muller).

        Принимает:
            n    — индекс
            salt — дополнительный сдвиг

        Возвращает:
            float.
        """
        u1 = self.uniform(n, salt * 2 + 0)
        u2 = self.uniform(n, salt * 2 + 1)
        # Защита от log(0) — u1 не должен быть ровно 0.
        if u1 == 0.0:
            u1 = 1e-300
        return math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2)