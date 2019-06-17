import json
import logging

from frontik.app import FrontikApplication
from frontik.loggers import bootstrap_logger
from frontik.options import options

from .pages.sentry import api


class TestApplication(FrontikApplication):
    def __init__(self, **settings):
        options.sentry_dsn = 'http://key@127.0.0.1:{}/123'.format(settings['port'])

        bootstrap_logger('custom_logger', logging.DEBUG, False)

        super().__init__(**settings)

    async def init_async(self):
        await super().init_async()

        try:
            from frontik.integrations.kafka import KafkaIntegration
            kafka_integration = next(i for i in self.integrations if isinstance(i, KafkaIntegration))
            kafka_integration.kafka_producers = {'infrastructure': TestKafkaProducer()}
        except Exception:
            pass

    def application_version(self):
        return 'last version'

    def application_urls(self):
        return [(r'/api/(\d+)/store/?', api.Page)] + super().application_urls()


class TestKafkaProducer:
    def __init__(self):
        self.data = []
        self.request_id = None

    async def send(self, topic, value=None):
        json_data = json.loads(value)

        if json_data['requestId'] == self.request_id:
            self.data.append({
                topic: json_data
            })

    def enable_for_request_id(self, request_id):
        self.request_id = request_id

    def disable_and_get_data(self):
        self.request_id = None
        return self.data
