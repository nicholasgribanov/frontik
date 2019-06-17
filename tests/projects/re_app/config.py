from .pages import handler_404
from .pages import id_param
from .pages import simple

urls = [
    ('/id/([^/]+)', id_param.Page),
    ('/id/([^/]+)/([^/]+)', handler_404.Page, {}, 'two_ids'),
    ('/not_simple', simple.Page),
]
