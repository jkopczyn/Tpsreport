from simple_salesforce import Salesforce
import config
import collections
import json

sf = Salesforce(username=config.username,
                password=config.password,
                security_token=config.security_token)

testresults = sf.query(
    "SELECT CaseNumber, (SELECT Field, OldValue, NewValue from Histories WHERE Field = 'Status') from Case where OwnerId = "
    + config.Maverick
    + " AND status = 'resolving internally'")

jsonresults = json.dumps(testresults, sort_keys=True, indent=4, separators=(',',': '))
#print jsonresults

parsedresults = json.loads(jsonresults)
for record in parsedresults["records"]:
    print record["CaseNumber"]
    for x in record["Histories"]["records"]:
        print x["NewValue"]