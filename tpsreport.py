from simple_salesforce import Salesforce
import config
import json

sf = Salesforce(username=config.username,
                password=config.password,
                security_token=config.security_token)

testresults = sf.query(
    ''.join(
        (
            "SELECT CaseNumber, Id, ",
            "(SELECT Field, NewValue ",
            "from Histories ",
            "WHERE Field = 'Owner') ",
            "from Case ",
            "where isClosed = True ",
            "and Type = 'support' ",
            "and ClosedDate = LAST_WEEK"
        )
    )
)

jsonresults = json.dumps(
    testresults,
    sort_keys=True,
    indent=4,
    separators=(',', ': ')
)

parsedresults = json.loads(jsonresults)
print parsedresults['totalSize']

tier2only = list()

for record in parsedresults["records"]:
    if record["Histories"]:
        for x in record["Histories"]["records"]:
            if x["NewValue"] in config.Closers:
                print x["NewValue"], record["CaseNumber"]
                tier2only.append(
                    (config.Closers[x["NewValue"]],
                    sf.query_all(
                        ''.join((
                            "SELECT Title, LastModifiedDate, ",
                            "(SELECT NewValue, FieldName ",
                            "from FeedTrackedChanges) ",
                            "from CaseFeed ",
                            "where ParentId = '",
                            record["Id"], "'"
                     )))))

tier2json = json.dumps(
    tier2only,
    sort_keys=True,
    indent=4,
    separators=(',', ': ')
)

print tier2json