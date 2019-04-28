import logging
import time

from lxml import etree

parser = etree.XMLParser()
xml_util_log = logging.getLogger('frontik.xml_util')


def xml_from_file(filename):
    try:
        return etree.parse(filename).getroot()
    except IOError:
        xml_util_log.error('failed to read xml file %s', filename)
        raise
    except Exception:
        xml_util_log.error('failed to parse xml file %s', filename)
        raise


def xsl_from_file(filename):
    start_time = time.time()
    result = etree.XSLT(etree.parse(filename, parser))
    xml_util_log.info('read xsl file %s in %.2fms', filename, (time.time() - start_time) * 1000)
    return result


def format_xslt_error(error_log):
    return '\n'.join(f'XSLT {m.level_name} in {m.filename}:{m.line}:{m.column}\n\t{m.message}' for m in error_log)
