#! /usr/bin/env python
#  -*- coding: utf-8 -*-
#
# This file is part of grafana_webhook_gammu_smsd

__intname__ = "grafana_webhook_gammu_smsd.server"
__author__ = "Orsiris de Jong"
__copyright__ = "Copyright (C) 2023 NetInvent"
__license__ = "BSD-3 Clause"
__build__ = "2023053001"
__version__ = "1.0.0"


from pydantic import BaseModel
from typing import List, Optional

class Alert(BaseModel):
    status: str
    labels: dict
    annotations: dict
    startsAt: str
    endsAt: str
    generatorUrl: Optional[str]
    fingerprint: str
    silenceURL: str
    dashboardURL: Optional[str]
    panelURL: Optional[str]
    values: Optional[str]
    valueString: str

class AlertMessage(BaseModel):
    receiver: Optional[str]
    status: str
    alerts: Alert
    groupLabels: dict
    commonLables: dict
    commonAnnotations: dict
    externalURL: str
    version: str
    groupKey: str
    truncatedAlerts: int
    orgId: int
    title: str
    state: str
    message: str