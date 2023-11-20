# Grafana webhook to gammu smsd server

This (quick and dirty) tool allows to receive grafana alerts in webhook format, and transfer it's content to an SMS gateway.  
In our case, the SMS gateway will be `gammu-smsd` but any command line driven SMS gateway can be configured.

## Setup

Install and setup a python environment
```
cd /opt
git clone https://github.com/netinvent/grafana_webhook_gammu_smsd
python3 -m venv /opt/grafana_webhook_gammu_smsd/venv
/opt/grafana_webhook_gammu_smsd/venv/bin/python -m pip install -r /opt/grafana_webhook_gammu_smsd/requirements.txt
```

Configure the file `/opt/grafana_webhook_gammu_smsd/grafana_webhook_gammu_smsd.conf` according to your needs.  
By default, it's configured to use Gammu-smsd-inject command to send SMS. 

Setup the service
```
cp /opt/grafana_webhook_gammu_smsd/examples/systemd/grafana_webhook_gammu_smsd.service /etc/systemd/system/
systemctl enable grafana_webhook_gammu_smsd
systemctl start grafana_webhook_gammu_smsd
systemctl status grafana_webhook_gammu_smsd
```

At this point, you can configure Grafana's webhook. Send endpoint is `/grafana` 

![image](img/new_webhook_grafana_9.5.png)

The url will be `http(s)://your_server.tld/grafana/{phone_number}` where `{phone_number}` must be replaced with actual number, URL encoded if needed.  
HTTP method should be post, and HTTP Basic authentication should be enabled.  
Please also use this server behind a HTTPS reverse proxy for better security.

You may add multiple phone numbers by separating them with a semicolon, eg
`http(s)://your_server.tld/grafana/0123456789;0234567890;02345678901`

You may also limit the number of sent sms by setting a minimal interval between two sent smses.  
The url will be `http(s)://your_server.tld/grafana/{phone_number}/{min_interval}`
Example, in order to not receive more than a SMS every two hours (7200 seconds):

`http(s)://your_server.tld/grafana/0123456789;0234567890;02345678901/7200`


