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
        self.filteredCases = list()
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
        print "Querying Tier 2 team members..."
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
            "cases in", config.SFDCdaterange

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
        print "Found", len(subquery), "T2-involved cases."
        print "Querying case details."
        sqsplit = len(subquery)/2
        squeries = (subquery[:sqsplit], subquery[sqsplit+1:])
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
            self.filteredCases.append(result)
        self.filteredCases = self.jsonizer(self.filteredCases)
        print "Found", self.filteredCases["totalSize"], "histories."

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
