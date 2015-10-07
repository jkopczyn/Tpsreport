from simple_salesforce import Salesforce
import config
import json
import dateparser

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
                     record["CaseNumber"],
                    sf.query_all(
                        ''.join((
                            "SELECT Id, LastModifiedDate, ",
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

tier2parsed = json.loads(tier2json)

for record in tier2parsed:
    for change in record[2]["records"]:
        if change["FeedTrackedChanges"]["records"][0]["NewValue"] == \
            "Ready For Close":
                print "Name: ", record[0]
                print "Case: ", record[1]
                print "Status: Ready For Close"
                print "Date: ", dateparser.parse(
                        change["LastModifiedDate"])