import asyncio
from typing import TYPE_CHECKING

from aiokafka import AIOKafkaProducer
from tornado import gen

from frontik.integrations import Integration
from frontik.options import options

if TYPE_CHECKING:  # pragma: no cover
    from asyncio import Future
    from typing import Optional

    from frontik.app import FrontikApplication
    from frontik.handler import PageHandler


class KafkaIntegration(Integration):
    def __init__(self):
        self.kafka_producers = {}

    def initialize_app(self, app: 'FrontikApplication') -> 'Optional[Future]':
        def get_kafka_producer(producer_name: str) -> 'Optional[AIOKafkaProducer]':
            return self.kafka_producers.get(producer_name)

        app.get_kafka_producer = get_kafka_producer

        if options.kafka_clusters:
            init_futures = []

            for cluster_name, producer_settings in options.kafka_clusters.items():
                if producer_settings:
                    producer = AIOKafkaProducer(loop=asyncio.get_event_loop(), **producer_settings)
                    self.kafka_producers[cluster_name] = producer
                    init_futures.append(asyncio.ensure_future(producer.start()))

            return gen.multi(init_futures)

        return None

    def initialize_handler(self, handler: 'PageHandler') -> None:
        handler.get_kafka_producer = handler.application.get_kafka_producer
