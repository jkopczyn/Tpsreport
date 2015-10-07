from simple_salesforce import Salesforce
import config
import json
import dateparser


class RFCReport:
    def __init__(self):
        self.sf = Salesforce(username=config.username,
                             password=config.password,
                             security_token=config.security_token)
        self.closerTeam = dict()
        self.caseData = None
        self.filteredCases = list()

    def jsonizer(self, rawdata):
        jsondata = json.dumps(
            rawdata,
            sort_keys=True,
            indent=4,
            separators=(',', ': ')
        )
        parsedata = json.loads(jsondata)
        return parsedata

    def getTeam(self):
        data = self.sf.query(
            ''.join((
                "SELECT Id ",
                "from User ",
                "where (UserRoleId = '00Ea0000001jJ6vEAE')"
            )))
        team = self.jsonizer(data)
        for member in team["records"]:
            rname = self.sf.User.get(member["Id"])
            jname = self.jsonizer(rname)
            name = jname["Name"]
            self.closerTeam[member["Id"]] = name

    def getData(self):
        data = self.sf.query(
            ''.join((
                "SELECT CaseNumber, Id, ",
                "(SELECT Field, NewValue ",
                "from Histories ",
                "WHERE Field = 'Owner') ",
                "from Case ",
                "where isClosed = True ",
                "and Type = 'support' ",
                "and ClosedDate = LAST_WEEK"
            )))
        self.caseData = self.jsonizer(data)

    def checkTeam(self):
        for record in self.caseData["records"]:
            if record["Histories"]:
                for x in record["Histories"]["records"]:
                    if x["NewValue"] in self.closerTeam:
                        print x["NewValue"], record["CaseNumber"]
                        self.filteredCases.append(
                            (self.closerTeam[x["NewValue"]],
                             record["CaseNumber"],
                             self.sf.query_all(
                                 ''.join((
                                     "SELECT Id, LastModifiedDate, ",
                                     "(SELECT NewValue, FieldName ",
                                     "from FeedTrackedChanges) ",
                                     "from CaseFeed ",
                                     "where ParentId = '",
                                     record["Id"], "'"
                                 )))))

    def genReport(self):
        for record in self.filteredCases:
            for change in record[2]["records"]:
                if change["FeedTrackedChanges"]["records"][0]["NewValue"] == \
                        "Ready For Close":
                    print "Name: ", record[0]
                    print "Case: ", record[1]
                    print "Status: Ready For Close"
                    print "Date: ", dateparser.parse(
                        change["LastModifiedDate"])


newreport = RFCReport()
newreport.getTeam()
newreport.getData()
newreport.checkTeam()
newreport.genReport()
