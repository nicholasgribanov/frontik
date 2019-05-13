from frontik.handler import PageHandler


class Page(PageHandler):
    async def get_page(self):
        statsd_client = self.get_statsd_client()

        statsd_client.count('count_metric', 10, tag1='tag1', tag2='tag2')
        statsd_client.gauge('gauge_metric', 100, tag='tag3')
        statsd_client.time('time_metric', 1000, tag='tag4')
