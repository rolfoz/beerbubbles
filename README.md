This is a Python script that is designed to run on Termux on Android.
Using this you can turn an old phone into a wireless sensor that sends a count per minute of the bubbles coming from your homebrew.
I am using a pressure fermentation setup and I am bubbling the gas through and old juice bottle and the phone is taped to the side of the bottle.
It used the microphone to detect the bubbles and sends the count to HA via MQTT about once a minute.

#Get an old android phone
#install LineageOS on it
#Root it with Magisk
#Install Termux and Termux API and Termux Boot
#Give Termux root permissions (just sudo in it)
#Give Termux API all Andoid permissions
#pkg install python termux-api mosquitto
#pkg install tur-repo     # Adds the TUR repository
#pkg update               # Refresh package lists
#pkg install python-scipy # Installs scipy
#pkg install python-numpy

If you have issues, record a test audio file to make sure that the android permissions are allowing termux to record.
Then check the audio file to make sure it has bubbles in it.
You can get the command from within the Python script.
