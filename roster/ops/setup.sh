#!/usr/bin/env bash
# One-time VM setup for the roster recorder (task 0.1). Ubuntu 24.04 on an Oracle Always Free Arm VM.
# Review before running as root; this file is not executed by the build. It contains no secrets.
set -euo pipefail

ROSTER=/srv/roster

# --- Block volume for recordings (150 GB), attached in the OCI console as paravirtualized ---
# lsblk                                   # find the new disk, e.g. /dev/sdb
# mkfs.ext4 -L recordings /dev/sdb        # first time only: destroys anything on it
# mkdir -p $ROSTER/data/recordings
# echo 'LABEL=recordings /srv/roster/data/recordings ext4 defaults,noatime,_netdev,nofail 0 2' >> /etc/fstab
# mount -a && df -h $ROSTER/data/recordings

# --- Users: recorder now; trader and advisor are created now so later phases only add services ---
# recorder gets a real shell (key-only, no password) because the home PC pulls the nightly rsync over SSH.
id recorder >/dev/null 2>&1 || useradd --system --create-home --shell /bin/bash recorder
for u in trader advisor; do
  id "$u" >/dev/null 2>&1 || useradd --system --create-home --shell /usr/sbin/nologin "$u"
done

# --- Packages: chrony for time sync (receive timestamps must be trustworthy), python, rsync ---
apt-get update
apt-get install -y chrony python3 python3-venv rsync
systemctl enable --now chrony
chronyc tracking

# --- Code and data directories (copy the roster folder to $ROSTER first, e.g. with rsync or git) ---
mkdir -p $ROSTER/data/recordings $ROSTER/data/markets $ROSTER/data/logs
chown -R recorder:recorder $ROSTER/data
python3 -m venv $ROSTER/.venv
$ROSTER/.venv/bin/pip install -r $ROSTER/requirements.txt

# --- Services ---
install -m 0644 $ROSTER/ops/roster-recorder.service /etc/systemd/system/roster-recorder.service
install -m 0644 $ROSTER/ops/roster.cron /etc/cron.d/roster
systemctl daemon-reload
systemctl enable --now roster-recorder
systemctl status roster-recorder --no-pager

# --- Nightly copy to the home PC: see the home-PC line at the bottom of ops/roster.cron. ---
# Put the home PC's *public* key in ~recorder/.ssh/authorized_keys (chmod 600, owned by recorder).
