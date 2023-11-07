# set default time zone if one is not set
import pytz
tz = "UTC"

print(pytz.timezone(tz))

dtz = tz
display_tz = pytz.timezone(dtz)
print(display_tz)