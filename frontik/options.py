# coding=utf-8

from tornado.options import define

define('app', None, str)
define('app_class', None, str)
define('tornado_settings', None, dict)
define('handlers_count', 100, int)
define('reuse_port', True, bool)
define('xheaders', False, bool)

define('config', None, str)
define('host', '0.0.0.0', str)
define('port', 8080, int)

define('autoreload', False, bool)
define('stop_timeout', 3, int)
define('log_blocked_ioloop_timeout', 0, float)

define('loglevel', 'info', str, 'Log level')
define('service_logfile', None, str, 'Service log file name')
define('requests_logfile', None, str, 'Request info log file name')
define(
    'logformat',
    '%(name)s: [%(process)s] %(asctime)s %(levelname)s mdc={%(handler_name)s} rid={%(request_id)s} %(message)s',
    str, 'Log format for files'
)

define('stderr_log', False, bool, 'Send log output to stderr (colorized if possible).')
define(
    'stderr_logformat',
    '%(color)s[%(levelname)1.1s %(asctime)s %(name)s %(module)s:%(lineno)d]%(end_color)s '
    'mdc={%(handler_name)s} rid={%(request_id)s} %(message)s',
    str
)

define('syslog', False, bool)
define('syslog_address', '/dev/log', str)
define('syslog_port', None, int)
define('syslog_facility', 'user', str)
define(
    'syslog_logformat',
    '%(name)s: [%(process)s] [%(asctime)s] %(levelname)s mdc={%(handler_name)s} rid={%(request_id)s} %(message)s',
    str, 'Log format for syslog'
)

define('suppressed_loggers', ['tornado.curl_httpclient'], list)

define('debug', False, bool)
define('debug_login', None, str)
define('debug_password', None, str)

define('datacenter', None, str)

define('http_client_default_connect_timeout_sec', 0.2, float)
define('http_client_default_request_timeout_sec', 2.0, float)
define('http_client_default_max_tries', 2, int)
define('http_client_default_max_timeout_tries', 1, int)
define('http_client_default_max_fails', 0, int)
define('http_client_default_fail_timeout_sec', 10, float)
define('http_client_default_retry_policy', 'timeout,http_503', str)
define('http_proxy_host', None, str)
define('http_proxy_port', 3128, int)
define('http_client_allow_cross_datacenter_requests', False, bool)

define('statsd_host', None, str)
define('statsd_port', None, int)

define('timeout_multiplier', 1.0, float)

define('xml_root', None, str)
define('xml_cache_limit', None, int)
define('xml_cache_step', None, int)
define('xsl_root', None, str)
define('xsl_cache_limit', None, int)
define('xsl_cache_step', None, int)
define('xsl_executor_pool_size', 1, int)
define('jinja_template_root', None, str)
define('jinja_template_cache_limit', 50, int)
define('jinja_streaming_render_timeout_ms', 50, int)

define('sentry_dsn', None, str, metavar='http://public:secret@example.com/1')

define('max_http_clients', 100, int)
define('max_http_clients_connects', None, int)
