#! /usr/bin/env python
#  -*- coding: utf-8 -*-
#
# This file is part of grafana_webhook_smsd

__intname__ = "grafana_webhook_api.sms"
__author__ = "Orsiris de Jong"
__copyright__ = "Copyright (C) 2023-2026 NetInvent"
__license__ = "BSD-3 Clause"
__build__ = "2026013001"

import logging
from datetime import datetime, timezone, timedelta
from command_runner import command_runner
from grafana_webhook_api import configuration


config_dict = configuration.load_config()

logger = logging.getLogger()

# Variable to keep track of last sends
LAST_SENT = {"global": []}


def send_sms(number: str, message: str, min_interval: int = None):
    global LAST_SENT

    try:
        sms_command = config_dict["sms_command"]
    except KeyError:
        logger.error("No sms command defined")
        return False

    try:
        sms_max_length = config_dict["alert_max_length"]
    except KeyError:
        sms_max_length = 2500

    # Hard per number interval
    try:
        hard_min_interval = config_dict["min_interval"]
    except KeyError:
        logger.info("No server side per number limit defined")
        hard_min_interval = None

    # global sms rate limit
    try:
        global_rate_limit = config_dict["global_rate_limit"]
        global_count, global_interval = global_rate_limit.split("/")
        global_count = int(global_count)
        global_interval = int(global_interval)
    except (KeyError, TypeError, ValueError) as exc:
        logger.info(f"No global rate limit defined: {exc}")
        global_interval = None
        global_rate_limit = None

    cur_timestamp = datetime.now(timezone.utc)
    if min_interval or hard_min_interval:
        try:
            elapsed_time_since_last_sms_sent = (
                cur_timestamp - LAST_SENT[number]["date"]
            ).seconds
        except KeyError:
            elapsed_time_since_last_sms_sent = None
        if min_interval and elapsed_time_since_last_sms_sent is not None:
            if elapsed_time_since_last_sms_sent < min_interval:
                logger.info(
                    f"Client side min_interval for number {number} not reached ({elapsed_time_since_last_sms_sent}). Not sending this SMS"
                )
                return False
        if hard_min_interval and elapsed_time_since_last_sms_sent is not None:
            if elapsed_time_since_last_sms_sent < hard_min_interval:
                logger.info(
                    f"Server side min_interval for number {number} not reached ({elapsed_time_since_last_sms_sent}). Not sending this SMS"
                )
                return False
    if global_interval and global_count:
        try:
            if LAST_SENT["global"][-global_count] >= (
                cur_timestamp - timedelta(seconds=global_interval)
            ):
                logger.info(
                    f"Global rate reached ({global_count}/{global_interval}s). Not sending this SMS"
                )
                return False
        except (KeyError, IndexError):
            pass

    # Update per number last sent date
    LAST_SENT[number] = {"date": cur_timestamp}
    if global_interval and global_count:
        # Update global last sent date
        LAST_SENT["global"].append(cur_timestamp)
        # Only keep last global_rate_limit objects so we don't fill memory for nothing
        LAST_SENT["global"] = LAST_SENT["global"][-global_count:]

    # Reduce sms to a specific length
    message_len = len(message)
    if message_len > sms_max_length:
        message = message[0 : (sms_max_length - 3)] + "..."
        message_len = len(message_len)

    parsed_sms_command = sms_command.replace("${NUMBER}", "'{}'".format(number))
    parsed_sms_command = parsed_sms_command.replace(
        "${ALERT_MESSAGE}", "'{}'".format(message)
    )
    parsed_sms_command = parsed_sms_command.replace(
        "${ALERT_MESSAGE_LEN}", str(message_len)
    )

    logger.info("sms_command: {}".format(parsed_sms_command))
    exit_code, output = command_runner(parsed_sms_command)
    if exit_code != 0:
        logger.error("Could not send SMS, code {}: {}".format(exit_code, output))
        return False
    logger.info("Sent SMS to {}".format(number))
    return True
