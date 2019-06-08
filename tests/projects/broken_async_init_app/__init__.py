from frontik.app import FrontikApplication


class TestApplication(FrontikApplication):
    async def init_async(self):
        raise Exception('broken init_async')
