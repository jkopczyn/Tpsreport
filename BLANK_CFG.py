# You will also need logo.html, which is a mosaic table of your header logo.
# Presumably you could stick an image in there and make it fit,
# but I am not going to try because this is designed for email
# and email sucks at images.
# Once you've filled this out, rename it config.py
# SFDC user information:
username = "USERNAME"
password = "PASSWORD"
security_token = "SECURITYTOKEN"
# config values:
SFDCdaterange = 'THIS_WEEK'  # Valid SFDC/SOQL date range qualifier
reportrole = 'ROLE'  # the SFDC ID of the role we are looking for
sendMailTo = "RECIPIENTS"  # separated by semicolons
# Color values, used in order for bars:
# Outlook can't handle #ffffff, use #fafafa for pure white
textcolors = ["#fafafa", "#fafafa", "#000000", "#000000"]
colors = ["#000000", "#995c00", "#FF9900", "#FFB84D"]
headcolor = "#000000"  # header text color
# logo table colors:
# if logo.html includes {} replace strings,
# they must be defined in this dict, which will be used to format them.
logocolors = dict()
