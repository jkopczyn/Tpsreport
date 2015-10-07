from simple_salesforce import Salesforce
import config
import json
import dateparser


class RFCReport:
    def __init__(self):
        print "Logging in to Salesforce API..."
        self.sf = Salesforce(username=config.username,
                             password=config.password,
                             security_token=config.security_token)
        self.closerTeam = dict()
        self.caseData = None
        self.filteredCases = None
        self.reportData = list()
        self.summaryReport = dict()
        print "Login successful."

    def jsonizer(self, rawdata):
        jsondata = json.dumps(
            rawdata,
            sort_keys=True,
            indent=4,
            separators=(',', ': ')
        )
        return jsondata

    def getTeam(self):
        print "Querying Escalations team members..."
        data = self.sf.query(
            ''.join((
                "SELECT Id ",
                "from User ",
                "where UserRoleId = '",
                config.reportrole, "'"
            )))
        team = json.loads(self.jsonizer(data))
        for member in team["records"]:
            rname = self.sf.User.get(member["Id"])
            jname = json.loads(self.jsonizer(rname))
            name = jname["Name"]
            self.closerTeam[member["Id"]] = name
        print "Found", len(self.closerTeam), "team members."

    def getData(self):
        print "Querying SFDC cases in", config.SFDCdaterange, "..."
        data = self.sf.query_all(
            ''.join((
                "SELECT CaseNumber, Id, ",
                "(SELECT Field, NewValue ",
                "from Histories ",
                "WHERE Field = 'Owner') ",
                "from Case ",
                "where (Status = 'Closed' or ",
                "Status = 'Ready For Close') ",
                "and Type = 'support' ",
                "and LastModifiedDate = ",
                config.SFDCdaterange
            )))
        self.caseData = json.loads(self.jsonizer(data))
        print "Got", self.caseData["totalSize"], \
            "rows in", config.SFDCdaterange

    def genReport(self, data):
        for change in data["records"]:
            if change["InsertedById"] not in self.closerTeam:
                continue
            for line in change["FeedTrackedChanges"]["records"]:
                if line["NewValue"] in ("Ready For Close", "Closed"):
                    self.reportData.append(
                        dict(Name=self.closerTeam[change["InsertedById"]],
                             Case=change["ParentId"],
                             Status=line["NewValue"],
                             Date=dateparser.parse(change["CreatedDate"])))

    def checkTeam(self):
        subquery = list()
        for record in self.caseData["records"]:
            if record["Histories"]:
                for x in record["Histories"]["records"]:
                    if x["NewValue"] in self.closerTeam:
                        name = self.closerTeam[x["NewValue"]]
                        casenum = record["CaseNumber"]
                        caseid = record["Id"]
                        subquery.append(caseid)
        print "Found", len(subquery), "Escalations-involved cases."
        print "Querying case details."
        sqsplit = len(subquery) / 2
        squeries = (subquery[:sqsplit], subquery[sqsplit + 1:])
        for each in squeries:
            newsquery = "','".join(each)
            newsquery = "('" + newsquery + "')"
            result = self.sf.query_all(
                ''.join((
                    "SELECT InsertedById, CreatedDate, "
                    "ParentID, ",
                    "(SELECT NewValue, FieldName ",
                    "from FeedTrackedChanges) ",
                    "from CaseFeed ",
                    "where ParentId IN ",
                    newsquery,
                    " and CreatedDate = ",
                    config.SFDCdaterange
                )))
            # print self.jsonizer(result)
            self.genReport(json.loads(self.jsonizer(result)))

    def sumReport(self):
        self.summaryReport["CaseCount"] = dict()
        self.summaryReport["ClosedCount"] = dict()
        self.summaryReport["RFCCount"] = dict()

        for case in self.reportData:
            if case["Name"] not in self.summaryReport["CaseCount"]:
                self.summaryReport["CaseCount"][case["Name"]] = set()
                self.summaryReport["ClosedCount"][case["Name"]] = set()
                self.summaryReport["RFCCount"][case["Name"]] = set()
            self.summaryReport["CaseCount"][case["Name"]].add(case["Case"])
            if case["Status"] == "Closed":
                self.summaryReport[
                    "ClosedCount"][case["Name"]].add(case["Case"])
            if case["Status"] == "Ready For Close":
                self.summaryReport[
                    "RFCCount"][case["Name"]].add(case["Case"])

    def printReport(self):
        for each in self.summaryReport["CaseCount"]:
            print each
            print len(self.summaryReport["CaseCount"][each]), "cases handled"
            print len(self.summaryReport["ClosedCount"][each]), "Closed cases"
            print len(self.summaryReport["RFCCount"][each]), "cases marked " \
                                                             "Ready for Close"

newreport = RFCReport()
newreport.getTeam()
newreport.getData()
# print newreport.jsonizer(newreport.caseData)
newreport.checkTeam()
# print newreport.reportData
newreport.sumReport()
newreport.printReport()
