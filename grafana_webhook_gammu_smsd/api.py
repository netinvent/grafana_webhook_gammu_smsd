#! /usr/bin/env python
#  -*- coding: utf-8 -*-
#
# This file is part of grafana_webhook_gammu_smsd

__intname__ = "grafana_webhook_gammu_smsd.api"
__author__ = "Orsiris de Jong"
__copyright__ = "Copyright (C) 2023-2024 NetInvent"
__license__ = "BSD-3 Clause"
__build__ = "2024040901"
__version__ = "1.5.0"
__appname__ = "Grafana 2 Gammu SMSD"


from typing import Union
from command_runner import command_runner
import logging
import secrets
import datetime
from argparse import ArgumentParser
from fastapi import FastAPI, HTTPException, Depends, status, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
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

# Timestamp of last time we sent an sms, per number
LAST_SENT_TIMESTAMP = {}


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


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Solution blatantly from https://github.com/tiangolo/fastapi/issues/3361#issuecomment-1002120988
    allows to log 422 errors
    """
    exc_str = f'{exc}'.replace('\n', ' ').replace('   ', ' ')
    logging.error(f"{request}: {exc_str}")
    content = {'status_code': 422, 'message': exc_str, 'data': None}
    return JSONResponse(content=content, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)


@app.get("/")
async def api_root(auth=Depends(get_current_username)):
    return {"app": __appname__}


@app.post("/grafana/{numbers}")
@app.post("/grafana/{numbers}/{min_interval}")
async def grafana(numbers: str, min_interval: Union[int, None] = None, alert: AlertMessage = None, auth=Depends(auth_scheme)):

    global LAST_SENT_TIMESTAMP

    if not numbers:
        raise HTTPException(
            status_code=404,
            detail="No phone number set"
        )

    if not alert or not alert.message:
        raise HTTPException(
            status_code=404,
            detail="No alert set"
        )

    # Multiple numbers with ';' are accepted
    numbers = numbers.split(';')


    # Escape single quotes here so we will stay in line
    try:
        title = alert.title.replace("'", r"-")
    except KeyError:
        title = ''

    try:
        orgId = str(alert.orgId).replace("'", r"-")
    except (KeyError, AttributeError, ValueError, TypeError):
        orgId = ''

    try:
        externalURL = alert.externalURL.replace("'", r"-")
    except KeyError:
        externalURL = ''

    try:
        message = alert.message.replace("'", r"-")
    except KeyError:
        message = ''

    try:
        supervision_name = config_dict["supervision_name"]
    except KeyError:
        supervision_name = "Supervision"

<<<<<<< HEAD
    timestr = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
=======
    timestr = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%d %H:%M:%S")
>>>>>>> 5a9413b0fa62d0da139300e700982c414da05403

    alert_message = '{} org {} {}:\n{} - {}'.format(supervision_name, orgId, timestr, title, message)
    alert_message_len = len(alert_message)
    if alert_message_len > 2500:
        alert_message = alert_message[0:2500]
        alert_message_len = len(alert_message)

    try:
        sms_command = config_dict["sms_command"]
    except KeyError:
        logger.error("No sms commandline tool defined")
        raise HTTPException(
            status_code=500,
            detail="Server not configured"
        )

    for number in numbers:
        number = number.replace("'", r"-")
        if min_interval:
<<<<<<< HEAD
            cur_timestamp = datetime.utcnow()
=======
            cur_timestamp = datetime.datetime.now(datetime.UTC)
>>>>>>> 5a9413b0fa62d0da139300e700982c414da05403
            try:
                elapsed_time_since_last_sms_sent = (cur_timestamp - LAST_SENT_TIMESTAMP[number]).seconds
                if elapsed_time_since_last_sms_sent < min_interval:
                    logger.info("Not sending an SMS since last SMS to {} was sent {} seconds ago, with minimum interval between sms being {}".format(number, elapsed_time_since_last_sms_sent, min_interval))
                    continue
            except KeyError:
                pass
<<<<<<< HEAD
        LAST_SENT_TIMESTAMP[number] = datetime.utcnow()
=======
        LAST_SENT_TIMESTAMP[number] = datetime.datetime.now(datetime.UTC)
>>>>>>> 5a9413b0fa62d0da139300e700982c414da05403
        logger.info("Received alert {} for number {}".format(title, number))
        parsed_sms_command = sms_command.replace("${NUMBER}", "'{}'".format(number))
        parsed_sms_command = parsed_sms_command.replace("${ALERT_MESSAGE}", "'{}'".format(alert_message))
        parsed_sms_command = parsed_sms_command.replace("${ALERT_MESSAGE_LEN}", str(alert_message_len))

        logger.info("sms_command: {}".format(parsed_sms_command))
        exit_code, output = command_runner(parsed_sms_command)
        if exit_code != 0:
            logger.error("Could not send SMS, code {}: {}".format(exit_code, output))
            raise HTTPException(
                status_code=400,
                detail="Cannot send text: {}".format(output),
            )
        logger.info("Sent SMS to {}".format(number))
