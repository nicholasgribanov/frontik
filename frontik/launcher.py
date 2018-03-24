#!/usr/bin/env python
# coding=utf-8

import argparse
import gc
import os
import signal

from frontik import server
from frontik.producers import xml_producer

if __name__ == '__main__':
    gc.disable()
    children = []

    parser = argparse.ArgumentParser(description='Simple supervisor for Frontik')
    parser.add_argument('--num', type=int, help='Processes count')
    args, _ = parser.parse_known_args()

    xml_producer.init_xsl_cache()

    for i in range(args.num):
        pid = os.fork()
        if pid:
            children.append(pid)
        else:
            gc.enable()
            os.closerange(0, 2048)
            server.main()
            break
    else:
        def sigterm_action(signum, stack):
            for child in children:
                os.kill(child, signum)

        signal.signal(signal.SIGTERM, sigterm_action)

        for child in children:
            os.waitpid(child, 0)
