#! /usr/bin/env python
#  -*- coding: utf-8 -*-
#
# This file is part of grafana_webhook_gammu_smsd

__intname__ = "grafana_webhook_gammu_smsd.api"
__author__ = "Orsiris de Jong"
__copyright__ = "Copyright (C) 2023 NetInvent"
__license__ = "BSD-3 Clause"
__build__ = "2023060101"
__version__ = "1.0.1"


from command_runner import command_runner
import logging
import secrets
from datetime import datetime
from argparse import ArgumentParser
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi_offline import FastAPIOffline
from grafana_webhook_gammu_smsd import configuration
from grafana_webhook_gammu_smsd.models import AlertMessage

# Make sure we load given config files again
parser = ArgumentParser()
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
if args.config_file:
    config_dict = configuration.load_config(args.config_file)
else:
    config_dict = configuration.load_config()

logger = logging.getLogger()


app = FastAPIOffline()
security = HTTPBasic()


def anonymous_auth():
    return "anonymous"


def get_current_username(credentials: HTTPBasicCredentials = Depends(security)):
    current_username_bytes = credentials.username.encode("utf8")
    correct_username_bytes = config_dict["http_server"]["username"].encode("utf-8")
    is_correct_username = secrets.compare_digest(
        current_username_bytes, correct_username_bytes
    )
    current_password_bytes = credentials.password.encode("utf8")
    correct_password_bytes = config_dict["http_server"]["password"].encode("utf-8")
    is_correct_password = secrets.compare_digest(
        current_password_bytes, correct_password_bytes
    )
    if not (is_correct_username and is_correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


try:
    if config_dict["http_server"]["no_auth"] is True:
        logger.warning("Running without HTTP authentication")
        auth_scheme = anonymous_auth
    else:
        logger.info("Running with HTTP authentication")
        auth_scheme = get_current_username
except (KeyError, AttributeError, TypeError):
    auth_scheme = get_current_username
    logger.info("Running with HTTP authentication")


@app.get("/")
async def api_root(auth=Depends(get_current_username)):
    return {"app": __appname__}


@app.post("/grafana/{number}")
async def grafana(number: str, alert: AlertMessage, auth=Depends(auth_scheme)):
#async def grafana(number: str, alert: AlertMessage, auth=auth_scheme):

    if not number:
        raise HTTPException(
            status_code=404,
            detail="No number set"
        )

    if not alert.message:
        raise HTTPException(
            stats_code=404,
            detial="No alert set"
        )

    # Escape single quotes here so we will stay in line
    try:
        title = alert.title.replace("'", r"\'")
    except KeyError:
        title = ''

    try:
        orgId = str(alert.orgId).replace("'", r"\'")
    except (KeyError, AttributeError, ValueError, TypeError):
        orgId = ''

    try:
        externalURL = alert.externalURL.replace("'", r"\'")
    except KeyError:
        externalURL = ''

    try:
        message = alert.message.replace("'", r"\'")
    except KeyError:
        message = ''

    number = number.replace("'", r"\'")
    try:
        supervision_name = config_dict["supervision_name"]
    except KeyError:
        supervision_name = "Supervision"

    timestr = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    alert_message = '{} org {} {}:\n{} - {}'.format(supervision_name, orgId, timestr, title, message)
    alert_message_len = len(alert_message)
    if alert_message_len > 2500:
        alert_message = alert_message[0:2500]
        alert_message_len = len(alert_message)

    logger.info("Received alert {} for number {}".format(title, number))
    try:
        sms_command = config_dict["sms_command"]
    except KeyError:
        logger.error("No sms command defined")
        raise HTTPException(
            status_code=500,
            detail="Server not configured"
        )

    sms_command = sms_command.replace("${NUMBER}", "'{}'".format(number))
    sms_command = sms_command.replace("${ALERT_MESSAGE}", "'{}'".format(alert_message))
    sms_command = sms_command.replace("${ALERT_MESSAGE_LEN}", str(alert_message_len))

    logger.info("sms_command: {}".format(sms_command))
    exit_code, output = command_runner(sms_command)
    if exit_code != 0:
        logger.error("Could not send SMS, code {}: {}".format(exit_code, output))
        raise HTTPException(
            status_code=400,
            detail="Cannot send text: {}".format(output),
        )
    logger.info("Sent SMS to {}".format(number))

