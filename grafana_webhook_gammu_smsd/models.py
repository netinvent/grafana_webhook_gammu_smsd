#! /usr/bin/env python
#  -*- coding: utf-8 -*-
#
# This file is part of grafana_webhook_gammu_smsd

__intname__ = "grafana_webhook_gammu_smsd.server"
__author__ = "Orsiris de Jong"
__copyright__ = "Copyright (C) 2023-2024 NetInvent"
__license__ = "BSD-3 Clause"
__build__ = "2024030901"
__version__ = "1.1.0"


from pydantic import BaseModel
from typing import List, Optional

class Alert(BaseModel):
    status: str
    labels: dict
    annotations: dict
    startsAt: str
    endsAt: str
    generatorUrl: Optional[str] = None
    fingerprint: str
    silenceURL: str
    dashboardURL: Optional[str] = None
    panelURL: Optional[str] = None
    values: Optional[str] = None
    valueString: str

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
