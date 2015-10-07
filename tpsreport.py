from simple_salesforce import Salesforce
import config
import json
import dateparser
import random
from frozendict import frozendict


class TeamMember:
    def __init__(self, name):
        self.name = name
        self.caseCount = set()
        self.rfcCount = set()
        self.closedCount = set()


class RFCReport:
    def __init__(self):
        print "Logging in to Salesforce API..."
        # initialize our SFDC connection
        self.sf = Salesforce(username=config.username,
                             password=config.password,
                             security_token=config.security_token)
        self.closerTeam = dict()
        self.listedUsers = dict()
        self.caseData = None
        self.filteredCases = None
        self.reportData = dict()
        self.dupecount = 0
        print "Login successful."

    def jsonizer(self, rawdata):
        # pretty prints SOQL dumps.
        # Run through this and then json.loads() to smooth data.
        jsondata = json.dumps(
            rawdata,
            sort_keys=True,
            indent=4,
            separators=(',', ': ')
        )
        return jsondata

    def getTeam(self):
        # figure out who we're interested in based on SFDC role
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
        # initial data set query
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
        # scrub data to reportable dict form
        for change in data["records"]:
            if change["InsertedById"] not in self.closerTeam:
                continue
            for line in change["FeedTrackedChanges"]["records"]:
                if line["NewValue"] in ("Ready For Close", "Closed"):
                    caseid = change["ParentId"]
                    changedate = dateparser.parse(change["CreatedDate"])
                    # need to account for more than one t2 on a case
                    if caseid in self.reportData:
                        # chronological order - latest gets it
                        if self.reportData[caseid]["Date"] > changedate:
                            self.dupecount += 1
                            continue
                    self.reportData[caseid] = frozendict(
                        Name=self.closerTeam[change["InsertedById"]],
                        Case=caseid,
                        Status=line["NewValue"],
                        Date=changedate)

    def checkTeam(self):
        # look for cases our team was involved in
        subquery = set()
        for record in self.caseData["records"]:
            if record["Histories"]:
                for x in record["Histories"]["records"]:
                    if x["NewValue"] in self.closerTeam:
                        name = self.closerTeam[x["NewValue"]]
                        casenum = record["CaseNumber"]
                        caseid = record["Id"]
                        subquery.add(caseid)
        print "Found", len(subquery), "unique Escalations-involved cases."
        print "Querying case details..."
        # list of cases is too large for SOQL query, split it
        sqsplit = len(subquery) / 2
        set1 = set(random.sample(subquery, sqsplit))
        subquery -= set1
        squeries = (set1, subquery)
        # run each split query, scrub each into reports
        print "Filtering and de-duplicating..."
        for each in squeries:
            newsquery = "','".join(each)
            newsquery = "('" + newsquery + "')"
            # structure query that pulls all TrackedChanges for case IDs
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
            self.genReport(json.loads(self.jsonizer(result)))
        print "Found and removed", self.dupecount, "cases handled twice."

    def sumReport(self):
        # generate summaries of data
        print "Generating summaries..."
        for case in self.reportData.itervalues():
            name = case["Name"]
            casenum = case["Case"]
            if name not in self.listedUsers:
                self.listedUsers[name] = TeamMember(name)
            nameobj = self.listedUsers[name]
            nameobj.caseCount.add(case)
            if case["Status"] == "Ready For Close":
                nameobj.closedCount.discard(case)
                nameobj.rfcCount.add(case)
            if case["Status"] == "Closed":
                nameobj.closedCount.add(case)
                nameobj.rfcCount.discard(case)

    def printReport(self):
        # print the results
        print "Reticulating splines..."
        for each in self.listedUsers.itervalues():
            print each.name
            print len(each.caseCount), "cases handled"
            print len(each.closedCount), "Closed cases"
            print len(each.rfcCount), "cases marked Ready for Close"


if __name__ == "__main__":
    # main execution steps
    newreport = RFCReport()
    newreport.getTeam()
    newreport.getData()
    # print newreport.jsonizer(newreport.caseData)
    newreport.checkTeam()
    # print newreport.reportData
    newreport.sumReport()
    newreport.printReport()
