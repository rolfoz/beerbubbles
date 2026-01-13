#!/data/data/com.termux/files/usr/bin/sh

su -c "setenforce 0"

# 1. Prevent CPU from sleeping
termux-wake-lock

# 2. Load the Termux environment (THIS IS THE KEY FIX)
. /data/data/com.termux/files/usr/etc/profile

# 3. Start SSH
sshd

# Granting standard Android Runtime Permissions
su -c "pm grant com.termux android.permission.RECORD_AUDIO"
su -c "pm grant com.termux.api android.permission.RECORD_AUDIO"

# Granting AppOps (The lower-level system that often blocks background apps)
su -c "appops set com.termux RECORD_AUDIO allow"
su -c "appops set com.termux.api RECORD_AUDIO allow"

# Specifically allowing "Project Media" and background starts
su -c "appops set com.termux PROJECT_MEDIA allow"
su -c "appops set com.termux.api PROJECT_MEDIA allow"
su -c "cmd deviceidle whitelist +com.termux"
su -c "cmd deviceidle whitelist +com.termux.api"

# 4. Clear any stuck microphone sessions from a failed boot
termux-microphone-record -q


#wait for audio to settle
sleep 15

# 4. Start the script using the ABSOLUTE path to python
# Also redirect errors to a log file so we can see why it fails
/data/data/com.termux/files/usr/bin/python ~/gbub.py > ~/bubble_log.txt 2>&1 &
