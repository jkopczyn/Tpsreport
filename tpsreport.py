from __future__ import division
from simple_salesforce import Salesforce
import config
import json
import dateparser
import random
from frozendict import frozendict
import win32com.client


def fileToStr(fileName):
    """Return a string containing the contents of the named file."""
    fin = open(fileName)
    contents = fin.read()
    fin.close()
    return contents


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
        self.message = ""
        self.logoimage = config.logo
        self.fulltable = ''
        self.oldestdate = None
        self.newestdate = None
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
        # note: currently this pulls all cases that are READY FOR CLOSE
        # or CLOSED and were last modified since the beginning of the target
        # date range, including days since then but NOT in that range.
        # The intent of this is that we will capture stuff we sent down on
        # the last days of the range that the agent had to do some follow-up
        # on. However as time passes from the range the number of uncaught
        # duplicates will increase as cases from the specified period get
        # reopened and reescalated.
        print "Querying all Support SFDC cases since start of", \
            config.SFDCdaterange, "..."
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
                "and LastModifiedDate >= ",
                config.SFDCdaterange
            )))
        self.caseData = json.loads(self.jsonizer(data))
        lengthset = set()
        for change in data["records"]:
            lengthset.add(change["Id"])
        totalcase = len(lengthset)
        print "Got", totalcase, "total closed/RFC Support cases."

    def genReport(self, data):
        # scrub data to reportable dict form
        for change in data["records"]:
            if change["InsertedById"] not in self.closerTeam:
                continue
            for line in change["FeedTrackedChanges"]["records"]:
                if line["NewValue"] in ("Ready For Close", "Closed"):
                    caseid = change["ParentId"]
                    changedate = dateparser.parse(change["CreatedDate"])
                    if self.oldestdate is None:
                        self.oldestdate = changedate
                    if self.newestdate is None:
                        self.newestdate = changedate
                    if changedate > self.newestdate:
                        self.newestdate = changedate
                    if changedate < self.oldestdate:
                        self.oldestdate = changedate
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
        sqsplit = int(len(subquery) / 2)
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
        print "Found and removed", self.dupecount, "cases handled more than " \
                                                   "once."
        print "Credit for duplicates given to latest resolver."

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
        sorted_list = sorted(self.listedUsers.itervalues(),
                             key=lambda x: len(x.caseCount), reverse=True)
        cMax = len(sorted_list[0].caseCount)
        for each in sorted_list:
            agentname = each.name
            cases = len(each.caseCount)
            casesadj = int((cases / cMax) * 400)
            if casesadj == 400:
                casesadj = 390
            casesrem = 400 - casesadj
            rfcs = len(each.rfcCount)
            rfcsadj = int((rfcs / cMax) * 400)
            if rfcsadj == 400:
                rfcsadj = 390
            rfcsrem = 400 - rfcsadj
            selfs = len(each.closedCount)
            selfadj = int((selfs / cMax) * 400)
            if selfadj == 400:
                selfadj = 390
            selfrem = 400 - selfadj
            bodypart = fileToStr("tablerow.html").format(**locals())
            self.fulltable += bodypart

    def sendEmail(self):
        fulltable = self.fulltable
        daterange = ' - '.join((str(self.oldestdate.strftime("%B %d, %Y")),
                                str(self.newestdate.strftime("%B %d, %Y"))))
        logoimage = self.logoimage
        imageCid = config.logo
        tablemoz = config.tablemoz
        emailbody = fileToStr("email.html").format(**locals())
        olMailItem = 0x0
        obj = win32com.client.Dispatch("Outlook.Application")
        email = obj.CreateItem(olMailItem)
        email.Subject = "Escalation Support Activity"
        email.HTMLBody = emailbody
        email.to = config.sendMailTo
        email.Send()


if __name__ == "__main__":
    print "==TPS Report v1=="
    # main execution steps
    newreport = RFCReport()
    newreport.getTeam()
    newreport.getData()
    newreport.checkTeam()
    newreport.sumReport()
    newreport.printReport()
    newreport.sendEmail()
