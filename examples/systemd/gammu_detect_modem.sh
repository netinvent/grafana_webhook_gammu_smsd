#!/usr/bin/env bash

# This script updates /etc/gammu-smsdrc file with first detected USB modem
# Really quick and dirty (TM) 2022-2026 Orsiris de Jong - ozy [at] netpower dot fr
SCRIPTVER=2026013001

log_file="/var/log/modem_update.log"
gammu_config_file="/etc/gammu-smsdrc"
modem=""

# gammu service
gammu_service="gammu-smsd"
# Optional command when modem port change detected
optional_cmd=""

function log {
    line="${1}"

    echo "${line}" >> "${log_file}"
    echo "${line}"
}


if ! type picocom > /dev/null 2&>1; then
    log "No picocom available"
    exit 1
fi

# Stop gammu before trying to discuss with modem
systemctl stop ${gammu_service}

for tty in $(ls /dev/ttyUSB*); do
    log "Checking $tty"
    picocom -qrX -b 9600 $tty
    sleep 1
    result=$(echo "AT&F" | picocom -qrix 1000 $tty)
    case $result in
        *"AT&F"*)
        log "Found AT compatible modem at $tty"
        modem="${tty}"
        ;;
    esac
done

curr_gammu_modem=$(cat "${gammu_config_file}" | grep -e "^device = " | awk -F'=' '{gsub(/ /,""); print $2}')
if [ "${modem}" != "" ]; then
    if [ "${modem}" != "${curr_gammu_modem}" ]; then
        log "Updating modem from ${curr_gammu_modem} to ${modem}"
        sed -i "s%\#\?\device \?=.*%\device = ${modem}%g" "${gammu_config_file}"
        if [ "${optional_cmd}" != "" ]; then
            log "Running ${optional_cmd}"
            ${optional_cmd} >> "${log_file}" 2>&1
            if [ $? -ne 0 ]; then
                log "Optional command failed with exitcode: $?"
            fi
        fi
    fi

else
    log "No usable modem found."
fi

systemctl start ${gammu_service}
