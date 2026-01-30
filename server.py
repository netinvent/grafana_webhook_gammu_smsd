#! /usr/bin/env python
#  -*- coding: utf-8 -*-
#
# This file is part of grafana_webhook_gammu_smsd

__intname__ = "grafana_webhook_gammu_smsd.server"
__author__ = "Orsiris de Jong"
__copyright__ = "Copyright (C) 2023-2026 NetInvent"
__license__ = "BSD-3 Clause"
__build__ = "2026012901"
__version__ = "1.0.1"


import sys
import os

import multiprocessing
from argparse import ArgumentParser
from __debug__ import _DEBUG
from ofunctions.logger_utils import logger_get_logger

LOG_FILE = f"/var/log/{__intname__}.log"
logger = logger_get_logger(log_file=LOG_FILE, debug=_DEBUG)
from grafana_webhook_gammu_smsd import configuration
import grafana_webhook_gammu_smsd.api

if __name__ == "__main__":
    _DEV = os.environ.get("_DEV", False)

    parser = ArgumentParser(
        prog="{} {} - {}".format(__intname__, __copyright__, __license__),
        description="""grafana_webhook_gammu_smsd server""",
    )

    parser.add_argument(
        "--dev", action="store_true", help="Run with uvicorn in devel environment"
    )

    parser.add_argument(
        "-c",
        "--config-file",
        dest="config_file",
        type=str,
        default=None,
        required=False,
        help="Path to grafana_webhook_gammu_smsd.conf file",
    )

    args = parser.parse_args()
    if args.dev:
        _DEV = True

    if args.config_file:
        config_dict = configuration.load_config(args.config_file)
    else:
        config_dict = configuration.load_config()

    try:
        listen = config_dict["http_server"]["listen"]
    except (TypeError, KeyError):
        listen = None
    try:
        port = config_dict["http_server"]["port"]
    except (TypeError, KeyError):
        port = None

    # Cannot use gunicorn on Windows
    if _DEV or os.name == "nt":
        logger.info("Running dev version")
        import uvicorn

        server_args = {
            "workers": 1,
            "log_level": "debug",
            "reload": True,
            "host": listen if listen else "0.0.0.0",
            "port": port if port else 8080,
        }
    else:
        import gunicorn.app.base

        class StandaloneApplication(gunicorn.app.base.BaseApplication):
            """
            This class supersedes gunicorn's class in order to load config before launching the app
            """

            def __init__(self, app, options=None):
                self.options = options or {}
                self.application = app
                super().__init__()

            def load_config(self):
                config = {
                    key: value
                    for key, value in self.options.items()
                    if key in self.cfg.settings and value is not None
                }
                for key, value in config.items():
                    self.cfg.set(key.lower(), value)

            def load(self):
                return self.application

        server_args = {
            "workers": 1,  # Don't run multiple workers since we don't have shared variables yet (multiprocessing.cpu_count() * 2) + 1,
            "bind": f"{listen}:{port}" if listen else "0.0.0.0:8080",
            "worker_class": "uvicorn.workers.UvicornWorker",
        }

    try:
        if _DEV or os.name == "nt":
            uvicorn.run("grafana_webhook_gammu_smsd.api:app", **server_args)
        else:
            StandaloneApplication(grafana_webhook_gammu_smsd.api.app, server_args).run()
    except KeyboardInterrupt as exc:
        logger.error("Program interrupted by keyoard: {}".format(exc))
        sys.exit(200)
    except Exception as exc:
        logger.error("Program interrupted by error: {}".format(exc))
        logger.critical("Trace:", exc_info=True)
        sys.exit(201)
