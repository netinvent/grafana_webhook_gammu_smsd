#! /usr/bin/env python
#  -*- coding: utf-8 -*-
#
# This file is part of grafana_webhook_smsd

__intname__ = "grafana_webhook_api.api"
__author__ = "Orsiris de Jong"
__copyright__ = "Copyright (C) 2023-2026 NetInvent"
__license__ = "BSD-3 Clause"
__build__ = "2026013001"
__version__ = "2.0.0"
__appname__ = "Grafana Alerts to commands"


from typing import Optional
from command_runner import command_runner
import logging
import secrets
from datetime import datetime, timezone
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
@app.post("/grafana/{numbers}/{min_interval}/{group}")
async def grafana(numbers: str, min_interval: Optional[int] = None, group: Optional[str] = "yes", alert: AlertMessage = None, auth=Depends(auth_scheme)):
    try:

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
        logger.debug(f"Alert\n{alert}")

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

        try:
            alert_max_length = config_dict["alert_max_length"]
        except KeyError:
            alert_max_length = 2500

        try:
            hard_min_interval = config_dict["min_interval"]
        except KeyError:
            hard_min_interval = None

        #timestr = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        #alert_message = '{} org {} {}:\n{}\n{}'.format(supervision_name, orgId, timestr, title, message)
        alert_header = '{} org {}:\n{}\n{}'.format(supervision_name, orgId, title, message)

        extracted_alerts = []
        # Alert may not contain sub alerts
        try:
            for i in range(0, len(alert.alerts)):
                try:
                    extracted_alerts[i] = "Alert: {}\n".format(alert.alerts[i].labels["alertname"])
                except KeyError:
                    pass
                try:
                    extracted_alerts[i] += "Rule: {}\n".format(alert.alerts[i].labels["rulename"])
                except KeyError:
                    pass
                try:
                    extracted_alerts[i] += "Instance: {}\n".format(alert.alerts[i].labels["instance"])
                except KeyError:
                    pass
                try:
                    extracted_alerts[i] += "Job: {}\n".format(alert.alerts[i].labels["job"])
                except KeyError:
                    pass
                if extracted_alerts[i] is None:
                    extracted_alerts[i] = f"Cannot parse alert. See {__appname__} code"
        except (KeyError, AttributeError, TypeError, IndexError):
            pass

        # Preflight check
        try:
            sms_command = config_dict["sms_command"]
        except KeyError:
            logger.error("No sms commandline tool defined")
            raise HTTPException(
                status_code=500,
                detail="Server not configured"
            )

        alert_message = alert_header
        for i in range(0, len(extracted_alerts)):
            alert_message += f'\n{extracted_alerts[i]}'

        # Reduce alert to a specific length
        alert_message_len = len(alert_message)
        if alert_message_len > alert_max_length:
            alert_message = alert_message[0:alert_max_length]
            alert_message_len = len(alert_message)

        # Send alerts
        for number in numbers:
            number = number.replace("'", r"-")
            if min_interval:
                cur_timestamp = datetime.now(timezone.utc)

                try:
                    elapsed_time_since_last_sms_sent = (cur_timestamp - LAST_SENT_TIMESTAMP[number]["date"]).seconds
                    if elapsed_time_since_last_sms_sent < min_interval:
                        logger.info("Not sending an SMS since last SMS to {} was sent {} seconds ago, with minimum interval between sms being {}".format(number, elapsed_time_since_last_sms_sent, min_interval))
                        continue

                except KeyError:
                    pass
            LAST_SENT_TIMESTAMP[number] = {
                "date": datetime.now(timezone.utc)
            }

            #if HAS_ALERTS:
            #    LAST_SENT_TIMESTAMP[number]["labels"] = str(alert.alerts[i].labels)

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
    except Exception as exc:
        exc_str = f"Exception {exc} occured"
        logger.error(exc_str, exc_info=True)
        raise HTTPException(
                status_code=500,
                detail=exc_str
            )
