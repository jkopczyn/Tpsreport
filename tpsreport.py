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
        return jsondata

    def getTeam(self):
        data = self.sf.query(
            ''.join((
                "SELECT Id ",
                "from User ",
                "where (UserRoleId = '00Ea0000001jJ6vEAE')"
            )))
        team = json.loads(self.jsonizer(data))
        for member in team["records"]:
            rname = self.sf.User.get(member["Id"])
            jname = json.loads(self.jsonizer(rname))
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
                "where (Status = 'Closed' or ",
                "Status = 'Ready For Close') ",
                "and Type = 'support' ",
                "and LastModifiedDate = LAST_WEEK"
            )))
        self.caseData = json.loads(self.jsonizer(data))

    def checkTeam(self):
        for record in self.caseData["records"]:
            if record["Histories"]:
                for x in record["Histories"]["records"]:
                    if x["NewValue"] in self.closerTeam:
                        print x["NewValue"], record["CaseNumber"]
                        self.filteredCases.append(
                            (self.sf.query_all(
                                ''.join((
                                    "SELECT InsertedById, CreatedDate, "
                                    "ParentID, ",
                                    "(SELECT NewValue, FieldName ",
                                    "from FeedTrackedChanges) ",
                                    "from CaseFeed ",
                                    "where ParentId = '",
                                    record["Id"], "'"
                                )))))

    def genReport(self):
        for record in self.filteredCases:
            for change in record["records"]:
                if change["InsertedById"] not in self.closerTeam:
                    break
                for line in change["FeedTrackedChanges"]["records"]:
                    if line["NewValue"] in ("Ready For Close", "Closed"):
                        print "Name: ", self.closerTeam[
                            change["InsertedById"]]
                        print "Case: ", change["ParentId"]
                        print "Status: ", line["NewValue"]
                        print "Date: ", dateparser.parse(
                            change["CreatedDate"])


newreport = RFCReport()
newreport.getTeam()
newreport.getData()
newreport.checkTeam()
#print newreport.jsonizer(newreport.filteredCases)
newreport.genReport()
