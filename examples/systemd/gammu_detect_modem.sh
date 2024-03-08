#!/usr/bin/env bash

# This script updates /etc/gammu-smsdrc file with first detected modem
# Written in 2022-2024 by Orsiris de Jong - NetInvent
SCRIPTVER=2024030801


log_file="/var/log/modem_update.log"
gammu_config_file="/etc/gammu-smsdrc"
modem=""

# gammu_srv
gammu_service="gammu-smsd"
# Optional command when modem port change detected
optional_cmd="systemctl restart ${gammu-smsd}"

function log {
    line="${1}"

    echo "${line}" >> "${log_file}"
    echo "${line}"
}


if ! type picocom > /dev/null 2>1; then
    log "No picocom available"
    exit 1
fi

systemctl stop ${gammu_service}

for tty in $(ls /dev/ttyUSB*); do
    log "Checking $tty"
    picocom -qrX -b 9600 $tty
    sleep 1
    result=$(echo "AT&F" | picocom -qrix 1000 $tty)
    if [ "${result}" = "AT&F" ]; then
        log "Found AT compatible modem at $tty"
        modem="${tty}"
    fi
done

curr_gammu_modem=$(cat "${gammu_config_file}" | grep -e "^device = " | awk -F'=' '{gsub(/ /,""); print $2}')
if [ "${modem}" != "" ]; then
    if [ "${modem}" != "${curr_gammu_modem}" ]; then
        log "Updating modem from ${curr_gammu_modem} to ${modem}"
        sed -i "s%\#\?\device \?=.*%\device = ${modem}%g" "${gammu_config_file}"
        #if [ "${optional_cmd}" != "" ]; then
        #    log "Running ${optional_cmd}"
        #    ${optional_cmd} >> "${log_file}"
        #    if [ $? -ne 0 ]; then
        #        log "Could not restart service, exitcode: $?"
        #    fi
        #fi
    fi
else
    log "No usable modem found."
fi

systemctl start ${gammu_service}
