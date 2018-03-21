# coding=utf-8

import tornado.options

tornado.options.define('app', default=None, type=str)
tornado.options.define('app_class', default=None, type=str)
tornado.options.define('tornado_settings', default=None, type=dict)
tornado.options.define('handlers_count', default=100, type=int)
tornado.options.define('reuse_port', default=True, type=bool)
tornado.options.define('xheaders', default=False, type=bool)

tornado.options.define('config', None, str)
tornado.options.define('host', '0.0.0.0', str)
tornado.options.define('port', 8080, int)

tornado.options.define('autoreload', False, bool)
tornado.options.define('stop_timeout', 3, int)
tornado.options.define('log_blocked_ioloop_timeout', 0, float)

tornado.options.define('loglevel', default='info', type=str, help='Log level')
tornado.options.define('logformat', default='[%(process)s] %(asctime)s %(levelname)s %(name)s: %(message)s', type=str,
                       help='Log format for files and syslog')
tornado.options.define('logfile', default=None, type=str, help='Log file name')

tornado.options.define('stderr_log', default=False, type=bool,
                       help='Send log output to stderr (colorized if possible).')
tornado.options.define('stderr_format', default='%(color)s[%(levelname)1.1s %(asctime)s %(name)s '
                                                '%(module)s:%(lineno)d]%(end_color)s %(message)s', type=str)
tornado.options.define('stderr_dateformat', default='%y.%m.%d %H:%M:%S', type=str)

tornado.options.define('syslog', default=False, type=bool)
tornado.options.define('syslog_address', default='/dev/log', type=str)
tornado.options.define('syslog_port', default=None, type=int)
tornado.options.define('syslog_facility', default='user', type=str)

tornado.options.define('suppressed_loggers', default=['tornado.curl_httpclient'], type=list)

tornado.options.define('debug', default=False, type=bool)
tornado.options.define('debug_login', default=None, type=str)
tornado.options.define('debug_password', default=None, type=str)

tornado.options.define('http_client_default_connect_timeout_sec', default=0.2, type=float)
tornado.options.define('http_client_default_request_timeout_sec', default=2.0, type=float)
tornado.options.define('http_client_default_max_tries', default=2, type=int)
tornado.options.define('http_client_default_max_timeout_tries', default=1, type=int)
tornado.options.define('http_client_default_max_fails', default=0, type=int)
tornado.options.define('http_client_default_fail_timeout_sec', default=10, type=float)
tornado.options.define('http_client_default_retry_policy', default='timeout,http_503', type=str)
tornado.options.define('http_proxy_host', default=None, type=str)
tornado.options.define('http_proxy_port', default=3128, type=int)

tornado.options.define('statsd_host', default=None, type=str)
tornado.options.define('statsd_port', default=None, type=int)

tornado.options.define('timeout_multiplier', default=1.0, type=float)

tornado.options.define('xml_root', default=None, type=str)
tornado.options.define('xml_cache_limit', default=None, type=int)
tornado.options.define('xml_cache_step', default=None, type=int)
tornado.options.define('xsl_root', default=None, type=str)
tornado.options.define('xsl_cache_limit', default=None, type=int)
tornado.options.define('xsl_cache_step', default=None, type=int)
tornado.options.define('xsl_executor_pool_size', default=1, type=int)
tornado.options.define('jinja_template_root', default=None, type=str)
tornado.options.define('jinja_template_cache_limit', default=50, type=int)
tornado.options.define('jinja_streaming_render_timeout_ms', default=50, type=int)

tornado.options.define('sentry_dsn', default=None, type=str, metavar='http://public:secret@example.com/1')

tornado.options.define('max_http_clients', default=100, type=int)
tornado.options.define('max_http_clients_connects', default=None, type=int)
