from simple_salesforce import Salesforce
import config

sf = Salesforce (username=config.username,
                 password=config.password,
                 security_token=config.security_token)

testresults = sf.query(
    "SELECT CaseNumber from Case where OwnerId = "
    + config.Maverick
    + " AND status = 'resolving internally'")

print testresults