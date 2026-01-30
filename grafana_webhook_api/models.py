#! /usr/bin/env python
#  -*- coding: utf-8 -*-
#
# This file is part of grafana_webhook_api

__intname__ = "grafana_webhook_api.server"
__author__ = "Orsiris de Jong"
__copyright__ = "Copyright (C) 2023-2024 NetInvent"
__license__ = "BSD-3 Clause"
__build__ = "2024030901"
__version__ = "1.2.0"

"""
These models were tested on Grafana 9x and 10x alerts.
"""


from pydantic import BaseModel
from typing import List, Optional, Any


class Alert(BaseModel):
    status: Optional[str] = None
    labels: dict
    annotations: dict
    startsAt: Optional[str] = None
    endsAt: Optional[str] = None
    generatorUrl: Optional[str] = None
    fingerprint: Optional[str] = None
    silenceURL: Optional[str] = None
    dashboardURL: Optional[str] = None
    panelURL: Optional[str] = None
    values: Any = None
    valueString: Optional[str] = None


class AlertMessage(BaseModel):
    receiver: Optional[str] = None
    status: str
    alerts: List[Alert]
    groupLabels: Optional[dict] = None
    commonLabels: Optional[dict] = None
    commonAnnotations: Optional[dict] = None
    externalURL: str
    version: str
    groupKey: str
    truncatedAlerts: int
    orgId: int
    title: str
    state: str
    message: str


class Message(BaseModel):
    message: Optional[str] = None
