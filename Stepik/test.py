from confluent_kafka import Consumer, TopicPartition, OFFSET_BEGINNING
from datetime import datetime, timezone

# import sys

conf = {
    "bootstrap.servers": "10.100.104.31:9092,10.100.104.32:9092,10.100.104.33:9092",
    "security.protocol": "SASL_PLAINTEXT",
    "sasl.mechanism": "PLAIN",
    "sasl.username": "admin",
    "sasl.password": "pass1",
    "group.id": "offset-fix-group",
    "auto.offset.reset": "latest",
    "enable.auto.commit": False,
}

consumer = Consumer(conf)
topic = "RECEIPTS_EXPORT"
start_date = datetime(2025, 5, 22, tzinfo=timezone.utc)
unique_values = set()

try:
    # partitions = consumer.list_topics(topic).topics[topic].partitions.keys()
    partitions = [
        p
        for p in consumer.list_topics(topic).topics[topic].partitions.keys()
        if p != 0  # Исключаем партицию 0
    ]
    for partition in partitions:
        tp = TopicPartition(topic, partition)
        timestamp = int(start_date.timestamp() * 1000)
        offsets = consumer.offsets_for_times(
            [TopicPartition(topic, partition, timestamp)]
        )

        if offsets[0].offset == -1:
            print(
                f"Партиция {partition}: нет данных после {start_date}, читаем с начала"
            )
            tp.offset = OFFSET_BEGINNING
        else:
            tp.offset = offsets[0].offset

        consumer.assign([tp])

        while True:
            msg = consumer.poll(1.0)
            if msg is None:
                break
            if msg.error():
                print(f"Ошибка в партиции {partition}: {msg.error()}")
                continue

            key = msg.key().decode("utf-8") if msg.key() else None
            if key:
                parts = key.split(".")
                if len(parts) >= 3:
                    unique_values.add(parts[2])

finally:
    consumer.close()
    with open("unique_values.txt", "w") as f:
        f.write("\n".join(sorted(unique_values)))
