#! /usr/bin/env python
#  -*- coding: utf-8 -*-
#
# This file is part of grafana_webhook_gammu_smsd

__intname__ = "grafana_webhook_gammu_smsd.api"
__author__ = "Orsiris de Jong"
__copyright__ = "Copyright (C) 2023 NetInvent"
__license__ = "BSD-3 Clause"
__build__ = "2023053001"
__version__ = "1.0.0"


from command_runner import command_runner
import logging
import secrets
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
    help="Path to upgrade_server.conf file",
)
args = parser.parse_args()
if args.config_file:
    config_dict = configuration.load_config(args.config_file)
else:
    config_dict = configuration.load_config()

logger = logging.getLogger()


app = FastAPIOffline()
security = HTTPBasic()


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


@app.get("/")
async def api_root(auth=Depends(get_current_username)):
    return {"app": __appname__}

@app.post("/sms/{number}")
async def sms(number: str, alert: AlertMessage):

    if not number:
        raise HTTPException(
            status_code=404,
            detail="No number set"
        )
    
    if not alert['message']:
        raise HTTPException(
            stats_code=404,
            detial="No alert set"
        )
    
    try:
        title = alert['title']
    except KeyError:
        title = ''

    try:
        orgId = alert['orgId']
    except KeyError:
        orgId = ''
    
    try:
        externalURL = alert['externalURL']
    except KeyError:
        externalURL = ''

    try:
        message: alert['message']
    except KeyError:
        message = ''

    alert_message = 'Alert from {} (org {}): {} - {}'.format(externalURL, orgId, title, message)

    exit_code, output = command_runner("gammu-smsd-inject TEXT '{}' -text '{}'".format(number, message))
    if exit_code != 0:
        raise HTTPException(
            status_code=400,
            detail="Cannot send text: {}".format(output),
        )

