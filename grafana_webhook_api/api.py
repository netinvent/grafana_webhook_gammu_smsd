#! /usr/bin/env python
#  -*- coding: utf-8 -*-
#
# This file is part of grafana_webhook_smsd

__intname__ = "grafana_webhook_api.api"
__author__ = "Orsiris de Jong"
__copyright__ = "Copyright (C) 2023-2026 NetInvent"
__license__ = "BSD-3 Clause"
__build__ = "2026013101"
__version__ = "2.0.0"
__appname__ = "Grafana Alerts to commands"


from typing import Optional
import logging
import secrets
from argparse import ArgumentParser
from fastapi import FastAPI, HTTPException, Depends, status, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi_offline import FastAPIOffline
from grafana_webhook_api import configuration
from grafana_webhook_api.models import AlertMessage, Message
from grafana_webhook_api.sms import send_sms

# Make sure we load given config files again
parser = ArgumentParser()
parser.add_argument(
    "-c",
    "--config-file",
    dest="config_file",
    type=str,
    default=None,
    required=False,
    help="Path to grafana_webhook_api.conf file",
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
    exc_str = f"{exc}".replace("\n", " ").replace("   ", " ")
    logging.error(f"{request}: {exc_str}")
    content = {"status_code": 422, "message": exc_str, "data": None}
    return JSONResponse(
        content=content, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY
    )


@app.get("/")
async def api_root(auth=Depends(get_current_username)):
    return {"app": __appname__}


@app.post("/grafana/{numbers}")
@app.post("/grafana/{numbers}/{min_interval}")
@app.post("/grafana/{numbers}/{min_interval}/{group}")
async def grafana(
    numbers: str,
    min_interval: Optional[int] = None,
    group: Optional[str] = "yes",
    alert: AlertMessage = None,
    auth=Depends(auth_scheme),
):
    global LAST_SENT_TIMESTAMP

    if not numbers:
        raise HTTPException(status_code=404, detail="No phone number set")

    if not alert or not alert.message:
        raise HTTPException(status_code=404, detail="No alert set")
    logger.debug(f"Alert\n{alert}")

    # Multiple numbers with ';' are accepted
    numbers = numbers.split(";")

    # Escape single quotes here so we will stay in line
    try:
        title = alert.title.replace("'", r"-")
    except KeyError:
        title = ""

    try:
        orgId = str(alert.orgId).replace("'", r"-")
    except (KeyError, AttributeError, ValueError, TypeError):
        orgId = ""

    try:
        externalURL = alert.externalURL.replace("'", r"-")
    except KeyError:
        externalURL = ""

    try:
        message = alert.message.replace("'", r"-")
    except KeyError:
        message = ""

    try:
        supervision_name = config_dict["supervision_name"]
    except KeyError:
        supervision_name = "Supervision"

    try:
        extracted_alerts = {}
        # Alert may not contain sub alerts
        try:
            for i in range(0, len(alert.alerts)):
                """
                try:
                    extracted_alerts[i] = "Alert: {}\n".format(
                        alert.alerts[i].labels["alertname"]
                    )
                except KeyError:
                    pass
                try:
                    extracted_alerts[i] += "Rule: {}\n".format(
                        alert.alerts[i].labels["rulename"]
                    )
                except KeyError:
                    pass
                try:
                    extracted_alerts[i] += "Instance: {}\n".format(
                        alert.alerts[i].labels["instance"]
                    )
                except KeyError:
                    pass
                try:
                    extracted_alerts[i] += "Job: {}\n".format(
                        alert.alerts[i].labels["job"]
                    )
                except KeyError:
                    pass
                """
                extracted_alerts[i] = f"ALERT {alert.alerts[i].status}:\n"
                for label, content in alert.alerts[i].labels.items():
                    extracted_alerts[i] += f"- {label}={content}\n"
                if extracted_alerts[i] is None:
                    extracted_alerts[i] = f"Cannot parse alert. See {__appname__} code"
        except (KeyError, AttributeError, TypeError, IndexError) as exc:
            logger.debug(f"Sub alert message extraction failed: {exc}", exc_info=True)

        # Preflight check
        try:
            config_dict["sms_command"]
        except KeyError:
            logger.error("No sms commandline tool defined")
            raise HTTPException(status_code=500, detail="Server not configured")

        alert_header = "{} org {}: {}".format(
            supervision_name, orgId, title
        )
        if extracted_alerts:
            alert_message = alert_header
            for i in range(0, len(extracted_alerts)):
                alert_message += f"\n{extracted_alerts[i]}"
        else:
            alert_message = alert_header + f"\n{message}"

        # Send alerts
        for number in numbers:
            number = number.replace("'", r"-")
            logger.info("Received alert {} for number {}".format(title, number))
            result = send_sms(number, alert_message)
            if not result:
                content = {
                    "status_code": 402,
                    "message": "Cannot send text to: {}".format(number),
                    "data": None,
                }
                return JSONResponse(
                    content=content, status_code=status.HTTP_402_PAYMENT_REQUIRED
                )
            content = {
                "status_code": 200,
                "message": "Message sent to: {}".format(number),
                "data": None,
            }
            return JSONResponse(content=content, status_code=status.HTTP_200_OK)

    except Exception as exc:
        exc_str = f"Exception {exc} occured"
        logger.error(exc_str, exc_info=True)
        raise HTTPException(status_code=500, detail=exc_str)


@app.post("/send/{numbers}")
async def grafana(numbers: str, message: Message = None, auth=Depends(auth_scheme)):

    if not numbers:
        raise HTTPException(status_code=404, detail="No phone number set")
    if not message:
        raise HTTPException(status_code=404, detail="No message set")
    if not message.message:
        raise HTTPException(status_code=404, detail="No message content")

    try:
        logger.debug(f"Message: {message}")
        # Multiple numbers with ';' are accepted
        numbers = numbers.split(";")
        for number in numbers:
            number = number.replace("'", r"-")
            logger.info("Received direct send request for number {}".format(number))
            result = send_sms(number, message.message)
            if not result:
                content = {
                    "status_code": 402,
                    "message": "Cannot send text to: {}".format(number),
                    "data": None,
                }
                return JSONResponse(
                    content=content, status_code=status.HTTP_402_PAYMENT_REQUIRED
                )
            content = {
                "status_code": 200,
                "message": "Message sent to: {}".format(number),
                "data": None,
            }
            return JSONResponse(content=content, status_code=status.HTTP_200_OK)
    except Exception as exc:
        exc_str = f"Exception {exc} occured"
        logger.error(exc_str, exc_info=True)
        raise HTTPException(status_code=500, detail=exc_str)
